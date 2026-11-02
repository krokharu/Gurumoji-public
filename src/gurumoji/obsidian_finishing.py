"""File-backed Obsidian workbench. Commands are explicit checkbox transitions.

One transcript note per recording; Markdown and controls never enter AI prompts.
Generated versions are separate notes so editing a note cannot be overwritten by AI.
"""
from __future__ import annotations

from .ai_effort import normalize_efforts

import copy
import hashlib
import html
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import yaml

from .analysis_store import safe_path, write_atomic, markdown

COMMANDS = {"outline": "アウトラインを作成", "finish": "AI仕上げを実行",
            "apply": "結果をアプリへ反映"}
BLOCK = re.compile(
    r"<!-- gurumoji:segment ([0-9a-f]+) -->\n### [^\n]*\n"
    r"(?P<fence>~{3,})text\n(?P<text>.*?)\n(?P=fence)(?:\n|$)", re.S)
QUOTE_BLOCK = re.compile(
    r"(?P<quote>(?:^>[^\n]*\n)+)(?:^[ \t]*\n)+^\^s-(?P<id>[0-9a-f]+)[ \t]*(?:\n|$)", re.M)


def split_properties(note: str) -> tuple[dict, str]:
    """Accept Obsidian's YAML rewrites; keep all properties out of AI inputs."""
    if not note.startswith("---\n"):
        return {}, note
    match = re.match(r"\A---\n(.*?)\n---(?:\n|$)", note, re.S)
    if not match or len(match.group(1)) > 64000:
        raise ValueError("ノート先頭のプロパティが不正です。--- の区切りを確認してください。")
    try:
        properties = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise ValueError("Obsidianのプロパティを読み取れませんでした。") from exc
    if not isinstance(properties, dict):
        raise ValueError("ノートのプロパティは項目名と値で指定してください。")
    return properties, note[match.end():]


def with_properties(body: str, properties: dict) -> str:
    return "---\n" + yaml.safe_dump(properties, allow_unicode=True, sort_keys=False,
                                     default_flow_style=False).rstrip() + "\n---\n\n" + body


def unescape_text(value: str) -> str:
    return html.unescape(re.sub(r"\\([\\`*_{}\[\]()#+.!|^~$])", r"\1", value))


def quote_text(value: str) -> str:
    return "\n".join("> " + markdown(line) for line in value.split("\n"))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_text(path: Path, limit: int = 20_000_000) -> str:
    if path.stat().st_size > limit:
        raise ValueError("作業ノートが読み込み上限を超えています。")
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def transcript_note(title: str, segments: list[dict], names: dict | None = None) -> str:
    lines = [f"# {markdown(title)}", "",
             "> [!info] 会話を編集する",
             "> 各発話の引用本文を編集できます。時刻・話者の見出しと、引用末尾のブロックIDは保持してください。", ""]
    for segment in segments:
        text = str(segment.get("text") or "")
        speaker = str(segment.get("speaker") or "UNKNOWN")
        label = (names or {}).get(speaker, speaker)
        lines.extend([f"### {float(segment.get('start', 0)):.2f}–{float(segment.get('end', 0)):.2f}秒 {markdown(label)}",
                      "", quote_text(text), "", f"^s-{segment['id'].encode().hex()}", ""])
        review = segment.get("ai_review") or {}
        if review:
            lines.append("> [!warning]- ノイズ候補（本文を保持）" if review.get("noise_candidate")
                         else "> [!note]- AIの修正理由と校正前の本文")
            lines.extend(quote_text(r.get("reason", "")) for r in review.get("fragments", []))
            lines.extend([">", quote_text("校正前：" + review.get("original_text", "")), ""])
    return "\n".join(lines)


