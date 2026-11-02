"""提供する画面に必要な素材だけを順序付きで返す。"""

from __future__ import annotations

CORE_SCRIPTS = tuple(
    "ui/" + name + ".js"
    for name in (
        "shared",
        "setup",
        "navigation",
        "speakers",
        "processing",
        "library",
        "result",
        "transcript",
    )
)
ANALYSIS_SCRIPTS = (
    "analysis-content.js",
    "analysis-storage.js",
    "analysis-visualizations.js",
    "analysis-method-view.js",
    "ui/analysis.js",
)


def application_scripts(analysis_enabled: bool = False) -> tuple[str, ...]:
    optional = ANALYSIS_SCRIPTS if analysis_enabled else ()
    after = (
        ("ui/analysis-bootstrap.js", "interview-comparison.js")
        if analysis_enabled
        else ()
    )
    return (
        ("transcript-math.js", "transcript-worker-client.js")
        + CORE_SCRIPTS
        + optional
        + ("app.js",)
        + after
        + (
            "data-catalog.js",
            "notation.js",
            "ai-effort.js",
            "create-dashboard.js",
            "general-settings.js",
        )
        + (
            (
                "analysis-execution.js",
                "analysis-orchestration.js",
                "analysis-history.js",
                "research-workspace.js",
            )
            if analysis_enabled
            else ()
        )
    )


def application_styles(analysis_enabled: bool = False) -> tuple[str, ...]:
    return ("style.css", "ai-effort.css", "stitch-theme.css") + (
        ("analysis-orchestration.css", "analysis-history.css")
        if analysis_enabled
        else ()
    )
