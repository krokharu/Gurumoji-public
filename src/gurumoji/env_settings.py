"""Environment-variable readers shared by the application and its services.

These live outside ``app`` so service modules can read tuning knobs without
importing the composition root, and so ``app`` can use them while building its
module-level constants.
"""

from __future__ import annotations

import os


def positive_env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return min(maximum, max(minimum, value))


def env_enabled(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().casefold() in {"1", "true", "yes", "on"}
