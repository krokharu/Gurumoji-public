"""Shared interview paths and native Obsidian navigation, without AI calls."""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import analysis_store
from .analysis_store import safe_path, write_atomic, markdown
from .text_utils import utc_now_iso
from .analysis_method_registry import METHOD_GROUPS, method_status_label

LAYOUT_LOCK = threading.RLock()
DELETED_STATUS = "アプリから削除済み"
LOGGER = logging.getLogger(__name__)
HOME = "00-ホーム.md"
ANALYSIS_INDEX = "01-分析結果.md"
GUIDE = "90-運用/使い方.md"
SYNC_STATUS = "90-運用/同期状況.md"
INDEX = "10-インタビュー/インタビュー一覧.md"
# The overview stays as a record after the conversation is deleted in the app (OBS-11).
DELETED_STATUS = "アプリから削除済み"
GLOBAL_QUERY = "tag:#graph/overview -tag:#graph/history -tag:#graph/support"
WIKILINK = re.compile(r"(?<![!\\])\[\[([^\]#|]+)(?:[^\]]*)\]\]")
# Process-wide, so the 10-second watcher reports a persistent condition once.
_WARNED: set[tuple[str, str]] = set()
_SCANNED: dict[tuple[str, str], float] = {}
# Theme sync runs every 10 seconds; unchanged notes are not read again (OBS-08).
_NOTE_LINKS: dict[str, tuple[int, int, object, list[str]]] = {}


def note_links(path: Path) -> tuple[object, list[str]]:
    """The note's graph_kind and, for research memos, its raw wikilink targets.

    Cached by modification time and size, so an idle Vault is only stat()ed.
    """
    stat = path.stat()
    key = str(path)
    cached = _NOTE_LINKS.get(key)
    if cached and cached[:2] == (stat.st_mtime_ns, stat.st_size):
        return cached[2], cached[3]
    props, body = unpack(path.read_text(encoding="utf-8-sig"))
    kind = props.get("graph_kind")
    links: list[str] = []
    if kind == "memo":
        body = re.sub(r"(?ms)^\s*(`{3,}|~{3,}).*?^\s*\1\s*$", "", body)
        body = re.sub(r"`[^`\n]*`", "", body)
        links = WIKILINK.findall(body)
    _NOTE_LINKS[key] = (stat.st_mtime_ns, stat.st_size, kind, links)
    return kind, links


def warn_once(key: tuple[str, str], message: str) -> None:
    if key not in _WARNED:
        _WARNED.add(key)
        LOGGER.warning(message)


def visible_notes(vault: Path) -> list[str]:
    """Vault-relative Markdown paths, excluding hidden folders such as .obsidian and .trash."""
    notes = []
    for path in vault.rglob("*.md"):
        relative = path.relative_to(vault).as_posix()
        if not any(part.startswith(".") for part in relative.split("/")):
            notes.append(relative)
    return notes


def find_notes(vault: Path, note_ids: set[str]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for relative in visible_notes(vault):
        try:
            with safe_path(vault, relative).open(encoding="utf-8-sig") as handle:
                props, _ = unpack(handle.read(65000))
        except (OSError, ValueError, yaml.YAMLError):
            continue
        note_id = props.get("note_id")
        if isinstance(note_id, str) and note_id in note_ids:
            found.setdefault(note_id, []).append(relative)
    return found


def unpack(text: str) -> tuple[dict, str]:
    text = text.removeprefix("\ufeff").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}, text
    match = re.match(r"\A---\n(.*?)\n---(?:\n|$)", text, re.S)
    if not match:
        raise ValueError("ノートのプロパティ区切りが不正です。")
    props = yaml.safe_load(match[1]) or {}
    if not isinstance(props, dict):
        raise ValueError("ノートのプロパティが不正です。")
    return props, text[match.end():]


def pack(props: dict, body: str) -> str:
    return "---\n" + yaml.safe_dump(props, allow_unicode=True, sort_keys=False).rstrip() + "\n---\n\n" + body.lstrip("\n")


def link(path: str, label: str = "") -> str:
    return "[[" + path.removesuffix(".md") + ("|" + markdown(label) if label else "") + "]]"


def interview_query(record: dict) -> str:
    return f"tag:#interview/{record['code'].lower()} (tag:#graph/overview OR tag:#graph/detail) -tag:#graph/history -tag:#graph/support"


def display_title(title: str) -> str:
    match = re.match(r"GMT(\d{4})(\d{2})(\d{2})-\d{6}_Recording", title)
    return f"{match[1]}-{match[2]}-{match[3]} の録音" if match else Path(title).stem


def method_group_path(group_id: str) -> str:
    return f"40-研究/分析手法/{group_id}.md"