def parse_transcript(note: str, base: list[dict]) -> list[dict]:
    _, body = split_properties(note)
    legacy = list(BLOCK.finditer(body))
    native = [m for m in QUOTE_BLOCK.finditer(body)
              if not any(old.start() <= m.start() < old.end() for old in legacy)]
    if native and legacy:
        raise ValueError("引用形式と旧形式が混在しています。発話の区切りを確認してください。")
    matches = native or legacy
    ids = [m.group("id") if native else m.group(1) for m in matches]
    if ids != [s["id"].encode().hex() for s in base]:
        raise ValueError("会話ノートの発話ID・区切り・順序が変わっています。引用本文を編集し、ブロックIDを保持してください。")
    texts = [unescape_text("\n".join(re.sub(r"^> ?", "", line)
             for line in m.group("quote").removesuffix("\n").split("\n"))) if native else m.group("text")
             for m in matches]
    return [{**copy.deepcopy(s), "text": text} for s, text in zip(base, texts)]


def outline_note(outline: dict) -> str:
    lines = ["# 全体アウトライン", "", "<!-- 議題は ## 見出し、要点は - 箇条書きで編集できます。 -->", ""]
    for section in outline.get("sections", []):
        lines.append("## " + markdown(section["title"].replace("\n", " ")))
        lines.extend("- " + markdown(point.replace("\n", " ")) for point in section["bullets"])
        lines.append("")
    return "\n".join(lines)


def meeting_time(value) -> str:
    try:
        seconds = max(0, int(float(value or 0)))
    except (TypeError, ValueError, OverflowError):
        seconds = 0
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def meeting_source_link(transcript_path: str, segment_id: str, start) -> str:
    label = meeting_time(start)
    if not segment_id:
        return label
    block_id = str(segment_id).encode().hex()
    return f"[[{transcript_path.removesuffix('.md')}#^s-{block_id}|{label}]]"


def meeting_minutes_note(title: str, minutes: dict, transcript_path: str,
                         tasks_path: str, json_path: str) -> str:
    """Render a meeting note that stays useful inside Obsidian without plugins."""
    tasks = minutes.get("tasks") if isinstance(minutes.get("tasks"), list) else []
    decisions = minutes.get("decisions") if isinstance(minutes.get("decisions"), list) else []
    analysis = minutes.get("analysis") if isinstance(minutes.get("analysis"), dict) else {}
    priority_labels = {"high": "高", "medium": "中", "low": "低", "unspecified": "未設定"}
    lines = [
        f"# {markdown(Path(title).stem)} 会議議事録",
        "",
        "> [!warning] 自動抽出された候補",
        "> 担当・優先度・期限・決定事項は、元発話を確認してから利用してください。",
        "",
        "## サマリー",
        "",
    ]
    summary = minutes.get("summary") if isinstance(minutes.get("summary"), list) else []
    lines.extend("- " + markdown(value) for value in summary if str(value or "").strip())
    if not summary:
        lines.append("- サマリーはありません。")
    priority_counts = analysis.get("priority_counts") if isinstance(analysis.get("priority_counts"), dict) else {}
    lines.extend([
        "",
        "## 集計",
        "",
        "| 項目 | 件数 |",
        "| --- | ---: |",
        f"| タスク候補 | {len(tasks)} |",
        f"| 期限の言及 | {int(analysis.get('due_count') or 0)} |",
        f"| 決定事項候補 | {len(decisions)} |",
        f"| 優先度 高 / 中 / 低 / 未設定 | {int(priority_counts.get('high') or 0)} / {int(priority_counts.get('medium') or 0)} / {int(priority_counts.get('low') or 0)} / {int(priority_counts.get('unspecified') or 0)} |",
        "",
        "## アクションアイテム",
        "",
    ])
    if tasks:
        for task in tasks:
            title_text = markdown(task.get("title") or "要確認のタスク候補")
            priority = priority_labels.get(str(task.get("priority") or ""), "未設定")
            due = markdown(task.get("due_date") or task.get("due_text") or "未設定")
            owner = markdown(task.get("owner") or "未特定")
            evidence = meeting_source_link(
                transcript_path, str(task.get("evidence_segment_id") or ""), task.get("evidence_start")
            )
            lines.extend([
                f"- [ ] {title_text}",
                f"  - 担当候補: {owner}",
                f"  - 優先度: **{priority}**",
                f"  - 期限: {due}",
                f"  - 根拠: {evidence}",
            ])
            if task.get("source_text"):
                lines.append("  - 元発話: " + markdown(task["source_text"]))
    else:
        lines.append("タスク候補は検出されませんでした。")
    lines.extend(["", "## 決定事項候補", ""])
    if decisions:
        for decision in decisions:
            evidence = meeting_source_link(
                transcript_path, str(decision.get("evidence_segment_id") or ""), decision.get("evidence_start")
            )
            lines.append(f"- {markdown(decision.get('text'))}（{evidence}）")
    else:
        lines.append("決定事項候補は検出されませんでした。")
    lines.extend(["", "## 発話量", ""])
    activity = analysis.get("speaker_activity") if isinstance(analysis.get("speaker_activity"), list) else []
    if activity:
        for item in activity:
            lines.append(
                f"- {markdown(item.get('speaker') or '話者不明')}: "
                f"{int(item.get('turns') or 0)}回 / {meeting_time(item.get('seconds'))}"
            )
    else:
        lines.append("発話量データはありません。")
    lines.extend([
        "",
        "## 連携ファイル",
        "",
        f"- [[{tasks_path}|タスクCSVを開く]]",
        f"- [[{json_path}|連携JSONを開く]]",
        f"- [[{transcript_path.removesuffix('.md')}|会話全文を開く]]",
        "",
    ])
    return "\n".join(lines)


