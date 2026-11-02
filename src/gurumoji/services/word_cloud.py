"""Word-cloud SVG used as the thumbnail of audio-only library items."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from .durable_files import atomic_write_text
from .group_analysis import text_mining_terms


WORD_CLOUD_SLOTS = (
    (320, 184, 250, 0, "middle"),
    (165, 118, 190, -8, "middle"),
    (478, 116, 190, 7, "middle"),
    (156, 232, 195, 6, "middle"),
    (480, 236, 190, -7, "middle"),
    (318, 96, 170, 0, "middle"),
    (319, 268, 180, 0, "middle"),
    (80, 170, 125, -12, "middle"),
    (560, 171, 125, 11, "middle"),
    (78, 283, 125, 0, "middle"),
    (557, 286, 125, 0, "middle"),
    (87, 86, 125, 0, "middle"),
    (551, 82, 125, 0, "middle"),
    (225, 304, 145, -5, "middle"),
    (413, 306, 145, 5, "middle"),
    (226, 58, 140, 0, "middle"),
    (411, 57, 140, 0, "middle"),
    (320, 330, 170, 0, "middle"),
)


def word_cloud_svg(source_name: str, segments: list[dict[str, Any]]) -> str:
    """Render a dependency-free word cloud as an SVG image."""
    terms = text_mining_terms(segments)
    max_count = max((count for _, count in terms), default=1)
    min_count = min((count for _, count in terms), default=1)
    palette = ("#d7f34a", "#ff9b42", "#79b791", "#efd6ac", "#b8d8d8", "#d3c4e3", "#f2b5d4", "#a7c7e7")
    words: list[str] = []
    for index, ((term, count), slot) in enumerate(zip(terms, WORD_CLOUD_SLOTS)):
        x, y, max_width, rotation, anchor = slot
        ratio = (count - min_count) / max(1, max_count - min_count)
        rank_bonus = max(0, 8 - index) * 0.7
        font_size = round(17 + ratio * 27 + rank_bonus, 1)
        label = html.escape(term[:24])
        estimated_width = len(term) * font_size * (0.95 if not term.isascii() else 0.58)
        length_attributes = (
            f' textLength="{max_width}" lengthAdjust="spacingAndGlyphs"'
            if estimated_width > max_width
            else ""
        )
        color = palette[index % len(palette)]
        words.append(
            f'<g transform="rotate({rotation} {x} {y})">'
            f'<text x="{x}" y="{y}" text-anchor="{anchor}" dominant-baseline="middle" '
            f'font-size="{font_size}" fill="{color}" class="word"{length_attributes}>'
            f'<title>{label}: {count}回</title>{label}</text></g>'
        )
    if not words:
        words.append(
            '<text x="320" y="178" class="empty" text-anchor="middle">テキストデータなし</text>'
            '<text x="320" y="211" class="hint" text-anchor="middle">'
            '文字起こしを保存するとワードクラウドを表示します</text>'
        )
    title = html.escape(Path(source_name).stem[:42] or "文字起こし")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360">
<rect width="640" height="360" rx="24" fill="#18211d"/>
<circle cx="604" cy="34" r="86" fill="#d7f34a" opacity=".09"/>
<circle cx="38" cy="344" r="105" fill="#ff9b42" opacity=".08"/>
<text x="24" y="25" class="eyebrow">WORD CLOUD</text>
<text x="616" y="25" class="source" text-anchor="end">{title}</text>
{''.join(words)}
<text x="616" y="345" class="footer" text-anchor="end">{len(segments)} SEGMENTS</text>
<style>
text {{ font-family: "Yu Gothic UI", "Meiryo", sans-serif; }}
.word {{ font-weight:800; paint-order:stroke; stroke:#18211d; stroke-width:2px; stroke-opacity:.22; }}
.eyebrow {{ fill:#d7f34a; font-size:10px; font-weight:800; letter-spacing:2px; }}
.source {{ fill:#91a098; font-size:10px; }}
.empty {{ fill:#d7f34a; font-size:23px; font-weight:800; }}
.hint {{ fill:#91a098; font-size:12px; }}
.footer {{ fill:#91a098; font-size:9px; font-weight:800; letter-spacing:1px; }}
</style>
</svg>"""


def write_word_cloud(
    target: Path,
    source_name: str,
    segments: list[dict[str, Any]],
) -> Path:
    return atomic_write_text(target, word_cloud_svg(source_name, segments), encoding="utf-8")
