"""公開版の画面に必要な素材を順序付きで返す。"""
from __future__ import annotations

def application_scripts() -> tuple[str, ...]:
    return ("transcript-math.js", "transcript-worker-client.js") + tuple(
        "ui/" + name + ".js" for name in (
            "shared", "setup", "navigation", "speakers", "processing", "library", "result", "transcript",
        )
    ) + ("app.js", "data-catalog.js", "notation.js", "ai-effort.js", "create-dashboard.js", "general-settings.js")

def application_styles() -> tuple[str, ...]:
    return ("style.css", "ai-effort.css", "stitch-theme.css")
