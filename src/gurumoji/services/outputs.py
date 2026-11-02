"""Transcript output files: text, SRT, JSON, subtitles, and burned-in video.

One transcription run writes a directory of deliverables.  Everything about
their names, their layout, and the FFmpeg invocations that produce the subtitle
assets lives here; the composition root supplies the cancellable subprocess
runner and the two writers that reach back into application state.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ..text_utils import clean_single_line
from .durable_files import atomic_write_text, durable_move, sync_file_data, temporary_output_path
from .meeting_minutes import (
    format_meeting_minutes_markdown,
    format_outline_text,
    meeting_external_payload,
    meeting_tasks_csv_text,
    normalize_meeting_minutes,
)
from .emotion import emotion_segments_for_output, segment_emotion_display
from .transcription.segments import default_speaker_name, display_time, srt_time

SPEAKER_THEME_COLORS = (
    "#E86A5A",
    "#2F80ED",
    "#27AE60",
    "#9B51E0",
    "#F2994A",
    "#00A6A6",
    "#EB5FA7",
    "#7A6FBE",
    "#6C8B3C",
    "#C47F17",
    "#3E8ED0",
    "#B85C5C",
    "#D1495B",
    "#00798C",
    "#6A4C93",
    "#8F5B34",
    "#B33C86",
    "#4D9078",
    "#E4572E",
    "#577590",
)


def safe_output_stem(source_name: str) -> str:
    stem = Path(source_name).stem.strip()
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem).rstrip(" .")
    return stem[:180] or "transcript"


def job_output_directory(output_root: Path, source_name: str, job_id: str) -> Path:
    """Return a unique, readable folder for one transcription execution."""
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    source_stem = safe_output_stem(source_name)[:72].rstrip(" ._") or "transcript"
    return output_root / f"{timestamp}_{source_stem}_{job_id[:8]}"


def manual_output_directory(source_name: str, item_id: str, *, output_root: Path) -> Path:
    """Give every manually-created record an output directory of its own."""
    source_stem = safe_output_stem(source_name)[:72].rstrip(" ._") or "transcript"
    return output_root / f"manual_{source_stem}_{item_id[:8]}"


def speaker_theme_color_map(
    segments: list[dict[str, Any]],
    speaker_profiles: dict[str, dict[str, Any]] | None = None,
) -> dict[str, str]:
    """Return stable, distinct RGB colors for every speaker label."""
    profiles = speaker_profiles if isinstance(speaker_profiles, dict) else {}
    labels = sorted({str(item.get("speaker") or "UNKNOWN") for item in segments})
    colors: dict[str, str] = {}
    for index, label in enumerate(labels):
        profile = profiles.get(label)
        profile = profile if isinstance(profile, dict) else {}
        requested = clean_single_line(profile.get("theme_color"), 7).upper()
        colors[label] = (
            requested
            if re.fullmatch(r"#[0-9A-F]{6}", requested)
            else SPEAKER_THEME_COLORS[index % len(SPEAKER_THEME_COLORS)]
        )
    return colors


def rgb_to_ass_color(value: str) -> str:
    """Convert #RRGGBB to libass' &H00BBGGRR format."""
    normalized = value.lstrip("#").upper()
    if not re.fullmatch(r"[0-9A-F]{6}", normalized):
        normalized = "FFFFFF"
    red, green, blue = normalized[0:2], normalized[2:4], normalized[4:6]
    return f"&H00{blue}{green}{red}"


def ass_time(seconds: Any) -> str:
    centiseconds = max(0, round(float(seconds or 0) * 100))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    whole_seconds, fraction = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{fraction:02d}"


def ass_escape_text(value: Any) -> str:
    text = str(value or "").strip()
    return (
        text.replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("\r\n", r"\N")
        .replace("\r", r"\N")
        .replace("\n", r"\N")
    )


def subtitle_text_width(value: str, font_size: int) -> float:
    """Estimate rendered subtitle width for mixed Japanese and Latin text."""
    width = 0.0
    for character in str(value or ""):
        if character == "\t":
            width += font_size * 2.0
        elif character.isspace():
            width += font_size * 0.35
        elif unicodedata.east_asian_width(character) in {"W", "F", "A"}:
            width += font_size
        else:
            width += font_size * 0.58
    return width


SUBTITLE_BREAK_AFTER = frozenset("、。！？!?，,．.：:；;）)]｝}」』】〉》・ ")