def parse_outline(note: str) -> dict:
    _, note = split_properties(note)
    sections = []
    for line in re.sub(r"<!--.*?-->", "", note, flags=re.S).splitlines():
        line = line.strip()
        if not line or line.startswith("# "):
            continue
        if line.startswith("## "):
            title = unescape_text(line[3:].strip())
            if not title or len(title) > 120:
                raise ValueError("アウトラインの議題名は1～120文字にしてください。")
            sections.append({"title": title, "bullets": []})
        else:
            if not sections:
                sections.append({"title": "会話全体", "bullets": []})
            text = unescape_text(re.sub(r"^[-*] ", "", line))
            sections[-1]["bullets"].extend(text[i:i + 500] for i in range(0, len(text), 500))
    return {"title": "全体アウトライン", "sections": [s for s in sections if s["bullets"]]}


def content_fingerprint(note: str, kind: str, ids: list[str] | None = None) -> str:
    if kind == "transcript":
        content = parse_transcript(note, [{"id": value} for value in ids or []])
    else:
        content = parse_outline(note)
    return sha(json.dumps(content, ensure_ascii=False, sort_keys=True).encode())


class ObsidianWorkbench:
    def __init__(self, database_file: Path):
        self.database_file = Path(database_file)
        from .obsidian_layout import ObsidianLayout
        self.layout = ObsidianLayout(database_file)
        self.root = Path(database_file).parent / "obsidian_workbench"
        self.vault = Path(database_file).parent / "obsidian" / "ResearchVault"

    def key(self, item_id: str) -> str:
        return sha(item_id.encode())[:32]

    def state_path(self, item_id: str) -> Path:
        return safe_path(self.root, self.key(item_id) + "/state.json")

    def load(self, item_id: str) -> dict | None:
        path = self.state_path(item_id)
        return json.loads(read_text(path)) if path.exists() else None

    def note_path(self, relative: str) -> Path:
        return safe_path(self.vault, relative)

    def save(self, state: dict) -> None:
        write_atomic(self.state_path(state["item_id"]), json.dumps(state, ensure_ascii=False).encode())

    def note(self, relative: str, body: str) -> None:
        write_atomic(self.note_path(relative), body.encode())

    def save_note(self, state: dict, relative: str, body: str, kind: str, **extra) -> None:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        previous = {}
        if self.note_path(relative).exists():
            previous, _ = split_properties(read_text(self.note_path(relative)))
        note_id = state.setdefault("note_ids", {}).setdefault(relative, "finishing-" + sha(relative.encode())[:32])
        properties = {"note_id": note_id, "note_type": "finishing-" + kind,
                      "title": state["title"], "conversation_id": state["item_id"],
                      "schema_version": 2, "revision": state.get("revision", 0),
                      "created": previous.get("created", now), "updated": now,
                      "managed_by": "researcher" if kind in {"transcript", "outline", "control", "result"} else "gurumoji",
                      "tags": ["gurumoji/finishing", "gurumoji/" + kind],
                      "aliases": [state["title"] + "・" + Path(relative).stem]}
        if state.get("control") and relative != state["control"]:
            properties["conversation"] = "[[" + state["control"][:-3] + "]]"
        if state.get("original_note") and relative != state["original_note"]:
            properties["source"] = "[[" + state["original_note"][:-3] + "]]"
        properties.update(extra)
        scope = "detail" if kind in {"transcript", "result", "outline", "meeting"} else "support"
        content = self.layout.decorate(with_properties(body, properties), state["item_id"],
                                       "transcript" if kind == "result" else kind, scope)
        # Researcher-owned notes are immutable from our side after creation.
        # The generated status note is the mutable status channel; it follows the
        # shared Vault note policy (history of edits, recreated when deleted).
        if kind == "status":
            self.layout.managed_note(relative, content, navigation=True)
        else:
            write_atomic(self.note_path(relative), content.encode(), create_only=True)

    def locate_note(self, relative: str, note_id: str | None = None) -> str:
        if self.note_path(relative).exists():
            return relative
        if not note_id:
            raise ValueError("作業ノートが見つかりません。旧形式のノートは元の場所に戻してください。")
        from .obsidian_layout import find_notes
        # Hidden folders are excluded: a note in Obsidian's .trash is deleted, not moved.
        matches = find_notes(self.vault, {note_id}).get(note_id, [])
        if not matches:
            raise ValueError("作業ノートが見つかりません。削除した場合は、Obsidianのゴミ箱などから保管庫内に戻してください。")
        if len(matches) != 1:
            raise ValueError("作業ノートの移動先を一意に確認できません。note_idの変更・重複を確認してください。")
        return matches[0]

    def refresh_paths(self, state: dict) -> None:
        changed = False
        for key in ("work", "outline", "control", "original_note", "result_note", "final_outline_note",
                    "meeting_minutes_note", "status_note"):
            relative = state.get(key)
            if relative is None:
                continue
            note_id = state.get("note_ids", {}).get(relative)
            found = self.locate_note(relative, note_id)
            if found != relative:
                state[key] = found
                state.setdefault("note_ids", {})[found] = note_id
                changed = True
        if changed:
            self.save(state)
            self.publish_index()

    def ensure_home(self) -> None:
        self.layout.publish_navigation()

    def prepare(self, item_id: str, title: str, segments: list[dict], *, revision: int,
                provider: str = "none", model: str = "", detect_names: bool = True,
                create_outline: bool = True, jev_compare: bool = False,
                ready: bool = True, source_kind: str = "whisper", ai_efforts: dict | None = None,
                speaker_names: dict[str, str] | None = None) -> dict:
        update_efforts = ai_efforts is not None
        ai_efforts = normalize_efforts(ai_efforts)
        existing = self.load(item_id)
        if existing and (existing["revision"] == revision or existing["status"] == "running"):
            if existing["status"] != "running":
                if update_efforts:
                    existing["ai_efforts"] = ai_efforts
                    self.save(existing)
                self.refresh_paths(existing)
            return existing
        version = uuid.uuid4().hex
        record = self.layout.register(item_id, title)
        folder = record["folder"] + (f"/履歴/仕上げ/{version[:8]}" if existing else "")
        prefix = record["code"] + "-"
        if existing:
            write_atomic(safe_path(self.root, self.key(item_id) + f"/state-{version}.json"),
                         json.dumps(existing, ensure_ascii=False).encode())
        original_note = (existing or {}).get("original_note") or folder + "/" + prefix + "保存原文.md"
        state = {"version": 2, "item_id": item_id, "title": title, "revision": revision,
                 "ready": ready, "folder": folder, "work": folder + "/" + prefix + "全文.md",
                 "outline": folder + "/" + prefix + "アウトライン.md", "control": folder + "/" + prefix + "操作.md",
                 "status_note": folder + "/" + prefix + "状態.md", "note_ids": dict((existing or {}).get("note_ids", {})),
                 "segments": copy.deepcopy(segments), "model": model, "provider": provider,
                 "detect_names": detect_names, "create_outline": create_outline,
                 "jev_compare": jev_compare, "ai_efforts": ai_efforts,
                 "original_note": original_note,
                  "observed": [], "status": "ready", "message": "会話本文を確認・編集し、操作を1つ選んでください。"}
        initial_paths = [state[key] for key in ("work", "outline", "control", "status_note")]
        if not existing:
            initial_paths.append(original_note)
        if any(self.note_path(relative).exists() for relative in initial_paths):
            raise ValueError("仕上げ用の保存先に既存ノートがあります。上書きせず停止しました。管理状態の復元を確認してください。")
        for key in ("meeting_minutes_note", "meeting_minutes_fingerprint", "meeting_tasks_path",
                    "meeting_json_path"):
            if existing and existing.get(key):
                state[key] = existing[key]
        # Publish state last: a partial export cannot trigger commands.
        write_atomic(safe_path(self.root, self.key(item_id) + f"/source-{version}.json"),
                     json.dumps(segments, ensure_ascii=False).encode())
        if not existing:
            label = "Whisper原文" if source_kind == "whisper" else "アプリ保存版"
            self.save_note(state, original_note, transcript_note(
                title + "：" + label, segments, speaker_names
            ), "source")
        self.save_note(state, state["work"], transcript_note(title, segments, speaker_names), "transcript")
        self.save_note(state, state["outline"], outline_note({"sections": []}), "outline")
        controls = ["# AI仕上げの操作", "",
                    "Gurumojiを起動したまま、下の操作を1つだけチェックして保存してください。",
                    "再実行は一度チェックを外して保存し、状態ノートに「次の操作を選べます」と出てから再チェックします。",
                    "先頭のプロパティ provider は openai / google / lmstudio。APIキーとモデルはアプリの設定を使います。",
                    f"本文・議題の編集先と結果は [[{state['status_note'][:-3]}]] から開けます。", ""]
        controls.extend(f"- [ ] {label} <!-- gurumoji-command:{key} -->" for key, label in COMMANDS.items())
        controls.extend(["", "## AI仕上げに含める処理", ""])
        for key, label in (("detect_names", "自己紹介から話者名も特定する"),
                           ("create_outline", "仕上げ後のアウトラインも出力する"),
                           ("jev_compare", "Jevでも修正要否を判定し、現行AIと比較する")):
            controls.append(f"- [{'x' if state[key] else ' '}] {label} <!-- gurumoji-option:{key} -->")
        controls.extend(["", "会話の自動削除は行いません。結果を確認してから「結果をアプリへ反映」を選べます。", ""])
        self.save_note(state, state["control"], "\n".join(controls), "control", provider=provider)
        self.publish_status(state)
        self.save(state)
        self.publish_index()
        self.ensure_home()
        return state

    def activate(self, item_id: str, revision: int, segments: list[dict] | None = None) -> None:
        state = self.load(item_id)
        if state:
            state.update(ready=True, revision=revision)
            if segments is not None:
                state["segments"] = copy.deepcopy(segments)
            self.save(state)

    def publish_index(self) -> None:
        for path in sorted(self.root.glob("*/state.json")):
            self.layout.sync_finishing(json.loads(read_text(path)))
        self.layout.publish_navigation()

    def public(self, state: dict) -> dict:
        return {"status": state["status"], "message": state["message"],
                "path": str(self.note_path(state["control"])),
                "uri": "obsidian://open?path=" + quote(str(self.note_path(state["control"]).resolve()), safe="")}

    def meeting_public(self, state: dict | None, fingerprint: str = "") -> dict:
        relative = state.get("meeting_minutes_note", "") if state else ""
        if not relative or not self.note_path(relative).is_file():
            return {"status": "unprepared", "message": "会議議事録はObsidianに未保存です。"}
        current = str(state.get("meeting_minutes_fingerprint") or "")
        stale = bool(fingerprint and current != fingerprint)
        return {
            "status": "stale" if stale else "completed",
            "message": "会議内容が更新されています。最新版を保存してください。" if stale else "会議議事録をObsidianに保存済みです。",
            "path": str(self.note_path(relative)),
            "uri": "obsidian://open?path=" + quote(str(self.note_path(relative).resolve()), safe=""),
            "tasks_path": str(self.note_path(state.get("meeting_tasks_path", ""))) if state.get("meeting_tasks_path") else "",
            "json_path": str(self.note_path(state.get("meeting_json_path", ""))) if state.get("meeting_json_path") else "",
        }

    def publish_meeting_minutes(self, state: dict, minutes: dict, *, task_csv: str,
                                external_json: str) -> dict:
        if not isinstance(minutes, dict) or not minutes:
            raise ValueError("会議議事録のデータがありません。")
        self.refresh_paths(state)
        fingerprint = sha(json.dumps(minutes, ensure_ascii=False, sort_keys=True).encode())
        current = self.meeting_public(state, fingerprint)
        if current["status"] == "completed":
            return current
        record = self.layout.register(state["item_id"], state["title"])
        revision = max(0, int(state.get("revision") or 0))
        suffix = f"r{revision}-{fingerprint[:8]}"
        target = f"{record['folder']}/{record['code']}-会議議事録-{suffix}.md"
        attachments = f"{record['folder']}/添付"
        tasks_path = f"{attachments}/{record['code']}-タスク-{suffix}.csv"
        json_path = f"{attachments}/{record['code']}-連携-{suffix}.json"
        task_target = self.note_path(tasks_path)
        json_target = self.note_path(json_path)
        if not task_target.exists():
            write_atomic(task_target, ("\ufeff" + task_csv).encode("utf-8"))
        if not json_target.exists():
            write_atomic(json_target, external_json.encode("utf-8"))
        if not self.note_path(target).exists():
            body = meeting_minutes_note(state["title"], minutes, state["work"], tasks_path, json_path)
            analysis = minutes.get("analysis") if isinstance(minutes.get("analysis"), dict) else {}
            self.save_note(
                state, target, body, "meeting", session_type="meeting",
                task_count=int(analysis.get("task_count") or 0),
                due_count=int(analysis.get("due_count") or 0),
                decision_count=int(analysis.get("decision_count") or 0),
            )
        state.update(
            meeting_minutes_note=target,
            meeting_minutes_fingerprint=fingerprint,
            meeting_tasks_path=tasks_path,
            meeting_json_path=json_path,
        )
        self.save(state)
        self.publish_status(state)
        self.layout.update(state["item_id"], state["title"], {"meeting_minutes": target})
        return self.meeting_public(state, fingerprint)

    def publish_status(self, state: dict) -> None:
        body = ["# 仕上げの状態", "", "> [!info] 進捗", quote_text(state["message"]), "",
                f"- 操作：[[{state['control'][:-3]}]]",
                f"- 編集する会話：[[{state['work'][:-3]}]]",
                f"- 編集する全体アウトライン：[[{state['outline'][:-3]}]]",
                f"- 保存原文：[[{state['original_note'][:-3]}]]"]
        if state.get("result_note"):
            body.append(f"- 仕上げ結果：[[{state['result_note'][:-3]}]]")
        if state.get("final_outline_note"):
            body.append(f"- 仕上げ後のアウトライン：[[{state['final_outline_note'][:-3]}]]")
        if state.get("meeting_minutes_note"):
            body.append(f"- 会議議事録・タスク：[[{state['meeting_minutes_note'][:-3]}]]")
        if state.get("archive_warning"):
            body.extend(["", markdown(state["archive_warning"])])
        usage = state.get("pending_usage") or state.get("last_usage") or {}
        if usage:
            body.extend(["", f"今回の反映までのAI使用量：{int(usage.get('request_count', 0))}回 / "
                         f"入力 {int(usage.get('input_tokens', 0))} / 出力 {int(usage.get('output_tokens', 0))} トークン",
                         "使用量はAPIが返した値です。未報告の呼び出しはトークン数に含まれません。"])
        body.extend(["", "状態ノートは自動更新されます。考察やメモは別ノートに記載してください。", ""])
        relative = state.get("status_note", state["folder"] + "/状態.md")
        self.save_note(state, relative, "\n".join(body), "status", status=state["status"])

    def selection(self, state: dict) -> tuple[list[str], str]:
        control = read_text(self.note_path(state["control"]), 64000)
        properties, control = split_properties(control)
        selected = re.findall(r"^- \[[xX]\] [^\n]*<!-- gurumoji-command:(outline|finish|apply) -->\s*$",
                              control, re.M)
        legacy_provider = re.search(r"^provider: *(\w+) *$", control, re.M)
        provider = properties.get("provider", legacy_provider.group(1) if legacy_provider else "none")
        if not isinstance(provider, str):
            raise ValueError("providerプロパティは openai / google / lmstudio の文字列で指定してください。")
        return selected, provider

    def recover(self) -> None:
        for path in self.root.glob("*/state.json"):
            state = json.loads(read_text(path))
            if state["status"] == "running":
                state.update(status="interrupted", message="処理が中断されました。結果を確認し、チェックを外してから再実行してください。")
                self.save(state)
                self.publish_status(state)

    def poll_once(self, engine, stopping=lambda: False) -> None:
        for path in self.root.glob("*/state.json"):
            if stopping():
                return
            state = None
            latched = False
            try:
                state = json.loads(read_text(path))
                if not state.get("ready") or state["status"] == "running":
                    continue
                self.refresh_paths(state)
                selected, provider = self.selection(state)
                # A note problem reported before latching clears once the notes are readable again.
                recovered = state.pop("poll_error", False)
                if recovered:
                    state.update(status="ready", message="次の操作を選べます。編集先と前回結果は下のリンクから開けます。")
                if selected == state["observed"]:
                    if not recovered:
                        continue
                else:
                    state["observed"] = selected
                    latched = True
                    # Latch before doing any AI work. Unchanged notes never repeat API calls.
                    self.save(state)
                    if not selected:
                        state.update(status="ready", message="次の操作を選べます。編集先と前回結果は下のリンクから開けます。")
                    elif len(selected) != 1:
                        raise ValueError("操作は1つだけチェックしてください。")
                    else:
                        self.execute(state, selected[0], provider, engine, stopping)
            except Exception as exc:
                if state is None:
                    continue
                if not latched:
                    # The same unresolved problem (e.g. a deleted note) is published once, not every poll.
                    if state.get("poll_error") and state.get("message") == str(exc):
                        continue
                    state["poll_error"] = True
                state.update(status="error", message=str(exc))
            if state is not None:
                self.publish_status(state)
                self.save(state)
                self.layout.sync_finishing(state)

    def execute(self, state: dict, action: str, provider: str, engine, stopping) -> None:
        def check():
            if stopping() or self.selection(state) != ([action], provider):
                raise InterruptedError("操作が中止されました。チェックを外してから再実行できます。")

        check()
        if action in {"outline", "finish"}:
            state.pop("candidate", None)
            _, control = split_properties(read_text(self.note_path(state["control"]), 64000))
            for key in ("detect_names", "create_outline", "jev_compare"):
                state[key] = bool(re.search(r"^- \[[xX]\] [^\n]*<!-- gurumoji-option:" + key + r" -->\s*$", control, re.M))
            if action == "finish":
                state.pop("final_outline_note", None)
        state.update(status="running", message=COMMANDS[action] + "：処理中です。チェックを外すと中止します。")
        self.save(state)
        self.publish_status(state)
        if action == "apply":
            if not state.get("candidate"):
                raise ValueError("先にAI仕上げを実行してください。")
            candidate = json.loads(read_text(safe_path(self.root, state["candidate"])))
            self.check_sources(candidate["sources"])
            result_body = read_text(self.note_path(state["result_note"]))
            revised = parse_transcript(result_body, candidate["segments"])
            result_ids = [s["id"] for s in revised]
            result_fingerprint = content_fingerprint(result_body, "transcript", result_ids)
            def check_apply():
                check()
                self.check_sources(candidate["sources"])
                if content_fingerprint(read_text(self.note_path(state["result_note"])),
                                       "transcript", result_ids) != result_fingerprint:
                    raise ValueError("反映中に仕上げ結果ノートが編集されました。チェックを外してから再反映してください。")
            result = engine(action, state, revised, candidate, provider, check_apply)
            state.update(revision=result["revision"], segments=revised, work=state["result_note"],
                         status="completed", message="仕上げ結果をアプリと出力ファイルへ反映しました。")
            if candidate.get("outline") and state.get("final_outline_note"):
                state["outline"] = state["final_outline_note"]
            state.pop("candidate", None)
            return

        if provider not in {"openai", "google", "lmstudio"}:
            raise ValueError("操作ノートの provider を openai / google / lmstudio に設定してください。")
        source_body = read_text(self.note_path(state["work"]))
        outline_body = read_text(self.note_path(state["outline"]), 1_000_000)
        segments = parse_transcript(source_body, state["segments"])
        outline = parse_outline(outline_body)
        sources = {}
        for relative, body, kind in ((state["work"], source_body, "transcript"),
                                     (state["outline"], outline_body, "outline")):
            ids = [s["id"] for s in segments] if kind == "transcript" else None
            sources[relative] = {"kind": kind, "ids": ids,
                                 "note_id": split_properties(body)[0].get("note_id"),
                                 "sha256": content_fingerprint(body, kind, ids)}
        run_id = uuid.uuid4().hex
        record = self.layout.register(state["item_id"], state["title"])
        result_folder = record["folder"] + "/履歴/仕上げ"
        prefix = record["code"]
        result = engine(action, state, segments, outline, provider, check)
        check()
        # All generated output has a fresh path. Never replace a human-edited note.
        if action == "outline":
            target = f"{result_folder}/{prefix}-アウトライン-{run_id[:8]}.md"
            self.save_note(state, target, outline_note(result["outline"]), "outline")
            self.check_sources(sources)
            state.update(outline=target, status="completed", message="全体アウトラインを作成しました。下のリンクから編集し、AI仕上げへ進めます。")
        else:
            candidate_path = f"{self.key(state['item_id'])}/result-{run_id}.json"
            result.update(sources=sources, before=segments, run_id=run_id, revision=state["revision"])
            write_atomic(safe_path(self.root, candidate_path), json.dumps(result, ensure_ascii=False).encode())
            target = f"{result_folder}/{prefix}-仕上げ結果-{run_id[:8]}.md"
            self.save_note(state, target, transcript_note(state["title"] + "：仕上げ結果", result["segments"], result.get("names")), "result")
            state["result_note"] = target
            if result.get("outline"):
                final_outline = f"{result_folder}/{prefix}-仕上げ後アウトライン-{run_id[:8]}.md"
                self.save_note(state, final_outline, outline_note(result["outline"]), "outline")
                state["final_outline_note"] = final_outline
            self.check_sources(sources)
            state.update(candidate=candidate_path, status="completed", message="AI仕上げが完了しました。結果ノートを確認・編集してから、アプリへ反映できます。")

    def check_sources(self, sources: dict) -> None:
        for relative, expected in sources.items():
            if isinstance(expected, dict):
                located = self.locate_note(relative, expected.get("note_id"))
                actual = content_fingerprint(read_text(self.note_path(located)),
                                             expected["kind"], expected.get("ids"))
                expected_hash = expected["sha256"]
            else:  # Previously generated candidates retain their original checks.
                actual = sha(read_text(self.note_path(relative)).encode())
                expected_hash = expected
            if actual != expected_hash:
                raise ValueError("処理中または処理後に元の会話・アウトラインが編集されました。編集内容を保持し、反映を停止しました。AI仕上げを再実行してください。")
