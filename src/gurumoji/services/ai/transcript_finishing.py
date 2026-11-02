"""AI-assisted transcript finishing without application-global state."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from ...ai_effort import cleanup_enabled, normalize_efforts


def clean(
    segments: list[dict[str, Any]], provider: str, api_key: str, model: str,
    status: Callable[[str], None], check_cancelled: Callable[[], None], *,
    call_json: Callable[..., dict[str, Any]], finish: Callable[..., list[dict[str, Any]]],
    usage_callback: Callable[[dict[str, Any]], None] | None = None, base_url: str = "",
    outline: dict[str, Any] | None = None, ai_efforts: dict | None = None,
) -> list[dict[str, Any]]:
    if not cleanup_enabled(ai_efforts):
        check_cancelled()
        return deepcopy(segments)
    def call(system: str, prompt: str, name: str, schema: dict[str, Any]) -> dict[str, Any]:
        return call_json(provider, api_key, model, system, prompt, name, schema,
                         check_cancelled, usage_callback, base_url,
                         **({"ai_efforts": ai_efforts} if ai_efforts else {}))
    return finish(segments, call, status, check_cancelled, outline=outline)


def review_with_jev(
    segments: list[dict[str, Any]], api_key: str, model: str,
    status: Callable[[str], None], check_cancelled: Callable[[], None], *,
    clean_single_line: Callable[[Any, int], str], default_model: str,
    post: Callable[..., dict[str, Any]], review: Callable[..., tuple[dict[str, dict[str, Any]], dict[str, Any]]],
    outline: dict[str, Any] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if not api_key:
        raise ValueError("tokens.json に typesafe_api_key を設定してください。")
    resolved_model = clean_single_line(model, 200) or default_model

    def call(state: dict[str, Any], questions: list[dict[str, Any]]) -> dict[str, Any]:
        return post("https://api.typesafe.ai/v1/systemone",
                    {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    {"state": state, "model": resolved_model, "questions": questions},
                    check_cancelled=check_cancelled)
    return review(segments, outline, call, status, check_cancelled, model=resolved_model)


def repair_recommended(
    segments: list[dict[str, Any]], reviews: dict[str, dict[str, Any]],
    provider: str, api_key: str, model: str, status: Callable[[str], None],
    check_cancelled: Callable[[], None], *, call_json: Callable[..., dict[str, Any]],
    repair: Callable[..., list[dict[str, Any]],], usage_callback: Callable[[dict[str, Any]], None] | None = None,
    base_url: str = "", ai_efforts: dict | None = None, effort: str = "medium",
    outline: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not cleanup_enabled(ai_efforts):
        check_cancelled()
        return deepcopy(segments)
    def call(system: str, prompt: str, name: str, schema: dict[str, Any]) -> dict[str, Any]:
        return call_json(provider, api_key, model, system, prompt, name, schema,
                         check_cancelled, usage_callback, base_url,
                         **({"ai_efforts": ai_efforts} if ai_efforts else {}))
    return repair(segments, reviews, call, status, check_cancelled, effort=effort, outline=outline)


def classify_with_jev(
    segments: list[dict[str, Any]], topics: list[dict[str, str]], api_key: str,
    model: str, *, clean_single_line: Callable[[Any, int], str], default_model: str,
    post: Callable[..., dict[str, Any]], classify: Callable[..., tuple[dict[str, dict[str, Any]], dict[str, Any]]],
    status: Callable[[str], None] = lambda _message: None,
    check_cancelled: Callable[[], None] = lambda: None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if not api_key:
        raise ValueError("tokens.json に typesafe_api_key を設定してください。")
    resolved_model = clean_single_line(model, 200) or default_model

    def call(state: dict[str, Any], questions: list[dict[str, Any]]) -> dict[str, Any]:
        return post("https://api.typesafe.ai/v1/systemone",
                    {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    {"state": state, "model": resolved_model, "questions": questions},
                    check_cancelled=check_cancelled)
    return classify(segments, topics, call, status, check_cancelled, model=resolved_model)


def create_outline(
    segments: list[dict[str, Any]], speaker_names: dict[str, str], provider: str,
    api_key: str, model: str, status: Callable[[str], None], check_cancelled: Callable[[], None], *,
    call_json: Callable[..., dict[str, Any]], create: Callable[..., dict[str, Any]], now_iso: Callable[[], str],
    usage_callback: Callable[[dict[str, Any]], None] | None = None, base_url: str = "",
    ai_efforts: dict | None = None,
) -> dict[str, Any]:
    def call(system: str, prompt: str, name: str, schema: dict[str, Any]) -> dict[str, Any]:
        return call_json(provider, api_key, model, system, prompt, name, schema,
                         check_cancelled, usage_callback, base_url,
                         **({"ai_efforts": ai_efforts} if ai_efforts else {}))
    result = create(segments, speaker_names, call, status, check_cancelled)
    result["provenance"].update({"provider": provider, "model": model, "generated_at": now_iso()})
    return result


FULL_CLEANUP_STAGES = ("outline_context", "cleanup", "jev_comparison", "notation")


def run_full_cleanup(
    segments: list[dict[str, Any]], *,
    check_cancelled: Callable[[], None],
    create_context_outline: Callable[[list[dict[str, Any]]], dict[str, Any]],
    clean_with_outline: Callable[[list[dict[str, Any]], dict[str, Any]], list[dict[str, Any]]] | None,
    review_with_jev: Callable[[dict[str, Any]], tuple[dict[str, dict[str, Any]], dict[str, Any]]] | None = None,
    attach_jev: Callable[[list[dict[str, Any]], dict[str, dict[str, Any]]], list[dict[str, Any]]] | None = None,
    outline: dict[str, Any] | None = None,
    on_failure: Callable[[str, BaseException | None], None] | None = None,
    unify_notation: Callable[..., dict[str, Any]] | None = None,
    ai_efforts: dict | None = None,
) -> dict[str, Any]:
    """Run context outline -> full cleanup -> Jev comparison for both finishing routes.

    The in-job route and the Obsidian workbench share this order and the stage
    record (ARCH-07). ``on_failure=None`` stops at the first failure (Obsidian:
    the researcher retries from the operation note). With a callback, a failed
    stage is recorded and reported, and the unedited text is kept (in-job: the
    transcript is still saved). The callback receives ``None`` when the Jev
    comparison is skipped because the cleanup did not complete.
    ``clean_with_outline=None`` means cleanup was not requested.
    """
    stages: dict[str, str] = {}
    result = segments
    context = outline if outline and outline.get("sections") else None
    jev_usage: dict[str, Any] = {}

    def failed(stage: str, exc: BaseException) -> None:
        if on_failure is None or isinstance(exc, InterruptedError):
            raise exc
        stages[stage] = "failed"
        on_failure(stage, exc)

    if clean_with_outline is not None:
        if context is None:
            try:
                context = create_context_outline(segments)
                if not context.get("sections"):
                    raise RuntimeError("会話全体のアウトラインが空でした。")
            except Exception as exc:
                context = None
                failed("outline_context", exc)
        if context is not None:
            stages["outline_context"] = "completed"
        try:
            if context is None:
                raise RuntimeError("参照する全体アウトラインがないため再校正を実行できません。")
            result = clean_with_outline(segments, context)
            stages["cleanup"] = "completed"
            check_cancelled()
        except Exception as exc:
            result = segments
            failed("cleanup", exc)

    if review_with_jev is not None:
        if stages.get("cleanup") != "completed":
            stages["jev_comparison"] = "skipped"
            if on_failure is not None:
                on_failure("jev_comparison", None)
        else:
            try:
                # A completed cleanup always had a context outline.
                reviews, jev_usage = review_with_jev(context)  # type: ignore[arg-type]
                if attach_jev is not None:
                    result = attach_jev(result, reviews)
                stages["jev_comparison"] = "completed"
                check_cancelled()
            except Exception as exc:
                jev_usage = {}
                failed("jev_comparison", exc)

    before_notation = deepcopy(result)
    notation_result = None
    if normalize_efforts(ai_efforts)["notation"] == "off":
        stages["notation"] = "off"
    elif unify_notation is None:
        stages["notation"] = "not_requested"
    else:
        try:
            check_cancelled()
            notation_result = unify_notation(deepcopy(result))
            result = notation_result["segments"]
            stages["notation"] = "completed"
            check_cancelled()
        except Exception as exc:
            result = before_notation
            notation_result = None
            failed("notation", exc)

    return {
        "segments": result,
        "context_outline": context,
        "stages": stages,
        "jev_usage": jev_usage,
        "before_notation": before_notation,
        "notation": notation_result["notation"] if notation_result else None,
    }