def wrap_subtitle_lines(value: Any, max_width: float, font_size: int) -> list[str]:
    """Wrap text before it reaches the video's horizontal safe area."""
    maximum = max(float(font_size) * 4.0, float(max_width))
    lines: list[str] = []
    paragraphs = re.split(r"\r\n|\r|\n", str(value or "").strip())
    for paragraph in paragraphs:
        remaining = paragraph.strip()
        if not remaining:
            if lines and lines[-1]:
                lines.append("")
            continue
        while remaining:
            current = ""
            last_break = 0
            for character in remaining:
                candidate = current + character
                if current and subtitle_text_width(candidate, font_size) > maximum:
                    break
                current = candidate
                if character in SUBTITLE_BREAK_AFTER:
                    last_break = len(current)
            if len(current) == len(remaining):
                lines.append(current.strip())
                break
            if not current:
                current = remaining[0]
            minimum_break_width = maximum * 0.45
            if (
                last_break > 0
                and subtitle_text_width(current[:last_break], font_size) >= minimum_break_width
            ):
                split_at = last_break
            else:
                split_at = len(current)
            line = remaining[:split_at].strip()
            if line:
                lines.append(line)
            remaining = remaining[split_at:].lstrip()
    return lines or [""]


def subtitle_text_pages(
    value: Any,
    max_width: float,
    font_size: int,
    max_lines: int = 2,
) -> list[str]:
    lines = wrap_subtitle_lines(value, max_width, font_size)
    page_size = max(1, int(max_lines))
    return ["\n".join(lines[index:index + page_size]) for index in range(0, len(lines), page_size)]


MEDIA_SESSION_DATE_TAGS = (
    "com.apple.quicktime.creationdate",
    "creation_time",
    "date",
)


def probe_media_payload(
    source_path: Path, check_cancelled: Callable[[], None] | None = None,
    *, run_subprocess: Callable[..., Any], entries: str | None = None,
    video_only: bool = False,
) -> tuple[dict[str, Any] | None, str | None]:
    """Shared bounded ffprobe reader for recording dates, dimensions and assets."""
    if shutil.which("ffprobe") is None:
        return None, "ffprobe_unavailable"
    command = ["ffprobe", "-v", "error"]
    if video_only:
        command.extend(["-select_streams", "v:0"])
    if entries is not None:
        command.extend(["-show_entries", entries])
    else:
        command.extend(["-show_format", "-show_streams", "-show_program_version"])
    command.extend(["-of", "json", str(source_path.resolve())])
    try:
        completed = run_subprocess(command, timeout=30, check_cancelled=check_cancelled)
        if completed.returncode != 0:
            return None, "ffprobe_failed"
        payload = json.loads(completed.stdout)
        if not isinstance(payload, dict):
            return None, "invalid_probe_json"
        return payload, None
    except InterruptedError:
        raise
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        return None, "ffprobe_failed"


def media_metadata_session_date(
    source_path: Path,
    check_cancelled: Callable[[], None] | None = None,
    *,
    run_subprocess: Callable[..., Any],
    is_video_path: Callable[[Path], bool],
) -> str:
    """Read an embedded recording date without guessing from filesystem times."""
    if not is_video_path(source_path) or shutil.which("ffprobe") is None:
        return ""
    try:
        payload, _reason = probe_media_payload(
            source_path, check_cancelled, run_subprocess=run_subprocess,
            entries="format_tags:stream_tags",
        )
        if not isinstance(payload, dict):
            return ""
        tag_sets: list[dict[str, Any]] = []
        format_data = payload.get("format")
        if isinstance(format_data, dict) and isinstance(format_data.get("tags"), dict):
            tag_sets.append(format_data["tags"])
        streams = payload.get("streams")
        if isinstance(streams, list):
            tag_sets.extend(
                stream["tags"]
                for stream in streams
                if isinstance(stream, dict) and isinstance(stream.get("tags"), dict)
            )
        normalized_tag_sets = [
            {str(key).casefold(): value for key, value in tags.items()}
            for tags in tag_sets
        ]
        for tag_name in MEDIA_SESSION_DATE_TAGS:
            for tags in normalized_tag_sets:
                raw_value = str(tags.get(tag_name, "")).strip()
                match = re.search(r"(?<!\d)(\d{4})[-:/](\d{2})[-:/](\d{2})(?!\d)", raw_value)
                if not match:
                    continue
                candidate = "-".join(match.groups())
                try:
                    datetime.strptime(candidate, "%Y-%m-%d")
                except ValueError:
                    continue
                return candidate
    except InterruptedError:
        raise
    except (OSError, TypeError, json.JSONDecodeError, subprocess.SubprocessError):
        return ""
    return ""


