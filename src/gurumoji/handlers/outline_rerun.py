"""Re-run the AI outline for one saved conversation.

The revision is checked before and after the AI call.  Only the outline and the
token usage are written; the transcript itself is never touched."""

from __future__ import annotations

import json
from typing import Any, Callable

from ..services.ai.settings import (
    ai_provider_label,
    local_llm_model_required_message,
)
from ..text_utils import json_load, utc_now_iso


class OutlineRerunError(Exception):
    def __init__(self, message: str, status: int = 400, current_revision: int | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.current_revision = current_revision


class OutlineRerunHandler:
    """Run one synchronous outline re-run without Flask."""

    def __init__(self, run_outline: Callable[..., dict[str, Any]]) -> None:
        self._run_outline = run_outline

    def run(self, item_id: str, *, provider: str, expected_revision: int) -> dict[str, Any]:
        return self._run_outline(item_id, provider=provider, expected_revision=expected_revision)


def make_library_outline_rerun(
    *,
    configured_ai_credentials: Any,
    create_outline_with_ai: Any,
    database_connection: Any,
    library_public: Any,
    library_row: Any,
    library_write_lock: Any,
    load_token_config: Any,
    merge_ai_usage: Any,
    public_diagnostic_text: Any,
    row_segments: Any,
) -> Callable[..., Any]:
    def rerun_library_outline(item_id: str, *, provider: str, expected_revision: int) -> dict[str, Any]:
        row = library_row(item_id)
        if row is None:
            raise OutlineRerunError("データが見つかりません。", 404)
        current_revision = int(row["revision_count"] or 0)
        if current_revision != expected_revision:
            raise OutlineRerunError(
                "別の画面でデータが更新されています。再読み込みしてください。", 409,
                current_revision=current_revision)
        segments = row_segments(row)
        if not segments:
            raise OutlineRerunError("アウトラインに使用できる発話がありません。", 400)
        try:
            token_config = load_token_config()
        except RuntimeError as exc:
            raise OutlineRerunError(str(exc), 503) from exc
        try:
            api_key, model = configured_ai_credentials(token_config, provider)
        except ValueError as exc:
            raise OutlineRerunError(str(exc), 400) from exc
        base_url = token_config.lmstudio_base_url if provider == "lmstudio" else ""
        if provider != "lmstudio" and not api_key:
            raise OutlineRerunError(
                f"tokens.json に {ai_provider_label(provider)} のAPIキーを設定してください。", 400)
        if not model:
            raise OutlineRerunError(local_llm_model_required_message(), 400)
        speaker_names = json_load(row["speaker_names_json"], {})
        if not isinstance(speaker_names, dict):
            speaker_names = {}

        run_usage: dict[str, Any] = {}

        def record_usage(sample: dict[str, Any]) -> None:
            nonlocal run_usage
            run_usage = merge_ai_usage(run_usage, sample)

        try:
            outline = create_outline_with_ai(
                segments, speaker_names, provider, api_key, model,
                lambda _message: None, lambda: None, record_usage, base_url)
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            raise OutlineRerunError(
                "アウトラインを作成できませんでした: "
                + public_diagnostic_text(str(exc), reveal_local_paths=False), 502) from exc
        if not outline.get("sections"):
            raise OutlineRerunError("AIがアウトラインを返しませんでした。もう一度実行してください。", 502)

        with library_write_lock:
            latest = library_row(item_id)
            if latest is None:
                raise OutlineRerunError("データが見つかりません。", 404)
            latest_revision = int(latest["revision_count"] or 0)
            if latest_revision != expected_revision:
                raise OutlineRerunError(
                    "AI処理中にデータが更新されました。結果を反映せず再読み込みします。", 409,
                    current_revision=latest_revision)
            combined_usage = merge_ai_usage(json_load(latest["ai_usage_json"], {}), run_usage)
            with database_connection() as connection:
                connection.execute(
                    "UPDATE library_items SET outline_json = ?, ai_usage_json = ?, updated_at = ? "
                    "WHERE id = ? AND revision_count = ?",
                    (json.dumps(outline, ensure_ascii=False),
                     json.dumps(combined_usage, ensure_ascii=False),
                     utc_now_iso(), item_id, latest_revision))
            refreshed = library_row(item_id)
            if refreshed is None:
                raise OutlineRerunError("データが見つかりません。", 404)
            result = library_public(refreshed)
            result["outline_run"] = {"provider": provider, "model": model,
                                     "section_count": len(outline["sections"])}
            return result

    return rerun_library_outline
