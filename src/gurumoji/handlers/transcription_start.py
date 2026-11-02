"""Validate a transcription request, reserve its work folders and start the worker.

The command runs without Flask: the HTTP layer passes the submitted form and
upload. Everything created before the worker starts is removed again if the
start fails."""

from __future__ import annotations

import shutil
import threading
import uuid
from pathlib import Path
from typing import Any, Callable

from werkzeug.exceptions import RequestEntityTooLarge

from ..ai_effort import normalize_efforts
from ..media_formats import ALLOWED_EXTENSIONS
from ..services.ai.settings import (
    AI_PROVIDERS,
    ai_provider_label,
    lmstudio_base_url,
    local_llm_model_required_message,
)
from ..services.library_rows import normalize_source_name
from ..services.media_files import safe_media_filename
from ..services.outputs import job_output_directory
from ..services.transcription.options import (
    ACTIVE_JOB_STATUSES,
    AIST_EMOTION_MODEL_CHOICES,
    CONVERSATION_MODES,
    JobOptions,
    LANGUAGES,
    MODEL_NAMES,
    TRANSCRIPTION_BACKENDS,
)
from ..services.transcription.qwen_stack import qwen_stack_available, qwen_stack_setup_message
from ..services.transcription.vocabulary import normalize_custom_vocabulary
from .form_fields import (
    parse_audio_preprocess,
    parse_bool,
    parse_optional_float,
    parse_optional_int,
)
from .jobs import JobRequestError