def session_profile_from_media(
    source_path: Path,
    check_cancelled: Callable[[], None] | None = None,
    *,
    run_subprocess: Callable[..., Any],
    is_video_path: Callable[[Path], bool],
) -> dict[str, str]:
    session_date = media_metadata_session_date(
        source_path, check_cancelled,
        run_subprocess=run_subprocess, is_video_path=is_video_path,
    )
    if not session_date:
        return {}
    return {
        "session_date": session_date,
        "session_date_source": "media_metadata",
    }


def probe_video_dimensions(
    source_path: Path,
    check_cancelled: Callable[[], None] | None = None,
    *,
    run_subprocess: Callable[..., Any],
) -> tuple[int, int]:
    """Return displayed video dimensions, accounting for rotation metadata."""
    if shutil.which("ffprobe") is None:
        return 1920, 1080
    try:
        payload, _reason = probe_media_payload(
            source_path, check_cancelled, run_subprocess=run_subprocess, video_only=True,
            entries="stream=width,height:stream_tags=rotate:stream_side_data=rotation",
        )
        streams = payload.get("streams") if isinstance(payload, dict) else None
        stream = streams[0] if isinstance(streams, list) and streams else {}
        width = int(stream.get("width") or 0)
        height = int(stream.get("height") or 0)
        rotation = int((stream.get("tags") or {}).get("rotate") or 0)
        for side_data in stream.get("side_data_list") or []:
            if isinstance(side_data, dict) and side_data.get("rotation") is not None:
                rotation = int(side_data["rotation"])
                break
        if width > 0 and height > 0:
            return (height, width) if abs(rotation) % 180 == 90 else (width, height)
    except (OSError, ValueError, TypeError, json.JSONDecodeError, subprocess.SubprocessError):
        pass
    return 1920, 1080


