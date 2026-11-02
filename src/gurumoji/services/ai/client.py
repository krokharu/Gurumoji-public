"""Provider-neutral JSON generation transport.

This module deliberately has no Flask or application-global dependencies.  The
composition root supplies the worker path and the cancellable subprocess
runner, which keeps cancellation and test doubles at the application edge.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from ...ai_effort import (
    SCHEMA_STAGES,
    effort_payload,
    local_effort_payload,
    local_cleanup_effort_payload,
    normalize_efforts,
)


def lmstudio_base_url(value: str, default_base_url: str, loopback_hosts: set[str] | frozenset[str]) -> str:
    """Validate and canonicalize the local-only OpenAI-compatible endpoint."""
    raw = str(value or "").strip() or default_base_url
    try:
        parsed = urllib.parse.urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("LM Studio の接続URLが不正です。") from exc
    host = (parsed.hostname or "").casefold()
    if (
        parsed.scheme not in {"http", "https"}
        or host not in loopback_hosts
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or port is None
        or not 1 <= port <= 65535
    ):
        raise ValueError(
            "LM Studio の接続URLは http://127.0.0.1:1234/v1 "
            "または http://[::1]:1234/v1 のように、このPCのループバックだけを指定してください。"
        )
    path = parsed.path.rstrip("/")
    if path not in {"", "/v1"}:
        raise ValueError("LM Studio の接続URLは /v1 までを指定してください。")
    netloc = f"[{host}]" if host == "::1" else host
    return urllib.parse.urlunsplit((parsed.scheme, f"{netloc}:{port}", "/v1", "", ""))


def lmstudio_headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


# Statuses that mean "try again shortly": rate limiting and transient server
# faults.  Authentication and request errors are never retried.
RETRYABLE_HTTP_STATUSES = frozenset({429, 500, 502, 503, 504})
RETRY_DELAYS_SECONDS = (2.0, 6.0)
MAX_RETRY_AFTER_SECONDS = 30.0

HTTP_STATUS_HINTS = {
    400: "要求の内容が受け付けられませんでした。モデル名や入力の長さを確認してください。",
    401: "APIキーが無効です。config/tokens.json を確認してください。",
    403: "APIキーにこの操作の権限がありません。",
    404: "モデルまたは接続先が見つかりません。モデル名を確認してください。",
    429: "利用回数またはトークンの上限に達しています。時間をおいて再実行してください。",
}


class RetryableApiError(RuntimeError):
    """An HTTP failure the provider expects the client to retry."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def http_error_message(status_code: Any) -> str:
    hint = HTTP_STATUS_HINTS.get(status_code)
    if hint is None and isinstance(status_code, int) and status_code >= 500:
        hint = "AI サービス側で一時的な障害が発生しています。"
    return f"API が HTTP {status_code} を返しました。" + (hint or "")


def wait_before_retry(
    seconds: float,
    check_cancelled: Callable[[], None] | None,
    sleep: Callable[[float], None],
) -> None:
    """Sleep in short steps so a cancelled job does not wait out the delay."""
    remaining = seconds
    while remaining > 0:
        if check_cancelled is not None:
            check_cancelled()
        step = min(0.25, remaining)
        sleep(step)
        remaining -= step
    if check_cancelled is not None:
        check_cancelled()


def post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    *,
    worker_file: Path,
    run_subprocess: Callable[..., Any],
    timeout: int = 240,
    check_cancelled: Callable[[], None] | None = None,
    retry_delays: tuple[float, ...] = RETRY_DELAYS_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """POST JSON in an isolated process, retrying rate limits and 5xx replies."""
    attempt = 0
    while True:
        try:
            return _post_json_once(
                url, headers, payload, worker_file=worker_file,
                run_subprocess=run_subprocess, timeout=timeout,
                check_cancelled=check_cancelled,
            )
        except RetryableApiError as exc:
            if attempt >= len(retry_delays):
                raise
            delay = retry_delays[attempt]
            if exc.retry_after is not None:
                delay = max(delay, min(MAX_RETRY_AFTER_SECONDS, exc.retry_after))
            wait_before_retry(delay, check_cancelled, sleep)
            attempt += 1