def make_transcription_start(
    *,
    JobRecord: Any,
    MAX_MEDIA_UPLOAD_BYTES: Any,
    TRANSCRIPT_FINISHING_MODES: Any,
    upload_directory: Callable[[], Any],
    configured_ai_credentials: Any,
    copy_file_limited: Any,
    get_machine_profile: Any,
    jobs: Any,
    jobs_lock: Any,
    load_token_config: Any,
    local_path_access_allowed: Any,
    prepare_output_root: Any,
    remove_owned_directory: Any,
    resolve_local_media_path: Any,
    run_transcription_job: Any,
    save_custom_vocabulary: Any,
    save_upload_limited: Any,
) -> tuple[Callable[..., Any], ...]:
    def start_transcription_job_command(
        form: Any, upload: Any, *, admission_id: str | None
    ) -> tuple[dict[str, Any], int]:
        upload_dir: Path | None = None
        reserved_output_dir: Path | None = None
        registered_job_id: str | None = None
        try:
            with jobs_lock:
                if any(job.status in ACTIVE_JOB_STATUSES for job in jobs.values()):
                    raise JobRequestError(
                        "別の文字起こしを処理中です。完了または中止までお待ちください。",
                        409,
                    )
            source_path_raw = form.get("source_path", "").strip().strip('"')
            direct_input_path: Path | None = None
            if source_path_raw:
                if not local_path_access_allowed():
                    raise ValueError("Direct local paths are disabled for remote access; upload the media instead.")
                direct_input_path = resolve_local_media_path(source_path_raw)
                original_name = direct_input_path.name
            elif upload is not None and upload.filename:
                original_name = Path(upload.filename).name
            else:
                raise ValueError("処理する音声・動画ファイルを選択してください。")
            original_name = normalize_source_name(original_name)
            if Path(original_name).suffix.lower() not in ALLOWED_EXTENSIONS:
                raise ValueError("対応形式は MP4/MOV/MKV/WAV/MP3/M4A/FLAC です。")

            model_name = form.get("model_name", "base")
            if model_name not in MODEL_NAMES:
                raise ValueError("認識モデルが不正です。")
            transcription_backend = form.get("transcription_backend", "whisperx").strip()
            if transcription_backend not in TRANSCRIPTION_BACKENDS:
                raise ValueError("文字起こしエンジンの指定が不正です。")
            if transcription_backend == "qwen3_nemotron" and not qwen_stack_available():
                raise ValueError(qwen_stack_setup_message())
            language_raw = form.get("language", "ja").strip()
            language = language_raw or None
            if language not in LANGUAGES:
                raise ValueError("言語が不正です。")
            audio_preprocess = parse_audio_preprocess(form=form)
            conversation_mode = form.get("conversation_mode", "meeting").strip()
            if conversation_mode not in CONVERSATION_MODES:
                raise ValueError("会話モードが不正です。")
            custom_vocabulary = normalize_custom_vocabulary(
                form.get("custom_vocabulary", "")
            )
            # Save here as well as from the UI's background save so a term entered
            # immediately before pressing start is retained for the next job.
            save_custom_vocabulary(custom_vocabulary)
            device = form.get("device", "cuda")
            diarization_device = form.get("diarization_device", "cpu")
            if device not in {"cpu", "cuda"} or diarization_device not in {"cpu", "cuda"}:
                raise ValueError("処理装置の指定が不正です。")
            machine = get_machine_profile()
            if (device == "cuda" or diarization_device == "cuda") and not machine["gpu"]["cuda_available"]:
                raise ValueError(
                    "このマシンではGPU (CUDA)を利用できません。"
                    "文字起こし装置と話者分離装置をCPUに設定してください。"
                )
            min_speakers = parse_optional_int("min_speakers", form=form)
            max_speakers = parse_optional_int("max_speakers", form=form)
            num_speakers = parse_optional_int("num_speakers", form=form)
            if transcription_backend == "qwen3_nemotron" and any(
                value is not None and value > 8
                for value in (min_speakers, max_speakers, num_speakers)
            ):
                raise ValueError("Nemotron 3 Diarization は最大8話者です。話者数の上限を8以下にしてください。")
            if min_speakers and max_speakers and min_speakers > max_speakers:
                raise ValueError("最少話者数は最多話者数以下にしてください。")
            triple_pass = parse_bool("triple_pass", form=form)
            if transcription_backend == "qwen3_nemotron" and triple_pass:
                raise ValueError("詳細処理はWhisperXでのみ利用できます。Qwen3方式ではオフにしてください。")
            boost_quiet_speech = parse_bool("boost_quiet_speech", default=True, form=form)
            if boost_quiet_speech or triple_pass:
                vad_onset = parse_optional_float(
                    "vad_onset", 0.35, 0.05, 0.95, form=form
                )
                vad_offset = parse_optional_float(
                    "vad_offset", 0.25, 0.05, 0.95, form=form
                )
                if vad_offset > vad_onset:
                    raise ValueError("VAD offset は onset 以下にしてください。")
                # Keep quiet speech discoverable without accepting nearly silent
                # hallucinations, which often duplicate or tear adjacent turns.
                no_speech_threshold = 0.8
            else:
                vad_onset = 0.5
                vad_offset = 0.363
                no_speech_threshold = 0.6

            provider = form.get("ai_provider", "none")
            if provider not in AI_PROVIDERS:
                raise ValueError("AI プロバイダーが不正です。")
            finishing_mode_value = form.get("transcript_finishing_mode", "").strip()
            transcript_finishing_mode = finishing_mode_value or "custom"
            if transcript_finishing_mode not in TRANSCRIPT_FINISHING_MODES:
                raise ValueError("文章整形モードの指定が不正です。")
            clean_transcript = parse_bool("clean_transcript", form=form)
            detect_names = parse_bool("detect_speaker_names", form=form)
            create_outline = parse_bool("create_outline", form=form)
            finish_in_obsidian = parse_bool(
                "finish_in_obsidian", default=not finishing_mode_value, form=form
            )
            ai_efforts = normalize_efforts({
                key: form.get("ai_effort_" + key, "auto")
                for key in ("outline", "cleanup", "name_extract", "name_verify", "notation")
                if key != "notation" or "ai_effort_notation" in form
            })
            recommended_cleanup = False
            jev_compare = parse_bool("jev_compare", form=form)
            if transcript_finishing_mode == "off":
                ai_efforts["notation"] = "off"
                clean_transcript = False
                detect_names = False
                create_outline = False
                jev_compare = False
                finish_in_obsidian = False
            elif transcript_finishing_mode == "recommended":
                # Jev triages each utterance and the configured cleanup effort
                # controls how much context the finishing LLM may read and rewrite.
                clean_transcript = False
                create_outline = False
                jev_compare = False
            elif transcript_finishing_mode == "advanced":
                clean_transcript = True
                detect_names = True
                finish_in_obsidian = False
                if provider == "none":
                    raise ValueError("高度モードでは使用するAIを選択してください。")
            if provider == "none":
                ai_efforts["notation"] = "off"
                clean_transcript = False
                detect_names = False
                create_outline = False
                jev_compare = False
            elif jev_compare:
                # The comparison needs a result from the existing finishing AI.
                clean_transcript = True
            emotion_analysis = parse_bool("emotion_analysis", form=form)
            emotion_model = form.get("emotion_model", "kushinada").strip() or "kushinada"
            if emotion_model not in AIST_EMOTION_MODEL_CHOICES:
                raise ValueError("感情分析モデルの指定が不正です。")
            token_config = load_token_config()
            if transcription_backend == "whisperx" and not token_config.huggingface_token:
                raise ValueError("tokens.json に huggingface_token を設定してください。")
            recommended_cleanup = bool(
                transcript_finishing_mode == "recommended"
                and provider != "none"
                and not finish_in_obsidian
                and ai_efforts.get("cleanup") != "off"
                and token_config.typesafe_api_key
            )
            if jev_compare and not token_config.typesafe_api_key:
                raise ValueError("Jev比較には tokens.json の typesafe_api_key が必要です。")
            ai_api_key = ""
            ai_model = ""
            ai_base_url = ""
            if clean_transcript or recommended_cleanup or detect_names or create_outline or (ai_efforts["notation"] != "off" and not finish_in_obsidian):
                ai_api_key, ai_model = configured_ai_credentials(token_config, provider)
                if provider == "lmstudio":
                    ai_base_url = lmstudio_base_url(token_config.lmstudio_base_url)
                    if not ai_model:
                        raise ValueError(local_llm_model_required_message())
                elif not ai_api_key:
                    raise ValueError(
                        f"tokens.json に {ai_provider_label(provider)} のAPIキーを設定してください。"
                    )

            output_raw = form.get("output_dir", "").strip().strip('"')
            if output_raw and not local_path_access_allowed():
                raise ValueError("Custom output paths are disabled for remote access.")
            output_root = prepare_output_root(output_raw)

            job_id = str(admission_id or uuid.uuid4().hex)
            output_dir = job_output_directory(output_root, original_name, job_id)
            output_dir.mkdir(exist_ok=False)
            reserved_output_dir = output_dir
            upload_dir = upload_directory() / job_id
            upload_directory().mkdir(parents=True, exist_ok=True)
            upload_dir.mkdir(parents=True, exist_ok=False)
            safe_name = safe_media_filename(original_name, fallback_stem="input")
            input_path = upload_dir / safe_name
            try:
                if direct_input_path is not None:
                    copy_file_limited(direct_input_path, input_path, MAX_MEDIA_UPLOAD_BYTES)
                else:
                    assert upload is not None
                    save_upload_limited(upload, input_path, MAX_MEDIA_UPLOAD_BYTES)
                if not input_path.is_file() or input_path.stat().st_size == 0:
                    raise ValueError("アップロードされたファイルが空です。")
            except Exception:
                shutil.rmtree(upload_dir, ignore_errors=True)
                raise

            options = JobOptions(
                input_path=input_path,
                work_dir=upload_dir,
                source_name=original_name,
                output_dir=output_dir,
                model_name=model_name,
                language=language,
                hf_token=token_config.huggingface_token,
                audio_preprocess=audio_preprocess,
                min_speakers=min_speakers,
                max_speakers=max_speakers,
                num_speakers=num_speakers,
                device=device,
                diarization_device=diarization_device,
                triple_pass=triple_pass,
                boost_quiet_speech=boost_quiet_speech,
                vad_onset=vad_onset,
                vad_offset=vad_offset,
                no_speech_threshold=no_speech_threshold,
                write_srt=parse_bool("write_srt", form=form),
                write_json=True,
                burn_subtitled_video=parse_bool("burn_subtitled_video", form=form),
                ai_provider=provider,
                clean_transcript=clean_transcript,
                detect_speaker_names=detect_names,
                create_outline=create_outline,
                emotion_analysis=emotion_analysis,
                emotion_model=emotion_model,
                ai_api_key=ai_api_key,
                ai_model=ai_model,
                ai_base_url=ai_base_url,
                owns_output_dir=True,
                ai_efforts=ai_efforts,
                finish_in_obsidian=finish_in_obsidian,
                conversation_mode=conversation_mode,
                custom_vocabulary=custom_vocabulary,
                recommended_cleanup=recommended_cleanup,
                jev_compare=jev_compare,
                jev_api_key=token_config.typesafe_api_key,
                jev_model=token_config.typesafe_model,
                transcript_finishing_mode=transcript_finishing_mode,
                write_word_cloud=parse_bool("write_word_cloud", form=form),
                generate_meeting_minutes=parse_bool("generate_meeting_minutes", form=form),
                transcription_backend=transcription_backend,
            )
            job = JobRecord(
                id=job_id,
                source_name=original_name,
                output_dir=output_dir,
                write_srt=options.write_srt,
                write_json=True,
                conversation_mode=conversation_mode,
                burn_subtitled_video=options.burn_subtitled_video,
            )
            with jobs_lock:
                jobs[job_id] = job
                registered_job_id = job_id
            thread = threading.Thread(
                target=run_transcription_job,
                args=(job, options),
                name=f"transcription-{job_id[:8]}",
                daemon=True,
            )
            try:
                thread.start()
            except Exception as exc:
                with jobs_lock:
                    jobs.pop(job_id, None)
                    registered_job_id = None
                shutil.rmtree(upload_dir, ignore_errors=True)
                if reserved_output_dir is not None:
                    remove_owned_directory(reserved_output_dir, ignore_errors=True)
                raise RuntimeError(f"Could not start the transcription worker: {exc}") from exc
            return job.public(), 202
        except RequestEntityTooLarge:
            if registered_job_id:
                with jobs_lock:
                    jobs.pop(registered_job_id, None)
            if upload_dir is not None:
                shutil.rmtree(upload_dir, ignore_errors=True)
            if reserved_output_dir is not None:
                remove_owned_directory(reserved_output_dir, ignore_errors=True)
            raise
        except JobRequestError:
            if registered_job_id:
                with jobs_lock:
                    jobs.pop(registered_job_id, None)
            if upload_dir is not None:
                shutil.rmtree(upload_dir, ignore_errors=True)
            if reserved_output_dir is not None:
                remove_owned_directory(reserved_output_dir, ignore_errors=True)
            raise
        except ValueError as exc:
            if registered_job_id:
                with jobs_lock:
                    jobs.pop(registered_job_id, None)
            if upload_dir is not None:
                shutil.rmtree(upload_dir, ignore_errors=True)
            if reserved_output_dir is not None:
                remove_owned_directory(reserved_output_dir, ignore_errors=True)
            raise JobRequestError(str(exc), 400) from exc
        except (RuntimeError, OSError) as exc:
            if registered_job_id:
                with jobs_lock:
                    jobs.pop(registered_job_id, None)
            if upload_dir is not None:
                shutil.rmtree(upload_dir, ignore_errors=True)
            if reserved_output_dir is not None:
                remove_owned_directory(reserved_output_dir, ignore_errors=True)
            raise JobRequestError(str(exc), 500) from exc

    def admission_job_public(job_id: str) -> dict[str, Any]:
        return {
            "id": job_id,
            "source_name": "",
            "output_dir": "",
            "status": "admitting",
            "progress": 0,
            "stage": "admitting",
            "stage_label": "送信データの受付",
            "stage_progress": 0,
            "message": "送信データを受け付けています…",
            "logs": [],
            "segments": [],
            "speaker_names": {},
            "session_profile": {},
            "speaker_profiles": {},
            "write_srt": False,
            "write_json": True,
            "burn_subtitled_video": False,
            "outline": None,
            "emotion_analysis": None,
            "media_url": None,
            "media_kind": None,
            "files": [],
            "error": "",
            "output_warning": "",
            "revision_count": 0,
        }

    return (start_transcription_job_command, admission_job_public)