def write_ass_subtitles(
    target: Path,
    source_name: str,
    segments: list[dict[str, Any]],
    speaker_names: dict[str, str],
    speaker_profiles: dict[str, dict[str, Any]] | None = None,
    video_width: int = 1920,
    video_height: int = 1080,
) -> Path:
    colors = speaker_theme_color_map(segments, speaker_profiles)
    play_res_x = max(160, int(video_width))
    play_res_y = max(90, int(video_height))
    scale = max(0.15, min(play_res_x / 1920.0, play_res_y / 1080.0))
    font_size = max(8, round(48 * scale))
    margin_h = max(8, round(90 * scale))
    margin_v = max(6, round(58 * scale))
    outline = max(1, round(3 * scale))
    shadow = max(1, round(scale))
    safe_text_width = max(font_size * 6.0, play_res_x - 2.0 * margin_h)
    header = f"""[Script Info]
Title: {ass_escape_text(source_name)}
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: {play_res_x}
PlayResY: {play_res_y}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Yu Gothic UI,{font_size},&H00FFFFFF,&H00FFFFFF,&H00101010,&H90000000,0,0,0,0,100,100,0,0,1,{outline},{shadow},2,{margin_h},{margin_h},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: list[str] = []
    for item in segments:
        label = str(item.get("speaker") or "UNKNOWN")
        name = str(speaker_names.get(label) or default_speaker_name(label)).strip()
        start = max(0.0, float(item.get("start", 0) or 0))
        end = max(start + 0.2, float(item.get("end", start) or start))
        color = rgb_to_ass_color(colors.get(label, "#FFFFFF"))
        name_text = ass_escape_text(name)
        pages = subtitle_text_pages(item.get("text", ""), safe_text_width, font_size)
        duration = end - start
        for page_index, page in enumerate(pages):
            page_start = start + duration * page_index / len(pages)
            page_end = start + duration * (page_index + 1) / len(pages)
            body_text = ass_escape_text(page)
            dialogue = f"{{\\c{color}\\b1}}{name_text}{{\\rDefault}}\\N{body_text}"
            events.append(
                f"Dialogue: 0,{ass_time(page_start)},{ass_time(page_end)},Default,{ass_escape_text(label)},"
                f"0,0,0,,{dialogue}"
            )
    return atomic_write_text(
        target,
        header + "\n".join(events) + ("\n" if events else ""),
        encoding="utf-8-sig",
    )


def burn_ass_subtitles_into_video(
    source_path: Path,
    ass_path: Path,
    target: Path,
    check_cancelled: Callable[[], None] | None = None,
    *,
    run_subprocess: Callable[..., Any],
    is_video_path: Callable[[Path], bool],
) -> Path:
    if not is_video_path(source_path):
        raise ValueError("字幕焼き込み動画は MP4/M4V/MOV/MKV からだけ作成できます。")
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("字幕動画の作成に必要な ffmpeg が見つかりません。")
    if check_cancelled is not None:
        check_cancelled()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = temporary_output_path(target)
    escaped_ass_name = (
        ass_path.name.replace("\\", r"\\")
        .replace("'", r"\'")
        .replace(",", r"\,")
        .replace("[", r"\[")
        .replace("]", r"\]")
    )
    try:
        completed = run_subprocess(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-i", str(source_path.resolve()),
                "-vf", f"ass='{escaped_ass_name}'",
                "-map", "0:v:0", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                "-max_muxing_queue_size", "2048",
                temporary.name,
            ],
            cwd=str(target.parent),
            timeout=float(os.environ.get("MOJIOKOSI_FFMPEG_TIMEOUT_SECONDS", "7200")),
            check_cancelled=check_cancelled,
        )
        if completed.returncode != 0 or not temporary.is_file() or temporary.stat().st_size == 0:
            details = completed.stderr.strip()[-2000:]
            raise RuntimeError("字幕動画を作成できませんでした。" + (f"\n{details}" if details else ""))
        if check_cancelled is not None:
            check_cancelled()
        sync_file_data(temporary)
        durable_move(temporary, target)
        if check_cancelled is not None:
            check_cancelled()
    finally:
        temporary.unlink(missing_ok=True)
    return target


def write_subtitled_video_assets(
    source_path: Path,
    source_name: str,
    output_dir: Path,
    segments: list[dict[str, Any]],
    speaker_names: dict[str, str],
    speaker_profiles: dict[str, dict[str, Any]] | None = None,
    check_cancelled: Callable[[], None] | None = None,
    *,
    run_subprocess: Callable[..., Any],
    is_video_path: Callable[[Path], bool],
) -> list[Path]:
    stem = safe_output_stem(source_name)
    if check_cancelled is not None:
        check_cancelled()
    video_width, video_height = probe_video_dimensions(
        source_path, check_cancelled, run_subprocess=run_subprocess
    )
    ass_path = write_ass_subtitles(
        output_dir / f"{stem}_話者カラー字幕.ass",
        source_name,
        segments,
        speaker_names,
        speaker_profiles,
        video_width,
        video_height,
    )
    if check_cancelled is not None:
        check_cancelled()
    video_path = burn_ass_subtitles_into_video(
        source_path,
        ass_path,
        output_dir / f"{stem}_字幕付き.mp4",
        check_cancelled,
        run_subprocess=run_subprocess,
        is_video_path=is_video_path,
    )
    return [ass_path, video_path]


def write_outputs(
    source_name: str,
    output_dir: Path,
    segments: list[dict[str, Any]],
    language: str | None,
    speaker_names: dict[str, str],
    write_srt: bool,
    write_json: bool,
    outline: dict[str, Any] | None = None,
    emotion_analysis: dict[str, Any] | None = None,
    speaker_profiles: dict[str, dict[str, Any]] | None = None,
    meeting_minutes: dict[str, Any] | None = None,
    check_cancelled: Callable[[], None] | None = None,
    formatting_result: dict[str, Any] | None = None,
    write_word_cloud_file: bool = False,
    *,
    session_profile: dict[str, Any] | None = None,
    write_word_cloud: Callable[[Path, str, list[dict[str, Any]]], Path],
    emotion_csv_text: Callable[[list[dict[str, Any]], dict[str, str]], str],
) -> list[Path]:
    # Keep direct callers using the previous positional final callback working.
    if check_cancelled is None and callable(meeting_minutes):
        check_cancelled = meeting_minutes
        meeting_minutes = None
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = safe_output_stem(source_name)
    written: list[Path] = []

    def check() -> None:
        if check_cancelled is not None:
            check_cancelled()

    def write_text(target: Path, value: str, encoding: str = "utf-8") -> None:
        check()
        atomic_write_text(target, value, encoding=encoding)
        check()

    def name_for(label: str | None) -> str:
        if label and speaker_names.get(label, "").strip():
            return speaker_names[label].strip()
        return default_speaker_name(label)

    # JSON is the durable machine-readable result and is intentionally written
    # before every optional presentation format.
    theme_colors = speaker_theme_color_map(segments, speaker_profiles)
    json_path = output_dir / f"{stem}_話者分離.json"
    payload = {
        "source": source_name,
        "language": language,
        "speaker_names": speaker_names,
        "speaker_theme_colors": theme_colors,
        "speaker_profiles": speaker_profiles or {},
        "speakers": [
            {
                "label": label,
                "name": speaker_names.get(label) or default_speaker_name(label),
                "theme_color": color,
            }
            for label, color in theme_colors.items()
        ],
        "segments": segments,
    }
    if session_profile is not None:
        payload["session_profile"] = session_profile
    if outline:
        payload["outline"] = outline
    if meeting_minutes:
        payload["meeting_minutes"] = normalize_meeting_minutes(meeting_minutes)
    if emotion_analysis:
        payload["emotion_analysis"] = emotion_analysis
    if formatting_result:
        payload["formatting_result"] = formatting_result
    write_text(json_path, json.dumps(payload, ensure_ascii=False, indent=2))
    written.append(json_path)

    if formatting_result:
        formatting_path = output_dir / f"{stem}_整形リザルト.json"
        write_text(
            formatting_path,
            json.dumps(formatting_result, ensure_ascii=False, indent=2),
        )
        written.append(formatting_path)

    text_path = output_dir / f"{stem}_話者分離.txt"
    lines = [f"元ファイル: {source_name}", ""]
    for item in segments:
        emotion_text = segment_emotion_display(item)
        header = f"[{display_time(item['start'])} - {display_time(item['end'])}] {name_for(item.get('speaker'))}"
        if emotion_text:
            header = f"{header} / 感情: {emotion_text}"
        lines.extend([
            header,
            str(item.get("text", "")).strip(),
            "",
        ])
    write_text(text_path, "\n".join(lines))
    written.append(text_path)

    if write_word_cloud_file:
        word_cloud_path = output_dir / f"{stem}_ワードクラウド.svg"
        check()
        write_word_cloud(word_cloud_path, source_name, segments)
        check()
        written.append(word_cloud_path)

    if write_srt:
        srt_path = output_dir / f"{stem}_話者分離.srt"
        blocks = [
            "\n".join([
                str(index),
                f"{srt_time(item['start'])} --> {srt_time(item['end'])}",
                f"{name_for(item.get('speaker'))}: {str(item.get('text', '')).strip()}",
            ])
            for index, item in enumerate(segments, 1)
        ]
        write_text(srt_path, "\n\n".join(blocks) + ("\n" if blocks else ""))
        written.append(srt_path)

    if outline:
        outline_path = output_dir / f"{stem}_アウトライン.txt"
        write_text(outline_path, format_outline_text(source_name, outline))
        written.append(outline_path)
    if meeting_minutes:
        normalized_minutes = normalize_meeting_minutes(meeting_minutes)
        minutes_path = output_dir / f"{stem}_会議議事録.md"
        write_text(minutes_path, format_meeting_minutes_markdown(source_name, normalized_minutes))
        written.append(minutes_path)
        tasks_path = output_dir / f"{stem}_タスク.csv"
        write_text(tasks_path, meeting_tasks_csv_text(normalized_minutes), encoding="utf-8-sig")
        written.append(tasks_path)
        external_json_path = output_dir / f"{stem}_meeting.json"
        write_text(
            external_json_path,
            json.dumps(meeting_external_payload(source_name, normalized_minutes), ensure_ascii=False, indent=2),
        )
        written.append(external_json_path)
    if emotion_analysis:
        emotion_payload = {
            "source": source_name,
            "language": language,
            "speaker_names": speaker_names,
            **emotion_analysis,
            "segments": emotion_segments_for_output(segments, speaker_names),
        }
        emotion_json_path = output_dir / f"{stem}_感情分析.json"
        write_text(
            emotion_json_path,
            json.dumps(emotion_payload, ensure_ascii=False, indent=2),
        )
        written.append(emotion_json_path)
        csv_body = emotion_csv_text(segments, speaker_names)
        if csv_body.count("\n") > 1:
            emotion_csv_path = output_dir / f"{stem}_感情分析.csv"
            write_text(emotion_csv_path, csv_body, encoding="utf-8-sig")
            written.append(emotion_csv_path)
    check()
    return written
