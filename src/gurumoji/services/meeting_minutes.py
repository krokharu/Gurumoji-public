"""Meeting minutes: candidate extraction, normalization, and export rendering.

The transcript is scanned for decision and task wording, and the resulting
minutes are rendered for the JSON, CSV, and Markdown exports.  The module is
free of Flask and application-global dependencies.
"""

from __future__ import annotations

import csv
import io
import math
import re
from datetime import datetime
from typing import Any

from ..text_utils import clean_single_line, utc_now_iso
from .transcription.segments import default_speaker_name, display_time, segment_bounds

MEETING_MINUTES_VERSION = "1.0"
MEETING_TASK_PRIORITIES = ("high", "medium", "low", "unspecified")
MEETING_TASK_PRIORITY_LABELS = {
    "high": "高",
    "medium": "中",
    "low": "低",
    "unspecified": "未設定",
}


def format_outline_text(source_name: str, outline: dict[str, Any]) -> str:
    lines = ["議題・アウトライン", f"元ファイル: {source_name}", ""]
    sections = outline.get("sections") if isinstance(outline, dict) else None
    if not isinstance(sections, list) or not sections:
        lines.append("アウトラインは作成されませんでした。")
        return "\n".join(lines)
    for index, section in enumerate(sections, 1):
        title = str(section.get("title", "")).strip() or f"議題 {index}"
        start = display_time(float(section.get("start", 0)))
        end = display_time(float(section.get("end", section.get("start", 0))))
        lines.append(f"{index}. [{start} - {end}] {title}")
        bullets = section.get("bullets")
        if isinstance(bullets, list):
            for bullet in bullets:
                text = str(bullet).strip()
                if text:
                    lines.append(f"   - {text}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def meeting_task_priority(text: Any) -> str:
    value = str(text or "")
    if re.search(r"至急|緊急|最優先|クリティカル|優先度\s*[:：]?\s*(?:高|A)", value, re.I):
        return "high"
    if re.search(r"急ぎではない|後回し|低優先|優先度\s*[:：]?\s*(?:低|C)", value, re.I):
        return "low"
    if re.search(r"優先|今週|期限|締切|までに|優先度\s*[:：]?\s*(?:中|B)", value, re.I):
        return "medium"
    return "unspecified"


def meeting_due_details(text: Any, session_date: Any = "") -> tuple[str, str]:
    """Return an exact ISO date only when the recording supplies one explicitly.

    Relative expressions are retained as text rather than silently converting an
    ambiguous phrase such as "来週" into a date. This keeps task exports safe to
    import into a calendar or task manager after a human check.
    """
    value = str(text or "")
    base: datetime | None = None
    try:
        base = datetime.strptime(str(session_date or ""), "%Y-%m-%d")
    except ValueError:
        pass
    exact = re.search(r"(?<!\d)(20\d{2})\s*(?:年|[-/.])\s*(\d{1,2})\s*(?:月|[-/.])\s*(\d{1,2})\s*日?", value)
    if exact:
        try:
            date = datetime(int(exact.group(1)), int(exact.group(2)), int(exact.group(3)))
            return date.date().isoformat(), exact.group(0).strip()
        except ValueError:
            pass
    month_day = re.search(r"(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*日?", value)
    if month_day and base:
        try:
            date = datetime(base.year, int(month_day.group(1)), int(month_day.group(2)))
            return date.date().isoformat(), month_day.group(0).strip()
        except ValueError:
            pass
    relative = re.search(r"今日|明日|明後日|今週(?:中|末)?|来週(?:中|末)?|再来週|月末|年度末|(?:\d{1,2})\s*日(?:まで|迄)?", value)
    if not relative:
        return "", ""
    due_text = relative.group(0).strip()
    if base and due_text in {"今日", "明日", "明後日"}:
        offset = {"今日": 0, "明日": 1, "明後日": 2}[due_text]
        return (base.date().fromordinal(base.date().toordinal() + offset).isoformat(), due_text)
    return "", due_text


def meeting_decision_candidate(text: Any) -> bool:
    return bool(re.search(
        r"決定(?:しました|する|です)|決まり(?:ました|です)|合意(?:しました|です)|"
        r"承認(?:しました|です)|採用(?:します|しました)|方針",
        str(text or ""),
    ))


def meeting_task_candidate(text: Any) -> bool:
    value = str(text or "")
    direct_action = bool(re.search(
        r"お願いします|依頼|担当|対応(?:します|する|を)|確認(?:します|する|を)|共有(?:します|する|を)|"
        r"提出(?:します|する|を)|作成(?:します|する|を)|送付(?:します|する|を)|連絡(?:します|する|を)|"
        r"準備(?:します|する|を)|実施(?:します|する|を)|レビュー(?:します|する|を)|"
        r"タスク|アクション|宿題|までに|締切|期限",
        value,
    ))
    if direct_action:
        return True
    # 「方針として進めることに決まった」は決定事項であり、担当者の
    # アクションとは限らないため、単独の進行表現は決定表現から除外する。
    return bool(re.search(r"進め(?:ます|る)", value)) and not meeting_decision_candidate(value)


def meeting_task_title(text: Any) -> str:
    value = clean_single_line(text, 500)
    value = re.sub(r"^(?:えーと|では|じゃあ|それでは|すみませんが)[、,\s]*", "", value)
    return value or "要確認のタスク候補"


def build_meeting_minutes(
    segments: list[dict[str, Any]],
    speaker_names: dict[str, str],
    session_profile: dict[str, Any] | None = None,
    outline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a reviewable, rule-based meeting record from diarized turns.

    The extractor intentionally emits *candidates*. It does not infer an owner,
    priority, or calendar date that is absent from the spoken record.
    """
    session_profile = session_profile if isinstance(session_profile, dict) else {}
    session_date = str(session_profile.get("session_date") or "")
    tasks: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    speaker_activity: dict[str, dict[str, Any]] = {}
    seen_tasks: set[str] = set()
    for index, segment in enumerate(segments):
        text = clean_single_line(segment.get("text"), 1200)
        if not text:
            continue
        label = str(segment.get("speaker") or "UNKNOWN")
        speaker = clean_single_line(speaker_names.get(label) or default_speaker_name(label), 120)
        start, end = segment_bounds(segment)
        activity = speaker_activity.setdefault(speaker, {"speaker": speaker, "turns": 0, "seconds": 0.0})
        activity["turns"] += 1
        activity["seconds"] += max(0.0, end - start)
        evidence_id = clean_single_line(segment.get("id") or f"segment-{index + 1}", 160)
        if meeting_task_candidate(text):
            title = meeting_task_title(text)
            dedupe_key = re.sub(r"\s+", "", title).casefold()
            if dedupe_key not in seen_tasks:
                seen_tasks.add(dedupe_key)
                due_date, due_text = meeting_due_details(text, session_date)
                tasks.append({
                    "task_id": f"task-{len(tasks) + 1}",
                    "title": title,
                    "owner": speaker,
                    "priority": meeting_task_priority(text),
                    "due_date": due_date,
                    "due_text": due_text,
                    "status": "open",
                    "confidence": "candidate",
                    "evidence_segment_id": evidence_id,
                    "evidence_start": round(start, 3),
                    "evidence_end": round(end, 3),
                    "source_text": text,
                })
        if meeting_decision_candidate(text):
            decisions.append({
                "decision_id": f"decision-{len(decisions) + 1}",
                "text": text,
                "speaker": speaker,
                "evidence_segment_id": evidence_id,
                "evidence_start": round(start, 3),
                "evidence_end": round(end, 3),
            })
    priority_counts = {priority: 0 for priority in MEETING_TASK_PRIORITIES}
    for task in tasks:
        priority_counts[task["priority"]] += 1
    due_count = sum(1 for task in tasks if task["due_date"] or task["due_text"])
    summary = [
        f"タスク候補 {len(tasks)}件（期限の言及 {due_count}件、決定事項候補 {len(decisions)}件）。",
        "音声文字起こしからの自動抽出です。担当・優先度・期限を確認してから外部アプリへ取り込んでください。",
    ]
    if outline and isinstance(outline.get("sections"), list):
        summary.insert(1, f"AIアウトラインの議題 {len(outline['sections'])}件を議事録に反映しています。")
    return {
        "version": MEETING_MINUTES_VERSION,
        "generated_at": utc_now_iso(),
        "method": "rule_based_candidate_extraction",
        "summary": summary,
        "tasks": tasks,
        "decisions": decisions[:100],
        "analysis": {
            "task_count": len(tasks),
            "due_count": due_count,
            "decision_count": len(decisions),
            "priority_counts": priority_counts,
            "speaker_activity": sorted(
                speaker_activity.values(), key=lambda item: (-float(item["seconds"]), item["speaker"])
            ),
        },
    }


def meeting_safe_number(value: Any, default: float = 0.0) -> float:
    """Return a finite numeric value from persisted meeting data."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def normalize_meeting_minutes(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    raw_tasks = value.get("tasks") if isinstance(value.get("tasks"), list) else []
    tasks: list[dict[str, Any]] = []
    for index, raw_task in enumerate(raw_tasks[:500], 1):
        if not isinstance(raw_task, dict):
            continue
        priority = clean_single_line(raw_task.get("priority"), 20).lower()
        if priority not in MEETING_TASK_PRIORITIES:
            priority = "unspecified"
        due_date = clean_single_line(raw_task.get("due_date"), 20)
        if due_date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due_date):
            due_date = ""
        tasks.append({
            "task_id": clean_single_line(raw_task.get("task_id") or f"task-{index}", 80),
            "title": clean_single_line(raw_task.get("title"), 500) or "要確認のタスク候補",
            "owner": clean_single_line(raw_task.get("owner"), 120),
            "priority": priority,
            "due_date": due_date,
            "due_text": clean_single_line(raw_task.get("due_text"), 80),
            "status": clean_single_line(raw_task.get("status") or "open", 30),
            "confidence": clean_single_line(raw_task.get("confidence") or "candidate", 30),
            "evidence_segment_id": clean_single_line(raw_task.get("evidence_segment_id"), 160),
            "evidence_start": round(meeting_safe_number(raw_task.get("evidence_start")), 3),
            "evidence_end": round(meeting_safe_number(raw_task.get("evidence_end")), 3),
            "source_text": clean_single_line(raw_task.get("source_text"), 1200),
        })
    raw_decisions = value.get("decisions") if isinstance(value.get("decisions"), list) else []
    decisions: list[dict[str, Any]] = []
    for index, raw_decision in enumerate(raw_decisions[:100], 1):
        if not isinstance(raw_decision, dict):
            continue
        text = clean_single_line(raw_decision.get("text"), 1000)
        if not text:
            continue
        decisions.append({
            "decision_id": clean_single_line(raw_decision.get("decision_id") or f"decision-{index}", 80),
            "text": text,
            "speaker": clean_single_line(raw_decision.get("speaker"), 120),
            "evidence_segment_id": clean_single_line(raw_decision.get("evidence_segment_id"), 160),
            "evidence_start": round(meeting_safe_number(raw_decision.get("evidence_start")), 3),
            "evidence_end": round(meeting_safe_number(raw_decision.get("evidence_end")), 3),
        })
    raw_activity = value.get("analysis", {}).get("speaker_activity", []) if isinstance(value.get("analysis"), dict) else []
    activity = []
    for raw_item in raw_activity[:100] if isinstance(raw_activity, list) else []:
        if not isinstance(raw_item, dict):
            continue
        activity.append({
            "speaker": clean_single_line(raw_item.get("speaker"), 120),
            "turns": max(0, int(meeting_safe_number(raw_item.get("turns")))),
            "seconds": max(0.0, round(meeting_safe_number(raw_item.get("seconds")), 3)),
        })
    priority_counts = {priority: sum(1 for task in tasks if task["priority"] == priority) for priority in MEETING_TASK_PRIORITIES}
    return {
        "version": clean_single_line(value.get("version") or MEETING_MINUTES_VERSION, 20),
        "generated_at": clean_single_line(value.get("generated_at"), 60),
        "method": clean_single_line(value.get("method") or "rule_based_candidate_extraction", 80),
        "summary": [clean_single_line(item, 1000) for item in value.get("summary", [])[:20] if clean_single_line(item, 1000)],
        "tasks": tasks,
        "decisions": decisions,
        "analysis": {
            "task_count": len(tasks),
            "due_count": sum(1 for task in tasks if task["due_date"] or task["due_text"]),
            "decision_count": len(decisions),
            "priority_counts": priority_counts,
            "speaker_activity": activity,
        },
    }


def meeting_external_payload(source_name: str, minutes: dict[str, Any], item_id: str = "") -> dict[str, Any]:
    minutes = normalize_meeting_minutes(minutes)
    return {
        "schema": "gurumoji.meeting.v1",
        "meeting": {
            "id": item_id,
            "source_name": source_name,
            "generated_at": minutes.get("generated_at", ""),
            "method": minutes.get("method", ""),
        },
        "summary": minutes.get("summary", []),
        "tasks": minutes.get("tasks", []),
        "decisions": minutes.get("decisions", []),
        "analysis": minutes.get("analysis", {}),
    }


def meeting_tasks_csv_text(minutes: dict[str, Any]) -> str:
    stream = io.StringIO(newline="")
    fields = ("name", "description", "assignee", "due_date", "priority", "status", "source_time", "evidence_segment_id")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for task in normalize_meeting_minutes(minutes).get("tasks", []):
        writer.writerow({
            "name": task["title"],
            "description": task["source_text"],
            "assignee": task["owner"],
            "due_date": task["due_date"],
            "priority": task["priority"],
            "status": task["status"],
            "source_time": display_time(float(task["evidence_start"])),
            "evidence_segment_id": task["evidence_segment_id"],
        })
    return stream.getvalue()


def format_meeting_minutes_markdown(source_name: str, minutes: dict[str, Any]) -> str:
    minutes = normalize_meeting_minutes(minutes)
    escape_cell = lambda value: str(value or "").replace("|", "\\|").replace("\n", " ")
    lines = [
        "# 会議議事録",
        "",
        f"- 元ファイル: {source_name}",
        f"- 生成日時: {minutes.get('generated_at') or '未記録'}",
        "- 抽出方法: 音声文字起こしのルール抽出（候補は要確認）",
        "",
        "## 分析サマリー",
    ]
    lines.extend(f"- {item}" for item in minutes.get("summary", []))
    analysis = minutes.get("analysis", {})
    lines.extend([
        "",
        "## アクションアイテム",
        "| タスク | 担当候補 | 優先度 | 期限 | 根拠 |",
        "| --- | --- | --- | --- | --- |",
    ])
    tasks = minutes.get("tasks", [])
    if tasks:
        for task in tasks:
            due = task.get("due_date") or task.get("due_text") or "未設定"
            priority = MEETING_TASK_PRIORITY_LABELS.get(task.get("priority"), "未設定")
            evidence = display_time(float(task.get("evidence_start") or 0))
            lines.append("| " + " | ".join([
                escape_cell(task.get("title")), escape_cell(task.get("owner") or "未特定"),
                priority, escape_cell(due), evidence,
            ]) + " |")
    else:
        lines.append("| タスク候補は検出されませんでした | — | — | — | — |")
    lines.extend(["", "## 決定事項候補"])
    decisions = minutes.get("decisions", [])
    if decisions:
        for decision in decisions:
            lines.append(
                f"- [{display_time(float(decision.get('evidence_start') or 0))}] "
                f"{decision.get('speaker') or '話者不明'}: {decision.get('text')}"
            )
    else:
        lines.append("- 決定事項候補は検出されませんでした。")
    lines.extend(["", "## 発話量（分析用）"])
    for speaker in analysis.get("speaker_activity", []):
        lines.append(
            f"- {speaker.get('speaker') or '話者不明'}: {int(speaker.get('turns') or 0)}回 / "
            f"{display_time(float(speaker.get('seconds') or 0))}"
        )
    return "\n".join(lines).rstrip() + "\n"
