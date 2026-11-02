"""Run segment classification synchronously for one conversation.

Checks the source and analysis revisions before and after classification,
keeps manual/rule/Jev/Transformer values apart and archives each run."""

from __future__ import annotations

import json
import re
import sqlite3
import urllib.request
import uuid
from typing import Any, Callable

from ..analysis_store import StoreConflict
from ..segment_classification import (
    build_result as build_segment_classification_result,
    topic_candidates as segment_classification_topic_candidates,
)
from ..text_utils import utc_now_iso
from .analysis_commands import AnalysisCommandRequestError


def make_segment_classification_command(
    *,
    AnalysisConflictError: Any,
    analysis_archive_store: Any,
    archive_segment_classification: Any,
    classify_segments_with_jev: Any,
    database_connection: Any,
    group_analysis_for_row: Any,
    library_row: Any,
    library_write_lock: Any,
    load_token_config: Any,
    local_path_access_allowed: Any,
    public_diagnostic_text: Any,
) -> Callable[..., Any]:
    def run_segment_classifications_command(
        item_id: str, payload: dict[str, Any], *, app_url: str
    ) -> dict[str, Any]:
        if any(type(payload.get(key)) is not int for key in ("source_revision", "analysis_revision")):
            raise AnalysisCommandRequestError(
                "元データと分析のrevisionを指定してください。", 400
            )
        if "use_jev" not in payload or not isinstance(payload.get("use_jev"), bool):
            raise AnalysisCommandRequestError(
                "Jevへ発話を送信するか use_jev で明示してください。", 400
            )
        request_id = str(payload.get("request_id") or uuid.uuid4().hex)
        if not re.fullmatch(r"[A-Za-z0-9_-]{16,100}", request_id):
            raise AnalysisCommandRequestError("リクエストIDが正しくありません。", 400)

        row = library_row(item_id)
        if row is None:
            raise AnalysisCommandRequestError("データが見つかりません。", 404)
        source_revision = int(row["revision_count"] or 0)
        analysis_revision = int(row["analysis_revision"] or 0)
        if (payload["source_revision"] != source_revision
                or payload["analysis_revision"] != analysis_revision):
            raise AnalysisCommandRequestError(
                "データが更新されています。分析を再読み込みしてください。",
                409,
                details={"conflict": True},
            )

        try:
            analysis = group_analysis_for_row(row)
            segments = analysis["segments"]
            if not segments:
                raise AnalysisCommandRequestError("分類できる発話がありません。", 400)
            transformer_state = analysis.get("transformer", {})
            transformer_result = (
                transformer_state.get("result") if not transformer_state.get("stale") else None
            )
            llm_proposals: dict[str, dict[str, Any]] = {}
            llm_usage: dict[str, Any] = {}
            if payload["use_jev"]:
                token_config = load_token_config()
                if not token_config.typesafe_api_key:
                    raise ValueError("tokens.json に typesafe_api_key を設定してください。")
                llm_proposals, llm_usage = classify_segments_with_jev(
                    segments,
                    segment_classification_topic_candidates(analysis["config"].get("codebook", [])),
                    token_config.typesafe_api_key,
                    token_config.typesafe_model,
                )
            result = build_segment_classification_result(
                segments, analysis["annotations"], analysis["config"].get("codebook", []),
                transformer_result, llm_proposals,
                source_revision=source_revision, analysis_revision=analysis_revision,
                llm_usage=llm_usage,
            )
            result["generated_at"] = utc_now_iso()
            result["request_id"] = request_id
            with library_write_lock:
                latest = library_row(item_id)
                if latest is None:
                    raise AnalysisCommandRequestError("データが削除されています。", 404)
                if (int(latest["revision_count"] or 0) != source_revision
                        or int(latest["analysis_revision"] or 0) != analysis_revision):
                    raise AnalysisCommandRequestError(
                        "実行中にデータが更新されました。もう一度実行してください。",
                        409,
                        details={"conflict": True},
                    )
                with database_connection() as connection:
                    cursor = connection.execute(
                        """UPDATE library_items SET segment_classification_json=?
                           WHERE id=? AND revision_count=? AND analysis_revision=?""",
                        (json.dumps(result, ensure_ascii=False), item_id,
                         source_revision, analysis_revision),
                    )
                    if cursor.rowcount != 1:
                        raise AnalysisConflictError(
                            "保存前にデータが更新されました。もう一度実行してください。"
                        )
            latest = library_row(item_id)
            refreshed = group_analysis_for_row(latest)
            archive_warning = ""
            public_run = None
            try:
                archived = archive_segment_classification(
                    latest, refreshed, result, "segment-classification-" + request_id,
                    app_url=app_url,
                )
                public_run = analysis_archive_store().public(
                    archived, local=local_path_access_allowed()
                )
                result["archive_id"] = archived["id"]
                with database_connection() as connection:
                    connection.execute(
                        "UPDATE library_items SET segment_classification_json=? WHERE id=?",
                        (json.dumps(result, ensure_ascii=False), item_id),
                    )
                refreshed = group_analysis_for_row(library_row(item_id))
            except (OSError, ValueError, TypeError, sqlite3.Error, StoreConflict) as exc:
                archive_warning = (
                    "分類結果は保存しましたが、固定分析履歴の作成に失敗しました: "
                    + public_diagnostic_text(str(exc), reveal_local_paths=False)[:500]
                )
            return {
                "segment_classification": refreshed["segment_classification"],
                "run": public_run, "archive_warning": archive_warning,
            }
        except AnalysisCommandRequestError:
            raise
        except AnalysisConflictError as exc:
            raise AnalysisCommandRequestError(
                str(exc), 409, details={"conflict": True}
            ) from exc
        except (ValueError, RuntimeError) as exc:
            raise AnalysisCommandRequestError(
                public_diagnostic_text(str(exc), reveal_local_paths=False)[:700], 400
            ) from exc
        except (OSError, urllib.error.URLError, sqlite3.Error) as exc:
            raise AnalysisCommandRequestError(
                "発話分類を実行できませんでした: "
                + public_diagnostic_text(str(exc), reveal_local_paths=False)[:500],
                500,
            ) from exc

    return run_segment_classifications_command
