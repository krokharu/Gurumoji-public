"""Save a conversation's analysis settings and manual annotations.

The save is accepted only for the source and analysis revisions the client
loaded. A changed codebook gets a new version with the change reason and a
summary of added, removed and changed codes; analysis_revision is bumped."""

from __future__ import annotations

import json
from typing import Any, Callable

from .. import transcript_preparation as preparation
from ..text_utils import utc_now_iso
from . import change_log
from .group_analysis import (
    normalize_analysis_annotations,
    normalize_analysis_config,
    row_analysis_annotation_state,
    row_analysis_config,
)


def make_analysis_annotation_save(
    *,
    AnalysisConflictError: Any,
    database_connection: Any,
    group_analysis_for_row: Any,
    library_row: Any,
    row_segments: Any,
) -> tuple[Callable[..., Any], ...]:
    def summarize_codebook_change(before: list[dict[str, str]], after: list[dict[str, str]]) -> str:
        previous = {str(item.get("id") or ""): item for item in before}
        current = {str(item.get("id") or ""): item for item in after}
        added = [item.get("label") or item_id for item_id, item in current.items() if item_id not in previous]
        removed = [item.get("label") or item_id for item_id, item in previous.items() if item_id not in current]
        changed = [
            current[item_id].get("label") or item_id for item_id in current.keys() & previous.keys()
            if current[item_id] != previous[item_id]
        ]
        parts = []
        if added:
            parts.append("追加: " + "、".join(str(value) for value in added))
        if removed:
            parts.append("削除: " + "、".join(str(value) for value in removed))
        if changed:
            parts.append("変更: " + "、".join(str(value) for value in changed))
        return " / ".join(parts) or "コードブックの順序または定義を変更"

    def _save_group_analysis_locked(item_id: str, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("分析設定はJSONオブジェクトで送信してください。")
        row = library_row(item_id)
        if row is None:
            raise LookupError("処理済みデータが見つかりません。")
        missing_revisions = [
            key for key in ("source_revision", "analysis_revision") if key not in payload
        ]
        if missing_revisions:
            raise ValueError("保存前に分析データを再読み込みしてください。")
        if "config" in payload and not isinstance(payload["config"], dict):
            raise ValueError("分析設定の形式が正しくありません。")
        provided_config = payload.get("config")
        if (
            isinstance(provided_config, dict)
            and "exclude_moderator" in provided_config
            and not isinstance(provided_config["exclude_moderator"], bool)
        ):
            raise ValueError("司会・運営役の除外設定はtrueまたはfalseで指定してください。")
        if "annotations" in payload and not isinstance(payload["annotations"], dict):
            raise ValueError("発話注釈の形式が正しくありません。")
        provided_annotations = payload.get("annotations")
        if isinstance(provided_annotations, dict):
            for index, value in enumerate(provided_annotations.values()):
                if index >= 100000:
                    break
                if not isinstance(value, dict):
                    continue
                for key in ("important", "excluded"):
                    if key in value and not isinstance(value[key], bool):
                        raise ValueError(f"注釈の{key}はtrueまたはfalseで指定してください。")
        segments = row_segments(row)
        source_revision = int(row["revision_count"] or 0)
        analysis_revision = int(row["analysis_revision"] or 0)
        for key, actual in (
            ("source_revision", source_revision),
            ("analysis_revision", analysis_revision),
        ):
            if key not in payload:
                continue
            try:
                expected = int(payload[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} が正しくありません。") from exc
            if expected != actual:
                raise AnalysisConflictError(
                    "元データまたは分析が別の画面で更新されました。再読み込みして確認してください。"
                )
        current_config = row_analysis_config(row)
        current_annotations, orphaned_annotations = row_analysis_annotation_state(
            row, segments, current_config
        )
        config_source = payload.get("config", current_config)
        config = normalize_analysis_config(config_source)
        # The client is allowed to submit an older configuration, but only the
        # server-held history is authoritative.  Record the reason even when it
        # was omitted so that a later reviewer can see the gap rather than assume
        # that no change occurred.
        config["codebook_history"] = list(current_config.get("codebook_history", []))
        config["codebook_version"] = int(current_config.get("codebook_version", 0))
        if config["codebook"] != current_config.get("codebook", []):
            version = config["codebook_version"] + 1
            config["codebook_version"] = version
            config["codebook_history"] = (
                config["codebook_history"] + [{
                    "version": version,
                    "changed_at": utc_now_iso(),
                    "reason": config["codebook_change_reason"] or "変更理由未記入（要確認）",
                    "summary": summarize_codebook_change(
                        current_config.get("codebook", []), config["codebook"]
                    ),
                }]
            )[-20:]
            config["codebook_change_reason"] = ""
        annotations_source = payload.get("annotations", current_annotations)
        annotations = normalize_analysis_annotations(annotations_source, segments, config)
        existing_links = {(sid, link.get("target_segment_id"), link.get("relation"))
            for sid, annotation in {**orphaned_annotations, **current_annotations}.items()
            for link in annotation.get("interaction_links", [])}
        current_ids = {s["id"] for s in segments}
        for sid, annotation in annotations.items():
            for link in annotation.get("interaction_links", []):
                if link["target_segment_id"] not in current_ids and (sid, link["target_segment_id"], link["relation"]) not in existing_links:
                    raise ValueError("相互作用リンクの対象発言が存在しません。削除済みの既存リンクのみ履歴として保持できます。")
        stored_annotations = {**orphaned_annotations, **annotations}
        now = utc_now_iso()
        with database_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            with change_log.tracking(connection, [("analysis_config", item_id), ("analysis_annotations", item_id)], process="analysis_annotation_save"):
                cursor = connection.execute(
                    """
                    UPDATE library_items SET
                        analysis_config_json = ?, analysis_annotations_json = ?,
                        analysis_revision = analysis_revision + 1, analysis_updated_at = ?
                    WHERE id = ? AND revision_count = ? AND analysis_revision = ?
                    """,
                    (
                        json.dumps(config, ensure_ascii=False),
                        json.dumps(stored_annotations, ensure_ascii=False),
                        now,
                        item_id,
                        source_revision,
                        analysis_revision,
                    ),
                )
                if cursor.rowcount != 1:
                    raise AnalysisConflictError(
                        "元データまたは分析が別の画面で更新されました。再読み込みして確認してください。"
                    )
                if stored_annotations and not current_annotations and not orphaned_annotations:
                    preparation.capture(connection, row, "analysis_baseline")
                    preparation.bind_analysis(connection, row)
        updated = library_row(item_id)
        if updated is None:
            raise LookupError("処理済みデータが見つかりません。")
        return group_analysis_for_row(updated)

    return (summarize_codebook_change, _save_group_analysis_locked)