def method_table(methods: list[dict]) -> str:
    text = "| 分析手法・結果 | 状態 | 保存日時（UTC） |\n| --- | --- | --- |\n"
    for method in methods:
        date = str(method.get("created_at", ""))[:19].replace("T", " ")
        # Inside a table, Obsidian requires the alias separator to be escaped.
        text += "| [[" + method["path"].removesuffix(".md") + "\\|" + markdown(method["title"]) + "]] | " + markdown(method_status_label(method)) + " | " + markdown(date) + " |\n"
    return text


def graph_options(query: str = GLOBAL_QUERY) -> dict:
    return {"search": query, "showTags": False, "showAttachments": False,
            "hideUnresolved": True, "showOrphans": True, "showArrow": False,
            "colorGroups": [{"query": f"[graph_kind:{kind}]", "color": {"a": 1, "rgb": color}}
                            for kind, color in (("interview", 0x4985D6), ("theme", 0x45A777),
                                                ("analysis", 0xDF9842), ("analysis_type", 0xC97B17),
                                                ("analysis_result", 0xE9B44C), ("memo", 0xA273CD),
                                                ("transcript", 0x8C97A3), ("outline", 0x51A9BA),
                                                ("meeting", 0xE26D5A))],
            "textFadeMultiplier": 0, "nodeSizeMultiplier": 1.1, "lineSizeMultiplier": 0.8,
            "centerStrength": 0.3, "repelStrength": 10, "linkStrength": 1,
            "linkDistance": 180, "scale": 0.65, "close": True,
            "collapse-filter": True, "collapse-color-groups": True,
            "collapse-display": True, "collapse-forces": True}


