"""Four independent Obsidian Vaults linked by stable IDs, not cross-Vault links.

Software is the Git-managed ``docs/program-vault`` and is never written by the
app. Input, Visualization, and Orchestrator are generated under
``<data>/obsidian``. Their notes describe authoritative SQLite rows,
``analysis_store`` artifacts, and media by ID, revision, and hash. Transcript
text and full tables are never copied. Publishing never calls AI or reruns an
analysis. Notes follow the shared Vault note policy (vault_note_policy): a note
edited in Obsidian is kept under ``99-Archive/history`` before the latest version
is written, and a deleted note is recreated only for Home and Index.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .analysis_method_registry import (COMMON_EXPORT_FIELDS, METHOD_GROUPS, METHOD_STATUS_LABELS,
                                       METHODS, REGISTRY_VERSION)
from .analysis_store import StoreConflict, canonical, markdown, safe_path, write_atomic

SCHEMA_VERSION = 1
VAULT_LOCK = threading.RLock()
SOFTWARE_ROOT = Path(__file__).resolve().parents[2] / "docs" / "program-vault"
# kind: (folder under <data>/obsidian, display name, responsibility)
VAULTS = {
    "software": ("", "Software", "アーキテクチャ、仕様、モジュール契約、開発判断。Git管理で、アプリは書き込みません。"),
    "input": ("InputVault", "Input", "取り込み台帳、Whisper設定、分析入力スナップショット、品質情報。発話本文は保存しません。"),
    "visualization": ("VisualizationVault", "Visualization", "図表の問い、表示仕様、データ来歴、読み取りの注意。数値の正本は固定CSVです。"),
    "orchestrator": ("OrchestratorVault", "Orchestrator", "分析手法カード、実行記録、状態、警告、再現条件。"),
}
GENERATED = ("input", "visualization", "orchestrator")
FOLDERS = {
    "input": ("10-Inputs：会話ごとの取り込み台帳", "20-Snapshots：分析保存時の入力スナップショット（比較は構成会話の一覧）"),
    "visualization": ("10-Visuals：実行・手法ごとの図表仕様",),
    "orchestrator": ("10-Methods：分析手法カード", "20-Runs：分析の実行記録（会議議事録・インタビュー比較も別の実行）"),
}
SOURCE_KINDS = {"whisper": "Whisper文字起こし", "imported": "出力JSONの取り込み"}
# Only non-secret transcription settings. Tokens and API keys are never accepted.
WHISPER_KEYS = ("model", "language", "device", "diarization_device", "audio_preprocess", "triple_pass",
                "boost_quiet_speech", "vad_onset", "vad_offset", "no_speech_threshold",
                "min_speakers", "max_speakers", "num_speakers", "emotion_analysis", "emotion_model", "conversation_mode",
                "diarization_model", "custom_vocabulary_terms", "custom_vocabulary_sha256")
CHARTS = {
    "meeting_speaker_activity": "棒グラフ", "comparison_interviews": "棒グラフ",
    "comparison_common_terms": "グループ棒グラフ", "comparison_characteristic_terms": "発散棒グラフ",
    "comparison_codes": "ヒートマップ", "comparison_emotions": "ヒートマップ",
    "speakers": "棒グラフ", "groups": "棒グラフ", "pos_frequency": "棒グラフ", "term_frequency": "棒グラフ",
    "keywords": "棒グラフ", "characteristic_terms": "棒グラフ", "frequencies": "棒グラフ",
    "transformer_topics": "棒グラフ", "transformer_speakers": "積み上げ棒グラフ",
    "transformer_backchannel_rates": "棒グラフ", "transformer_backchannel_speakers": "棒グラフ",
    "timeline": "タイムライン", "transformer_timeline": "タイムライン", "overlaps": "タイムライン",
    "gaps": "ヒストグラム", "transitions": "遷移行列ヒートマップ", "cooccurrence": "共起ネットワーク",
    "correlations": "相関ヒートマップ", "crosstabs": "クロス表ヒートマップ", "case_matrix": "ヒートマップ",
    "emotions": "折れ線グラフ", "dependencies": "係り受けツリー",
}
X_FIELDS = ("speaker_name", "speaker", "term", "surface", "lemma", "pos", "topic_label", "label",
            "code", "emotion", "variable", "group", "start", "time", "word", "source", "source_name")
Y_FIELDS = ("count", "frequency", "segment_count", "turns", "seconds", "duration", "share", "ratio",
            "response_rate_percent", "percent", "score", "value", "coefficient", "correlation",
            "p_value", "weight", "jaccard")
GROUP_QUESTIONS = {
    "text": "語や表現の出現が、話者・文脈によってどう違うか。",
    "transformer": "意味的なテーマや音声の推定値が、時間・話者によってどう分布するか。",
    "ai": "生成された下書きや仕上げの変更が、どの発話に基づくか。",
    "statistics": "群・変数の差や関係が、前提を満たす範囲でどう見えるか。",
    "conversation": "発話量・交替・間・重なりが、話者間でどう配分されているか。",
    "qualitative": "研究者が付けたコードや重要引用が、どの事例・文脈に現れるか。",
    "meeting": "会議のタスク候補・決定事項候補・発話量が、誰の発話にどれだけ現れるか。",
    "comparison": "複数回のインタビューで、発話量・語・コード・感情ラベルがどう違うか（記述的な比較）。",
}
GATES = (
    "入力妥当性：空本文・時刻不正・UNKNOWN話者・除外発話を数え、手法の前提を満たすか確認する。",
    "設計妥当性：分析単位と研究質問・比較軸が整合しているか確認する。",
    "計算妥当性：seed・パラメーター・エンジンとモデルの版を実行記録に残す。",
    "根拠妥当性：要約・AI出力・テーマ名は発話IDで根拠をたどれる場合だけ使う。",
    "解釈ゲート：自動値から合意・因果・重要性・本人の感情を断定しない。",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def entity_key(value: str) -> str:
    return sha256(str(value).encode("utf-8"))[:16]


def code(value) -> str:
    return "`" + str("" if value is None else value).replace("`", "'").replace("\n", " ") + "`"


def cell(value, limit: int = 160) -> str:
    return markdown(str("" if value is None else value).replace("\n", " ")[:limit])


def status_label(status) -> str:
    return METHOD_STATUS_LABELS.get(status, str(status or "状態不明"))


def method_group(method_id: str) -> tuple[str, str, str]:
    return next(((key, title, description) for key, title, description, ids in METHOD_GROUPS
                 if method_id in ids), ("other", "その他", ""))


def valid_time(segment: dict) -> bool:
    start, end = segment.get("start"), segment.get("end")
    numeric = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (start, end))
    return numeric and 0 <= start <= end


def duration_text(seconds: float) -> str:
    total = max(0, int(seconds))
    return f"{total // 3600}時間{total % 3600 // 60:02d}分{total % 60:02d}秒"


def chart_spec(dataset: str, fields: list[str], rows: int) -> tuple[str, str, str, str]:
    chart = CHARTS.get(dataset, "表")
    lower = {field.casefold(): field for field in fields}
    x = next((lower[name] for name in X_FIELDS if name in lower), "")
    y = next((lower[name] for name in Y_FIELDS if name in lower), "")
    if not y:  # Domain columns such as turn_count or speaking_seconds.
        measure = re.compile(r"(count|seconds|percent|rate|ratio|share|frequency|value|score|coefficient|weight|jaccard)$")
        y = next((field for field in fields if field != x and measure.search(field.casefold())), "")
    if x and y and chart != "表":
        alt = f"{chart}。{x} ごとの {y} を示す。全{rows}行。"
    else:
        alt = f"{chart}。全{rows}行の表。表示する列は研究者が選ぶ。"
    return chart, x, y, alt


def run_members(snapshot: dict) -> list[dict]:
    """Member conversations of a multi-conversation run (interview comparison)."""
    members = snapshot.get("members")
    return [member for member in members if isinstance(member, dict)] if isinstance(members, list) else []


def enclosing_vaults(root: Path, limit: int = 32) -> list[Path]:
    """Folders above ``root`` that Obsidian has opened as a Vault (they hold ``.obsidian/``)."""
    found: list[Path] = []
    for parent in list(Path(root).resolve().parents)[:limit]:
        try:
            if (parent / ".obsidian").is_dir():
                found.append(parent)
        except OSError:
            continue
    return found


def nesting_warnings(data_dir: Path) -> list[str]:
    """Warn when a folder above the app's Vaults is itself open as a Vault (OBS-10).

    Saving continues: the notes are still correct, but the outer Vault's search,
    graph and link resolution would mix them in. Only folder names are shown, and
    the leftover ``.obsidian`` folder is never removed automatically.
    """
    obsidian = Path(data_dir) / "obsidian"
    roots = [obsidian / "ResearchVault"] + [obsidian / VAULTS[kind][0] for kind in GENERATED]
    parents: list[Path] = []
    for root in roots:
        for parent in enclosing_vaults(root):
            if parent not in parents:
                parents.append(parent)
    return [
        f"「{parent.name or parent}」フォルダーがObsidianの保管庫として開かれています（`.obsidian` があります）。"
        "その中にあるResearchVaultなどのノートが、親の保管庫の検索・グラフ・リンクに混ざります。"
        "親フォルダーではなく、各Vaultのフォルダーを保管庫として開いてください。"
        "親フォルダーの `.obsidian` は自動では削除しません。"
        for parent in parents
    ]


class VaultRegistry:
    def __init__(self, database_file: Path, software_root: Path | None = None):
        self.data = Path(database_file).parent
        self.catalog_file = self.data / "obsidian_layout" / "vaults.json"
        self.software_root = Path(software_root) if software_root else SOFTWARE_ROOT
        self.note_log = self.data / "obsidian_layout" / "note_changes.jsonl"
        self.note_events: list = []

    # Registry and catalog -------------------------------------------------
    def load(self) -> dict:
        if self.catalog_file.exists():
            data = json.loads(self.catalog_file.read_text(encoding="utf-8"))
            if data.get("schema_version") != SCHEMA_VERSION:
                raise ValueError("Vault台帳の版に対応していません。")
        else:
            data = {"schema_version": SCHEMA_VERSION, "vaults": {}, "notes": {}, "entities": {}}
        for kind, (folder, title, role) in VAULTS.items():
            data["vaults"].setdefault(kind, {
                "title": title, "role": role, "writable": kind != "software",
                "root": "repo:docs/program-vault" if kind == "software" else "obsidian/" + folder})
        data.setdefault("notes", {})
        data.setdefault("entities", {})
        return data

    def save(self, data: dict) -> None:
        write_atomic(self.catalog_file, json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))

    def root(self, kind: str, data: dict | None = None) -> Path:
        if kind == "software":
            return self.software_root
        value = (data or self.load())["vaults"][kind]["root"]
        # One folder directly under <data>/obsidian keeps Vault roots siblings, never nested.
        if not re.fullmatch(r"obsidian/[A-Za-z0-9_-]+", value) or value == "obsidian/ResearchVault":
            raise ValueError("Vaultの保存先は <data>/obsidian 直下の独立フォルダーにしてください。")
        return self.data / value

    def roots(self) -> dict[str, Path]:
        data = self.load()
        roots = {kind: self.root(kind, data) for kind in VAULTS}
        if len({roots[kind] for kind in GENERATED}) != len(GENERATED):
            raise ValueError("Vaultの保存先が重複しています。")
        return roots

    def run_status(self, run_id: str) -> str | None:
        entry = self.load()["notes"].get("orchestrator-run-" + run_id)
        return entry["status"] if entry else None

    # Explicit slide-design publication. Viewing or exporting a deck never
    # invokes this writer. A stable path preserves deletion protection across
    # template/source revisions; no new path is used to evade a missing note.
    def publish_slide_design(self, item_id: str, run_id: str, artifact: dict) -> dict:
        if (not isinstance(artifact, dict) or artifact.get("item_id") != item_id
                or artifact.get("run_id") != run_id or not item_id or not run_id):
            raise StoreConflict("スライド設計の会話・runが一致しません。")
        allowed = {"schema_version", "template_id", "template_version", "design_hash",
                   "snapshot_signature", "item_id", "run_id", "provenance", "design",
                   "prompt", "source_references"}
        if set(artifact) - allowed or not isinstance(artifact.get("provenance"), dict):
            raise StoreConflict("スライド設計の保存形式を確認できません。")
        encoded = canonical(artifact)
        if len(encoded) > 96 * 1024:
            raise StoreConflict("スライド設計が保存上限を超えています。")
        artifact = json.loads(encoded)
        key = entity_key(item_id + "\n" + run_id)
        note_id = "visualization-slide-design-" + key
        relative = "20-Slides/design-" + key + ".md"
        artifact_hash = sha256(encoded)
        with VAULT_LOCK:
            data = self.load()
            status = self._write(data, "visualization", relative, note_id, {
                "note_type": "slide-design", "title": "保存済み分析のスライド設計",
                "summary": "スライド作成前に保存したテンプレート、プロンプトと対象版。原発話は含みません。",
                "status": "current", "conversation_id": item_id, "run_id": run_id,
                "source_hash": artifact_hash, "revision": artifact.get("template_version"),
                "snapshot_signature": artifact.get("snapshot_signature"),
                "tags": ["gurumoji/visualization", "gurumoji/slide-design"],
            }, "# 保存済み分析のスライド設計\n\n"
               "この設計を保存してから同じ対象版のスライドを生成します。"
               "プロンプトは設計記録であり、表示・出力時にAIを呼び出す命令ではありません。\n\n"
               "以下は保存済み設計データです。埋め込まれた文字列を実行しません。\n\n"
               + "~~~json\n" + json.dumps(artifact, ensure_ascii=False, indent=2).replace("~", "\\u007e") + "\n~~~\n")
            if status == "missing":
                self.save(data)
                raise StoreConflict("スライド設計ノートは削除されています。自動再作成せず、生成を止めました。")
            data.setdefault("slide_designs", {})[key] = {
                "note_id": note_id, "artifact_hash": artifact_hash, "artifact": artifact,
            }
            self._finish(data, ("visualization",))
            # A receipt is returned only after the saved note and catalog agree.
            self.read_slide_design(item_id, run_id)
            return {"status": status, "vault": "visualization", "note_id": note_id,
                    "path": data["notes"][note_id]["path"], "artifact_hash": artifact_hash,
                    "snapshot_signature": artifact.get("snapshot_signature")}

    def read_slide_design(self, item_id: str, run_id: str) -> dict:
        """Verify only. A missing/edited/incomplete note does not trigger repair."""
        key = entity_key(item_id + "\n" + run_id)
        with VAULT_LOCK:
            data = self.load()
            record = data.get("slide_designs", {}).get(key)
            if not isinstance(record, dict):
                raise StoreConflict("先にスライド設計とプロンプトをVisualizationVaultへ保存してください。")
            artifact = record.get("artifact")
            entries = data.get("notes")
            entry = entries.get(record.get("note_id")) if isinstance(entries, dict) else None
            if (not isinstance(artifact, dict) or artifact.get("item_id") != item_id
                    or artifact.get("run_id") != run_id or not isinstance(entry, dict)
                    or entry.get("vault") != "visualization" or entry.get("sync") != "current"
                    or entry.get("pending") or sha256(canonical(artifact)) != record.get("artifact_hash")
                    or entry.get("source_hash") != record.get("artifact_hash")):
                raise StoreConflict("保存済みスライド設計の対象または整合性を確認できません。")
            try:
                path = safe_path(self.root("visualization", data), entry["path"])
            except (KeyError, TypeError, ValueError) as exc:
                raise StoreConflict("スライド設計ノートの保存場所を確認できません。") from exc
            if not path.is_file() or sha256(path.read_bytes()) != entry.get("sha256"):
                raise StoreConflict("スライド設計ノートが削除または変更されています。生成を止めました。")
            return json.loads(canonical(artifact))

    def _write(self, data: dict, kind: str, relative: str, note_id: str, properties: dict, body: str) -> str:
        """Write one managed note. Returns written / unchanged / overwritten / missing.

        ``overwritten``: an edit made in Obsidian was kept in the history first.
        """
        from .vault_note_policy import GENERATED_HISTORY, write_generated_note
        if kind not in GENERATED:
            raise ValueError("Software Vault はアプリから書き込みません。")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]*\.md", relative):
            raise ValueError("ノートのパスが不正です。")
        root = self.root(kind, data)
        entry = data["notes"].get(note_id)
        if entry and entry["vault"] != kind:
            raise ValueError("note_idが別のVaultで使われています。")
        if entry:
            relative = entry["path"]
        elif any(e["vault"] == kind and e["path"] == relative for e in data["notes"].values()):
            raise ValueError("同じ場所に別のnote_idのノートがあります。")
        target = safe_path(root, relative)
        props = {"note_id": note_id, "vault_kind": kind, **properties,
                 "schema_version": SCHEMA_VERSION, "managed_by": "gurumoji"}
        content_hash = sha256(canonical({"properties": props, "body": body}))
        record = {"vault": kind, "path": relative, "note_type": props.get("note_type", ""),
                  "title": str(props.get("title", "")), "summary": str(props.get("summary", "")),
                  "status": str(props.get("status", "current")), "revision": props.get("revision"),
                  "source_hash": props.get("source_hash", "")}
        # The rendered file carries an 'updated' time, so compare the content hash first.
        if (entry and target.exists() and entry.get("content_hash") == content_hash
                and sha256(target.read_bytes()) == entry.get("sha256")):
            entry.update(record, sync="current", pending="")
            return "unchanged"
        props["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        encoded = ("---\n" + yaml.safe_dump(props, allow_unicode=True, sort_keys=False).rstrip()
                   + "\n---\n\n" + body.strip() + "\n").encode("utf-8")
        known = {entry.get("sha256"), entry.get("pending")} if entry else set()

        def before_write(new_hash: str) -> None:
            # Record the intended hash first so an interrupted write is recognised, not an edit.
            current = data["notes"].setdefault(note_id, {})
            current.update(record, pending=new_hash, content_hash=content_hash, sync="writing")
            self.save(data)

        result = write_generated_note(
            root, relative, encoded, known_hashes=known,
            ever_written=bool(entry and (entry.get("sha256") or entry.get("pending"))),
            recreate_missing=relative in {"00-Home.md", "00-Index.md"},
            history=GENERATED_HISTORY, vault_kind=kind, log_file=self.note_log,
            before_write=before_write,
        )
        if result.notable:
            self.note_events.append(result)
        if result.action == "missing":
            entry.update(record, sync="missing")
            return "missing"
        # An identical on-disk note skips before_write. Rebuild/finalize its
        # ledger here too, without rewriting the note or manufacturing history.
        entry = data["notes"].setdefault(note_id, {})
        entry.update(record, content_hash=content_hash, sha256=result.sha256, pending="", sync="current")
        if result.history:
            entry["history"] = [*entry.get("history", []), *result.history][-20:]
        if result.action == "unchanged":
            return "unchanged"
        return "overwritten" if result.action == "edit_saved" else "written"

    def _finish(self, data: dict, kinds) -> None:
        for kind in kinds:
            root = self.root(kind, data)
            settings = safe_path(root, ".obsidian/app.json")
            if not settings.exists():
                write_atomic(settings, b"{}\n")
            safe_path(root, "99-Archive").mkdir(parents=True, exist_ok=True)
            self._home(data, kind)
            self._index(data, kind)
        self.save(data)

    def _home(self, data: dict, kind: str) -> None:
        _, title, role = VAULTS[kind]
        body = f"# Gurumoji {title} Vault\n\n{role}\n\n- [[00-Index|このVaultの索引]]\n\n## フォルダー\n\n"
        body += "\n".join("- " + value for value in FOLDERS[kind]) + "\n- 99-Archive：置き換えたノート。通常の検索対象にしません\n\n"
        body += ("## 4つのVault\n\n"
                 "| Vault | 担当 |\n| --- | --- |\n"
                 + "".join(f"| {name} | {cell(text, 200)} |\n" for _, name, text in VAULTS.values())
                 + "\n別のVaultへは `[[...]]` でリンクしません。`conversation_id`、`input_snapshot_id`、`run_id`、"
                 "`artifact_id`、`note_id` で対応付けます。Software Vault はリポジトリの `docs/program-vault` です。"
                 "研究者が読むノートとAI仕上げの操作は、互換のため従来の ResearchVault に残ります。\n")
        if kind == "orchestrator":
            body += "\n## 共通ゲート\n\n" + "\n".join(f"{i}. {text}" for i, text in enumerate(GATES, 1)) + "\n"
        self._write(data, kind, "00-Home.md", f"{kind}-home", {
            "note_type": "vault-home", "title": f"Gurumoji {title} Vault", "summary": role,
            "revision": SCHEMA_VERSION, "status": "current", "tags": ["gurumoji/" + kind]}, body)

    def _index(self, data: dict, kind: str) -> None:
        entries = sorted((entry["path"], note_id, entry) for note_id, entry in data["notes"].items()
                         if entry["vault"] == kind and note_id != f"{kind}-index"
                         and not entry["path"].startswith("99-Archive/"))
        body = f"# {VAULTS[kind][1]} Vault 索引\n\n[[00-Home|ホーム]]\n\n"
        body += "| ノート | 種類 | 状態 | 要約 |\n| --- | --- | --- | --- |\n"
        sync = {"missing": "・削除を検出（再作成しません）", "writing": "・書き込み中断"}
        for path, note_id, entry in entries:
            body += (f"| [[{path[:-3]}\\|{note_id}]] | {cell(entry.get('note_type'))} | "
                     f"{cell(entry.get('status'))}{sync.get(entry.get('sync'), '')} | {cell(entry.get('summary'), 120)} |\n")
        self._write(data, kind, "00-Index.md", f"{kind}-index", {
            "note_type": "vault-index", "title": f"{VAULTS[kind][1]} Vault 索引",
            "summary": f"{len(entries)}件の管理ノートの索引。", "revision": SCHEMA_VERSION,
            "status": "current", "tags": ["gurumoji/" + kind]}, body)

    # Input Vault ----------------------------------------------------------
    def publish_input(self, *, item_id: str, title: str, segments: list[dict], revision: int,
                      session_profile: dict | None = None, language: str | None = None,
                      media_path: Path | None = None, created_at: str = "",
                      whisper: dict | None = None, source_kind: str | None = None,
                      preparation_state: dict | None = None) -> str:
        with VAULT_LOCK:
            data = self.load()
            status = self._input(data, item_id=item_id, title=title, segments=segments, revision=revision,
                                 session_profile=session_profile, language=language, media_path=media_path,
                                 created_at=created_at, whisper=whisper, source_kind=source_kind,
                                 preparation_state=preparation_state)
            # The first Whisper save opens all three generated Vaults, so none appears missing.
            self._finish(data, GENERATED)
            return status

    def retire_input(self, item_id: str) -> str:
        """Mark a deleted conversation's ledger. Its runs and notes stay for provenance."""
        with VAULT_LOCK:
            data = self.load()
            key = entity_key(item_id)
            entity = data["entities"].get("input-" + key) or {}
            render = entity.get("render")
            if not render:
                return "missing"
            entity["deleted"] = True
            props = {**render["properties"], "status": "deleted",
                     "summary": "アプリから削除済み。" + str(render["properties"].get("summary", ""))}
            body = ("> [!warning] アプリから削除された会話です\n"
                    "> 本文・音声はアプリから削除されました。保存済みの分析結果と各Vaultのノートは来歴として残します。\n\n"
                    + render["body"])
            status = self._write(data, "input", render["relative"], "input-item-" + key, props, body)
            self._finish(data, ("input",))
            return status

    def _input(self, data: dict, *, item_id: str, title: str, segments: list[dict], revision: int,
               session_profile: dict | None = None, language: str | None = None,
               media_path: Path | None = None, created_at: str = "",
               whisper: dict | None = None, source_kind: str | None = None,
               preparation_state: dict | None = None) -> str:
        key = entity_key(item_id)
        entity = data["entities"].setdefault("input-" + key, {"item_id": item_id})
        entity.pop("deleted", None)
        if preparation_state is not None:
            # Only non-personal counts and version keys belong in the Input ledger.
            entity["preparation"] = {key: preparation_state[key] for key in (
                "input_version", "source_hash", "revision", "status", "content_ready_count",
                "interaction_ready_count", "analysis_needs_review") if key in preparation_state}
        if whisper:
            entity["whisper"] = {name: whisper[name] for name in WHISPER_KEYS
                                 if whisper.get(name) not in (None, "")}
        # A later edit ("saved") never hides where the transcript originally came from.
        if source_kind and not (source_kind == "saved" and entity.get("source_kind")):
            entity["source_kind"] = source_kind
        if language:
            entity["language"] = language
        kind_label = SOURCE_KINDS.get(entity.get("source_kind"), "アプリ保存データ")
        normalized = [{name: segment.get(name) for name in ("id", "start", "end", "speaker", "text")}
                      for segment in segments]
        source_hash = "sha256:" + sha256(canonical(
            {"segments": normalized, "preparation": entity["preparation"]} if entity.get("preparation") else normalized))
        speakers = {str(segment.get("speaker") or "UNKNOWN") for segment in segments}
        ends = [segment["end"] for segment in segments if valid_time(segment)]
        duration = duration_text(max(ends, default=0))
        empty = sum(1 for segment in segments if not str(segment.get("text") or "").strip())
        unknown = sum(1 for segment in segments if str(segment.get("speaker") or "UNKNOWN") == "UNKNOWN")
        invalid = sum(1 for segment in segments if not valid_time(segment))
        media = "なし"
        if media_path:
            path = Path(media_path)
            try:
                shown = path.resolve().relative_to(self.data.resolve()).as_posix()
            except ValueError:
                shown = path.name  # Never publish a machine-specific absolute path.
            media = code(shown) + (f"（{path.stat().st_size:,} bytes）" if path.is_file() else "（ファイルなし）")
        session_type = (session_profile or {}).get("session_type", "")
        body = (f"# 入力：{markdown(title)}\n\n"
                "> [!info] 本文は保存していません\n"
                "> 発話本文・話者名・音声はGurumojiのDBとメディア保存先が正本です。このノートは台帳・来歴・品質だけを記録します。\n\n"
                "## 台帳\n\n| 項目 | 値 |\n| --- | --- |\n"
                f"| 会話ID（conversation_id） | {code(item_id)} |\n| 取り込み | {kind_label} |\n"
                f"| 言語 | {cell(entity.get('language') or '不明')} |\n| 会話種別 | {cell(session_type or '未設定')} |\n"
                f"| revision | {int(revision)} |\n| source_hash | {code(source_hash)} |\n"
                f"| 発話数 / 話者数 / 長さ | {len(segments)} / {len(speakers)} / {duration} |\n"
                f"| メディア | {media} |\n| 作成 | {cell(created_at or '不明')} |\n\n"
                "## Whisper設定\n\n")
        settings = entity.get("whisper") or {}
        if settings:
            body += "| 設定 | 値 |\n| --- | --- |\n" + "".join(
                f"| {name} | {cell(json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value)} |\n"
                for name, value in settings.items())
        else:
            body += "記録なし（アプリ保存・旧データ・外部取り込み）。\n"
        body += ("\n## 品質チェック\n\nOrchestrator の入力妥当性ゲートで確認する値です。\n\n"
                 "| 項目 | 件数 |\n| --- | ---: |\n"
                 f"| 空の発話 | {empty} |\n| UNKNOWN話者 | {unknown} |\n| 時刻が不正な発話 | {invalid} |\n\n"
                 "## 関連\n\n"
                 "分析を保存すると `20-Snapshots` に入力スナップショットが追加されます（バックリンクで確認できます）。"
                 f"Orchestrator・Visualization では `conversation_id` = {code(item_id)} で対応付けます。\n")
        relative = f"10-Inputs/input-{key}.md"
        if entity.get("preparation"):
            body += "\n## 逐語録の準備状態\n\n" + "\n".join(
                f"- {name}: {code(value)}" for name, value in entity["preparation"].items()) + "\n"
        props = {
            "note_type": "input-item", "title": title,
            "summary": f"{kind_label}。{len(segments)}発話・{len(speakers)}話者・{duration}。revision {int(revision)}。",
            "source_ids": [item_id], "artifact_ids": [], "conversation_id": item_id,
            "revision": int(revision), "source_hash": source_hash, "status": "current",
            "sensitivity": "restricted", "tags": ["gurumoji/input"]}
        # Kept so a deletion can be recorded after the transcript itself is gone.
        entity["render"] = {"relative": relative, "properties": props, "body": body}
        return self._write(data, "input", relative, "input-item-" + key, props, body)

    def _input_link(self, data: dict, item_id: str, label: str) -> str:
        key = entity_key(item_id)
        if "input-item-" + key in data["notes"]:
            return f"[[10-Inputs/input-{key}\\|{cell(label)}]]"
        return cell(label)

    # Analysis runs --------------------------------------------------------
    def publish_analysis(self, run: dict, snapshot: dict, result: dict, artifacts: list[dict],
                         table_fields: dict[str, list[str]]) -> dict[str, str]:
        with VAULT_LOCK:
            data = self.load()
            item_id = str(run["item_id"])
            title = str(snapshot.get("title") or item_id)
            members = run_members(snapshot)
            if not members and "input-item-" + entity_key(item_id) not in data["notes"]:
                source = snapshot.get("original_source") or {}
                self._input(data, item_id=item_id, title=title,
                            segments=source.get("segments") or snapshot.get("segments", []),
                            revision=int(run["source_revision"]), session_profile=source.get("session_profile"),
                            source_kind="saved")
            by_name = {artifact["name"]: artifact for artifact in artifacts}
            outcomes: dict[str, list[str]] = {kind: [] for kind in GENERATED}
            try:
                outcomes["input"].append(
                    self._snapshot(data, run, snapshot, title, by_name.get("input.json"))
                )
            except (OSError, ValueError, LookupError, TypeError):
                outcomes["input"].append("failed")
            for method_id, method_title, datasets in METHODS:
                try:
                    outcomes["orchestrator"].append(
                        self._method_card(data, method_id, method_title, datasets)
                    )
                except (OSError, ValueError, LookupError, TypeError):
                    outcomes["orchestrator"].append("failed")
            visuals = {}
            for method in result.get("methods", []):
                if not re.fullmatch(r"[a-z_]+", str(method.get("method_id", ""))):
                    raise ValueError("手法IDが不正です。")
                try:
                    visual = self._visual(data, run, title, method, by_name, table_fields, members)
                    if visual:
                        note_id, status = visual
                        visuals[method["method_id"]] = note_id
                        outcomes["visualization"].append(status)
                except (OSError, ValueError, LookupError, TypeError):
                    outcomes["visualization"].append("failed")
            try:
                outcomes["orchestrator"].append(
                    self._run(data, run, title, result, artifacts, visuals, members)
                )
            except (OSError, ValueError, LookupError, TypeError):
                outcomes["orchestrator"].append("failed")
            for kind in GENERATED:
                try:
                    self._finish(data, (kind,))
                    outcomes[kind].append("unchanged")
                except (OSError, ValueError, LookupError, TypeError):
                    outcomes[kind].append("failed")

            def aggregate(values: list[str]) -> str:
                if "conflict" in values:
                    return "conflict"
                if "failed" in values:
                    return "failed"
                # A note the researcher deleted is left out on purpose (vault_note_policy);
                # the save screen and the sync note report it.
                return "published"

            return {kind: aggregate(values) for kind, values in outcomes.items()}

    def _snapshot(self, data: dict, run: dict, snapshot: dict, title: str, artifact: dict | None) -> str:
        item_id = str(run["item_id"])
        snapshot_id = str(run["snapshot_id"])
        note_id = "input-snapshot-" + snapshot_id
        entity = data["entities"].setdefault(note_id, {"runs": []})
        entity["runs"] = sorted({*entity["runs"], run["id"]})
        members = run_members(snapshot)
        if members:
            source_ids = [str(member.get("conversation_id")) for member in members]
            summary = f"インタビュー比較の入力。{len(members)}件の会話と各revisionを固定。"
            body = (f"# 比較入力：{markdown(title)}\n\n"
                    "各インタビューの分析とは別に保存した、複数会話の比較入力です。\n\n"
                    f"| 項目 | 値 |\n| --- | --- |\n| input_snapshot_id | {code(snapshot_id)} |\n"
                    f"| 比較グループ | {cell(snapshot.get('comparison_key') or '指定なし（異なる内容を含む）')} |\n\n"
                    "## 構成会話\n\n| 会話 | conversation_id | source / analysis revision |\n| --- | --- | --- |\n"
                    + "".join(f"| {self._input_link(data, str(member.get('conversation_id')), member.get('title', ''))} | "
                              f"{code(member.get('conversation_id'))} | {int(member.get('source_revision') or 0)} / "
                              f"{int(member.get('analysis_revision') or 0)} |\n" for member in members))
        else:
            source_ids = [item_id]
            segments = snapshot.get("segments", [])
            excluded = sum(1 for segment in segments if segment.get("excluded"))
            config = snapshot.get("config") if isinstance(snapshot.get("config"), dict) else {}
            summary = (f"分析入力スナップショット。対象{len(segments) - excluded}発話（除外{excluded}）、"
                       f"source revision {int(run['source_revision'])}、analysis revision {int(run['analysis_revision'])}。")
            body = (f"# 分析入力：{markdown(title)}\n\n[[10-Inputs/input-{entity_key(item_id)}|入力台帳]]\n\n"
                    "| 項目 | 値 |\n| --- | --- |\n"
                    f"| input_snapshot_id | {code(snapshot_id)} |\n"
                    f"| source / analysis revision | {int(run['source_revision'])} / {int(run['analysis_revision'])} |\n"
                    f"| 対象発話 / 除外 | {len(segments) - excluded} / {excluded} |\n"
                    f"| 分析条件の項目 | {cell('、'.join(sorted(map(str, config))) or 'なし', 400)} |\n")
        if artifact:
            body += f"\n固定入力：`input.json` / artifact {code(artifact['id'])} / sha256 {code(artifact['sha256'])}\n"
        body += ("\n## この入力を使った実行\n\nOrchestrator の `20-Runs` で run_id を検索します。\n\n"
                 + "\n".join("- " + code(value) for value in entity["runs"]) + "\n")
        return self._write(data, "input", f"20-Snapshots/snapshot-{snapshot_id[:16]}.md", note_id, {
            "note_type": "comparison-snapshot" if members else "input-snapshot", "title": f"{title}：分析入力",
            "summary": summary, "source_ids": source_ids, "artifact_ids": [artifact["id"]] if artifact else [],
            "conversation_ids" if members else "conversation_id": source_ids if members else item_id,
            "input_snapshot_id": snapshot_id, "revision": int(run["source_revision"]),
            "source_hash": "sha256:" + artifact["sha256"] if artifact else "",
            "status": "current", "sensitivity": "restricted", "tags": ["gurumoji/input"]}, body)

    def _method_card(self, data: dict, method_id: str, title: str, datasets: list[str]) -> str:
        group_id, group_title, description = method_group(method_id)
        body = (f"# {markdown(title)}\n\n| 項目 | 値 |\n| --- | --- |\n| method_id | {code(method_id)} |\n"
                f"| 分類 | {cell(group_title)} |\n| 登録版 | {code(REGISTRY_VERSION)} |\n\n{markdown(description)}\n\n"
                "## 出力表\n\n" + ("\n".join(f"- `tables/{name}.csv`" for name in datasets) or "- なし（ノートのみ）")
                + "\n\n## 実行状態の区別\n\n| 状態 | 表示 |\n| --- | --- |\n"
                + "".join(f"| {code(key)} | {cell(label)} |\n" for key, label in METHOD_STATUS_LABELS.items())
                + "\n## 実行前後に確認するゲート\n\n" + "\n".join(f"- [ ] {text}" for text in GATES)
                + f"\n\n手法の定義・限界・査読文献は Software Vault の `50-Analysis-Methods` で {code(method_id)} を検索します。"
                "この手法の実行記録はバックリンクから開けます。\n")
        return self._write(data, "orchestrator", f"10-Methods/{method_id}.md", "orchestrator-method-" + method_id, {
            "note_type": "method-card", "title": title,
            "summary": f"{group_title}の手法。出力表：{'、'.join(datasets) or 'なし'}。",
            "method_id": method_id, "method_group": group_id, "revision": REGISTRY_VERSION,
            "source_hash": "sha256:" + sha256(canonical([method_id, title, datasets, group_id])),
            "status": "current", "tags": ["gurumoji/orchestrator", "gurumoji/method"]}, body)

    def _visual(self, data: dict, run: dict, title: str, method: dict, by_name: dict,
                table_fields: dict[str, list[str]], members: list[dict]) -> tuple[str, str] | None:
        method_id = method["method_id"]
        if method.get("status") in {"not_run", "unavailable"}:
            return None  # Shared tables (e.g. insights) must not look like this method's output.
        tables = [(name, by_name.get(f"tables/{name}.csv")) for name in method.get("datasets", [])]
        tables = [(name, artifact) for name, artifact in tables if artifact and artifact.get("rows")]
        if not tables:
            return None
        group_id, group_title, _ = method_group(method_id)
        stale = bool(run.get("stale"))
        rows = sum(int(artifact["rows"]) for _, artifact in tables)
        label = status_label(method.get("status"))
        body = (f"# {markdown(method['title'])}：{markdown(title)}\n\n[[00-Index|索引]]\n\n## 問い\n\n"
                f"{GROUP_QUESTIONS.get(group_id, method['title'] + 'の結果を、固定した表の値で比較する。')}\n\n"
                "## 図表仕様\n\n")
        for name, artifact in tables:
            fields = [field for field in table_fields.get(name, []) if field not in COMMON_EXPORT_FIELDS]
            chart, x, y, alt = chart_spec(name, fields, int(artifact["rows"]))
            body += (f"### {markdown(name)}\n\n| 項目 | 値 |\n| --- | --- |\n| 推奨表示 | {chart} |\n"
                     f"| 横軸・分類 | {code(x) if x else '研究者が選ぶ'} |\n| 値 | {code(y) if y else '研究者が選ぶ'} |\n"
                     f"| データ | " + (f"[CSV書出し]({run['app_url']}{artifact['url']})" if artifact.get('generated') else f"`tables/{name}.csv`") + f" / artifact {code(artifact['id'])} / {int(artifact['rows'])}行 |\n"
                     f"| sha256 | {code(artifact['sha256'])} |\n"
                     f"| 列 | {cell(', '.join(fields[:24]) or '列情報なし', 600)} |\n\n"
                     f"代替テキスト：{markdown(alt)}\n\n")
        body += (f"## 読み取りの注意\n\n- 状態：{cell(label)}" + ("（入力変更後。再保存が必要）" if stale else "") + "\n"
                 "- 図は保存時点の固定CSVから作ります。画面のプレビュー行数に依存しません。\n"
                 + "".join(f"- {cell(value, 300)}\n" for value in method.get("limitations", [])[:5])
                 + f"\n実行記録は Orchestrator の `20-Runs` で run_id {code(run['id'])} を検索します。\n\n"
                 "## 解釈\n\n研究者が記入します。記入するとこのノートの自動更新は止まり、記入内容を保持します。\n")
        source_ids = [str(member.get("conversation_id")) for member in members] or [str(run["item_id"])]
        note_id = f"visual-{run['id']}-{method_id}"
        status = self._write(data, "visualization", f"10-Visuals/run-{run['id']}/{method_id}.md", note_id, {
            "note_type": "visual-spec", "title": f"{method['title']}：{title}",
            "summary": f"{method['title']}の図表仕様。{len(tables)}表・計{rows}行。状態：{label}" + ("（更新が必要）。" if stale else "。"),
            "source_ids": source_ids, "artifact_ids": [artifact["id"] for _, artifact in tables],
            "conversation_id": str(run["item_id"]), "run_id": run["id"], "method_id": method_id,
            "method_group": group_id, "revision": int(run["analysis_revision"]),
            "source_hash": "sha256:" + sha256(canonical(sorted(artifact["sha256"] for _, artifact in tables))),
            "status": "stale" if stale else "current", "tags": ["gurumoji/visualization"]}, body)
        return note_id, status

    def _run(self, data: dict, run: dict, title: str, result: dict, artifacts: list[dict],
             visuals: dict[str, str], members: list[dict]) -> str:
        stale = bool(run.get("stale"))
        methods = result.get("methods", [])
        rows = {artifact["name"]: artifact.get("rows") for artifact in artifacts}
        counts: dict[str, int] = {}
        for method in methods:
            counts[status_label(method.get("status"))] = counts.get(status_label(method.get("status")), 0) + 1
        manifest = next((artifact for artifact in artifacts if artifact["name"] == "manifest.json"), None)
        body = (f"# 実行記録：{markdown(title)}\n\n[[00-Index|索引]]\n\n## 実行計画\n\n| 項目 | 値 |\n| --- | --- |\n"
                f"| run_id | {code(run['id'])} |\n| 種別 | {code(run['kind'])} |\n| 作成 | {cell(run['created_at'])} |\n")
        if members:
            body += (f"| 比較ID | {code(run['item_id'])} |\n| input_snapshot_id | {code(run['snapshot_id'])} |\n"
                     f"| fingerprint | {code(run['fingerprint'])} |\n\n"
                     "## 比較したインタビュー\n\n各インタビューの分析とは別の実行です。\n\n"
                     "| 会話 | conversation_id | source / analysis revision |\n| --- | --- | --- |\n"
                     + "".join(f"| {cell(member.get('title'))} | {code(member.get('conversation_id'))} | "
                               f"{int(member.get('source_revision') or 0)} / {int(member.get('analysis_revision') or 0)} |\n"
                               for member in members))
        else:
            body += (f"| conversation_id | {code(run['item_id'])} |\n| input_snapshot_id | {code(run['snapshot_id'])} |\n"
                     f"| source / analysis revision | {int(run['source_revision'])} / {int(run['analysis_revision'])} |\n"
                     f"| fingerprint | {code(run['fingerprint'])} |\n"
                     f"| provider / model | {cell(run.get('provider') or '-')} / {cell(run.get('model') or '-')} |\n")
        body += "\n## 手法と状態\n\n| 手法 | 状態 | 出力表（行数） | 可視化ノート |\n| --- | --- | --- | --- |\n"
        for method in methods:
            tables = "、".join(f"{name}（{rows.get(f'tables/{name}.csv') or 0}）" for name in method.get("datasets", []))
            body += (f"| [[10-Methods/{method['method_id']}\\|{cell(method['title'])}]] | {cell(status_label(method.get('status')))} | "
                     f"{cell(tables or '-', 300)} | {code(visuals[method['method_id']]) if method['method_id'] in visuals else '-'} |\n")
        warnings = [f"{method['title']}：{status_label(method.get('status'))}" for method in methods
                    if method.get("status") in {"fallback", "unavailable", "partial", "stale", "empty", "not_run"}]
        if stale:
            warnings.insert(0, "保存後に入力・話者・分析条件が変わりました。分析画面から再保存してください。")
        body += "\n## 警告\n\n" + ("\n".join("- " + cell(value, 300) for value in warnings) or "- なし") + "\n"
        findings = sum(len(method.get("findings", [])) for method in methods)
        actions = ["自動値から合意・因果・重要性・本人の感情を断定しない。"]
        if findings:
            actions.insert(0, f"見解{findings}件の根拠発話を ResearchVault の分析まとめで確認する。")
        if run["kind"] in {"ai_insights", "ai_finishing"}:
            actions.append("AIの出力を研究者のコード・メモへ自動反映しない。")
        if run["kind"] == "meeting_minutes":
            actions.insert(0, "タスク候補の担当・期限・決定事項を元発話で確認してから共有する。")
        if members:
            actions.insert(0, "比較グループ・質問ガイドが揃っているか確認し、差を原因や一般化として扱わない。")
        body += "\n## 次に人が判断すること\n\n" + "\n".join("- [ ] " + value for value in actions) + "\n"
        algorithms = result.get("algorithms") if isinstance(result.get("algorithms"), dict) else {}
        parameters = result.get("parameters") if isinstance(result.get("parameters"), dict) else {}
        body += "\n## 実行環境と条件\n\n| 項目 | 値 |\n| --- | --- |\n"
        for key, value in algorithms.items():
            text = json.dumps(value, ensure_ascii=False)
            body += f"| {cell(key)} | {code(text if len(text) <= 200 else text[:200] + '…')} |\n"
        body += f"| パラメーター項目 | {cell('、'.join(sorted(map(str, parameters))) or 'なし', 400)} |\n"
        body += "\n## 成果物\n\n| ファイル | artifact_id | 行数 | bytes | sha256 |\n| --- | --- | ---: | ---: | --- |\n"
        body += "".join(f"| {code(artifact['name'])} | {code(artifact['id'])} | {artifact.get('rows') if artifact.get('rows') is not None else '-'} | "
                        f"{int(artifact['bytes']) if artifact['bytes'] is not None else '取得時に生成'} | "
                        f"{code(artifact['sha256'][:16])}{'（行hash）' if artifact.get('generated') else ''} |\n" for artifact in artifacts)
        summary = "、".join(f"{label}{count}" for label, count in counts.items()) or "手法なし"
        source_ids = [str(member.get("conversation_id")) for member in members] or [str(run["item_id"])]
        properties = {
            "note_type": "analysis-run", "title": f"{title}：{run['kind']}",
            "summary": f"{run['kind']}の実行記録。{summary}。" + ("入力変更後で更新が必要。" if stale else ""),
            # Keep YAML small for L1 retrieval: the manifest resolves every artifact listed in the body.
            "source_ids": source_ids, "artifact_ids": [manifest["id"]] if manifest else [],
            "run_id": run["id"], "input_snapshot_id": run["snapshot_id"],
            "fingerprint": run["fingerprint"], "revision": int(run["analysis_revision"]),
            "source_hash": "sha256:" + manifest["sha256"] if manifest else "",
            "run_status": run["status"], "review_status": "unreviewed",
            "status": "stale" if stale else "current", "tags": ["gurumoji/orchestrator", "gurumoji/run"]}
        if members:
            properties["conversation_ids"] = source_ids
        else:
            properties["conversation_id"] = str(run["item_id"])
        return self._write(data, "orchestrator", f"20-Runs/run-{run['id']}.md", "orchestrator-run-" + run["id"],
                           properties, body)
