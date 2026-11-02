"""Redaction of local filesystem paths from diagnostics shown to remote clients.

Error messages, logs and warnings can contain absolute paths (user names,
folder layout). When the UI is reached remotely without the local-path
opt-in, any diagnostic item that contains such a path is replaced as a whole.
"""

from __future__ import annotations

import re
from typing import Any

WINDOWS_ABSOLUTE_PATH_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:[A-Z]:[\\/]|\\\\(?:[?.]\\)?[^\\/\r\n]+[\\/])"
)


POSIX_ABSOLUTE_PATH_RE = re.compile(
    r"(?:^|(?<=[\s'\`(<\[{=:]))/(?!/)[^\s'\`<>()\[\]{}\r\n]+"
)


FILE_URI_RE = re.compile(r"(?i)\bfile://")


HIDDEN_LOCAL_PATH_MESSAGE = "[local path hidden]"


REMOTE_DIAGNOSTIC_KEYS = frozenset({
    "error", "message", "logs", "reason", "warning", "warnings",
    "restore_errors", "cleanup_errors", "recovery_paths",
    "output_warning", "learning_warning", "output_dir", "default_output_dir",
})


def public_diagnostic_text(value: str, *, reveal_local_paths: bool) -> str:
    """Hide a whole diagnostic item if it contains an absolute local path."""
    text = str(value or "")
    if reveal_local_paths or not text:
        return text
    if (
        WINDOWS_ABSOLUTE_PATH_RE.search(text)
        or POSIX_ABSOLUTE_PATH_RE.search(text)
        or FILE_URI_RE.search(text)
    ):
        return HIDDEN_LOCAL_PATH_MESSAGE
    return text


def sanitize_remote_diagnostic_value(value: Any) -> Any:
    if isinstance(value, str):
        return public_diagnostic_text(value, reveal_local_paths=False)
    if isinstance(value, list):
        return [sanitize_remote_diagnostic_value(item) for item in value]
    if isinstance(value, dict):
        return {
            key: sanitize_remote_diagnostic_value(item)
            for key, item in value.items()
        }
    return value


def sanitize_remote_json_payload(value: Any) -> Any:
    if isinstance(value, list):
        return [sanitize_remote_json_payload(item) for item in value]
    if not isinstance(value, dict):
        return value
    sanitized: dict[str, Any] = {}
    for key, item in value.items():
        key_text = str(key)
        diagnostic = (
            key_text in REMOTE_DIAGNOSTIC_KEYS
            or key_text.endswith("_warning")
            or key_text.endswith("_errors")
        )
        sanitized[key] = (
            sanitize_remote_diagnostic_value(item)
            if diagnostic
            else sanitize_remote_json_payload(item)
        )
    return sanitized