def _post_json_once(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    *,
    worker_file: Path,
    run_subprocess: Callable[..., Any],
    timeout: int,
    check_cancelled: Callable[[], None] | None,
) -> dict[str, Any]:
    """POST JSON in an isolated process so cancellation can stop network I/O."""
    if not worker_file.is_file():
        raise RuntimeError("AI API 通信ワーカーが見つかりません。")
    timeout_seconds = max(1.0, min(600.0, float(timeout)))
    worker_input = json.dumps(
        {"url": url, "headers": headers, "payload": payload, "timeout": timeout_seconds},
        ensure_ascii=False,
    )
    try:
        completed = run_subprocess(
            [sys.executable, "-I", str(worker_file)], input_text=worker_input,
            timeout=timeout_seconds + 5, check_cancelled=check_cancelled,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("AI API の応答がタイムアウトしました。") from exc
    if completed.returncode != 0:
        raise RuntimeError("AI API 通信ワーカーを実行できませんでした。")
    if len(completed.stdout.encode("utf-8")) > 10 * 1024 * 1024:
        raise RuntimeError("AI API 通信ワーカーの応答が大きすぎます。")
    try:
        worker_result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AI API 通信ワーカーの応答形式が不正です。") from exc
    if not isinstance(worker_result, dict) or not worker_result.get("ok"):
        kind = worker_result.get("kind") if isinstance(worker_result, dict) else ""
        if kind == "http":
            # The worker never relays the error body (it may echo secrets), so
            # the message is built from the status code alone.
            status_code = worker_result.get("status", "不明")
            message = http_error_message(status_code)
            if status_code in RETRYABLE_HTTP_STATUSES:
                retry_after = worker_result.get("retry_after")
                if isinstance(retry_after, bool) or not isinstance(retry_after, int):
                    retry_after = None
                raise RetryableApiError(message, retry_after)
            raise RuntimeError(message)
        if kind == "response_too_large":
            raise RuntimeError("AI API の応答が大きすぎます。")
        raise RuntimeError("AI API に接続できません。")
    body = worker_result.get("body")
    if not isinstance(body, str):
        raise RuntimeError("AI API 通信ワーカーの応答形式が不正です。")
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("API から JSON ではない応答が返されました。") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("API 応答の形式が不正です。")
    return parsed


def extract_openai_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    for item in response.get("output") or []:
        for content in item.get("content") or []:
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                return content["text"]
    raise RuntimeError("OpenAI API 応答に出力テキストがありません。")


def extract_google_text(response: dict[str, Any]) -> str:
    candidates = response.get("candidates") or []
    if not candidates:
        raise RuntimeError("Google API 応答に候補がありません。")
    parts = candidates[0].get("content", {}).get("parts") or []
    text = "".join(str(part.get("text", "")) for part in parts if part.get("text"))
    if not text:
        raise RuntimeError("Google API 応答に出力テキストがありません。")
    return text


def extract_lmstudio_text(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("LM Studio API 応答に候補がありません。")
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message") if isinstance(first.get("message"), dict) else {}
    text = message.get("content")
    if isinstance(text, str) and text.strip():
        return text
    raise RuntimeError("LM Studio API 応答に出力テキストがありません。")


def safe_token_count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return 0
    return max(0, min(10**12, int(value)))


def normalize_ai_usage(value: Any, providers: set[str] | frozenset[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    provider = str(value.get("provider") or "").strip().casefold()
    if provider not in providers:
        return {}
    return {
        "provider": provider, "model": str(value.get("model") or "").strip()[:200],
        "request_count": safe_token_count(value.get("request_count")),
        "input_tokens": safe_token_count(value.get("input_tokens")),
        "output_tokens": safe_token_count(value.get("output_tokens")),
        "total_tokens": safe_token_count(value.get("total_tokens")),
        "cached_tokens": safe_token_count(value.get("cached_tokens")),
        "reasoning_tokens": safe_token_count(value.get("reasoning_tokens")),
        "reported": bool(value.get("reported")),
    }


def merge_ai_usage(current_value: Any, sample_value: Any, providers: set[str] | frozenset[str]) -> dict[str, Any]:
    current, sample = normalize_ai_usage(current_value, providers), normalize_ai_usage(sample_value, providers)
    if not sample:
        return current
    if current and current["provider"] != sample["provider"]:
        current = {}
    return normalize_ai_usage({
        "provider": sample["provider"], "model": sample["model"] or current.get("model", ""),
        **{key: current.get(key, 0) + sample[key] for key in (
            "request_count", "input_tokens", "output_tokens", "total_tokens", "cached_tokens", "reasoning_tokens"
        )}, "reported": bool(current.get("reported") or sample["reported"]),
    }, providers)


def extract_ai_token_usage(provider: str, model: str, response: dict[str, Any], providers: set[str] | frozenset[str]) -> dict[str, Any]:
    raw = response.get("usage" if provider != "google" else "usageMetadata")
    usage = raw if isinstance(raw, dict) else {}
    if provider == "openai":
        source, details = usage, usage.get("input_tokens_details") if isinstance(usage.get("input_tokens_details"), dict) else {}
        output_details = usage.get("output_tokens_details") if isinstance(usage.get("output_tokens_details"), dict) else {}
        values = (source.get("input_tokens"), source.get("output_tokens"), source.get("total_tokens"), details.get("cached_tokens"), output_details.get("reasoning_tokens"))
    elif provider == "google":
        values = (usage.get("promptTokenCount"), usage.get("candidatesTokenCount"), usage.get("totalTokenCount"), usage.get("cachedContentTokenCount"), usage.get("thoughtsTokenCount"))
    elif provider == "lmstudio":
        prompt = usage.get("prompt_tokens_details") if isinstance(usage.get("prompt_tokens_details"), dict) else {}
        completion = usage.get("completion_tokens_details") if isinstance(usage.get("completion_tokens_details"), dict) else {}
        values = (usage.get("prompt_tokens"), usage.get("completion_tokens"), usage.get("total_tokens"), prompt.get("cached_tokens") or prompt.get("cached_tokens_count"), completion.get("reasoning_tokens"))
    else:
        return {}
    result = normalize_ai_usage({
        "provider": provider, "model": model, "request_count": 1,
        "input_tokens": safe_token_count(values[0]), "output_tokens": safe_token_count(values[1]),
        "total_tokens": safe_token_count(values[2]), "cached_tokens": safe_token_count(values[3]),
        "reasoning_tokens": safe_token_count(values[4]), "reported": bool(usage),
    }, providers)
    if result and not result["total_tokens"]:
        result["total_tokens"] = result["input_tokens"] + result["output_tokens"] + result["reasoning_tokens"]
    return result


def json_messages(system_prompt: str, user_prompt: str, data_messages=None) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    if data_messages is not None:
        if not isinstance(data_messages, list) or any(not isinstance(value, str) for value in data_messages):
            raise ValueError("Data messages must be a list of strings")
        messages.extend({"role": "user", "content": value} for value in data_messages)
    return messages


def openai_request(
    api_key: str, model: str, system_prompt: str, user_prompt: str,
    schema_name: str, schema: dict[str, Any], reasoning: dict[str, Any],
) -> tuple[str, dict[str, str], dict[str, Any]]:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "store": False,
        **reasoning,
        "input": json_messages(system_prompt, user_prompt),
        "text": {"format": {"type": "json_schema", "name": schema_name, "strict": True, "schema": schema}},
    }
    return "https://api.openai.com/v1/responses", headers, payload


def google_request(
    api_key: str, model: str, system_prompt: str, user_prompt: str,
    schema: dict[str, Any], reasoning: dict[str, Any],
) -> tuple[str, dict[str, str], dict[str, Any]]:
    encoded_model = urllib.parse.quote(model, safe="-_.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{encoded_model}:generateContent"
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {**reasoning, "responseMimeType": "application/json", "responseJsonSchema": schema},
    }
    return url, headers, payload


def lmstudio_request(
    endpoint: str, api_key: str, model_id: str, system_prompt: str, user_prompt: str,
    schema_name: str, schema: dict[str, Any], reasoning: dict[str, Any],
) -> tuple[str, dict[str, str], dict[str, Any]]:
    payload = {
        "model": model_id,
        "messages": json_messages(system_prompt, user_prompt),
        "response_format": {"type": "json_schema", "json_schema": {"name": schema_name, "strict": True, "schema": schema}},
        "temperature": 0.1,
        "stream": False,
        **reasoning,
    }
    return f"{endpoint}/chat/completions", lmstudio_headers(api_key), payload


TRUNCATED_MESSAGE = "AI の応答が出力トークン上限で途中終了しました。入力を小さくするか、出力上限を見直してください。"
LMSTUDIO_TRUNCATED_MESSAGE = (
    "ローカルLLMの応答がトークン上限で途中終了しました。"
    "入力を小さくするか、LM Studioのコンテキスト長・出力上限を見直してください。"
)
# Gemini finish reasons that mean the answer was withheld or cut short.  Other
# values (STOP, or a reason added later) fall through to normal parsing.
GOOGLE_BLOCKED_FINISH_REASONS = frozenset({
    "SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "IMAGE_SAFETY",
})
GOOGLE_INCOMPLETE_FINISH_REASONS = frozenset({"LANGUAGE", "OTHER"})


def _dict_items(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def ensure_complete_response(provider: str, response: dict[str, Any]) -> None:
    """Explain a truncated, filtered, or refused reply instead of a JSON error.

    Each provider reports an incomplete answer in its own field; without this
    check the partial text fails later as an unhelpful "invalid JSON" error.
    """
    if provider == "openai":
        if response.get("status") == "incomplete":
            details = response.get("incomplete_details")
            reason = details.get("reason") if isinstance(details, dict) else None
            if reason == "content_filter":
                raise RuntimeError("OpenAI の安全フィルターにより応答が途中で止められました。")
            if reason == "max_output_tokens":
                raise RuntimeError(TRUNCATED_MESSAGE)
            raise RuntimeError(f"OpenAI の応答が完了しませんでした（{str(reason or '理由不明')[:80]}）。")
        for item in _dict_items(response.get("output")):
            for content in _dict_items(item.get("content")):
                if content.get("type") == "refusal":
                    refusal = str(content.get("refusal") or "").strip()[:300]
                    raise RuntimeError("AI が回答を拒否しました" + (f": {refusal}" if refusal else "。"))
    elif provider == "google":
        candidates = _dict_items(response.get("candidates"))
        if not candidates:
            feedback = response.get("promptFeedback")
            block_reason = feedback.get("blockReason") if isinstance(feedback, dict) else None
            if block_reason:
                raise RuntimeError(f"入力が Google の安全判定でブロックされました（{str(block_reason)[:80]}）。")
            return
        finish_reason = str(candidates[0].get("finishReason") or "")
        if finish_reason == "MAX_TOKENS":
            raise RuntimeError(TRUNCATED_MESSAGE)
        if finish_reason in GOOGLE_BLOCKED_FINISH_REASONS:
            raise RuntimeError(f"Google の安全判定により応答が止められました（{finish_reason}）。")
        if finish_reason in GOOGLE_INCOMPLETE_FINISH_REASONS:
            raise RuntimeError(f"Google の応答が完了しませんでした（{finish_reason}）。")
    elif provider == "lmstudio":
        if any(choice.get("finish_reason") == "length" for choice in _dict_items(response.get("choices"))):
            raise RuntimeError(LMSTUDIO_TRUNCATED_MESSAGE)


def call_ai_json(
    provider: str, api_key: str, model: str, system_prompt: str, user_prompt: str,
    schema_name: str, schema: dict[str, Any], *, post: Callable[..., dict[str, Any]],
    lmstudio_base: Callable[[str], str], lmstudio_model_id: Callable[[Any], str],
    lmstudio_reasoning: Callable[[str, str, str], dict[str, Any]],
    providers: set[str] | frozenset[str],
    extract_openai: Callable[[dict[str, Any]], str] = extract_openai_text,
    extract_google: Callable[[dict[str, Any]], str] = extract_google_text,
    extract_lmstudio: Callable[[dict[str, Any]], str] = extract_lmstudio_text,
    check_cancelled: Callable[[], None] | None = None,
    usage_callback: Callable[[dict[str, Any]], None] | None = None, base_url: str = "",
    ai_efforts: dict | None = None,
    max_output_tokens: int | None = None,
    data_messages: list[str] | None = None,
) -> dict[str, Any]:
    reasoning = effort_payload(provider, model, schema_name, ai_efforts)
    if provider == "openai":
        request = openai_request(api_key, model, system_prompt, user_prompt, schema_name, schema, reasoning)
        extract = extract_openai
    elif provider == "google":
        request = google_request(api_key, model, system_prompt, user_prompt, schema, reasoning)
        extract = extract_google
    elif provider == "lmstudio":
        level = normalize_efforts(ai_efforts).get(SCHEMA_STAGES.get(schema_name), "auto")
        if level != "auto":
            resolve_effort = (local_cleanup_effort_payload
                              if SCHEMA_STAGES.get(schema_name) in {"cleanup", "notation"}
                              else local_effort_payload)
            reasoning = resolve_effort(level, lmstudio_reasoning(base_url, api_key, model))
        request = lmstudio_request(
            lmstudio_base(base_url), api_key, lmstudio_model_id(model),
            system_prompt, user_prompt, schema_name, schema, reasoning,
        )
        extract = extract_lmstudio
    else:
        raise RuntimeError(f"未対応の AI プロバイダーです: {provider}")
    url, headers, payload = request
    if data_messages is not None:
        messages = json_messages(system_prompt, user_prompt, data_messages)
        if provider == "google":
            payload["contents"] = [{"role": "user", "parts": [{"text": entry["content"]} for entry in messages[1:]]}]
        else:
            payload["input" if provider == "openai" else "messages"] = messages
    if max_output_tokens is not None:
        if type(max_output_tokens) is not int or max_output_tokens < 1 or provider != "lmstudio":
            raise ValueError("Output reservation requires a positive local-model token limit")
        payload["max_tokens"] = max_output_tokens
    response = post(url, headers, payload, check_cancelled=check_cancelled)
    # Usage is recorded before the completeness check: a truncated reply is still billed.
    usage = extract_ai_token_usage(provider, model, response, providers)
    if usage_callback is not None:
        usage_callback(usage)
    ensure_complete_response(provider, response)
    text = extract(response)
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AI が有効な JSON を返しませんでした。") from exc
    if not isinstance(result, dict):
        raise RuntimeError("AI の出力形式が不正です。")
    return result
