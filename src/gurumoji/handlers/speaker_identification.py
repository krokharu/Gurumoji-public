"""Re-run AI speaker identification for one saved conversation.

The use case checks the revision before and after the AI call, merges only
names the user has not set, and saves through the ordinary edit path."""

from __future__ import annotations

import json
from typing import Any, Callable

from ..services.ai.settings import (
    ai_provider_label,
    local_llm_model_required_message,
)
from ..services.speaker_identification import apply_speaker_identity_repairs
from ..text_utils import clean_single_line, json_load, utc_now_iso
from .analysis_commands import TranscriptConflictError
from .speaker_registry import SpeakerIdentificationRequestError


def make_library_speaker_identification(
    *,
    _update_library_from_payload_locked: Any,
    configured_ai_credentials: Any,
    database_connection: Any,
    detect_speaker_names_with_ai: Any,
    library_public: Any,
    library_row: Any,
    library_write_lock: Any,
    load_token_config: Any,
    merge_ai_usage: Any,
    public_diagnostic_text: Any,
    publish_input_vault: Any,
    refresh_archive_index: Any,
    register_detected_speakers: Any,
    row_segments: Any,
    row_session_profile: Any,
    row_speaker_profiles: Any,
) -> Callable[..., Any]:
    def identify_library_speakers(
        item_id: str, *, provider: str, expected_revision: int
    ) -> dict[str, Any]:
        row = library_row(item_id)
        if row is None:
            raise SpeakerIdentificationRequestError("データが見つかりません。", 404)
        current_revision = int(row["revision_count"] or 0)
        if current_revision != expected_revision:
            raise SpeakerIdentificationRequestError(
                "別の画面でデータが更新されています。再読み込みしてください。",
                409,
                current_revision=current_revision,
            )
        segments = row_segments(row)
        if not segments:
            raise SpeakerIdentificationRequestError(
                "話者特定に使用できる発話がありません。", 400
            )

        try:
            token_config = load_token_config()
        except RuntimeError as exc:
            raise SpeakerIdentificationRequestError(str(exc), 503) from exc
        try:
            api_key, model = configured_ai_credentials(token_config, provider)
        except ValueError as exc:
            raise SpeakerIdentificationRequestError(str(exc), 400) from exc
        base_url = token_config.lmstudio_base_url if provider == "lmstudio" else ""
        if provider != "lmstudio" and not api_key:
            raise SpeakerIdentificationRequestError(
                f"tokens.json に {ai_provider_label(provider)} のAPIキーを設定してください。",
                400,
            )
        if not model:
            raise SpeakerIdentificationRequestError(
                local_llm_model_required_message(), 400
            )

        run_usage: dict[str, Any] = {}
        diagnostics: dict[str, Any] = {}

        def record_usage(sample: dict[str, Any]) -> None:
            nonlocal run_usage
            run_usage = merge_ai_usage(run_usage, sample)

        try:
            detected_names = detect_speaker_names_with_ai(
                segments,
                provider,
                api_key,
                model,
                usage_callback=record_usage,
                diagnostics_callback=diagnostics.update,
                base_url=base_url,
            )
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            raise SpeakerIdentificationRequestError(
                "話者特定AIを実行できませんでした: "
                + public_diagnostic_text(str(exc), reveal_local_paths=False),
                502,
            ) from exc

        try:
            with library_write_lock:
                latest = library_row(item_id)
                if latest is None:
                    raise SpeakerIdentificationRequestError(
                        "データが見つかりません。", 404
                    )
                latest_revision = int(latest["revision_count"] or 0)
                if latest_revision != expected_revision:
                    raise SpeakerIdentificationRequestError(
                        "AI処理中にデータが更新されました。結果を反映せず再読み込みします。",
                        409,
                        current_revision=latest_revision,
                    )
                existing_names = json_load(latest["speaker_names_json"], {})
                if not isinstance(existing_names, dict):
                    existing_names = {}
                latest_segments = row_segments(latest)
                segments, merged_names, repair_summary = apply_speaker_identity_repairs(
                    latest_segments,
                    {
                        str(label): clean_single_line(name, 80)
                        for label, name in existing_names.items()
                        if clean_single_line(name, 80)
                    },
                    diagnostics,
                )
                _, detected_names, _ = apply_speaker_identity_repairs(
                    segments,
                    detected_names,
                    diagnostics,
                )
                speaker_profiles = row_speaker_profiles(latest, segments, merged_names)
                applied_names: dict[str, str] = {}
                for label, name in detected_names.items():
                    profile = speaker_profiles.get(label, {})
                    if merged_names.get(label) or profile.get("display_name"):
                        continue
                    merged_names[label] = name
                    profile["display_name"] = name
                    speaker_profiles[label] = profile
                    applied_names[label] = name
                speaker_profiles, registration_summary = register_detected_speakers(
                    speaker_profiles,
                    applied_names,
                )
                combined_usage = merge_ai_usage(
                    json_load(latest["ai_usage_json"], {}),
                    run_usage,
                )
                repairs_applied = bool(
                    repair_summary["aliased_segments"]
                    or repair_summary["corrected_segments"]
                )
                if applied_names or repairs_applied or registration_summary["changed"]:
                    result = _update_library_from_payload_locked(
                        item_id,
                        {
                            "revision_count": latest_revision,
                            "source_name": latest["source_name"],
                            "segments": segments,
                            "speaker_names": merged_names,
                            "session_profile": row_session_profile(latest),
                            "speaker_profiles": speaker_profiles,
                        },
                        ai_usage_override=combined_usage,
                        record_training=False,
                    )
                    # Same follow-up as an ordinary edit: stale analyses and the Input ledger.
                    refresh_archive_index(item_id)
                    publish_input_vault(library_row(item_id))
                else:
                    with database_connection() as connection:
                        connection.execute(
                            "UPDATE library_items SET ai_usage_json = ?, updated_at = ? "
                            "WHERE id = ? AND revision_count = ?",
                            (
                                json.dumps(combined_usage, ensure_ascii=False),
                                utc_now_iso(),
                                item_id,
                                latest_revision,
                            ),
                        )
                    refreshed = library_row(item_id)
                    if refreshed is None:
                        raise LookupError("データが見つかりません。")
                    result = library_public(refreshed)
                result["speaker_identity"] = {
                    "provider": provider,
                    "model": model,
                    "detected_count": len(detected_names),
                    "applied_count": len(applied_names),
                    "applied_names": applied_names,
                    "ambiguous_labels": diagnostics.get("ambiguous_labels", {}),
                    "duplicate_names": diagnostics.get("duplicate_names", {}),
                    "repairs": repair_summary,
                    "registration": registration_summary,
                }
                return result
        except TranscriptConflictError as exc:
            raise SpeakerIdentificationRequestError(
                str(exc), 409, current_revision=exc.current_revision
            ) from exc

    return identify_library_speakers
