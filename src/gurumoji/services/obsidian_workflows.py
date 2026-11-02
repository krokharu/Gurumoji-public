"""Application workflows around the researcher-owned Obsidian workbench.

The workbench owns Markdown and work-state persistence.  This service only
coordinates its explicit actions with the authoritative SQLite transcript.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable

from ..ai_effort import cleanup_enabled
from ..ai_finishing import FINISHING_VERSION
from .ai.transcript_finishing import run_full_cleanup
from .notation import NOTATION_VERSION


@dataclass(frozen=True)
class ObsidianWorkflowService:
    dependencies: Any

    def meeting_minutes_fingerprint(self, minutes: dict[str, Any]) -> str:
        normalized = self.dependencies.normalize_meeting_minutes(minutes)
        return hashlib.sha256(
            json.dumps(normalized, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

    def publish_meeting_minutes(self, row: Any) -> dict[str, Any]:
        d = self.dependencies
        if d.row_session_profile(row).get("session_type") != "meeting":
            raise ValueError("会議モードのデータではありません。")
        minutes = d.row_meeting_minutes(row)
        if not minutes:
            raise ValueError("会議議事録はまだ作成されていません。")
        workbench = d.workbench()
        segments = d.row_segments(row)
        state = workbench.prepare(
            str(row["id"]), str(row["source_name"]), segments,
            revision=int(row["revision_count"] or 0), source_kind="saved_transcript",
        )
        if not state.get("ready"):
            workbench.activate(str(row["id"]), int(row["revision_count"] or 0), segments)
            state = workbench.load(str(row["id"])) or state
        external = json.dumps(
            d.meeting_external_payload(str(row["source_name"]), minutes, str(row["id"])),
            ensure_ascii=False,
            indent=2,
        )
        return workbench.publish_meeting_minutes(
            state, minutes,
            task_csv=d.meeting_tasks_csv_text(minutes),
            external_json=external,
        )

    def meeting_minutes_export_row(self, item_id: str) -> tuple[Any, dict[str, Any]]:
        d = self.dependencies
        row = d.library_row(item_id)
        if row is None:
            raise LookupError("処理済みデータが見つかりません。")
        if d.row_session_profile(row).get("session_type") != "meeting":
            raise ValueError("会議モードのデータではありません。")
        minutes = d.row_meeting_minutes(row)
        if not minutes:
            raise LookupError("会議議事録はまだ作成されていません。")
        return row, minutes

    def run_finishing(
        self,
        action: str,
        state: dict[str, Any],
        segments: list[dict[str, Any]],
        context: dict[str, Any],
        provider: str,
        check: Callable[[], None],
    ) -> dict[str, Any]:
        """Execute one explicit workbench action using configured credentials."""
        d = self.dependencies
        item_id = state["item_id"]
        row = d.library_row(item_id)
        if row is None:
            raise LookupError("アプリ側の会話が見つかりません。")
        if int(row["revision_count"] or 0) != state["revision"]:
            raise ValueError("アプリ側の会話が更新されています。作業ノートを保持して停止しました。新しい作業版をアプリから作成してください。")
        check()
        if action == "apply":
            with d.library_write_lock:
                check()
                latest = d.library_row(item_id)
                if latest is None or int(latest["revision_count"] or 0) != context["revision"]:
                    raise ValueError("AI処理後にアプリ側の会話が更新されました。反映を停止しました。")
                profiles = d.row_speaker_profiles(latest, context["segments"], context["names"])
                for label, name in context["names"].items():
                    if label in profiles:
                        profiles[label]["display_name"] = name
                before_names = context.get("before_names", d.json_load(latest["speaker_names_json"], {}))
                finishing_history = [
                    {"segments": context["before"], "speaker_names": before_names,
                     "speaker_profiles": d.row_speaker_profiles(latest, context["before"], before_names),
                     "origin": "researcher", "process": "workbench_input"},
                    {"segments": context.get("before_notation", context["segments"]), "speaker_names": context["names"],
                     "speaker_profiles": profiles, "origin": "ai", "process": "ai_finishing",
                     "process_version": FINISHING_VERSION,
                     "metadata": {"run_id": "obsidian-finishing-" + context["run_id"],
                                  "provider": context["provider"], "model": context["model"],
                                  "stages": context["stages"]}},
                    {"segments": segments, "speaker_names": context["names"],
                     "speaker_profiles": profiles,
                     "origin": "researcher", "process": "workbench_result_edit"},
                ]
                if context.get("notation") is not None:
                    notation_names = before_names
                    notation_profiles = d.row_speaker_profiles(latest, context["notation_segments"], notation_names)
                    finishing_history[1]["speaker_names"] = notation_names
                    finishing_history[1]["speaker_profiles"] = notation_profiles
                    finishing_history.insert(-1, {"segments": context["notation_segments"], "speaker_names": notation_names,
                        "speaker_profiles": notation_profiles, "origin": "ai", "process": "notation",
                        "process_version": NOTATION_VERSION,
                        "metadata": {"run_id": "obsidian-finishing-" + context["run_id"], "provider": context["provider"],
                                     "model": context["model"], "notation": context["notation"]}})
                    finishing_history.insert(-1, {"segments": context["segments"], "speaker_names": context["names"],
                        "speaker_profiles": profiles, "origin": "ai", "process": "ai_finishing",
                        "process_version": FINISHING_VERSION,
                        "metadata": {"run_id": "obsidian-finishing-" + context["run_id"], "provider": context["provider"],
                                     "model": context["model"], "stages": {"speaker_identity": context["stages"]["speaker_identity"]}}})
                result = d.update_library_item_locked(
                    item_id,
                    {
                        "revision_count": context["revision"],
                        "segments": segments,
                        "speaker_names": context["names"],
                        "speaker_profiles": profiles,
                    },
                    record_training=False,
                    outline_override=context.get("outline"),
                    ai_usage_override=d.merge_ai_usage(
                        d.json_load(latest["ai_usage_json"], {}),
                        state.get("pending_usage", {}),
                    ),
                    check_cancelled=check,
                    finishing_history=finishing_history,
                )
                d.publish_input_vault(d.library_row(item_id))
                try:
                    d.archive_ai_finishing(
                        d.library_row(item_id), context["before"], context["stages"],
                        context["provider"], context["model"], context["usage"],
                        context_outline=context["context_outline"],
                        jev_usage=context.get("jev_usage"),
                        request_id="obsidian-finishing-" + context["run_id"],
                    )
                except (OSError, ValueError, TypeError, d.sqlite_error):
                    state["archive_warning"] = "反映済みです。分析履歴の書き出しに失敗しました。作業結果JSONは保持しています。"
                state["last_usage"] = state.get("pending_usage", {})
                state["pending_usage"] = {}
                return {"revision": result["revision_count"]}

        config = d.load_token_config()
        api_key, configured_model = d.configured_ai_credentials(config, provider)
        model = configured_model
        if not model or (provider != "lmstudio" and not api_key):
            raise ValueError("アプリでAPIキーと使用モデルを設定してください。キーはObsidianに書かないでください。")
        base_url = config.lmstudio_base_url if provider == "lmstudio" else ""
        usage: dict[str, Any] = {}

        def record_usage(sample: dict[str, Any]) -> None:
            nonlocal usage
            usage = d.merge_ai_usage(usage, sample)
            state["pending_usage"] = d.merge_ai_usage(state.get("pending_usage", {}), sample)
            d.workbench().save(state)

        def status(message: str) -> None:
            state["message"] = message
            d.workbench().save(state)
            d.workbench().publish_status(state)

        names = d.json_load(row["speaker_names_json"], {})
        before_names = dict(names)

        def create_context_outline(source: list[dict[str, Any]]) -> dict[str, Any]:
            return d.create_outline_with_ai(
                source, names, provider, api_key, model, status, check, record_usage,
                base_url=base_url, ai_efforts=state.get("ai_efforts"),
            )

        if action == "outline":
            return {"outline": create_context_outline(segments), "usage": usage}

        def clean_with_outline(
            source: list[dict[str, Any]], outline: dict[str, Any]
        ) -> list[dict[str, Any]]:
            return d.clean_segments_with_ai(
                source, provider, api_key, model, status, check, record_usage,
                base_url=base_url, ai_efforts=state.get("ai_efforts"), outline=outline,
            )

        def review_source_with_jev(outline: dict[str, Any]) -> tuple[dict, dict]:
            return d.review_segments_with_jev(
                segments, config.typesafe_api_key, config.typesafe_model, status, check,
                outline=outline,
            )

        # Same order and stage record as the in-job route (ARCH-07). Any failure
        # stops here so the researcher can retry from the operation note.
        full_cleanup = run_full_cleanup(
            segments,
            check_cancelled=check,
            create_context_outline=create_context_outline,
            clean_with_outline=(clean_with_outline
                                if cleanup_enabled(state.get("ai_efforts")) else None),
            review_with_jev=review_source_with_jev if state.get("jev_compare") else None,
            attach_jev=d.attach_jev_comparison,
            outline=context,
            ai_efforts=state.get("ai_efforts"),
            unify_notation=lambda source: d.unify_notation(
                source, provider, api_key, model, check, record_usage,
                base_url=base_url, ai_efforts=state.get("ai_efforts"), item_id=item_id),
        )
        revised = full_cleanup["segments"]
        context = full_cleanup["context_outline"]
        jev_usage: dict[str, Any] = full_cleanup["jev_usage"]
        stages = {
            "outline_context": "not_requested", "cleanup": "not_requested",
            "jev_comparison": "not_requested", "speaker_identity": "not_requested",
            "outline": "not_requested",
            **full_cleanup["stages"],
        }
        if state.get("detect_names"):
            diagnostics: dict[str, Any] = {}
            detected = d.detect_speaker_names_with_ai(
                segments, provider, api_key, model, check, record_usage, status,
                diagnostics.update, base_url=base_url,
                ai_efforts=state.get("ai_efforts"),
            )
            revised, names, _ = d.apply_speaker_identity_repairs(
                revised, {**names, **detected}, diagnostics,
            )
            stages["speaker_identity"] = "completed"
        final_outline = None
        if state.get("create_outline"):
            final_outline = d.create_outline_with_ai(
                revised, names, provider, api_key, model, status, check, record_usage,
                base_url=base_url, ai_efforts=state.get("ai_efforts"),
            )
            stages["outline"] = "completed"
        check()
        return {
            "segments": revised, "names": names, "outline": final_outline,
            "context_outline": context, "stages": stages, "provider": provider,
            "model": model, "usage": state.get("pending_usage", usage),
            "jev_usage": jev_usage,
            "before_names": before_names,
            "before_notation": full_cleanup["before_notation"], "notation": full_cleanup["notation"],
            "notation_segments": full_cleanup["segments"],
        }