class ObsidianLayout:
    def __init__(self, database_file: Path):
        self.data = Path(database_file).parent
        self.vault = self.data / "obsidian" / "ResearchVault"
        self.registry = self.data / "obsidian_layout" / "interviews.json"
        self.note_log = self.data / "obsidian_layout" / "note_changes.jsonl"

    def load(self) -> dict:
        if self.registry.exists():
            return json.loads(self.registry.read_text(encoding="utf-8"))
        return {"version": 1, "interviews": {}, "managed": {}}

    def save(self, data: dict) -> None:
        write_atomic(self.registry, json.dumps(data, ensure_ascii=False, indent=2).encode())

    def relocate(self, data: dict, item_id: str) -> bool:
        """Follow an interview folder renamed or moved in Obsidian instead of recreating it."""
        record = data["interviews"].get(item_id)
        if (not record or record["hub"] not in data["managed"]
                or safe_path(self.vault, record["folder"]).exists()):
            return False
        key = (str(self.vault), item_id)
        # A deleted folder stays missing; do not rescan the whole Vault on every call.
        if time.monotonic() - _SCANNED.get(key, float("-inf")) < 60:
            return False
        _SCANNED[key] = time.monotonic()
        found = find_notes(self.vault, {"interview-" + item_id}).get("interview-" + item_id, [])
        if len(found) != 1 or "/" not in found[0]:
            warn_once(("missing-folder", record["folder"]),
                      "インタビューのフォルダーが見つからないため、概要ノートを元の場所に作成します。")
            return False
        old, hub = record["folder"], found[0]
        folder = hub.rsplit("/", 1)[0]
        def move(path: str) -> str:
            return folder + path[len(old):] if path == old or path.startswith(old + "/") else path
        managed = {move(path): value for path, value in data["managed"].items()}
        if move(record["hub"]) != hub and move(record["hub"]) in managed:
            managed[hub] = managed.pop(move(record["hub"]))
        data["managed"] = managed
        record.update(folder=folder, hub=hub, links={k: move(v) for k, v in record["links"].items()})
        for method in record.get("analysis_methods", []):
            method["path"] = move(method["path"])
        # AnalysisStore applies the same prefix change to its SQLite catalog.
        record["moved_from"] = list(dict.fromkeys(record.get("moved_from", []) + [old]))
        _SCANNED.pop(key, None)
        LOGGER.info("移動されたインタビューのフォルダーに追従しました。")
        return True

    def follow(self, item_id: str) -> None:
        with LAYOUT_LOCK:
            data = self.load()
            if self.relocate(data, item_id):
                self.save(data)

    def register(self, item_id: str, title: str) -> dict:
        with LAYOUT_LOCK:
            data = self.load()
            if self.relocate(data, item_id):
                self.save(data)
            if item_id not in data["interviews"]:
                code = f"I{len(data['interviews']) + 1:03d}"
                # Leave room below the folder for history and graph notes (OBS-14).
                room = analysis_store.PATH_LIMIT - len(str(self.vault)) - len(f"/10-インタビュー/{code}-") - 130
                name = re.sub(r'[\\/:*?"<>|#^\[\]%\x00-\x1f]', '_', Path(title).stem).strip(' ._')
                name = analysis_store.fit_name(name, min(48, max(12, room))).strip(' ._') or "インタビュー"
                folder = f"10-インタビュー/{code}-{name}"
                data["interviews"][item_id] = {"item_id": item_id, "code": code, "title": title,
                    "folder": folder, "hub": f"{folder}/{code}-概要.md", "links": {}, "status": "保存済み"}
                self.save(data)
            return copy.deepcopy(data["interviews"][item_id])

    def note_path(self, item_id: str, title: str, name: str) -> str:
        record = self.register(item_id, title)
        return f"{record['folder']}/{record['code']}-{name}.md"

    def analysis_dir(self, item_id: str, title: str, run_id: str) -> str:
        return self.register(item_id, title)["folder"] + f"/履歴/分析/{run_id}"

    def source_dir(self, item_id: str, title: str, snapshot: str) -> str:
        return self.register(item_id, title)["folder"] + f"/履歴/引用/{snapshot}"

    def decorate(self, text: str, item_id: str, kind: str, scope: str) -> str:
        props, body = unpack(text)
        record = self.register(item_id, str(props.get("title") or item_id))
        tags = props.get("tags") or []
        if isinstance(tags, str): tags = tags.split()
        tags = [t for t in tags if not t.startswith("graph/") and not t.startswith("interview/")]
        props.update(tags=tags + ["graph/" + scope, "interview/" + record["code"].lower()],
                     graph_kind=kind, interview_code=record["code"])
        classes = props.get("cssclasses") or []
        if isinstance(classes, str): classes = classes.split()
        classes = [c for c in classes if c not in {"gurumoji-reading", "gurumoji-control"}]
        props["cssclasses"] = classes + ["gurumoji-control" if kind == "control" else "gurumoji-reading"]
        if kind != "interview": props["interview"] = link(record["hub"])
        return pack(props, body)

    def managed_note(self, relative: str, text: str, *, navigation: bool = True) -> bool:
        """Write one generated note; False when a deleted content note is left missing.

        Markdown goes through the shared Vault note policy (vault_note_policy):
        a researcher's edit is kept in the history before the latest version is
        written, and a deleted note is recreated only for ``navigation``.
        Settings-like files (.base, .css) keep the older rule: never replace an edit.
        """
        if relative.endswith(".md"):
            from .vault_note_policy import write_generated_note
            with LAYOUT_LOCK:
                data = self.load()
                known = data["managed"].get(relative)
                result = write_generated_note(
                    self.vault, relative, text.encode(),
                    known_hashes={known} if known else set(), ever_written=known is not None,
                    recreate_missing=navigation, log_file=self.note_log,
                )
                if result.action == "missing":
                    return False
                if known != result.sha256:
                    data["managed"][relative] = result.sha256
                    self.save(data)
                return True
        with LAYOUT_LOCK:
            data = self.load()
            path = safe_path(self.vault, relative)
            if path.exists():
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
                if actual != data["managed"].get(relative):
                    reason = "未管理の既存ノート" if relative not in data["managed"] else "人が編集したノート"
                    warn_once(("skip", relative), f"{reason}のため生成ノートを更新しませんでした: {relative}")
                    return False
            encoded = text.encode()
            if not path.exists() or path.read_bytes() != encoded:
                write_atomic(path, encoded)
            digest = hashlib.sha256(encoded).hexdigest()
            if data["managed"].get(relative) != digest:
                data["managed"][relative] = digest
                self.save(data)
            return True

    def update(self, item_id: str, title: str, links: dict, status: str | None = None,
               *, analysis_methods: list[dict] | None = None) -> None:
        with LAYOUT_LOCK:
            self.register(item_id, title)
            data = self.load()
            record = data["interviews"][item_id]
            record["links"].update({k: v for k, v in links.items() if v})
            if analysis_methods is not None: record["analysis_methods"] = analysis_methods
            if status is not None and not record.get("deleted_at"): record["status"] = status
            self.save(data)
            deleted = bool(record.get("deleted_at"))
            memo = self.note_path(item_id, title, "研究メモ")
            if not deleted and not safe_path(self.vault, memo).exists():
                # The memo belongs to the researcher: create it once, never rewrite it.
                try:
                    write_atomic(safe_path(self.vault, memo), self.decorate(pack({"note_type": "research-memo"},
                        "# 研究メモ\n\n自由に記録してください。関連テーマは `[[20-テーマ/テーマ名]]` でリンクできます。\n"),
                        item_id, "memo", "detail").encode(), create_only=True)
                except FileExistsError:
                    pass
            data = self.load()
            record = data["interviews"][item_id]
            body = f"# {record['code']} {markdown(display_title(title))}\n\n状態：{markdown(record['status'])}\n\n"
            body += "> [!info]- 元の録音ファイル名\n> " + markdown(title) + "\n\n"
            body += "## 分析結果\n\n"
            analysis = record["links"].get("analysis")
            if analysis and safe_path(self.vault, analysis).is_file():
                body += "> [!summary] 分析結果を読む\n> " + link(analysis, "分析まとめを開く") + "\n> 見解・根拠・分析条件・保存履歴を確認できます。\n\n"
            elif not deleted:
                body += "このインタビューの分析結果はまだ保存されていません。アプリの「分析結果をObsidianに保存」で追加できます。\n\n"
            if deleted:
                body += ("> [!warning] この会話はアプリから削除されています\n> 削除日時：" + markdown(record["deleted_at"])
                         + "\n> このフォルダーの研究ノートは記録として残しています。アプリからは開けません。\n\n")
            body += link(ANALYSIS_INDEX, "全インタビューの分析結果一覧") + "\n\n## 本文・仕上げ\n\n"
            labels = {"work": "会話全文", "outline": "全体アウトライン", "analysis": "分析まとめ",
                      "control": "AI仕上げの操作", "status_note": "仕上げの状態", "original_note": "保存原文",
                      "result_note": "確認する仕上げ結果", "final_outline_note": "仕上げ後アウトライン",
                      "meeting_minutes": "会議議事録・タスク"}
            body += "\n".join("- " + link(p, labels.get(k, k)) for k, p in record["links"].items() if k != "analysis")
            body += "\n- " + link(memo, "研究メモ") + "\n\n"
            body += "## 表示の切り替え\n\nブックマークの「Gurumoji」→「インタビュー別」から、このインタビューのグラフを開けます。\n\n"
            body += "> [!tip]- 検索条件を手動で指定する場合\n> ```text\n> " + interview_query(record) + "\n> ```\n"
            # User-maintained theme links live in the memo, not in the generated block.
            body += "\n## 関連テーマ\n\n研究メモで共通テーマにリンクすると、テーマを経由して他のインタビューと比較できます。\n"
            hub = self.decorate(pack({"note_id": "interview-" + item_id, "note_type": "interview",
                "title": title, "conversation_id": item_id, "status": record["status"]}, body), item_id, "interview", "overview")
            # The overview is a content note: a deleted one is reported, not recreated.
            self.managed_note(record["hub"], hub, navigation=False)
            self.publish_navigation()

    def publish_sync_status(self, props: dict) -> None:
        """List what the shared note policy did to researcher-touched notes (OBS-04, OBS-15)."""
        from .vault_note_policy import recent_changes
        labels = {"edit_saved": "研究者の編集を履歴に保存して更新", "missing": "削除を検出（再作成しません）",
                  "recreated": "削除を検出して再作成（ナビゲーション）"}
        vault_names = {"research": "ResearchVault", "input": "InputVault",
                       "visualization": "VisualizationVault", "orchestrator": "OrchestratorVault"}
        rows = []
        for event in recent_changes(self.note_log, limit=100):
            path = str(event.get("path") or "")
            research = event.get("vault", "research") == "research"
            note = link(path) if research and path.endswith(".md") else "`" + markdown(path) + "`"
            # Inside a table the alias separator must be escaped (OBS-19).
            history = " / ".join((link(h, "履歴").replace("|", "\\|") if research else "`" + markdown(h) + "`")
                                 for h in event.get("history") or [])
            rows.append(f"| {markdown(str(event.get('at', ''))[:19])} | {vault_names.get(event.get('vault'), markdown(event.get('vault')))} "
                        f"| {note} | {labels.get(event.get('action'), markdown(event.get('action')))} | {history or '―'} |")
        body = ("# 同期状況\n\n" + link(HOME, "ホームへ戻る") + "\n\n"
                "アプリが作るノートを研究者が編集していた場合は、編集した版を履歴に保存してから最新版に更新します。"
                "削除されていた場合、分析ノート・概要は作り直さず、ホーム・一覧などのナビゲーションだけ作り直します。"
                "履歴の写しは全体グラフに表示しません。研究者のノート（全文・操作・研究メモ・仕上げ結果）はアプリが上書きしません。\n\n"
                "## 最近の記録（新しい順、最大100件）\n\n")
        if rows:
            body += "| 日時（UTC） | Vault | ノート | 内容 | 履歴 |\n| --- | --- | --- | --- | --- |\n" + "\n".join(rows) + "\n"
        else:
            body += "記録はありません。\n"
        body += "\nすべての変更の記録は、データフォルダーの `obsidian_layout/note_changes.jsonl` にあります。\n"
        self.managed_note(SYNC_STATUS, pack(props, body))

    def mark_deleted(self, item_id: str) -> bool:
        """Say the conversation left the app; its research notes stay as history (OBS-11)."""
        with LAYOUT_LOCK:
            data = self.load()
            record = data["interviews"].get(item_id)
            if record is None or record.get("deleted_at"):
                return False
            record["status_before_delete"] = record.get("status", "")
            record["status"] = DELETED_STATUS
            record["deleted_at"] = utc_now_iso()
            self.save(data)
            self.update(item_id, record["title"], {})
            return True

    def clear_deleted(self, item_id: str) -> bool:
        """A conversation imported again under the same ID is no longer deleted."""
        with LAYOUT_LOCK:
            data = self.load()
            record = data["interviews"].get(item_id)
            if record is None or not record.get("deleted_at"):
                return False
            record["status"] = record.pop("status_before_delete", "") or "保存済み"
            del record["deleted_at"]
            self.save(data)
            self.update(item_id, record["title"], {})
            return True

    def sync_finishing(self, state: dict) -> None:
        # Existing finishing notes belong to the researcher. Refresh navigation only.
        status = {"ready": "操作待ち", "running": "処理中", "error": "確認が必要", "interrupted": "中断"}.get(state["status"], "完了")
        if state["status"] == "completed":
            action = (state.get("observed") or [""])[-1]
            status = {"outline": "アウトライン作成済み", "finish": "結果確認待ち", "apply": "反映済み"}.get(action, "完了")
        self.update(state["item_id"], state["title"],
                    {k: state[k] for k in ("work", "outline", "control", "status_note", "original_note",
                                           "result_note", "final_outline_note") if state.get(k)}
                    | ({"meeting_minutes": state["meeting_minutes_note"]} if state.get("meeting_minutes_note") else {}), status)

    def publish_navigation(self) -> None:
        with LAYOUT_LOCK:
            records = list(self.load()["interviews"].values())
            props = {"note_type": "navigation", "tags": ["graph/support"]}
            def label(r: dict) -> str:
                return r["code"] + " " + display_title(r["title"]) + ("（" + DELETED_STATUS + "）" if r.get("deleted_at") else "")
            rows = "\n".join("- " + link(r["hub"], label(r)) for r in records)
            available = [r for r in records if r["links"].get("analysis")
                         and safe_path(self.vault, r["links"]["analysis"]).is_file()]
            analysis_rows = "\n".join("- " + link(r["links"]["analysis"], label(r) + " の分析結果") for r in available)
            pending_rows = "\n".join("- " + link(r["hub"], label(r)) + "：未保存" for r in records
                                     if r not in available and not r.get("deleted_at"))
            group_links = "\n".join("- " + link(method_group_path(key), title) for key, title, _, _ in METHOD_GROUPS)
            for key, title, description, method_ids in METHOD_GROUPS:
                body = "# " + title + "\n\n" + link(ANALYSIS_INDEX, "分析結果一覧へ戻る") + "\n\n" + description + "\n\n"
                body += "各手法の最新の保存記録を掲載します。状態は保存時点のものです。過去の結果は各インタビューの分析まとめにある保存履歴から開けます。\n\n"
                for record in records:
                    methods = [m for m in record.get("analysis_methods", []) if m["method_id"] in method_ids
                               and safe_path(self.vault, m["path"]).is_file()]
                    body += "## " + markdown(record["code"] + " " + display_title(record["title"])) + "\n\n"
                    body += link(record["hub"], "インタビューの概要") + "\n\n"
                    body += method_table(methods) + "\n" if methods else "この分類の保存記録はまだありません。\n\n"
                if not records: body += "インタビューを保存すると、ここに表示されます。\n"
                self.managed_note(method_group_path(key), pack({**props, "cssclasses": ["gurumoji-reading"]}, body))
            self.managed_note(ANALYSIS_INDEX, pack(props, "# 分析結果\n\n"
                + link(HOME, "ホームへ戻る") + "\n\n"
                "分析まとめから、見解・根拠・分析条件・保存履歴へ進めます。\n\n"
                "## 分析手法から選ぶ\n\n" + group_links + "\n\n"
                f"## 保存済みの分析（{len(available)}件）\n\n"
                + (analysis_rows or "保存済みの分析結果はまだありません。") + "\n\n"
                "## 分析結果が未保存のインタビュー\n\n"
                + (pending_rows or "未保存のインタビューはありません。") + "\n\n"
                "アプリの「分析結果をObsidianに保存」で保存すると、この一覧にも自動で追加されます。\n"))
            self.managed_note(INDEX, pack(props, "# インタビュー一覧\n\n" + (rows or "文字起こしを保存すると、ここにインタビューが追加されます。") + "\n"))
            self.managed_note(HOME, pack(props, "# インタビュー研究\n\n"
                "- " + link(INDEX, "インタビューを選ぶ") + "\n"
                "- [[インタビュー一覧.base|日付・状態で一覧を見る]]\n"
                "- " + link(GUIDE, "全体グラフ・インタビュー別グラフの使い方") + "\n"
                "- " + link(SYNC_STATUS, "同期状況（履歴に保存した編集・削除を検出したノート）") + "\n\n"
                "左のブックマーク → **Gurumoji** → **研究全体のグラフ** または **インタビュー別** で表示を切り替えます。\n\n"
                "## 分析結果\n\n"
                "> [!summary] 保存済みの分析を読む\n> " + link(ANALYSIS_INDEX, "分析結果一覧を開く") + "\n\n"
                + group_links + "\n\n"
                + (analysis_rows or "分析結果を保存すると、ここから開けます。") + "\n\n"
                "## インタビュー\n\n" + rows + "\n"))
            self.publish_sync_status(props)
            self.managed_note(GUIDE, pack(props, "# グラフと仕上げの使い方\n\n"
                "1. この ResearchVault フォルダーを保管庫として開きます。\n"
                "2. 左のブックマークから Gurumoji → 研究全体のグラフ を開きます。\n"
                "3. インタビュー別のグラフは、その1件と関連テーマだけを表示します。\n"
                "4. 概要から全文・アウトライン・分析まとめ・研究メモ・仕上げ操作を開きます。\n"
                "5. 操作ノートではアウトライン作成 → 内容を調整 → AI仕上げ → 結果を確認 → アプリへ反映と進めます。\n"
                "6. チェックは1つずつ選びます。次の操作の前にチェックを外し、状態ノートが「次の操作を選べます」になるのを待ちます。Gurumojiは起動したままにします。\n\n"
                "## 関連テーマ\n\n研究メモに `[[20-テーマ/働き方]]` のようなリンクを記入して、リンク先にテーマノートを作成します。"
                "テーマの対応はGurumoji起動中に40-研究/テーマ関連へ出力します。テーマ本文は書き換えません。"
                "仕上げノートのタグは作成時のまま保持し、現在の参照先は概要・状態ノートで確認します。"
                "発言本文にはリンクを挿入せず、メモや根拠欄に発話のブロックリンクを置きます。"
                "AIがテーマを勝手に確定することはありません。\n\n"
                "## 画面配置\n\nWorkspacesの「Gurumoji・研究全体」「Gurumoji・インタビュー作業」で配置を切り替えます。"
                "グラフの表示対象はブックマークで選びます。"
                "ローカルグラフは関連を探索する表示です。深度を上げると別のインタビューも表示されます。\n\n"
                "全文は録音1件につき1ノートです。プロパティ・表示用リンクをAI入力に加えません。"
                "操作・原文・履歴・テンプレートは通常のグラフから除外しています。\n\n"
                "[Graph](https://help.obsidian.md/plugins/graph) / [Bookmarks](https://help.obsidian.md/plugins/bookmarks) / "
                "[Workspaces](https://help.obsidian.md/plugins/workspaces)\n"))
            base = {"filters": {"and": ['file.ext == "md"', 'note.graph_kind == "interview"']},
                    "properties": {"note.title": {"displayName": "インタビュー"}, "note.status": {"displayName": "状態"}},
                    "views": [{"type": "table", "name": "インタビュー一覧", "order": ["file.name", "note.title", "note.status", "file.mtime"]}]}
            self.managed_note("インタビュー一覧.base", yaml.safe_dump(base, allow_unicode=True, sort_keys=False))
            for folder in ("20-テーマ", "30-人物", "40-研究", "80-添付", "90-運用"):
                safe_path(self.vault, folder).mkdir(parents=True, exist_ok=True)
            self.configure(records)

    def configure(self, records: list[dict]) -> None:
        """Write recommended Obsidian settings once, when the app creates the Vault (OBS-03).

        A Vault that already has `.obsidian/` belongs to the user's settings: plugins,
        appearance, graph and workspaces are left as they are. Later syncs only refresh
        the app's own bookmark group, and only while it still exists.
        """
        data = self.load()
        applied = data.get("obsidian_settings")
        if applied is None:
            fresh = not safe_path(self.vault, ".obsidian").exists()
            applied = {"mode": "initialized" if fresh else "existing", "at": utc_now_iso()}
            data["obsidian_settings"] = applied
            self.save(data)
            initialize = fresh
        else:
            initialize = False
        def read(name, default, valid=lambda value: isinstance(value, dict)):
            p = safe_path(self.vault, ".obsidian/" + name)
            if not p.exists():
                return default
            try:
                value = json.loads(p.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                value = None
            if value is None or not valid(value):
                # Unreadable or half-written by Obsidian: never replace the user's settings.
                warn_once(("settings", name), f"Obsidian設定 {name} を読み取れないため、変更しませんでした。")
                return None
            return value
        def write(name, value):
            p = safe_path(self.vault, ".obsidian/" + name)
            b = json.dumps(value, ensure_ascii=False, indent=2).encode()
            if not p.exists() or p.read_bytes() != b: write_atomic(p, b)
        if initialize:
            core = read("core-plugins.json", {"file-explorer": True, "global-search": True, "switcher": True,
                "command-palette": True, "file-recovery": True, "outline": True},
                lambda value: isinstance(value, (dict, list)))
            enabled = ("search", "global-search", "graph", "bookmarks", "workspaces", "bases", "backlink", "properties", "canvas")
            if isinstance(core, list): write("core-plugins.json", list(dict.fromkeys(core + list(enabled))))
            elif core is not None: write("core-plugins.json", core | {key: True for key in enabled})
        # The snippet is the app's own hash-protected file; enabling it is a one-time setting.
        self.managed_note(".obsidian/snippets/gurumoji-reading.css",
            ".gurumoji-reading .metadata-container, .gurumoji-reading .inline-title { display: none !important; }\n"
            ".gurumoji-control .metadata-property:not([data-property-key=\"provider\"]), "
            ".gurumoji-control .metadata-add-button { display: none; }\n"
            ".gurumoji-reading h1 { font-size: 1.6em; }\n")
        if initialize:
            appearance = read("appearance.json", {}, lambda value: isinstance(value, dict)
                              and isinstance(value.get("enabledCssSnippets", []), list))
            if appearance is not None:
                appearance["enabledCssSnippets"] = list(dict.fromkeys(appearance.get("enabledCssSnippets", []) + ["gurumoji-reading"]))
                write("appearance.json", appearance)
            if not safe_path(self.vault, ".obsidian/graph.json").exists(): write("graph.json", graph_options())
        bookmarks = read("bookmarks.json", {"items": []} if initialize else None,
                         lambda value: isinstance(value, dict) and isinstance(value.get("items"), list))
        items = [g for g in (bookmarks or {"items": []})["items"] if isinstance(g, dict)]
        group = next((g for g in items if g.get("gurumoji") == "navigation"), None)
        if group is None:
            # Obsidian may drop the unknown marker key when it rewrites bookmarks; avoid a duplicate group.
            group = next((g for g in items if g.get("type") == "group" and g.get("title") == "Gurumoji"
                          and isinstance(g.get("items"), list) and g["items"]
                          and isinstance(g["items"][0], dict) and g["items"][0].get("path") == HOME), None)
        generated = {"type": "group", "title": "Gurumoji", "ctime": 0, "gurumoji": "navigation", "items": [
            {"type": "file", "path": HOME, "title": "ホーム", "ctime": 0},
            {"type": "file", "path": ANALYSIS_INDEX, "title": "分析結果", "ctime": 0},
            {"type": "graph", "title": "研究全体のグラフ", "ctime": 0, "options": graph_options()},
            {"type": "file", "path": "インタビュー一覧.base", "title": "インタビュー一覧", "ctime": 0},
            {"type": "group", "title": "分析手法別", "ctime": 0, "items": [
                {"type": "file", "path": method_group_path(key), "title": title, "ctime": 0}
                for key, title, _, _ in METHOD_GROUPS]},
            {"type": "group", "title": "分析を検索", "ctime": 0, "items": [
                {"type": "search", "query": 'path:"10-インタビュー" tag:#graph/detail "相づち"',
                 "title": "相づち・応答率", "ctime": 0},
                {"type": "search", "query": 'path:"10-インタビュー" tag:#graph/detail ("意見・認識が変わった" OR "意見・認識が変わらなかった" OR "新しい見解・気づきを得た" OR "支持・選好が明確になった")',
                 "title": "話者別リザルト", "ctime": 0},
                {"type": "search", "query": 'path:"10-インタビュー" tag:#graph/detail "相づち統計"',
                 "title": "相づち統計", "ctime": 0},
            ]},
            {"type": "group", "title": "インタビュー別", "ctime": 0, "items": [
                {"type": "graph", "title": r["code"] + " " + display_title(r["title"]), "ctime": 0, "options": graph_options(interview_query(r))} for r in records]}]}
        if bookmarks is not None:
            if group:
                bookmarks["items"][bookmarks["items"].index(group)] = generated
                write("bookmarks.json", bookmarks)
            elif initialize:
                bookmarks["items"].append(generated)
                write("bookmarks.json", bookmarks)
            # A group the user removed is not added back.
        # Native workspace leaf shapes, matching the installed Obsidian format.
        def leaf(kind, state):
            return {"id": hashlib.sha256((kind + json.dumps(state)).encode()).hexdigest()[:16],
                    "type": "leaf", "state": {"type": kind, "state": state}}
        def pane(children, direction="vertical"):
            key = hashlib.sha256(json.dumps(children).encode()).hexdigest()[:16]
            return {"id": key, "type": "split", "children": [
                {"id": key + str(i), "type": "tabs", "children": [c]} for i, c in enumerate(children)], "direction": direction}
        def workspace(local):
            record = records[0] if records else None
            path = record["hub"] if local and record else HOME
            main = [leaf("markdown", {"file": path, "mode": "preview"})] if local else [leaf("graph", {})]
            return {"main": pane(main),
                    "left": {**pane([leaf("bookmarks", {})]), "width": 220},
                    "right": {**pane([leaf("localgraph", {"file": path, "options": {**graph_options(),
                        "search": "-tag:#graph/support -tag:#graph/history",
                        "localJumps": 1}})]), "width": 280, "collapsed": not local},
                    "lastOpenFiles": [path]}
        if not initialize:
            return
        layouts = read("workspaces.json", {"workspaces": {}, "active": ""},
                       lambda value: isinstance(value, dict) and isinstance(value.get("workspaces"), dict))
        if layouts is not None:
            for name, local in (("Gurumoji・研究全体", False), ("Gurumoji・インタビュー作業", True)):
                if name not in layouts["workspaces"]: layouts["workspaces"][name] = workspace(local)
            write("workspaces.json", layouts)
        if not safe_path(self.vault, ".obsidian/workspace.json").exists(): write("workspace.json", workspace(False))

    def sync_themes(self) -> None:
        """Publish explicit theme relationships separately; never rewrite human themes."""
        with LAYOUT_LOCK:
            data = self.load()
            if any([self.relocate(data, item_id) for item_id in list(data["interviews"])]):
                self.save(data)
            records = list(data["interviews"].values())
            theme_root = safe_path(self.vault, "20-テーマ")
            themes = {"20-テーマ/" + path for path in visible_notes(theme_root)} if theme_root.is_dir() else set()
            notes = None
            def resolve(target: str) -> str | None:
                nonlocal notes
                target = target.strip().removesuffix(".md")
                if target + ".md" in themes:
                    return target + ".md"
                # Obsidian's default "shortest path" links omit folders when the name is unique in the Vault.
                if not any(theme.endswith("/" + target + ".md") for theme in themes):
                    return None
                if notes is None:
                    notes = visible_notes(self.vault)
                matches = [note for note in notes if note == target + ".md" or note.endswith("/" + target + ".md")]
                return matches[0] if len(matches) == 1 and matches[0] in themes else None
            memberships = {}
            for record in records:
                for path in safe_path(self.vault, record["folder"]).glob("*.md"):
                    try:
                        kind, values = note_links(path)
                    except (OSError, ValueError, yaml.YAMLError):
                        warn_once(("memo", path.as_posix()), "テーマ同期で読めないメモをスキップしました。")
                        continue
                    if kind != "memo": continue
                    for target in dict.fromkeys(resolve(value) for value in values):
                        if target:
                            memberships.setdefault(target, []).append(record)
            managed = self.load()["managed"]
            # Include previously generated relations when links or themes disappear.
            prefix = "40-研究/テーマ関連/"
            relatives = {target: prefix + hashlib.sha256(target.encode()).hexdigest()[:24] + ".md"
                         for target in memberships}
            for relative in managed:
                if not relative.startswith(prefix): continue
                path = safe_path(self.vault, relative)
                if not path.is_file(): continue
                try:
                    props, _ = unpack(path.read_text(encoding="utf-8-sig"))
                    target = props.get("theme_target")
                    if isinstance(target, str) and target.startswith("20-テーマ/"):
                        relatives.setdefault(target, relative)
                except (OSError, ValueError, yaml.YAMLError):
                    warn_once(("relation-read", relative), "テーマ関連ノートを読み込めませんでした。")
            for target, relative in sorted(relatives.items()):
                if relative in managed and not safe_path(self.vault, relative).exists():
                    warn_once(("relation-missing", relative), "移動・削除されたテーマ関連ノートは再作成しません。")
                    continue
                related = {r["item_id"]: r for r in memberships.get(target, [])}
                source = {"theme": target, "exists": safe_path(self.vault, target).is_file(),
                          "interviews": [{k: r[k] for k in ("item_id", "code", "title", "hub")}
                                         for _, r in sorted(related.items())]}
                props = {"note_id": "theme-links-" + Path(relative).stem,
                         "note_type": "theme-relations", "managed_by": "gurumoji",
                         "title": "テーマ関連：" + Path(target).stem,
                         "theme_target": target, "schema_version": 1,
                         "source_hash": hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest(),
                         "graph_kind": "theme", "tags": ["graph/overview" if related else "graph/history"]
                         + ["interview/" + r["code"].lower() for r in related.values()]}
                body = "# テーマとインタビューの関連\n\n"
                body += (link(target, Path(target).stem) if safe_path(self.vault, target).is_file()
                         else "テーマノートは移動または削除されています。") + "\n\n"
                body += "研究メモの明示リンクから作成した一覧です。テーマ本文は変更しません。\n\n"
                body += "\n".join("- " + link(r["hub"], r["code"] + " " + r["title"])
                                  for r in related.values()) or "現在、このテーマに関連するインタビューはありません。"
                # Deleted relation notes are skipped above; an edited one is kept in the history.
                self.managed_note(relative, pack(props, body + "\n"), navigation=False)
