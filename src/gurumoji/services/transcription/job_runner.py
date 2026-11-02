"""Run the transcription job while the application supplies its mutable boundaries."""

from __future__ import annotations

import gc
import json
import shutil
import sqlite3
import subprocess
import time
import traceback
from pathlib import Path
from typing import Any, Mapping

from ...ai_effort import cleanup_enabled
from ...ai_finishing import FINISHING_VERSION, RECOMMENDED_FINISHING_VERSION
from ..ai.transcript_finishing import run_full_cleanup
from ..notation import NOTATION_VERSION

def run_transcription_job(job: Any, options: Any, dependencies: Mapping[str, Any]) -> None:
    TranscriptionReporter = dependencies["TranscriptionReporter"]
    CONVERSATION_MODES = dependencies["CONVERSATION_MODES"]
    DIARIZATION_MODEL = dependencies["DIARIZATION_MODEL"]
    MAX_LOG_LINES = dependencies["MAX_LOG_LINES"]
    NORMAL_NO_SPEECH_THRESHOLD = dependencies["NORMAL_NO_SPEECH_THRESHOLD"]
    NORMAL_VAD_OFFSET = dependencies["NORMAL_VAD_OFFSET"]
    NORMAL_VAD_ONSET = dependencies["NORMAL_VAD_ONSET"]
    TRIPLE_PASS_GAP_CONTEXT_SECONDS = dependencies["TRIPLE_PASS_GAP_CONTEXT_SECONDS"]
    TRIPLE_PASS_MIN_GAP_SECONDS = dependencies["TRIPLE_PASS_MIN_GAP_SECONDS"]
    UPLOAD_DIRECTORY = dependencies["UPLOAD_DIRECTORY"]
    WHISPER_SAMPLE_RATE = dependencies["WHISPER_SAMPLE_RATE"]
    aist_emotion_model_keys = dependencies["aist_emotion_model_keys"]
    apply_speaker_identity_repairs = dependencies["apply_speaker_identity_repairs"]
    attach_jev_comparison = dependencies["attach_jev_comparison"]
    audio_preprocess_label = dependencies["audio_preprocess_label"]
    build_emotion_analysis_summary = dependencies["build_emotion_analysis_summary"]
    build_meeting_minutes = dependencies["build_meeting_minutes"]
    clean_recommended_segments_with_ai = dependencies["clean_recommended_segments_with_ai"]
    clean_segments_with_ai = dependencies["clean_segments_with_ai"]
    cleanup_uncommitted_job_artifacts = dependencies["cleanup_uncommitted_job_artifacts"]
    commit_staged_media = dependencies["commit_staged_media"]
    configure_huggingface_hub_compatibility = dependencies["configure_huggingface_hub_compatibility"]
    configure_speechbrain_lazy_import_compatibility = dependencies["configure_speechbrain_lazy_import_compatibility"]
    create_diarization_pipeline = dependencies["create_diarization_pipeline"]
    create_outline_with_ai = dependencies["create_outline_with_ai"]
    detect_speaker_names_with_ai = dependencies["detect_speaker_names_with_ai"]
    diarization_access_error_message = dependencies["diarization_access_error_message"]
    display_time = dependencies["display_time"]
    ensure_segment_ids = dependencies["ensure_segment_ids"]
    find_long_asr_gaps = dependencies["find_long_asr_gaps"]
    is_diarization_access_error = dependencies["is_diarization_access_error"]
    is_video_path = dependencies["is_video_path"]
    jobs_lock = dependencies["jobs_lock"]
    json_load = dependencies["json_load"]
    make_display_segments = dependencies["make_display_segments"]
    merge_ai_usage = dependencies["merge_ai_usage"]
    merge_supplemental_asr_segments = dependencies["merge_supplemental_asr_segments"]
    normalize_ai_usage = dependencies["normalize_ai_usage"]
    normalize_asr_segments = dependencies["normalize_asr_segments"]
    normalize_conversation_speaker_profiles = dependencies["normalize_conversation_speaker_profiles"]
    normalize_meeting_minutes = dependencies["normalize_meeting_minutes"]
    obsidian_workbench = dependencies["obsidian_workbench"]
    offset_asr_segments_to_gap = dependencies["offset_asr_segments_to_gap"]
    path_entry_exists = dependencies["path_entry_exists"]
    publish_input_vault = dependencies["publish_input_vault"]
    publish_meeting_minutes_to_obsidian = dependencies["publish_meeting_minutes_to_obsidian"]
    register_detected_speakers = dependencies["register_detected_speakers"]
    review_segments_with_jev = dependencies["review_segments_with_jev"]
    row_segments = dependencies["row_segments"]
    row_session_profile = dependencies["row_session_profile"]
    row_speaker_profiles = dependencies["row_speaker_profiles"]
    run_aist_emotion_analysis = dependencies["run_aist_emotion_analysis"]
    run_audio_interval_preprocess = dependencies["run_audio_interval_preprocess"]
    run_audio_preprocess = dependencies["run_audio_preprocess"]
    run_diarization_audio_preprocess = dependencies["run_diarization_audio_preprocess"]
    safe_output_stem = dependencies["safe_output_stem"]
    safe_token_count = dependencies["safe_token_count"]
    session_profile_from_media = dependencies["session_profile_from_media"]
    stage_media_archive = dependencies["stage_media_archive"]
    transcript_formatting_result = dependencies["transcript_formatting_result"]
    update_job = dependencies["update_job"]
    upsert_library_item = dependencies["upsert_library_item"]
    whisper_vault_settings = dependencies["whisper_vault_settings"]
    whisper_vocabulary_prompt = dependencies["whisper_vocabulary_prompt"]
    write_outputs = dependencies["write_outputs"]
    write_subtitled_video_assets = dependencies["write_subtitled_video_assets"]

    model: Any = None
    model_a: Any = None
    audio: Any = None
    diarize_model: Any = None
    diarize_segments: Any = None
    staged_media_path: Path | None = None

    reporter = TranscriptionReporter(
        job=job,
        update_job=update_job,
        jobs_lock=jobs_lock,
        normalize_usage=normalize_ai_usage,
        merge_usage=merge_ai_usage,
    )
    status = reporter.status
    progress = reporter.progress
    set_stage = reporter.stage
    record_ai_usage = reporter.record_ai_usage
    check_cancelled = reporter.check_cancelled
    record_warning = reporter.warning

    with jobs_lock:
        job.status = "running"
    try:
        check_cancelled()
        set_stage("environment", "処理環境の確認", 5)
        progress(2)
        status("処理環境を確認しています…")
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg が見つかりません。README の手順でインストールしてください。")
        internal_work_dir = options.work_dir / ".pipeline_internal"
        internal_work_dir.mkdir(parents=True, exist_ok=True)
        processing_input_path = options.input_path
        if options.audio_preprocess != "none":
            label = audio_preprocess_label(options.audio_preprocess)
            set_stage("preprocess", "音声の前処理", 10)
            status(f"文字起こし用に音声を前処理しています（{label}）…")
            processed_path = internal_work_dir / "preprocessed.wav"
            processing_input_path = run_audio_preprocess(
                options.input_path,
                processed_path,
                options.audio_preprocess,
                check_cancelled,
            )
            set_stage("preprocess", "音声の前処理", 100)
            status("前処理済み音声を使用します（16kHz / mono / WAV）。")
        else:
            status("音声前処理は行わず、元ファイルの音声を使用します。")
        check_cancelled()
        set_stage("environment", "処理環境の確認", 100)
        progress(8)
        if options.transcription_backend == "qwen3_nemotron":
            import numpy as np
            import torch
            import wave
            import whisperx

            from .qwen_stack import run_qwen_stack

            device = options.device
            diarization_device = options.diarization_device
            if (device == "cuda" or diarization_device == "cuda") and not torch.cuda.is_available():
                raise RuntimeError("CUDA is unavailable. Select CPU or install a CUDA-enabled PyTorch runtime.")
            set_stage("transcription", "Qwen3-ASR / ForcedAligner", 10)
            status("Running Qwen3-ASR with Qwen3 ForcedAligner.")
            qwen_audio = whisperx.load_audio(str(processing_input_path))
            qwen_audio_path = internal_work_dir / "qwen-asr-input.wav"
            pcm_audio = (np.clip(np.asarray(qwen_audio), -1.0, 1.0) * 32767).astype("<i2")
            with wave.open(str(qwen_audio_path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(WHISPER_SAMPLE_RATE)
                wav_file.writeframes(pcm_audio.tobytes())
            del qwen_audio, pcm_audio

            if processing_input_path != options.input_path:
                qwen_diarization_path = run_diarization_audio_preprocess(
                    options.input_path,
                    internal_work_dir / "nemotron-input.wav",
                    check_cancelled,
                )
            else:
                qwen_diarization_path = qwen_audio_path

            qwen_result = run_qwen_stack(
                asr_audio_path=qwen_audio_path,
                diarization_audio_path=qwen_diarization_path,
                work_dir=internal_work_dir,
                language=options.language,
                asr_device=device,
                diarization_device=diarization_device,
                status=status,
                check_cancelled=check_cancelled,
            )
            language_code = options.language or qwen_result.get("language")
            result = {"language": language_code, "segments": qwen_result["segments"]}
            audio = None
            set_stage("transcription", "Qwen3-ASR / ForcedAligner", 100)
            progress(64)
            set_stage("alignment", "Qwen3 ForcedAligner", 100)
            progress(72)
            set_stage("diarization", "Nemotron 3 Diarization", 100)
            progress(80)
            set_stage("speaker_assignment", "Speaker assignment", 100)
            segments = ensure_segment_ids(job.id, make_display_segments(result["segments"]))
            if not segments:
                raise RuntimeError("Qwen3-ASR / ForcedAligner returned no transcript segments.")
        else:
            try:
                import torch

                configure_huggingface_hub_compatibility()
                import whisperx

                configure_speechbrain_lazy_import_compatibility()
                from whisperx.diarize import DiarizationPipeline
            except ImportError as exc:
                raise RuntimeError("必要な Python パッケージがありません。run.bat でセットアップしてください。") from exc

            device = options.device
            diarization_device = options.diarization_device
            needs_cuda = device == "cuda" or diarization_device == "cuda"
            if needs_cuda and not torch.cuda.is_available():
                raise RuntimeError("CUDA を利用できません。CPU を選ぶか NVIDIA ドライバーを確認してください。")
            capability: tuple[int, int] | None = None
            vram_gib = 0.0
            gpu_name = ""
            if needs_cuda:
                gpu_name = torch.cuda.get_device_name(0)
                capability = torch.cuda.get_device_capability(0)
                vram_gib = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            compute_type = "float16" if capability and capability[0] >= 7 else "float32"
            use_openai_whisper = device == "cpu" or (capability is not None and capability[0] < 7)
            if device == "cuda":
                assert capability is not None
                status(
                    f"GPU: {gpu_name} / VRAM {vram_gib:.1f} GB / "
                    f"Compute Capability {capability[0]}.{capability[1]}"
                )
                if capability[0] < 7 and options.model_name not in {"tiny", "base"}:
                    raise RuntimeError("旧世代 4 GB GPU では tiny / base だけを選べます。")
            else:
                status("文字起こしは CPU を使用します。")

            backend = "OpenAI Whisper" if use_openai_whisper else "WhisperX (faster-whisper)"
            vocabulary_prompt = whisper_vocabulary_prompt(options.custom_vocabulary)
            if vocabulary_prompt:
                status(
                    f"単語登録をWhisperの認識ヒントに使用します"
                    f"（{len(options.custom_vocabulary)}語登録・先頭から順に使用）。"
                )

            def decoding_settings_text(
                vad_onset: float, vad_offset: float, no_speech_threshold: float
            ) -> str:
                # OpenAI Whisper has no VAD stage, so only the no-speech threshold
                # reaches the decoder there; never report VAD values it ignores.
                if use_openai_whisper:
                    return (
                        f"VADなし・無音判定しきい値 no_speech_threshold={no_speech_threshold:.2f}"
                    )
                return f"VAD onset={vad_onset:.2f}, offset={vad_offset:.2f}"

            if options.triple_pass:
                status(
                    f"詳細処理を使います。通常結果の{TRIPLE_PASS_MIN_GAP_SECONDS:g}秒以上の空白だけを、"
                    "軽め・強めの順で切り出して補完します。"
                )
            elif options.boost_quiet_speech:
                status(
                    "小さい声を拾いやすくする設定を使います（"
                    + decoding_settings_text(
                        options.vad_onset, options.vad_offset, options.no_speech_threshold
                    )
                    + "）…"
                )

            def release_asr_model() -> None:
                nonlocal model
                if model is not None:
                    del model
                    model = None
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

            def load_asr_model(
                language_hint: str | None,
                vad_onset: float,
                vad_offset: float,
                no_speech_threshold: float,
            ) -> None:
                nonlocal model
                if use_openai_whisper:
                    import whisper

                    model = whisper.load_model(options.model_name, device=device)
                else:
                    asr_options: dict[str, Any] = {
                        "no_speech_threshold": no_speech_threshold,
                    }
                    if vocabulary_prompt:
                        # WhisperX stores faster-whisper decoding options on the
                        # pipeline when the model is loaded; its transcribe()
                        # method does not accept initial_prompt.
                        asr_options["initial_prompt"] = vocabulary_prompt
                    model = whisperx.load_model(
                        options.model_name,
                        device,
                        device_index=0,
                        compute_type=compute_type,
                        language=language_hint,
                        asr_options=asr_options,
                        vad_options={"vad_onset": vad_onset, "vad_offset": vad_offset},
                    )

            def transcribe_pass(
                pass_label: str,
                audio_path: Path,
                language_hint: str | None,
                vad_onset: float,
                vad_offset: float,
                no_speech_threshold: float,
                progress_value: int,
            ) -> tuple[dict[str, Any], Any]:
                set_stage("transcription", f"{pass_label}の文字起こし", 10)
                status(f"{pass_label}: 音声認識モデルを読み込んでいます（{options.model_name} / {backend}）…")
                # The model is held only by the enclosing ``model`` binding so that
                # release_asr_model() can actually return its memory.
                load_asr_model(
                    language_hint,
                    vad_onset,
                    vad_offset,
                    no_speech_threshold,
                )
                check_cancelled()
                set_stage("transcription", f"{pass_label}の文字起こし", 35)

                status(
                    f"{pass_label}: 音声を読み込み、文字起こししています（"
                    + decoding_settings_text(vad_onset, vad_offset, no_speech_threshold)
                    + "）…"
                )
                pass_audio = whisperx.load_audio(str(audio_path))
                if use_openai_whisper:
                    transcribe_kwargs: dict[str, Any] = {
                        "language": language_hint,
                        "fp16": False,
                        "verbose": False,
                        "condition_on_previous_text": False,
                        "no_speech_threshold": no_speech_threshold,
                        "word_timestamps": True,
                    }
                else:
                    transcribe_kwargs = {"batch_size": 1}
                if vocabulary_prompt and use_openai_whisper:
                    transcribe_kwargs["initial_prompt"] = vocabulary_prompt
                pass_result = model.transcribe(pass_audio, **transcribe_kwargs)
                set_stage("transcription", f"{pass_label}の文字起こし", 90)
                release_asr_model()
                check_cancelled()
                set_stage("transcription", f"{pass_label}の文字起こし", 100)
                progress(progress_value)
                return pass_result, pass_audio

            def transcribe_gap_pass(
                pass_label: str,
                preset: str,
                gaps: list[tuple[float, float]],
                audio_duration: float,
                language_hint: str | None,
                vad_onset: float,
                vad_offset: float,
                no_speech_threshold: float,
                progress_value: int,
            ) -> dict[str, Any]:
                if not gaps:
                    set_stage("transcription", f"{pass_label}の文字起こし", 100)
                    status(f"{pass_label}: {TRIPLE_PASS_MIN_GAP_SECONDS:g}秒以上の空白はありません。")
                    progress(progress_value)
                    return {"segments": [], "language": language_hint}

                total_gap_seconds = sum(end - start for start, end in gaps)
                set_stage("transcription", f"{pass_label}の文字起こし", 10)
                status(
                    f"{pass_label}: {len(gaps)}か所、計{total_gap_seconds:.1f}秒の空白だけを再確認します。"
                )
                status(f"{pass_label}: 音声認識モデルを読み込んでいます（{options.model_name} / {backend}）…")
                # The model is held only by the enclosing ``model`` binding so that
                # release_asr_model() can actually return its memory.
                load_asr_model(
                    language_hint,
                    vad_onset,
                    vad_offset,
                    no_speech_threshold,
                )
                detected_language = language_hint
                collected: list[dict[str, Any]] = []
                try:
                    for index, (gap_start, gap_end) in enumerate(gaps, 1):
                        check_cancelled()
                        set_stage(
                            "transcription",
                            f"{pass_label}の文字起こし",
                            15 + round(75 * (index - 1) / max(1, len(gaps))),
                        )
                        clip_start = max(0.0, gap_start - TRIPLE_PASS_GAP_CONTEXT_SECONDS)
                        clip_end = min(audio_duration, gap_end + TRIPLE_PASS_GAP_CONTEXT_SECONDS)
                        status(
                            f"{pass_label}: 空白 {index}/{len(gaps)} "
                            f"（{display_time(gap_start)}–{display_time(gap_end)}）を切り出して再文字起こししています…"
                        )
                        clip_path = internal_work_dir / f"gap_{preset}_{index:04d}.wav"
                        try:
                            run_audio_interval_preprocess(
                                options.input_path,
                                clip_path,
                                clip_start,
                                clip_end,
                                preset,
                                check_cancelled,
                            )
                            clip_audio = whisperx.load_audio(str(clip_path))
                            if use_openai_whisper:
                                transcribe_kwargs = {
                                    "language": detected_language,
                                    "fp16": False,
                                    "verbose": False,
                                    "condition_on_previous_text": False,
                                    "no_speech_threshold": no_speech_threshold,
                                    "word_timestamps": True,
                                }
                            else:
                                transcribe_kwargs = {"batch_size": 1}
                            if vocabulary_prompt and use_openai_whisper:
                                transcribe_kwargs["initial_prompt"] = vocabulary_prompt
                            clip_result = model.transcribe(clip_audio, **transcribe_kwargs)
                            if not detected_language:
                                detected_language = clip_result.get("language")
                            collected.extend(
                                offset_asr_segments_to_gap(
                                    clip_result.get("segments", []),
                                    clip_start,
                                    gap_start,
                                    gap_end,
                                )
                            )
                        finally:
                            clip_path.unlink(missing_ok=True)
                finally:
                    release_asr_model()
                check_cancelled()
                set_stage("transcription", f"{pass_label}の文字起こし", 100)
                progress(progress_value)
                return {"segments": collected, "language": detected_language}

            if options.triple_pass:
                primary_vad_onset = NORMAL_VAD_ONSET
                primary_vad_offset = NORMAL_VAD_OFFSET
                primary_no_speech_threshold = NORMAL_NO_SPEECH_THRESHOLD
                primary_progress = 26
            else:
                primary_vad_onset = options.vad_onset
                primary_vad_offset = options.vad_offset
                primary_no_speech_threshold = options.no_speech_threshold
                primary_progress = 52

            result, audio = transcribe_pass(
                "通常モード",
                processing_input_path,
                options.language,
                primary_vad_onset,
                primary_vad_offset,
                primary_no_speech_threshold,
                primary_progress,
            )
            language_code = options.language or result.get("language")

            if options.triple_pass:
                audio_duration = len(audio) / WHISPER_SAMPLE_RATE
                original_segments = result.get("segments", [])
                original_count = len(normalize_asr_segments(original_segments))

                light_gaps = find_long_asr_gaps(original_segments, audio_duration)
                light_result = transcribe_gap_pass(
                    "2回目（軽め）",
                    "light",
                    light_gaps,
                    audio_duration,
                    language_code,
                    options.vad_onset,
                    options.vad_offset,
                    options.no_speech_threshold,
                    38,
                )
                if not language_code:
                    language_code = light_result.get("language")
                after_light, light_counts = merge_supplemental_asr_segments(
                    original_segments,
                    [("長い空白・軽め", light_result.get("segments", []))],
                )

                strong_gaps = find_long_asr_gaps(after_light, audio_duration)
                strong_result = transcribe_gap_pass(
                    "3回目（強め）",
                    "strong",
                    strong_gaps,
                    audio_duration,
                    language_code,
                    options.vad_onset,
                    options.vad_offset,
                    options.no_speech_threshold,
                    50,
                )
                if not language_code:
                    language_code = strong_result.get("language")
                merged_segments, strong_counts = merge_supplemental_asr_segments(
                    after_light,
                    [("長い空白・強め", strong_result.get("segments", []))],
                )
                result = dict(result)
                result["segments"] = merged_segments
                if language_code:
                    result["language"] = language_code
                status(
                    "詳細処理の統合完了: "
                    f"通常 {original_count} 区間、"
                    f"2回目 {len(light_gaps)} 空白から +{light_counts.get('長い空白・軽め', 0)}、"
                    f"3回目 {len(strong_gaps)} 空白から +{strong_counts.get('長い空白・強め', 0)} を追加しました。"
                )
            check_cancelled()
            progress(52)

            if language_code:
                try:
                    set_stage("alignment", "発話時刻の補正", 10)
                    status("発話時刻を整えています…")
                    model_a, metadata = whisperx.load_align_model(language_code=language_code, device=device)
                    result = whisperx.align(
                        result["segments"], model_a, metadata, audio, device, return_char_alignments=False
                    )
                except InterruptedError:
                    raise
                except Exception as exc:
                    status(f"時刻補正を省略しました: {exc}")
                finally:
                    if model_a is not None:
                        del model_a
                        model_a = None
                    gc.collect()
                    if device == "cuda":
                        torch.cuda.empty_cache()
            check_cancelled()
            set_stage("alignment", "発話時刻の補正", 100)
            progress(64)

            set_stage("diarization", "話者の分離", 10)
            if processing_input_path != options.input_path:
                # The transcription presets denoise, band-limit and normalize, which
                # reshapes the voice characteristics speaker embeddings compare.
                # Diarize the original recording instead, with only too-quiet speech
                # lifted so soft speakers still reach the segmentation model.
                # Both filters preserve timing, so every stage shares one clock.
                status("話者分離用に、元音声の小さすぎる声だけを持ち上げています…")
                diarization_path = run_diarization_audio_preprocess(
                    options.input_path,
                    internal_work_dir / "diarization.wav",
                    check_cancelled,
                )
                audio = None
                gc.collect()
                audio = whisperx.load_audio(str(diarization_path))
                diarization_path.unlink(missing_ok=True)
                check_cancelled()
            status(f"話者を分離しています（{diarization_device.upper()}）…")
            try:
                diarize_model = create_diarization_pipeline(
                    DiarizationPipeline, options.hf_token, diarization_device
                )
            except Exception as exc:
                if is_diarization_access_error(exc):
                    raise RuntimeError(diarization_access_error_message(DIARIZATION_MODEL)) from exc
                raise
            diarize_kwargs: dict[str, int] = {}
            if options.num_speakers is not None:
                diarize_kwargs["num_speakers"] = options.num_speakers
            elif options.min_speakers is not None:
                diarize_kwargs["min_speakers"] = options.min_speakers
            if options.num_speakers is None and options.max_speakers is not None:
                diarize_kwargs["max_speakers"] = options.max_speakers
            diarize_segments = diarize_model(audio, **diarize_kwargs)
            check_cancelled()
            set_stage("diarization", "話者の分離", 100)
            progress(80)

            set_stage("speaker_assignment", "話者ラベルの割り当て", 15)
            status("話者ラベルを文字起こしに対応付けています…")
            result = whisperx.assign_word_speakers(
                diarize_segments,
                result,
                fill_nearest=True,
            )
            segments = ensure_segment_ids(job.id, make_display_segments(result.get("segments", [])))
            if not segments:
                raise RuntimeError("文字起こし結果が空でした。音声が含まれているか確認してください。")
        # Speaker identification uses the unedited transcript as a dedicated
        # source so text cleanup cannot remove or rewrite a self-introduction.
        speaker_identity_segments = [dict(item) for item in segments]
        obsidian_prepared = False
        finishing_stages = {"outline_context": "not_requested", "cleanup": "not_requested",
                            "recommended_cleanup": "not_requested",
                            "jev_comparison": "not_requested",
                            "speaker_identity": "not_requested", "outline": "not_requested"}
        jev_usage: dict[str, Any] = {}
        check_cancelled()
        set_stage("speaker_assignment", "話者ラベルの割り当て", 100)

        # Diarization and the full decoded audio are no longer needed. Releasing
        # them before optional emotion inference substantially reduces peak VRAM.
        diarize_segments = None
        diarize_model = None
        audio = None
        result = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        # Freeze the ASR/diarization output before any AI rewriting.
        segments = ensure_segment_ids(job.id, segments)
        imported_transcript = json.loads(json.dumps(segments, ensure_ascii=False))
        set_stage("finishing", "文字起こしの仕上げ", 10)
        ai_base_kwargs = (
            {"base_url": options.ai_base_url}
            if options.ai_provider == "lmstudio" else {}
        )
        if any(level != "auto" for key, level in options.ai_efforts.items()
               if key != "notation" or level != "off"):
            ai_base_kwargs["ai_efforts"] = options.ai_efforts
        context_outline: dict[str, Any] | None = None
        if (options.recommended_cleanup and not options.finish_in_obsidian
                and options.ai_efforts.get("cleanup", "medium") != "off"):
            try:
                cleanup_effort = options.ai_efforts.get("cleanup", "medium")
                if cleanup_effort == "auto":
                    cleanup_effort = "medium"
                if cleanup_effort in {"high", "ultra"}:
                    status("おすすめ文章整形の参照用アウトラインを作成しています…")
                    context_outline = create_outline_with_ai(
                        segments, {}, options.ai_provider, options.ai_api_key, options.ai_model,
                        status, check_cancelled, record_ai_usage, **ai_base_kwargs,
                    )
                    if not context_outline.get("sections"):
                        raise RuntimeError("会話全体のアウトラインが空でした。")
                    finishing_stages["outline_context"] = "completed"
                recommended_reviews, jev_usage = review_segments_with_jev(
                    imported_transcript,
                    options.jev_api_key,
                    options.jev_model,
                    status,
                    check_cancelled,
                    outline=context_outline,
                )
                segments = clean_recommended_segments_with_ai(
                    segments,
                    recommended_reviews,
                    options.ai_provider,
                    options.ai_api_key,
                    options.ai_model,
                    status,
                    check_cancelled,
                    record_ai_usage,
                    effort=cleanup_effort,
                    outline=context_outline,
                    **ai_base_kwargs,
                )
                finishing_stages["recommended_cleanup"] = "completed"
                check_cancelled()
            except InterruptedError:
                raise
            except Exception as exc:
                details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
                finishing_stages["recommended_cleanup"] = "failed"
                record_warning(
                    "おすすめのJev判定・発話単位LLM整形を省略しました。元の文字起こしを保存します: "
                    + details
                )
        full_cleanup = None
        if ((options.clean_transcript or options.jev_compare or options.ai_efforts.get("notation", "off") != "off")
                and not options.finish_in_obsidian):
            # The same order and stage record as the Obsidian workbench (ARCH-07).
            def create_context_outline(source: list[dict[str, Any]]) -> dict[str, Any]:
                status("再校正に先立ち、会話全体のアウトラインを作成しています…")
                return create_outline_with_ai(
                    source, {}, options.ai_provider, options.ai_api_key, options.ai_model,
                    status, check_cancelled, record_ai_usage, **ai_base_kwargs,
                )

            def clean_with_outline(
                source: list[dict[str, Any]], outline: dict[str, Any]
            ) -> list[dict[str, Any]]:
                return clean_segments_with_ai(
                    source,
                    options.ai_provider,
                    options.ai_api_key,
                    options.ai_model,
                    status,
                    check_cancelled,
                    record_ai_usage,
                    outline=outline,
                    **ai_base_kwargs,
                )

            def review_original_with_jev(outline: dict[str, Any]) -> tuple[dict, dict]:
                return review_segments_with_jev(
                    imported_transcript,
                    options.jev_api_key,
                    options.jev_model,
                    status,
                    check_cancelled,
                    outline=outline,
                )

            def warn_full_cleanup(stage: str, exc: BaseException | None) -> None:
                if exc is None:
                    record_warning("現行AIの文字整形が完了しなかったため、Jevとの比較を省略しました。")
                    return
                details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
                if stage == "outline_context":
                    record_warning("再校正用の全体アウトラインを作成できませんでした: " + str(exc))
                elif stage == "cleanup":
                    record_warning("AI文字整形を省略しました。元の文字起こしを保存します: " + details)
                elif stage == "notation":
                    record_warning("表記ゆれの統一に失敗しました。統一前の本文を保存します: " + details)
                else:
                    record_warning("Jevによる修正要否の比較を省略しました: " + details)

            full_cleanup = run_full_cleanup(
                segments,
                check_cancelled=check_cancelled,
                create_context_outline=create_context_outline,
                clean_with_outline=(clean_with_outline
                                    if options.clean_transcript and cleanup_enabled(options.ai_efforts)
                                    else None),
                review_with_jev=review_original_with_jev if options.jev_compare else None,
                attach_jev=attach_jev_comparison,
                on_failure=warn_full_cleanup,
                ai_efforts=options.ai_efforts,
                unify_notation=lambda source: dependencies["unify_notation"](
                    source, options.ai_provider, options.ai_api_key, options.ai_model,
                    check_cancelled, record_ai_usage, **ai_base_kwargs),
            )
            segments = full_cleanup["segments"]
            finishing_stages.update(full_cleanup["stages"])
            if full_cleanup["stages"].get("jev_comparison") == "completed":
                jev_usage = full_cleanup["jev_usage"]
        finishing_history = [{
            "segments": json.loads(json.dumps(full_cleanup["before_notation"] if full_cleanup else segments, ensure_ascii=False)), "speaker_names": {},
            "origin": "ai" if any(finishing_stages.get(s) == "completed" for s in (
                "cleanup", "recommended_cleanup", "jev_comparison")) else "rule",
            "process": "ai_finishing" if any(finishing_stages.get(s) == "completed" for s in (
                "cleanup", "recommended_cleanup", "jev_comparison")) else "import_processing",
            "process_version": FINISHING_VERSION,
            "metadata": {"run_id": job.id, "provider": options.ai_provider, "model": options.ai_model,
                         "stages": dict(finishing_stages), "recommended_version": RECOMMENDED_FINISHING_VERSION},
        }]
        if full_cleanup and full_cleanup["notation"] is not None:
            finishing_history.append({"segments": json.loads(json.dumps(segments, ensure_ascii=False)),
                "speaker_names": {}, "origin": "ai", "process": "notation", "process_version": NOTATION_VERSION,
                "metadata": {"run_id": job.id, "provider": options.ai_provider, "model": options.ai_model,
                             "notation": full_cleanup["notation"]}})
        set_stage("finishing", "文字起こしの仕上げ", 100)
        progress(88)
        emotion_analysis: dict[str, Any] | None = None
        if options.emotion_analysis:
            emotion_model_keys = aist_emotion_model_keys(options.emotion_model)
            try:
                set_stage("emotion", "音声感情の分析", 10)
                # Emotion models depend on loudness dynamics that the
                # transcription preprocessing deliberately flattens.
                segments, emotion_analysis = run_aist_emotion_analysis(
                    options.input_path,
                    segments,
                    options.emotion_model,
                    options.hf_token,
                    device,
                    internal_work_dir / "emotion_work",
                    status,
                    check_cancelled,
                )
                status("AIST感情分析が完了しました。")
            except InterruptedError:
                raise
            except Exception as exc:
                details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
                record_warning("AIST感情分析は失敗しました。文字起こし処理は続行します: " + details)
                emotion_analysis = build_emotion_analysis_summary(
                    segments,
                    emotion_model_keys,
                    status="failed",
                    error=details,
                )
            set_stage("emotion", "音声感情の分析", 100)
        progress(90)
        finishing_history.append({"segments": json.loads(json.dumps(segments, ensure_ascii=False)),
                                  "speaker_names": {}, "origin": "rule", "process": "emotion_projection"})
        speaker_names: dict[str, str] = {}
        speaker_identity_diagnostics: dict[str, Any] = {}
        speaker_repair_summary = {
            "alias_count": 0,
            "aliased_segments": 0,
            "corrected_segments": 0,
        }
        # Name identification does not rewrite the transcript, so it can run
        # with the standard Obsidian finishing flow as well.  That makes the
        # first result use verified names instead of diarization numbers.
        if options.detect_speaker_names:
            set_stage("speaker_names", "話者名の確認", 10)
            status("文字校正とは独立した2段階処理で、自己紹介と話者ラベルを確認しています…")
            try:
                check_cancelled()
                speaker_names = detect_speaker_names_with_ai(
                    speaker_identity_segments,
                    options.ai_provider,
                    options.ai_api_key,
                    options.ai_model,
                    check_cancelled,
                    record_ai_usage,
                    status,
                    speaker_identity_diagnostics.update,
                    **ai_base_kwargs,
                )
                segments, speaker_names, speaker_repair_summary = apply_speaker_identity_repairs(
                    segments,
                    speaker_names,
                    speaker_identity_diagnostics,
                )
                finishing_stages["speaker_identity"] = "completed"
                if any(speaker_repair_summary.values()):
                    status(
                        "AI話者連続性修復: "
                        f"重複ラベル {speaker_repair_summary['alias_count']}件 / "
                        f"ラベル統合発話 {speaker_repair_summary['aliased_segments']}件 / "
                        f"断裂修正 {speaker_repair_summary['corrected_segments']}件"
                    )
                    if emotion_analysis is not None:
                        emotion_analysis = build_emotion_analysis_summary(
                            segments,
                            aist_emotion_model_keys(options.emotion_model),
                            status=str(emotion_analysis.get("status") or "completed"),
                            error=str(emotion_analysis.get("error") or ""),
                        )
                check_cancelled()
            except InterruptedError:
                raise
            except Exception as exc:
                details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
                record_warning("AI話者名推定を省略しました。話者ラベルで保存します: " + details)
                finishing_stages["speaker_identity"] = "failed"
            set_stage("speaker_names", "話者名の確認", 100)
        if finishing_stages["speaker_identity"] == "completed":
            finishing_history.append({"segments": json.loads(json.dumps(segments, ensure_ascii=False)),
                "speaker_names": dict(speaker_names), "origin": "ai", "process": "ai_finishing",
                "process_version": FINISHING_VERSION,
                "metadata": {"run_id": job.id, "provider": options.ai_provider, "model": options.ai_model,
                             "stages": {"speaker_identity": "completed"}}})
        segments, formatting_result = transcript_formatting_result(
            imported_transcript,
            segments,
            mode=options.transcript_finishing_mode,
            audio_preprocess=options.audio_preprocess,
            speaker_names=speaker_names,
            speaker_diagnostics=speaker_identity_diagnostics,
            speaker_repair_summary=speaker_repair_summary,
            finishing_stages=finishing_stages,
            ai_usage=job.ai_usage,
            jev_usage=jev_usage,
        )
        formatting_summary = formatting_result["summary"]
        status(
            "整形チェック完了: "
            f"文字調整 {formatting_summary['text_change_count']}件 / "
            f"AI文章置換 {formatting_summary['recommended_replacement_count']}件 / "
            f"境界確認 {formatting_summary['boundary_warning_count']}件 / "
            f"ノイズ候補 {formatting_summary['noise_candidate_count']}件 / "
            f"話者統合 {formatting_summary['speaker_relabel_count']}発話"
        )
        speaker_profiles = normalize_conversation_speaker_profiles(
            None,
            {str(item.get("speaker") or "UNKNOWN") for item in segments},
            speaker_names,
        )
        speaker_profiles, speaker_registration_summary = register_detected_speakers(
            speaker_profiles,
            speaker_names,
        )
        if speaker_registration_summary["created"]:
            status(
                "自己紹介から確認した話者を話者管理に登録しました: "
                + "、".join(
                    speaker_names[label]
                    for label in speaker_registration_summary["created"]
                    if speaker_names.get(label)
                )
            )
        if speaker_registration_summary["temporary"]:
            status(
                "台帳に一致しない話者を、この会話のみの一時話者として登録しました: "
                + "、".join(speaker_registration_summary["temporary"].values())
            )
        if options.finish_in_obsidian:
            try:
                # Work notes are researcher-owned after their first creation.
                # Create them only after the non-text-changing identity pass,
                # so their headers already show names without overwriting a
                # note a researcher may later edit.
                obsidian_workbench().prepare(
                    job.id, options.source_name, segments, revision=0,
                    provider=options.ai_provider, model=options.ai_model,
                    ai_efforts=options.ai_efforts,
                    detect_names=options.detect_speaker_names or options.ai_provider == "none",
                    create_outline=options.create_outline or options.ai_provider == "none",
                    jev_compare=options.jev_compare, ready=False,
                    speaker_names=speaker_names,
                )
                obsidian_prepared = True
                status("Whisperの原文と会話全文をObsidianに保存しました。仕上げは操作ノートから実行できます。")
            except (OSError, ValueError) as exc:
                record_warning("Obsidianの作業ノートを保存できませんでした。処理完了後に「Obsidianで仕上げ」から再試行してください: " + str(exc))
        session_profile = session_profile_from_media(options.input_path, check_cancelled)
        session_profile["session_type"] = CONVERSATION_MODES.get(
            options.conversation_mode, "meeting"
        )
        if session_profile.get("session_date"):
            status(
                "動画の撮影日時から実施日を自動入力しました: "
                f"{session_profile['session_date']}"
            )
        progress(94)
        outline: dict[str, Any] | None = None
        if options.create_outline and not options.finish_in_obsidian:
            try:
                set_stage("outline", "議題アウトラインの作成", 10)
                outline = create_outline_with_ai(
                    segments,
                    speaker_names,
                    options.ai_provider,
                    options.ai_api_key,
                    options.ai_model,
                    status,
                    check_cancelled,
                    record_ai_usage,
                    **ai_base_kwargs,
                )
                finishing_stages["outline"] = "completed"
                check_cancelled()
            except InterruptedError:
                raise
            except Exception as exc:
                details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
                finishing_stages["outline"] = "failed"
                record_warning("AIアウトライン作成を省略しました。文字起こし結果は保存します: " + details)
            set_stage("outline", "議題アウトラインの作成", 100)
        final_usage = normalize_ai_usage(job.ai_usage)
        formatting_result["summary"]["llm_request_count"] = (
            safe_token_count(final_usage.get("request_count"))
            + safe_token_count(jev_usage.get("request_count"))
        )
        meeting_minutes: dict[str, Any] | None = None
        if options.conversation_mode == "meeting" and options.generate_meeting_minutes:
            set_stage("meeting_minutes", "会議議事録とタスク候補の作成", 20)
            status("会議のタスク・優先度・期限候補と分析サマリーを作成しています…")
            meeting_minutes = build_meeting_minutes(
                segments, speaker_names, session_profile, outline
            )
            set_stage("meeting_minutes", "会議議事録とタスク候補の作成", 100)
        progress(97)
        check_cancelled()

        set_stage("output", "結果ファイルの保存", 10)
        status("出力ファイルを書き出しています…")
        files = write_outputs(
            options.source_name,
            options.output_dir,
            segments,
            language_code,
            speaker_names,
            options.write_srt,
            options.write_json,
            outline,
            emotion_analysis,
            speaker_profiles,
            meeting_minutes,
            check_cancelled,
            formatting_result=formatting_result,
            write_word_cloud_file=options.write_word_cloud,
            session_profile=session_profile,
        )
        check_cancelled()
        set_stage("output", "結果ファイルの保存", 45)
        if options.burn_subtitled_video:
            if is_video_path(options.input_path):
                optional_stem = safe_output_stem(options.source_name)
                optional_ass = options.output_dir / f'{optional_stem}_話者カラー字幕.ass'
                optional_video = options.output_dir / f'{optional_stem}_字幕付き.mp4'
                optional_ass_existed = path_entry_exists(optional_ass)
                optional_video_existed = path_entry_exists(optional_video)
                status("話者名・テーマカラー付き字幕を動画へ焼き込んでいます…")
                try:
                    files.extend(write_subtitled_video_assets(
                        options.input_path,
                        options.source_name,
                        options.output_dir,
                        segments,
                        speaker_names,
                        speaker_profiles,
                        check_cancelled,
                    ))
                except InterruptedError:
                    if not optional_video_existed:
                        optional_video.unlink(missing_ok=True)
                    if not optional_ass_existed:
                        optional_ass.unlink(missing_ok=True)
                    raise
                except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                    if not optional_video_existed:
                        optional_video.unlink(missing_ok=True)
                    if not optional_ass_existed:
                        optional_ass.unlink(missing_ok=True)
                    warning = f"字幕動画の作成を完了できませんでした: {exc}"
                    record_warning(warning)
            else:
                status("音声ファイルのため、字幕焼き込み動画の作成は省略しました。")
        check_cancelled()
        set_stage("output", "結果ファイルの保存", 75)
        status("元の音声・動画をライブラリへ保存しています…")
        media_target, staged_media_path = stage_media_archive(
            job.id, options.input_path, check_cancelled
        )
        check_cancelled()
        with jobs_lock:
            if job.cancel_event.is_set():
                raise InterruptedError("The transcription job was cancelled.")
            job.status = "committing"
        saved_media_path = commit_staged_media(media_target, staged_media_path)
        staged_media_path = None
        persisted = upsert_library_item(
            item_id=job.id,
            source_name=options.source_name,
            output_dir=options.output_dir,
            media_path=saved_media_path,
            original_media_path=options.input_path,
            language=language_code,
            segments=segments,
            speaker_names=speaker_names,
            outline=outline,
            emotion_analysis=emotion_analysis,
            files=files,
            write_srt=options.write_srt,
            original_segments=imported_transcript,
            finishing_history=finishing_history,
            write_json=True,
            burn_subtitled_video=options.burn_subtitled_video,
            session_profile=session_profile,
            speaker_profiles=speaker_profiles,
            ai_usage=job.ai_usage,
            meeting_minutes=meeting_minutes,
            formatting_result=formatting_result,
        )
        publish_input_vault(persisted, whisper_vault_settings(options, language_code))
        if obsidian_prepared:
            try:
                obsidian_workbench().activate(job.id, int(persisted["revision_count"] or 0), segments)
            except (OSError, ValueError) as exc:
                record_warning("原文は保存済みです。「Obsidianで仕上げ」から作業状態の更新を再試行してください: " + str(exc))
            try:
                publish_meeting_minutes_to_obsidian(persisted)
            except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as exc:
                # Transcript persistence is authoritative; a meeting note can be retried later.
                record_warning("会議議事録のObsidian公開を後で再試行してください: " + str(exc))
        with jobs_lock:
            job.segments = row_segments(persisted)
            job.speaker_names = speaker_names
            job.session_profile = row_session_profile(persisted)
            job.speaker_profiles = row_speaker_profiles(persisted, job.segments, speaker_names)
            job.speaker_registration = speaker_registration_summary
            job.outline = outline
            try:
                persisted_minutes = json_load(persisted["meeting_minutes_json"], {})
            except (KeyError, TypeError, IndexError):
                persisted_minutes = meeting_minutes or {}
            job.meeting_minutes = normalize_meeting_minutes(persisted_minutes)
            job.emotion_analysis = emotion_analysis
            job.formatting_result = formatting_result
            job.media_path = saved_media_path
            job.files = files
            job.language = language_code
            job.status = "completed"
        set_stage("completed", "処理完了", 100)
        progress(100)
        status("Transcription completed and output files were saved.")
    except InterruptedError as exc:
        with jobs_lock:
            job.status = "cancelled"
            job.error = str(exc)
        set_stage("cancelled", "処理を中止", job.stage_progress)
        status(str(exc))
    except Exception as exc:
        details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        with jobs_lock:
            job.status = "failed"
            job.error = details
        set_stage("failed", "エラー", job.stage_progress)
        status("処理を完了できませんでした: " + details)
    finally:
        if staged_media_path is not None:
            staged_media_path.unlink(missing_ok=True)
        with jobs_lock:
            terminal_status = job.status
            if job.status in {"completed", "failed", "cancelled"}:
                job.finished_at = time.time()
        if terminal_status in {"failed", "cancelled"}:
            cleanup_warnings = cleanup_uncommitted_job_artifacts(job, options)
            if cleanup_warnings:
                with jobs_lock:
                    warning_text = "\n".join(cleanup_warnings)
                    job.output_warning = "\n".join(
                        value for value in (job.output_warning, warning_text) if value
                    )
                    job.logs.extend(cleanup_warnings)
                    job.logs = job.logs[-MAX_LOG_LINES:]
        if model is not None:
            del model
        if model_a is not None:
            del model_a
        diarize_model = None
        diarize_segments = None
        audio = None
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        # Processing files and any uploaded browser copy are isolated in this job directory.
        upload_parent = options.work_dir.resolve()
        upload_root = UPLOAD_DIRECTORY.resolve()
        if upload_parent.parent == upload_root and upload_parent.name == job.id:
            shutil.rmtree(upload_parent, ignore_errors=True)
