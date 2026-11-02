"""Immutable analysis artifacts, SQLite catalog, and evidence-linked Vault notes.

The artifact catalog commits before Vault publication. A failed or edited Vault
can be retried from the saved package without repeating analysis or AI calls.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import html
import io
import json
import logging
import os
import re
import threading
import uuid
import unicodedata
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from urllib.parse import quote, urlencode

from .analysis_method_registry import REGISTRY_VERSION, METHOD_GROUPS
from .analysis_core import PUBLICATION_TARGETS, EFFECTIVE_PUBLICATION_WRITERS, validate_publication_targets
from .services.durable_files import write_durably
from .services import analysis_package as package_v2

LOGGER = logging.getLogger(__name__)
STORE_LOCK = threading.RLock()
STORE_VERSION = 2
TABLE_FORMAT_VERSION = 1


class StoreConflict(ValueError):
    pass


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def initialize_store(connection) -> None:
    package_v2.initialize(connection)
    connection.execute("INSERT OR IGNORE INTO application_metadata(key,value) VALUES ('library_id',?)", (uuid.uuid4().hex,))
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_runs (
        id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE, item_id TEXT NOT NULL,
        kind TEXT NOT NULL, fingerprint TEXT NOT NULL, input_fingerprint TEXT NOT NULL,
        snapshot_id TEXT NOT NULL, source_revision INTEGER NOT NULL, analysis_revision INTEGER NOT NULL,
        created_at TEXT NOT NULL, status TEXT NOT NULL, vault_status TEXT NOT NULL DEFAULT 'pending',
        stale INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '',
        note_path TEXT NOT NULL DEFAULT '', app_url TEXT NOT NULL DEFAULT '',
        provider TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '')""")
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_publication_attempts (
        attempt_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, sequence INTEGER NOT NULL,
        package_hash TEXT NOT NULL, requested_json TEXT NOT NULL, effective_json TEXT NOT NULL,
        executed_json TEXT NOT NULL DEFAULT '[]', outcomes_json TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL, error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, ended_at TEXT,
        UNIQUE(run_id,sequence))""")
    for attempt in connection.execute("SELECT attempt_id,outcomes_json FROM analysis_publication_attempts WHERE status='publishing'").fetchall():
        outcomes = json.loads(attempt["outcomes_json"])
        for value in outcomes.values():
            if value.get("status") == "pending":
                value.update(status="unknown", error="再起動で公開結果の確認が中断されました。")
        connection.execute("UPDATE analysis_publication_attempts SET status='incomplete',outcomes_json=?,error=?,ended_at=? WHERE attempt_id=?",
                           (canonical(outcomes).decode(), "公開試行が中断されました。", datetime.now(timezone.utc).isoformat(), attempt["attempt_id"]))
    connection.execute("CREATE INDEX IF NOT EXISTS analysis_runs_item ON analysis_runs(item_id,created_at)")
    if 'reuse_fingerprint' not in {row[1] for row in connection.execute('PRAGMA table_info(analysis_runs)')}:
        connection.execute("ALTER TABLE analysis_runs ADD COLUMN reuse_fingerprint TEXT NOT NULL DEFAULT ''")
    connection.execute("CREATE INDEX IF NOT EXISTS analysis_runs_reuse ON analysis_runs(item_id,reuse_fingerprint,status)")
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_save_requests (
        request_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, fingerprint TEXT NOT NULL)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_artifacts (
        id TEXT PRIMARY KEY, run_id TEXT NOT NULL, path TEXT NOT NULL,
        name TEXT NOT NULL, media_type TEXT NOT NULL, sha256 TEXT NOT NULL,
        bytes INTEGER NOT NULL, rows INTEGER, UNIQUE(run_id,path))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS obsidian_notes (
        path TEXT PRIMARY KEY, note_id TEXT NOT NULL UNIQUE, item_id TEXT NOT NULL,
        sha256 TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_pending_packages (
        run_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL)""")
    # A multi-conversation run (interview comparison) records every member conversation.
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_run_members (
        run_id TEXT NOT NULL, item_id TEXT NOT NULL, PRIMARY KEY(run_id,item_id))""")
    connection.execute("CREATE INDEX IF NOT EXISTS analysis_run_members_item ON analysis_run_members(item_id)")
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_run_groups (
        run_id TEXT NOT NULL, group_id TEXT NOT NULL, PRIMARY KEY(run_id,group_id))""")
    connection.execute("CREATE INDEX IF NOT EXISTS analysis_run_groups_group ON analysis_run_groups(group_id)")
    connection.execute("""CREATE TRIGGER IF NOT EXISTS analysis_store_member_changed
        AFTER UPDATE OF segments_json,speaker_names_json,speaker_profiles_json,session_profile_json,
            analysis_config_json,analysis_annotations_json,revision_count,analysis_revision,outline_json,emotion_analysis_json ON library_items
        BEGIN UPDATE analysis_runs SET stale=1
            WHERE id IN (SELECT run_id FROM analysis_run_members WHERE item_id=NEW.id); END""")
    connection.execute("""CREATE TRIGGER IF NOT EXISTS analysis_store_input_changed
        AFTER UPDATE OF segments_json,speaker_names_json,speaker_profiles_json,session_profile_json,
            analysis_config_json,analysis_annotations_json,revision_count,analysis_revision,outline_json,emotion_analysis_json ON library_items
        BEGIN UPDATE analysis_runs SET stale=1 WHERE item_id=NEW.id; END""")
    connection.execute("""CREATE TRIGGER IF NOT EXISTS analysis_store_speaker_changed
        AFTER UPDATE ON speaker_registry BEGIN UPDATE analysis_runs SET stale=1; END""")
    connection.execute("""CREATE TRIGGER IF NOT EXISTS analysis_store_registry_changed
        AFTER UPDATE OF value ON application_metadata WHEN NEW.key='speaker_registry_revision'
        BEGIN UPDATE analysis_runs SET stale=1; END""")
    connection.execute("UPDATE analysis_runs SET status='interrupted',error='保存が中断されました。再保存してください。' WHERE status='writing'")


def safe_path(root: Path, relative: str) -> Path:
    if not relative or "\\" in relative or ":" in relative:
        raise ValueError("保存パスが正しくありません。")
    parts = Path(relative).parts
    if Path(relative).is_absolute() or any(part in {"..", "."} for part in parts):
        raise ValueError("保存先の外は参照できません。")
    # Detect links in each component, including the configured root itself.
    target = root / relative
    for part in [root, *root.parents, *target.parents, target]:
        if part.is_symlink() or getattr(part, "is_junction", lambda: False)():
            raise ValueError("リンクを経由する保存先には書き出せません。")
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("保存先の外は参照できません。")
    return target


def _artifact_member_key(name: str) -> str:
    """Validate portable ZIP-member syntax without repairing the stored name.

    Filesystem containment remains safe_path's responsibility. Output stem
    sanitizers would silently rename immutable members, so they cannot be used here.
    """
    if (not isinstance(name, str) or not name or name.startswith("/")
            or re.search(r'[<>:"\\|?*\x00-\x1f\x7f]', name)):
        raise StoreConflict("固定packageのファイル名が安全な相対パスではありません。")
    parts = name.split("/")
    if any(part in {"", ".", ".."} or part.endswith((".", " ")) or PureWindowsPath(part).is_reserved() for part in parts):
        raise StoreConflict("固定packageのファイル名に未対応のパス要素があります。")
    if len(name.encode("utf-8")) > 65535:
        raise StoreConflict("固定packageのファイル名がZIPの上限を超えています。")
    # Case-insensitive / normalization-insensitive destinations must not overwrite
    # another member. The original spelling and file bytes are never changed.
    return unicodedata.normalize("NFC", name).casefold()


def write_atomic(path: Path, data: bytes, *, create_only: bool = False) -> None:
    # One implementation with the transcript outputs: folder sync and lock retries included (ARCH-04, OBS-17).
    write_durably(path, data, create_only=create_only)


def markdown(value) -> str:
    text = html.escape(str(value or ""), quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|^~$])", r"\\\1", text)


# Windows without long-path support fails at 260 characters; stay below it with a margin (OBS-14).
PATH_LIMIT = 250 if os.name == "nt" else 4000


def fit_name(stem: str, available: int) -> str:
    """Shorten ``stem`` to ``available`` characters, kept unique and stable by a short hash."""
    if len(stem) <= available:
        return stem
    tag = "-" + hashlib.sha256(stem.encode("utf-8")).hexdigest()[:8]
    keep = max(0, available - len(tag))
    return stem[:keep].rstrip(" ._-") + tag if keep else tag[1:]


def graph_node_path(run_dir: str, prefix: str, label: str, root: Path | None = None) -> str:
    """Make readable, filesystem-safe names for nodes shown in Obsidian Graph.

    With ``root``, the name is shortened when the full path would pass PATH_LIMIT.
    """
    clean = re.sub(r'[\\/:*?"<>|#^\[\]%\x00-\x1f]', "_", str(label)).strip(" ._")
    clean = re.sub(r"\s+", " ", clean)[:72] or "結果"
    stem = f"{prefix}-{clean}"
    if root is not None:
        over = len(str(Path(root) / run_dir / "graph" / (stem + ".md"))) - PATH_LIMIT
        if over > 0:
            stem = fit_name(stem, max(12, len(stem) - over))
    return f"{run_dir}/graph/{stem}.md"


def csv_bytes(fields: list[str], rows: list[dict]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        values = {}
        for key in fields:
            value = row.get(key)
            if value is None: value = ""
            elif isinstance(value, (dict, list, tuple)): value = json.dumps(value, ensure_ascii=False)
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                value = "'" + value
            values[key] = value
        writer.writerow(values)
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


def _table_value_type(value):
    if value is None:
        return "null"
    for kind, name in ((bool, "boolean"), (int, "integer"), (float, "number"), (str, "string")):
        if isinstance(value, kind):
            return name
    if isinstance(value, (list, tuple)):
        for child in value:
            _table_value_type(child)
        return "array"
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for child in value.values():
            _table_value_type(child)
        return "object"
    raise StoreConflict("型付き表にJSONで保持できない値があります。")


def table_package(name, fields, rows, *, run_id, snapshot_id, source_revision, analysis_revision):
    """Keep full typed values; absent keys and unknown semantics stay explicit."""
    if (not isinstance(fields, (list, tuple)) or any(not isinstance(f, str) for f in fields)
            or len(set(fields)) != len(fields) or not isinstance(rows, (list, tuple))
            or any(not isinstance(row, dict) or any(not isinstance(k, str) for k in row) for row in rows)):
        raise StoreConflict("型付き表の列・行形式が正しくありません。")
    names = list(fields) + sorted({key for row in rows for key in row} - set(fields))
    columns = []
    for key in names:
        columns.append({"name": key,
                        "observed_types": sorted({_table_value_type(row[key]) for row in rows if key in row}),
                        "absent_count": sum(key not in row for row in rows),
                        "null_count": sum(key in row and row[key] is None for row in rows)})
    return {"format": "gurumoji.analysis-table", "schema_version": TABLE_FORMAT_VERSION,
            "dataset_id": name, "run_id": run_id, "input_snapshot_id": snapshot_id,
            "source_revision": source_revision, "analysis_revision": analysis_revision,
            "fields": list(fields), "columns": columns, "row_count": len(rows),
            "rows": [{"row_id": f"{name}:{index}", "values": copy.deepcopy(row)}
                     for index, row in enumerate(rows, 1)]}


def _read_typed_json(data):
    def object_pairs(pairs):
        value = {}
        for key, child in pairs:
            if key in value:
                raise StoreConflict("型付き表のJSONキーが重複しています。")
            value[key] = child
        return value
    def reject_constant(_value):
        raise StoreConflict("型付き表に非有限値があります。")
    return json.loads(data, object_pairs_hook=object_pairs, parse_constant=reject_constant)


def frontmatter(note_id: str, title: str, **properties) -> str:
    data = {"note_id": note_id, "note_type": "analysis-result", "title": title,
            "schema_version": STORE_VERSION, "managed_by": "gurumoji", **properties}
    return "---\n" + "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in data.items()) + "\n---\n\n"


class AnalysisStore:
    def __init__(self, database_file: Path, connect):
        from .obsidian_layout import ObsidianLayout
        from .vault_registry import VaultRegistry
        self.layout = ObsidianLayout(database_file)
        self.vaults = VaultRegistry(database_file)
        self.connect = connect
        self.root = Path(database_file).parent / "analysis_store"
        self.vault = Path(database_file).parent / "obsidian" / "ResearchVault"
        self._last_publication_outcomes: dict[str, dict[str, dict[str, str]]] = {}
        self.note_log = Path(database_file).parent / "obsidian_layout" / "note_changes.jsonl"
        self.run_notes = Path(database_file).parent / "obsidian_layout" / "run_notes"
        self._note_events: list = []

    def export_artifacts(self, run_id: str) -> list[dict]:
        artifacts = self.artifacts(run_id)
        manifest_artifact = next((a for a in artifacts if a['name'] == 'manifest.json'), None)
        if not manifest_artifact:
            return artifacts
        manifest = json.loads(self.read_artifact(manifest_artifact['id'])[1])
        if manifest.get('schema_version') != 2:
            return artifacts
        for name, entry in manifest.get('typed_tables', {}).items():
            artifacts.append({'id': run_id + '.' + name, 'run_id': run_id,
                'name': f'tables/{name}.csv', 'media_type': 'text/csv', 'rows': entry['row_count'],
                'bytes': None, 'sha256': entry['rows_hash'], 'generated': True,
                'url': f'/api/analysis/runs/{run_id}/tables/{name}.csv'})
        return artifacts

    def table_csv(self, run_id: str, name: str) -> bytes:
        table = self.read_table(run_id, name)
        return csv_bytes(table['fields'], [r['values'] for r in table['rows']])

    def readable_package(self, run_id: str):
        try:
            return self.verified_package(run_id)
        except package_v2.MissingReference as exc:
            if exc.recoverable:
                manifest = json.loads(self.read_artifact(next(a['id'] for a in self.artifacts(run_id)
                    if a['name'] == 'manifest.json'))[1])
                snapshot = json.loads(self.read_artifact(next(a['id'] for a in self.artifacts(run_id)
                    if a['name'] == 'input.json'))[1])
                status = package_v2.schedule_recovery(self, run_id, manifest['references'], snapshot)
                if status == 'ready':
                    return self.verified_package(run_id)
                exc.recovery_status = status
            raise

    def _publish_generated_vaults(self, run_id: str) -> dict[str, str]:
        """Mirror a completed run into the Input, Orchestrator, and Visualization Vaults.

        Those Vaults hold ID-linked summaries only. A failure there never changes
        the run, its artifacts, or the ResearchVault publication.
        """
        run = self.get(run_id)
        if not run or run["status"] != "completed":
            return {}
        try:
            snapshot, result, manifest, content = self.readable_package(run_id)
            artifacts = self.export_artifacts(run_id)
            fields = {}
            for artifact in artifacts:
                name = artifact["name"]
                if name.startswith("tables/") and name.endswith(".csv"):
                    dataset = name[7:-4]
                    if artifact.get('generated'):
                        entry = manifest['typed_tables'][dataset]
                        fields[dataset] = (manifest['references'][dataset]['fields'] if 'reference' in entry
                                           else json.loads(content[entry['data']])['fields'])
                    else:
                        table_content = content[name].decode('utf-8-sig')
                        fields[dataset] = next(csv.reader(io.StringIO(table_content)), [])
            self.vaults.note_events = []
            statuses = self.vaults.publish_analysis(run, snapshot, result, artifacts, fields)
            self._note_events.extend(self.vaults.note_events)
            outcomes = {
                kind: {"status": status, "error": "" if status == "published" else "公開先を確認してください。"}
                for kind, status in statuses.items()
            }
            self._last_publication_outcomes[run_id] = outcomes
            return statuses
        except (OSError, ValueError, LookupError, TypeError) as exc:
            LOGGER.warning("4 Vaultへの書き出しを完了できませんでした（%s）: %s", run_id, exc)
            outcomes = {kind: {"status": "failed", "error": str(exc)}
                        for kind in ("input", "orchestrator", "visualization")}
            self._last_publication_outcomes[run_id] = outcomes
            return {"error": str(exc)}

    def publication_attempts(self, run_id: str) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM analysis_publication_attempts WHERE run_id=? ORDER BY sequence", (run_id,),
            ).fetchall()
        return [{**{key: row[key] for key in ("attempt_id", "sequence", "package_hash", "status", "error", "created_at", "ended_at")},
                 **{key: json.loads(row[key + "_json"]) for key in ("requested", "effective", "executed", "outcomes")}}
                for row in rows]

    def publication_outcomes(self, run_id: str) -> dict[str, dict[str, str]]:
        """Only a durable attempt proves that these writers processed this package."""
        if not self.get(run_id):
            raise LookupError("保存結果がありません。")
        attempts = self.publication_attempts(run_id)
        if attempts:
            return copy.deepcopy(attempts[-1]["outcomes"])
        return {kind: {"status": "unknown", "error": "公開試行記録がなく、完了を確認できません。"}
                for kind in EFFECTIVE_PUBLICATION_WRITERS}

    def publish_vaults(self, run_id: str) -> dict[str, str]:
        """Compatibility entry point using the same scope and durable-attempt guard."""
        self.publish(run_id)
        return {kind: value["status"] for kind, value in self.publication_outcomes(run_id).items()
                if kind in PUBLICATION_TARGETS}

    def refresh_vaults(self, item_id: str) -> None:
        """Republish only runs whose stale state differs from their Orchestrator note.

        Comparisons that include this conversation are checked as well.
        Autonomous output requires its dedicated source/generation/attempt guard;
        generic refresh cannot authorize those writers.
        """
        with self.connect() as conn:
            rows = conn.execute("""SELECT id,stale FROM analysis_runs WHERE status='completed' AND kind!='autonomous_analysis' AND
                (item_id=? OR id IN (SELECT run_id FROM analysis_run_members WHERE item_id=?))""",
                                (item_id, item_id)).fetchall()
        for row in rows:
            try:
                current = self.vaults.run_status(row["id"])
            except (OSError, ValueError) as exc:
                LOGGER.warning("Vault台帳を読み込めませんでした: %s", exc)
                return
            if current != ("stale" if row["stale"] else "current"):
                self.publish_vaults(row["id"])

    def members(self, run_id: str) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute("SELECT item_id FROM analysis_run_members WHERE run_id=? ORDER BY item_id",
                                (run_id,)).fetchall()
        return [row[0] for row in rows]

    def list_comparisons(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("""SELECT * FROM analysis_runs WHERE kind='interview_comparison'
                ORDER BY created_at DESC,id DESC LIMIT 100""").fetchall()
        return [dict(row) for row in rows]

    def library_id(self) -> str:
        with self.connect() as conn:
            return conn.execute("SELECT value FROM application_metadata WHERE key='library_id'").fetchone()[0]

    def get(self, run_id: str):
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM analysis_runs WHERE id=?", (run_id,)).fetchone()
        return dict(row) if row else None

    def by_request(self, request_id: str):
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM analysis_runs WHERE request_id=?", (request_id,)).fetchone()
            if row is None:
                alias = conn.execute("SELECT r.*,q.fingerprint AS request_fingerprint FROM analysis_save_requests q JOIN analysis_runs r ON r.id=q.run_id WHERE q.request_id=?", (request_id,)).fetchone()
                if alias is not None:
                    value = dict(alias)
                    value['fingerprint'] = value.pop('request_fingerprint')
                    return value
        return dict(row) if row else None

    def list(self, item_id: str, *, limit: int = 100, offset: int = 0) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
            raise ValueError("履歴のページ指定が正しくありません。")
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM analysis_runs WHERE item_id=? ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?", (item_id, limit, offset)).fetchall()
        return [dict(row) for row in rows]

    def run_count(self, item_id: str) -> int:
        with self.connect() as conn:
            return conn.execute("SELECT count(*) FROM analysis_runs WHERE item_id=?", (item_id,)).fetchone()[0]

    def artifacts(self, run_id: str) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM analysis_artifacts WHERE run_id=? ORDER BY name", (run_id,)).fetchall()
        return [dict(row) for row in rows]

    def read_artifact(self, artifact_id: str):
        if re.fullmatch(r'[0-9a-f]{32}\.[a-z_]+', artifact_id):
            run_id, name = artifact_id.split('.')
            data = self.table_csv(run_id, name)
            return next(a for a in self.export_artifacts(run_id) if a['id'] == artifact_id), data
        with self.connect() as conn:
            row = conn.execute("""SELECT a.* FROM analysis_artifacts a JOIN analysis_runs r ON r.id=a.run_id
                WHERE a.id=? AND r.status='completed'""", (artifact_id,)).fetchone()
        if row is None: raise LookupError("保存済みファイルが見つかりません。")
        _artifact_member_key(row["name"])
        path = safe_path(self.root, row["path"])
        content = path.read_bytes()
        if len(content) != row["bytes"] or hashlib.sha256(content).hexdigest() != row["sha256"]:
            raise StoreConflict("保存済みファイルが外部で変更されています。")
        return dict(row), content

    def public(self, row: dict, *, local: bool = False) -> dict:
        result = {key: row[key] for key in ("id", "item_id", "kind", "source_revision", "analysis_revision",
                  "created_at", "status", "vault_status", "stale", "error", "provider", "model")}
        result.update({key: row.get(key) for key in ("fingerprint", "input_fingerprint", "snapshot_id")})
        result["artifacts"] = [{key: a[key] for key in ("id", "name", "media_type", "rows", "bytes", "sha256")}
                               for a in self.export_artifacts(row["id"])]
        for artifact in result["artifacts"]:
            artifact["url"] = (f"/api/analysis/runs/{row['id']}/tables/{artifact['name'][7:-4]}.csv"
                if '.' in artifact['id'] else f"/api/analysis/artifacts/{artifact['id']}")
        result["obsidian_uri"] = ("obsidian://open?" + urlencode({"path": str(self.vault / row["note_path"])})
                                    if local and row["note_path"] and row["vault_status"] == "completed" else "")
        result["vault_notes"] = self.vault_notes(row["id"])
        # One SQLite read snapshot: never mix outcomes and writer evidence from
        # different publication attempts that finish during this GET.
        with self.connect() as connection:
            connection.execute("BEGIN")
            attempts = connection.execute("SELECT * FROM analysis_publication_attempts WHERE run_id=? ORDER BY sequence", (row["id"],)).fetchall()
            result["publication_attempts"] = [
                {**{key: attempt[key] for key in ("attempt_id", "sequence", "package_hash", "status", "error", "created_at", "ended_at")},
                 **{key: json.loads(attempt[key + "_json"]) for key in ("requested", "effective", "executed", "outcomes")}}
                for attempt in attempts]
            result["publication_records"] = []
            if row["kind"] == "milestone_analysis" and connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE name='analysis_pipeline_publications'").fetchone():
                records = connection.execute("""SELECT target_role,status,error,result_run_id,package_hash
                    FROM analysis_pipeline_publications WHERE pipeline_id=(
                        SELECT pipeline_id FROM analysis_pipeline_requests WHERE result_run_id=?
                        ORDER BY created_at DESC,pipeline_id DESC LIMIT 1) ORDER BY target_role""", (row["id"],)).fetchall()
                result["publication_records"] = [dict(record) for record in records]
        latest = result["publication_attempts"][-1] if result["publication_attempts"] else {}
        all_outputs = latest.get("outcomes", {}) if latest else {
            kind: {"status": "unknown", "error": "公開試行記録がなく、完了を確認できません。"}
            for kind in EFFECTIVE_PUBLICATION_WRITERS}
        result["publication_outcomes"] = all_outputs
        result["vault_outputs"] = {kind: value for kind, value in all_outputs.items() if kind in PUBLICATION_TARGETS}
        requested = latest.get("requested", [])
        effective = latest.get("effective", [])
        executed = latest.get("executed", [])
        valid_scope = (isinstance(requested, list) and len(requested) == len(PUBLICATION_TARGETS)
                       and set(requested) == set(PUBLICATION_TARGETS)
                       and isinstance(effective, list) and len(effective) == len(EFFECTIVE_PUBLICATION_WRITERS)
                       and set(effective) == set(EFFECTIVE_PUBLICATION_WRITERS)
                       and isinstance(executed, list) and len(executed) == len(EFFECTIVE_PUBLICATION_WRITERS)
                       and set(executed) == set(EFFECTIVE_PUBLICATION_WRITERS))
        result["vault_outputs_complete"] = row["status"] == "completed" and bool(row.get("fingerprint")) and valid_scope and latest.get("status") == "completed" and latest.get("package_hash") == row.get("fingerprint") and all(
            kind in latest.get("effective", []) and kind in latest.get("executed", [])
            and all_outputs.get(kind, {}).get("status") == "published"
            for kind in EFFECTIVE_PUBLICATION_WRITERS)
        return result

    def _vault_outputs(self, row: dict) -> dict[str, dict[str, str]]:
        if row["status"] != "completed":
            return {}
        try:
            return {kind: value for kind, value in self.publication_outcomes(row["id"]).items()
                    if kind in PUBLICATION_TARGETS}
        except (OSError, ValueError, LookupError) as exc:
            return {kind: {"status": "unknown", "error": str(exc)}
                    for kind in ("input", "orchestrator", "visualization")}

    def save(self, *, item_id: str, kind: str, snapshot: dict, result: dict, datasets: dict,
             request_id: str, input_fingerprint: str, source_revision: int, analysis_revision: int,
             app_url: str = "http://127.0.0.1:7860", provider: str = "", model: str = "",
             member_ids: list[str] | None = None, check_cancelled=lambda: None,
             publish: bool = True, commit_guard=None, table_format_version=TABLE_FORMAT_VERSION,
             package_version=STORE_VERSION) -> dict:
        with STORE_LOCK:
            check_cancelled()
            library_id = self.library_id()
            snapshot = {**snapshot, "library_id": library_id}
            snapshot_id = digest(snapshot)
            identity = {"snapshot": snapshot_id, "kind": kind, "registry": REGISTRY_VERSION,
                        "input_fingerprint": input_fingerprint,
                        "algorithms": result.get("algorithms", {}), "parameters": result.get("parameters", {}),
                        "ai_request": result.get("ai_request_id", "")}
            inference = kind in {'ai_finishing', 'ai_insights'} or package_version == 2 and (kind in {"segment_classification", "transformer_topics",
                                 "autonomous_analysis", "milestone_analysis"} or any(
                datasets.get(name, ([], []))[1] for name in package_v2.LABEL_TABLES))
            if kind in {"ai_finishing", "ai_insights"} or package_version == 2 and inference:
                identity["request"] = request_id
            payload_hash = package_v2.input_hash(result, datasets)
            if package_version == 2:
                identity['package_version'] = 2
                identity['payload_hash'] = payload_hash
                identity.update(provider=provider, model=model, member_ids=list(member_ids or []),
                                source_revision=source_revision, analysis_revision=analysis_revision)
            fingerprint = digest(identity)
            # Q23: exact scientific content can share an immutable run. Request
            # identity remains separate, so resending an alias with new content
            # still conflicts. Never deduplicate from input alone.
            reusable_result = copy.deepcopy(result)
            for key in ('request_id', 'ai_request_id', 'generated_at'):
                reusable_result.pop(key, None)
            if isinstance(reusable_result.get('parameters'), dict):
                reusable_result['parameters'].pop('pipeline_id', None)
            for chart in reusable_result.get('chart_specs', []):
                if isinstance(chart, dict):
                    chart.pop('chart_id', None)
            reuse_identity = {**identity, 'payload_hash': package_v2.input_hash(reusable_result, datasets)}
            for key in ('request', 'ai_request'):
                reuse_identity.pop(key, None)
            if isinstance(reuse_identity.get('parameters'), dict):
                reuse_identity['parameters'] = {k:v for k,v in reuse_identity['parameters'].items() if k != 'pipeline_id'}
            reuse_fingerprint = digest(reuse_identity)
            previous = self.by_request(request_id)
            if previous and (previous["item_id"] != item_id or previous["fingerprint"] != fingerprint):
                raise StoreConflict("リクエストIDが別の入力に使われています。")
            if not previous:
                with self.connect() as conn:
                    match = conn.execute("SELECT * FROM analysis_runs WHERE (reuse_fingerprint=? OR (fingerprint=? AND ?=0)) AND item_id=? AND status='completed' ORDER BY created_at DESC LIMIT 1", (reuse_fingerprint, fingerprint, int(inference), item_id)).fetchone()
                if match: previous = dict(match)
            if previous and previous["status"] == "completed":
                if commit_guard is not None:
                    with self.connect() as connection:
                        connection.execute("BEGIN IMMEDIATE")
                        commit_guard(connection)
                self._verified_package(previous["id"])
                if previous['request_id'] != request_id:
                    with self.connect() as conn:
                        conn.execute("INSERT OR IGNORE INTO analysis_save_requests VALUES (?,?,?)", (request_id, previous['id'], fingerprint))
                if publish and previous["vault_status"] != "completed":
                    self.publish(previous["id"])
                elif publish:
                    try:
                        unpublished = self.vaults.run_status(previous["id"]) is None
                    except (OSError, ValueError):
                        unpublished = False
                    # Runs saved before the four Vaults existed are mirrored when saved again.
                    if unpublished:
                        self.publish_vaults(previous["id"])
                return self.get(previous["id"])
            run_id = previous["id"] if previous else uuid.uuid5(uuid.NAMESPACE_URL, library_id + request_id).hex
            now = previous["created_at"] if previous else datetime.now(timezone.utc).isoformat()
            result = copy.deepcopy(result)
            if "generated_at" in result.get("analysis", {}):
                result["analysis"]["generated_at"] = now
            pending = {"item_id": item_id, "kind": kind, "snapshot": snapshot, "result": result,
                       "datasets": datasets, "request_id": request_id, "input_fingerprint": input_fingerprint,
                       "source_revision": source_revision, "analysis_revision": analysis_revision,
                       "app_url": app_url, "provider": provider, "model": model,
                       "member_ids": list(member_ids or []), "publish": publish,
                       "package_version": package_version,
                       "table_format_version": table_format_version}
            with self.connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                if commit_guard is not None:
                    commit_guard(conn)
                if package_version == 2:
                    fixed = conn.execute('SELECT payload_hash FROM analysis_package_inputs WHERE run_id=?', (run_id,)).fetchone()
                    if fixed and fixed[0] != payload_hash:
                        raise StoreConflict('同じ実行IDに異なる入力・設定・結果は保存できません。')
                    conn.execute('INSERT OR IGNORE INTO analysis_package_inputs VALUES (?,?)', (run_id, payload_hash))
                conn.execute("""INSERT INTO analysis_runs(id,request_id,item_id,kind,fingerprint,input_fingerprint,
                    snapshot_id,source_revision,analysis_revision,created_at,status,app_url,provider,model)
                    VALUES (?,?,?,?,?,?,?,?,?,?,'writing',?,?,?) ON CONFLICT(id) DO UPDATE SET status='writing',error=''""",
                    (run_id, request_id, item_id, kind, fingerprint, input_fingerprint, snapshot_id,
                     source_revision, analysis_revision, now, app_url.rstrip("/"), provider, model))
                conn.execute("UPDATE analysis_runs SET reuse_fingerprint=? WHERE id=?", (reuse_fingerprint, run_id))
                conn.executemany("INSERT OR IGNORE INTO analysis_run_members(run_id,item_id) VALUES (?,?)",
                                 [(run_id, member) for member in (member_ids or [])])
                conn.executemany("INSERT OR IGNORE INTO analysis_run_groups(run_id,group_id) VALUES (?,?)",
                    [(run_id, group['group_id']) for group in result.get('parameters', {}).get('target_snapshot', {}).get('groups', [])])
                existing = conn.execute("SELECT payload_json FROM analysis_pending_packages WHERE run_id=?", (run_id,)).fetchone()
                if existing:
                    pending = json.loads(existing[0])
                    snapshot, result, datasets = pending['snapshot'], pending['result'], pending['datasets']
                    # A partial package must keep its original provenance as
                    # well as its values, even when the retry caller changed.
                    source_revision = pending['source_revision']
                    analysis_revision = pending['analysis_revision']
                    app_url, provider, model = pending['app_url'], pending['provider'], pending['model']
                else:
                    if table_format_version == TABLE_FORMAT_VERSION:
                        # Reject non-string object keys before pending JSON can
                        # silently stringify them on a later retry.
                        for _fields, rows in datasets.values():
                            for row in rows:
                                _table_value_type(row)
                    conn.execute("INSERT INTO analysis_pending_packages(run_id,payload_json) VALUES (?,?)", (run_id, canonical(pending).decode('utf-8')))
            try:
                version = pending.get('package_version', 1)
                if type(version) is not int or version not in (1, 2):
                    raise StoreConflict('保存packageの形式に対応していません。')
                table_version = pending.get("table_format_version")
                if table_version is not None and (type(table_version) is not int or table_version != TABLE_FORMAT_VERSION):
                    raise StoreConflict("再試行する表の保存形式に対応していません。")
                files = {"input.json": (canonical(snapshot), "application/json", None),
                         "parameters.json": (canonical(result.get("parameters", {})), "application/json", None),
                         "result.json": (canonical(result), "application/json", None)}
                references, table_mapping = {}, {}
                run_record = self.get(run_id)
                vectors = None
                if version == 2:
                    embedded = package_v2.embedding_reference(self, snapshot, result)
                    if embedded:
                        vectors, vector_rows, reference = embedded
                        datasets = {**datasets, 'segment_embeddings': (reference['fields'], vector_rows)}
                        references['segment_embeddings'] = reference
                for name, (fields, rows) in datasets.items():
                    if not re.fullmatch(r"[a-z_]+", name): raise ValueError("表の名前が正しくありません。")
                    if version == 2 or table_version == TABLE_FORMAT_VERSION:
                        table = table_package(name, fields, rows, run_id=run_id, snapshot_id=snapshot_id,
                                              source_revision=source_revision, analysis_revision=analysis_revision)
                        table_data = canonical(table)
                        # Export from the same JSON-compatible values, including
                        # tuple-to-array normalization, never from a display preview.
                        exported = json.loads(table_data)
                        rows = [row["values"] for row in exported["rows"]]
                        if version == 2:
                            entry = {'row_count': len(rows), 'rows_hash': digest(rows)}
                            if name == 'segment_embeddings':
                                entry['reference'] = name
                            elif name in {'morphemes', 'dependencies'}:
                                references[name] = package_v2.lexical_reference(self, name, fields, rows, snapshot, result)
                                entry['reference'] = name
                            elif name in package_v2.LABEL_TABLES:
                                references[name] = package_v2.label_reference(self, run_record, name, fields, rows, snapshot, result)
                                entry['reference'] = name
                            else:
                                files[f'tables/{name}.json'] = (table_data, 'application/json', len(rows))
                                entry['data'] = f'tables/{name}.json'
                            table_mapping[name] = entry
                        else:
                            files[f"tables/{name}.json"] = (table_data, "application/json", len(rows))
                    if version == 1:
                        files[f"tables/{name}.csv"] = (csv_bytes(fields, rows), "text/csv", len(rows))
                if version == 2:
                    document = package_v2.compact_document(result, datasets, vectors, snapshot)
                    document['schema_version'] = 2
                    files['documents/result.json'] = (canonical(document), 'application/json', None)
                    compact = {'schema_version': 2, 'parameters': result.get('parameters', {}),
                        'algorithms': result.get('algorithms', {}), 'document': 'documents/result.json',
                        'tables': table_mapping}
                    files['result.json'] = (canonical(compact), 'application/json', None)
                artifacts = []
                for name, (content, media_type, rows) in files.items():
                    check_cancelled()
                    relative = (f"inputs/{snapshot_id}/input.json" if name == "input.json" else f"runs/{run_id}/{name}")
                    target = safe_path(self.root, relative)
                    if target.exists():
                        if target.read_bytes() != content: raise StoreConflict("既存の固定結果を上書きできません。")
                    else: write_atomic(target, content)
                    artifacts.append({"id": uuid.uuid5(uuid.NAMESPACE_URL, run_id + name).hex,
                                      "run_id": run_id, "path": relative, "name": name,
                                      "media_type": media_type, "sha256": hashlib.sha256(content).hexdigest(),
                                      "bytes": len(content), "rows": rows})
                manifest = {"schema_version": version, "analysis_id": run_id, "library_id": library_id,
                            "conversation_id": item_id, "input_snapshot_id": snapshot_id,
                            "input_fingerprint": input_fingerprint, "fingerprint": fingerprint,
                            "kind": kind, "created_at": now, "source_revision": source_revision,
                            "analysis_revision": analysis_revision, "artifacts": artifacts,
                            "method_version": REGISTRY_VERSION, "provider": provider, "model": model}
                if version == 2:
                    manifest.update(table_format_version=TABLE_FORMAT_VERSION, typed_tables=table_mapping,
                                    references=references, document='documents/result.json')
                elif table_version == TABLE_FORMAT_VERSION:
                    manifest.update(table_format_version=table_version,
                                    typed_tables={name: {"data": f"tables/{name}.json", "export": f"tables/{name}.csv"}
                                                  for name in datasets})
                content = canonical(manifest)
                target = safe_path(self.root, f"runs/{run_id}/manifest.json")
                if target.exists() and target.read_bytes() != content: raise StoreConflict("manifestが変更されています。")
                if not target.exists(): write_atomic(target, content)
                artifacts.append({"id": uuid.uuid5(uuid.NAMESPACE_URL, run_id + "manifest").hex,
                                  "run_id": run_id, "path": f"runs/{run_id}/manifest.json", "name": "manifest.json",
                                  "media_type": "application/json", "sha256": hashlib.sha256(content).hexdigest(),
                                  "bytes": len(content), "rows": None})
                check_cancelled()
                with self.connect() as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    if commit_guard is not None:
                        commit_guard(conn)
                    for artifact in artifacts:
                        conn.execute("""INSERT OR REPLACE INTO analysis_artifacts
                            (id,run_id,path,name,media_type,sha256,bytes,rows) VALUES (:id,:run_id,:path,:name,:media_type,:sha256,:bytes,:rows)""", artifact)
                    conn.execute("UPDATE analysis_runs SET status='completed',error='' WHERE id=?", (run_id,))
                    conn.execute("DELETE FROM analysis_pending_packages WHERE run_id=?", (run_id,))
            except Exception:
                with self.connect() as conn:
                    conn.execute("UPDATE analysis_runs SET status='failed',error='分析結果を保存できませんでした。再保存してください。' WHERE id=?", (run_id,))
                raise
            if publish:
                self.publish(run_id)
            return self.get(run_id)

    def retry(self, run_id: str) -> dict:
        with STORE_LOCK:
            run = self.get(run_id)
            if not run: raise LookupError("保存結果がありません。")
            if run['status'] == 'completed': return self.publish(run_id)
            if run['kind'] in {'milestone_analysis', 'autonomous_analysis'}:
                raise StoreConflict("未完了の固定保存は、その分析の専用画面から再試行してください。")
            with self.connect() as conn:
                row = conn.execute("SELECT payload_json FROM analysis_pending_packages WHERE run_id=?", (run_id,)).fetchone()
            if not row: raise StoreConflict("再保存用の入力がありません。分析画面から保存してください。")
            return self.save(**json.loads(row[0]))

    def _verified_package(self, run_id: str) -> tuple[dict, dict]:
        """Validate every immutable catalog artifact before any publication side effect."""
        snapshot, result, _manifest, _content = self.verified_package(run_id)
        return snapshot, result

    def verified_package(self, run_id: str) -> tuple[dict, dict, dict, dict[str, bytes]]:
        """Read the fixed package only; never recover, publish, stamp or rewrite it."""
        run = self.get(run_id)
        artifacts = self.artifacts(run_id)
        by_name = {artifact["name"]: artifact for artifact in artifacts}
        required = {"input.json", "result.json", "parameters.json", "manifest.json"}
        if not run or run["status"] != "completed" or not required <= by_name.keys():
            raise StoreConflict("固定packageが欠落しています。再計算せず停止しました。")
        member_keys = [_artifact_member_key(artifact["name"]) for artifact in artifacts]
        members = set(member_keys)
        if len(members) != len(member_keys) or any(
                "/".join(key.split("/")[:index]) in members
                for key in member_keys for index in range(1, len(key.split("/")))):
            raise StoreConflict("固定packageのファイル名が移動先で競合するため停止しました。")
        content = {artifact["name"]: self.read_artifact(artifact["id"])[1] for artifact in artifacts}
        manifest = json.loads(content["manifest.json"])
        if (not isinstance(manifest, dict) or manifest.get('schema_version') is not None
                and (type(manifest['schema_version']) is not int or manifest['schema_version'] not in (1, 2))):
            raise StoreConflict("固定packageの形式に対応していません。")
        entries = manifest.get("artifacts")
        if not isinstance(entries, list) or any(not isinstance(entry, dict) or not isinstance(entry.get("name"), str) for entry in entries):
            raise StoreConflict("固定packageのmanifest形式が正しくありません。")
        expected = {artifact["name"]: artifact for artifact in entries}
        actual = {name: artifact for name, artifact in by_name.items() if name != "manifest.json"}
        if (len(by_name) != len(artifacts) or len(expected) != len(manifest.get("artifacts", []))
                or expected != actual or manifest.get("analysis_id") != run_id
                or manifest.get("fingerprint") != run["fingerprint"]
                or manifest.get("input_snapshot_id") != run["snapshot_id"]):
            raise StoreConflict("固定packageのmanifestが一致しません。再計算せず停止しました。")
        snapshot, result = json.loads(content["input.json"]), json.loads(content["result.json"])
        if not isinstance(snapshot, dict) or not isinstance(result, dict):
            raise StoreConflict("固定packageのJSON形式が正しくありません。")
        if digest(snapshot) != run["snapshot_id"]:
            raise StoreConflict("固定packageの入力snapshot hashが一致しません。再計算せず停止しました。")
        if (result.get('schema_version') is not None
                and (type(result['schema_version']) is not int or result['schema_version'] not in (1, 2))):
            raise StoreConflict("固定結果の形式に対応していません。")
        parameters = json.loads(content["parameters.json"])
        if not isinstance(parameters, dict) or not isinstance(result.get("parameters", {}), dict):
            raise StoreConflict("固定packageの条件形式が正しくありません。")
        if parameters != result.get("parameters", {}):
            raise StoreConflict("固定packageの条件が一致しません。")
        if manifest.get('schema_version') == 2:
            result = self._verify_v2(run, snapshot, result, manifest, by_name, content)
        else:
            self._verify_typed_tables(run, manifest, by_name, content)
        return snapshot, result, manifest, content

    def _verify_v2(self, run, snapshot, result, manifest, artifacts, content):
        mapping, references = manifest.get('typed_tables'), manifest.get('references')
        if (not isinstance(mapping, dict) or not isinstance(references, dict)
                or type(manifest.get('table_format_version')) is not int
                or manifest['table_format_version'] != TABLE_FORMAT_VERSION
                or result.get('schema_version') != 2 or result.get('tables') != mapping
                or manifest.get('document') != 'documents/result.json'
                or result.get('document') != manifest['document']
                or set(references) != {name for name, entry in mapping.items() if 'reference' in entry}
                or {n for n in content if n.startswith('tables/')} !=
                   {f'tables/{n}.json' for n, entry in mapping.items() if 'data' in entry}):
            raise StoreConflict('版2の表・文書・参照の対応が一致しません。')
        tables = {}
        for name, entry in mapping.items():
            if not re.fullmatch(r'[a-z_]+', name) or set(entry) not in (
                    {'data','row_count','rows_hash'}, {'reference','row_count','rows_hash'}):
                raise StoreConflict('版2の表の形式が正しくありません。')
            if 'reference' in entry:
                if entry['reference'] != name:
                    raise StoreConflict('版2の参照先が一致しません。')
                reference = references[name]
                expected_kind = (name if name in {'morphemes','dependencies','segment_embeddings'}
                                 else 'segment_labels' if name in package_v2.LABEL_TABLES else None)
                if (type(reference.get('version')) is not int or reference['version'] != 1
                        or reference.get('kind') != expected_kind):
                    raise StoreConflict('版2のDB参照の形式版・種類に対応していません。')
                if reference.get('run_id', run['id']) != run['id']:
                    raise StoreConflict('推論結果の実行IDが一致しません。')
                rows = package_v2.resolve(self, name, reference, snapshot)
                table = table_package(name, reference['fields'], rows, run_id=run['id'],
                    snapshot_id=run['snapshot_id'], source_revision=run['source_revision'],
                    analysis_revision=run['analysis_revision'])
            else:
                if entry['data'] != f'tables/{name}.json':
                    raise StoreConflict('版2の表の参照先が一致しません。')
                table = _read_typed_json(content[entry['data']])
                rows = [r['values'] for r in table['rows']]
                expected = table_package(name, table['fields'], rows, run_id=run['id'],
                    snapshot_id=run['snapshot_id'], source_revision=run['source_revision'],
                    analysis_revision=run['analysis_revision'])
                artifact = artifacts[entry['data']]
                if canonical(table) != canonical(expected) or artifact['rows'] != len(rows) or artifact['media_type'] != 'application/json':
                    raise StoreConflict('版2の型付き表の型・版・件数が一致しません。')
            if type(entry['row_count']) is not int or len(rows) != entry['row_count'] or digest(rows) != entry['rows_hash']:
                raise StoreConflict('版2の表の件数・hashが一致しません。')
            tables[name] = table
        document = _read_typed_json(content[manifest['document']])
        expanded = package_v2.expand_document(document, tables, snapshot)
        if (not isinstance(expanded, dict) or expanded.get('schema_version') != 2
                or expanded.get('parameters', {}) != result.get('parameters', {})
                or expanded.get('algorithms', {}) != result.get('algorithms', {})):
            raise StoreConflict('版2の文書の条件が一致しません。')
        return expanded

    @staticmethod
    def _verify_typed_tables(run, manifest, artifacts, content):
        json_names = {name for name in content if name.startswith("tables/") and name.endswith(".json")}
        if "table_format_version" not in manifest:
            if json_names or "typed_tables" in manifest:
                raise StoreConflict("型付き表の形式版が欠落しています。")
            return  # Legacy CSV remains readable; no inferred typed reconstruction.
        if type(manifest["table_format_version"]) is not int or manifest["table_format_version"] != TABLE_FORMAT_VERSION:
            raise StoreConflict("型付き表の保存形式に対応していません。")
        mapping = manifest.get("typed_tables")
        csv_names = {name for name in content if name.startswith("tables/") and name.endswith(".csv")}
        if (not isinstance(mapping, dict) or any(not re.fullmatch(r"[a-z_]+", name) for name in mapping)
                or json_names != {f"tables/{name}.json" for name in mapping}
                or csv_names != {f"tables/{name}.csv" for name in mapping}):
            raise StoreConflict("型付き表と共有CSVの対応が欠落しています。")
        for name, references in mapping.items():
            json_name, csv_name = f"tables/{name}.json", f"tables/{name}.csv"
            if references != {"data": json_name, "export": csv_name}:
                raise StoreConflict("型付き表の参照先が一致しません。")
            table = _read_typed_json(content[json_name])
            if (not isinstance(table, dict) or not isinstance(table.get("rows"), list)
                    or any(not isinstance(row, dict) or set(row) != {"row_id", "values"} for row in table["rows"])):
                raise StoreConflict("型付き表の行形式が正しくありません。")
            rows = [row["values"] for row in table["rows"]]
            expected_table = table_package(name, table.get("fields"), rows,
                                           run_id=run["id"], snapshot_id=run["snapshot_id"],
                                           source_revision=run["source_revision"], analysis_revision=run["analysis_revision"])
            if (canonical(table) != canonical(expected_table)
                    or artifacts[json_name]["media_type"] != "application/json"
                    or artifacts[csv_name]["media_type"] != "text/csv"
                    or type(artifacts[json_name]["rows"]) is not int or artifacts[json_name]["rows"] != len(rows)
                    or type(artifacts[csv_name]["rows"]) is not int or artifacts[csv_name]["rows"] != len(rows)
                    or csv_bytes(table["fields"], rows) != content[csv_name]):
                raise StoreConflict("型付き表の版・型・件数またはCSVとの対応が一致しません。")

    def read_table(self, run_id: str, dataset_id: str) -> dict:
        """Resolve a complete machine table through the verified saved manifest."""
        if not isinstance(dataset_id, str) or not re.fullmatch(r"[a-z_]+", dataset_id):
            raise StoreConflict("表の識別子が正しくありません。")
        snapshot, _result, manifest, content = self.readable_package(run_id)
        references = manifest.get("typed_tables", {}).get(dataset_id)
        if references is None:
            raise StoreConflict("型付き全件表は保存されていません。CSVからの型推測は行いません。")
        if 'reference' in references:
            run = self.get(run_id)
            reference = manifest['references'][dataset_id]
            rows = package_v2.resolve(self, dataset_id, reference, snapshot)
            return table_package(dataset_id, reference['fields'], rows, run_id=run_id,
                snapshot_id=run['snapshot_id'], source_revision=run['source_revision'], analysis_revision=run['analysis_revision'])
        return _read_typed_json(content[references["data"]])

    def _publication_scope(self, run: dict, result: dict, targets: list[str] | None) -> list[str]:
        if run["kind"] in {"milestone_analysis", "autonomous_analysis"}:
            saved = result.get("parameters", {}).get("publication_targets")
            if saved is None:
                raise StoreConflict("旧packageの公開範囲を確認できません。新しい範囲へ自動拡大しません。")
            saved = validate_publication_targets(saved)
            if targets is not None and validate_publication_targets(targets) != saved:
                raise StoreConflict("再公開は保存時の承認範囲から変更できません。")
            if run["kind"] == "autonomous_analysis" and saved and run.get("stale"):
                raise StoreConflict("入力変更後の自律分析はVaultへ公開できません。固定成果物を確認してください。")
            return saved
        return validate_publication_targets(list(PUBLICATION_TARGETS) if targets is None else targets)

    def _record_blocked_publication(self, run: dict, targets: list[str] | None, error: Exception) -> None:
        """Keep validation failures visible without claiming any writer ran."""
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            latest = connection.execute("SELECT * FROM analysis_publication_attempts WHERE run_id=? ORDER BY sequence DESC LIMIT 1", (run["id"],)).fetchone()
            if latest and latest["status"] == "publishing":
                return
            requested = json.loads(latest["requested_json"]) if latest else targets
            if requested is None and run["kind"] not in {"milestone_analysis", "autonomous_analysis"}:
                requested = list(PUBLICATION_TARGETS)
            if requested is None:
                return  # Legacy scope is unknown; never invent permission.
            requested = validate_publication_targets(requested)
            if targets is not None and validate_publication_targets(targets) != requested:
                return  # A request for a different scope was not accepted.
            effective = list(EFFECTIVE_PUBLICATION_WRITERS) if requested else []
            message = str(error)[:1000]
            outcomes = {kind: {"status": "failed" if kind in effective else "not_selected", "error": message}
                        for kind in EFFECTIVE_PUBLICATION_WRITERS}
            now = datetime.now(timezone.utc).isoformat()
            connection.execute("""INSERT INTO analysis_publication_attempts
                (attempt_id,run_id,sequence,package_hash,requested_json,effective_json,executed_json,outcomes_json,status,error,created_at,ended_at)
                VALUES (?,?,?,?,?,?,'[]',?,'blocked',?,?,?)""", (uuid.uuid4().hex, run["id"], latest["sequence"] + 1 if latest else 1,
                run["fingerprint"], canonical(requested).decode(), canonical(effective).decode(), canonical(outcomes).decode(), message, now, now))

    def publish(self, run_id: str, *, targets: list[str] | None = None, commit_guard=None,
                reuse_completed: bool = False) -> dict:
        with STORE_LOCK:
            run = self.get(run_id)
            if not run or run["status"] != "completed":
                raise LookupError("完了した保存結果がありません。")
            # Scope resolution reads the saved result and never recomputes a missing package.
            try:
                snapshot, result, _manifest, _content = self.readable_package(run_id)
                requested = self._publication_scope(run, result, targets)
                if run["kind"] == "autonomous_analysis" and requested and commit_guard is None:
                    raise StoreConflict("自律分析の公開は専用の保存・公開再試行から実行してください。")
            except (OSError, ValueError, KeyError, TypeError, LookupError) as exc:
                self._record_blocked_publication(run, targets, exc)
                raise
            effective = list(EFFECTIVE_PUBLICATION_WRITERS) if requested else []
            outcomes = {kind: {"status": "pending" if kind in effective else "not_selected", "error": ""}
                        for kind in EFFECTIVE_PUBLICATION_WRITERS}
            attempt_id = uuid.uuid4().hex
            now = datetime.now(timezone.utc).isoformat()
            with self.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if commit_guard is not None:
                    commit_guard(connection)
                latest = connection.execute("SELECT * FROM analysis_publication_attempts WHERE run_id=? ORDER BY sequence DESC LIMIT 1", (run_id,)).fetchone()
                if latest and latest["status"] == "publishing":
                    raise StoreConflict("このpackageの公開試行はまだ実行中です。")
                if latest and (json.loads(latest["requested_json"]) != requested or latest["package_hash"] != run["fingerprint"]):
                    raise StoreConflict("公開試行の固定packageまたは承認範囲が一致しません。")
                # Pipeline cancellation may arrive after the publication committed.
                # Reuse only the latest durable success, after package verification,
                # scope checks and the caller's current-generation guard above.
                # Direct user-requested republication keeps its existing behavior.
                if (reuse_completed and latest and latest["status"] == "completed" and effective
                        and all(json.loads(latest["outcomes_json"]).get(kind, {}).get("status") == "published"
                                for kind in effective)):
                    return self.get(run_id)
                sequence = latest["sequence"] + 1 if latest else 1
                connection.execute("""INSERT INTO analysis_publication_attempts
                    (attempt_id,run_id,sequence,package_hash,requested_json,effective_json,outcomes_json,status,created_at)
                    VALUES (?,?,?,?,?,?,?,'publishing',?)""", (attempt_id, run_id, sequence, run["fingerprint"],
                    canonical(requested).decode(), canonical(effective).decode(), canonical(outcomes).decode(), now))
            executed: list[str] = []
            error = ""
            self._note_events = []
            self._last_publication_outcomes.pop(run_id, None)
            try:
                if requested:
                    executed.extend(PUBLICATION_TARGETS)
                    self._update_publication_attempt(attempt_id, executed, outcomes, "publishing")
                    self._publish_generated_vaults(run_id)
                    generated = self._last_publication_outcomes.get(run_id, {})
                    for kind in PUBLICATION_TARGETS:
                        outcomes[kind] = generated.get(kind, {"status": "unknown", "error": "公開結果が返されませんでした。"})
                    executed.append("research")
                    self._update_publication_attempt(attempt_id, executed, outcomes, "publishing")
                    published = self._publish_research(run_id)
                    state = published.get("vault_status", "unknown")
                    outcomes["research"] = {"status": "published" if state == "completed" else state,
                                             "error": str(published.get("error") or "")}
            except Exception as exc:
                error = str(exc)[:1000]
                for kind in effective:
                    if outcomes[kind]["status"] == "pending":
                        outcomes[kind] = {"status": "failed" if kind in executed else "unknown", "error": error}
            status = ("not_selected" if not effective else "completed" if all(
                outcomes[kind]["status"] == "published" for kind in effective) else "incomplete")
            self._update_publication_attempt(attempt_id, executed, outcomes, status, error)
            return self.get(run_id)

    def _update_publication_attempt(self, attempt_id: str, executed: list[str], outcomes: dict,
                                    status: str, error: str = "") -> None:
        with self.connect() as connection:
            connection.execute("""UPDATE analysis_publication_attempts SET executed_json=?,outcomes_json=?,status=?,error=?,ended_at=?
                WHERE attempt_id=? AND status='publishing'""", (canonical(executed).decode(), canonical(outcomes).decode(),
                status, error, None if status == "publishing" else datetime.now(timezone.utc).isoformat(), attempt_id))

    def _read_package(self, run_id: str) -> tuple[dict, dict]:
        snapshot, result, _manifest, _content = self.readable_package(run_id)
        return snapshot, result

    def follow_moves(self, item_id: str) -> None:
        """Apply interview folder moves detected by ObsidianLayout to the SQLite catalog."""
        self.layout.follow(item_id)
        record = self.layout.load()["interviews"].get(item_id) or {}
        if not record.get("moved_from"):
            return
        with self.connect() as conn:
            for old in record["moved_from"]:
                prefix = old + "/"
                # substr from the "/" keeps the remainder of the path under the new folder.
                conn.execute("UPDATE OR IGNORE obsidian_notes SET path=?||substr(path,?) WHERE substr(path,1,?)=?",
                             (record["folder"], len(prefix), len(prefix), prefix))
                conn.execute("UPDATE analysis_runs SET note_path=?||substr(note_path,?) WHERE substr(note_path,1,?)=?",
                             (record["folder"], len(prefix), len(prefix), prefix))

    def write_note(self, relative: str, note_id: str, item_id: str, content: str,
                   *, graph_kind: str = "analysis", graph_scope: str | None = None,
                   navigation: bool = False) -> None:
        """Write through the shared Vault note policy (vault_note_policy, OBS-04).

        A researcher's edit is kept in the history before the latest version is
        written. A deleted note is recreated only when it is ``navigation``.
        """
        from .vault_note_policy import write_generated_note
        if item_id:
            content = self.layout.decorate(content, item_id, graph_kind,
                graph_scope or ("detail" if relative.endswith("-分析まとめ.md") else "history"))
            self.follow_moves(item_id)
        with self.connect() as conn:
            previous = conn.execute("SELECT * FROM obsidian_notes WHERE path=?", (relative,)).fetchone()
        result = write_generated_note(
            self.vault, relative, content.encode("utf-8"),
            known_hashes={previous["sha256"]} if previous else set(),
            ever_written=previous is not None, recreate_missing=navigation,
            log_file=self.note_log,
        )
        if result.notable:
            self._note_events.append(result)
        if result.action == "missing":
            return
        with self.connect() as conn:
            conn.execute("""INSERT INTO obsidian_notes(path,note_id,item_id,sha256,updated_at) VALUES(?,?,?,?,?)
                ON CONFLICT(path) DO UPDATE SET sha256=excluded.sha256,updated_at=excluded.updated_at""",
                (relative, note_id, item_id, result.sha256, datetime.now(timezone.utc).isoformat()))

    def _record_note_events(self, run_id: str) -> None:
        """Keep what the last Vault save did to researcher-touched notes, for the app screen."""
        target = self.run_notes / f"{run_id}.json"
        events = self._note_events
        self._note_events = []
        if not events:
            target.unlink(missing_ok=True)
            return
        summary = {
            "edit_saved": [{"vault": e.vault, "path": e.path, "history": e.history}
                           for e in events if e.action == "edit_saved"],
            "missing": [{"vault": e.vault, "path": e.path} for e in events if e.action == "missing"],
            "recreated": [{"vault": e.vault, "path": e.path} for e in events if e.action == "recreated"],
        }
        write_atomic(target, json.dumps(summary, ensure_ascii=False).encode("utf-8"))

    def vault_notes(self, run_id: str) -> dict:
        try:
            data = json.loads((self.run_notes / f"{run_id}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def source_notes(self, segments: list[dict], item_id: str, title: str, app_url: str) -> dict[str, str]:
        snapshot_id = digest({"segments": segments, "item_id": item_id, "title": title})
        refs = {}
        for index in range(0, len(segments), 200):
            page = self.layout.source_dir(item_id, title, snapshot_id) + f"/part-{index // 200 + 1:04d}"
            body = frontmatter(f"source-{snapshot_id}-{index}", title, note_type="source-snapshot",
                               conversation_id=item_id, input_snapshot_id=snapshot_id)
            body += f"# {markdown(title)}\n\n保存時点の原文です。\n\n"
            for segment in segments[index:index + 200]:
                sid = str(segment["id"])
                block = "s-" + sid.encode("utf-8").hex()
                refs[sid] = f"[[{page}#^{block}|{markdown(segment.get('speaker_name') or segment.get('speaker'))}・{segment.get('start', 0)}秒]]"
                body += f"### {markdown(segment.get('speaker_name') or segment.get('speaker'))} / {segment.get('start', 0)}–{segment.get('end', 0)}秒\n\n"
                body += "\n".join("> " + markdown(line) for line in str(segment.get("text") or "").splitlines()) + f"\n\n^{block}\n\n"
                params = urlencode({"view": "analysis", "item": item_id, "segment": sid,
                                    "text_hash": hashlib.sha256(str(segment.get("text") or "").strip().encode("utf-8")).hexdigest(),
                                    "start": segment.get("start", 0), "end": segment.get("end", 0),
                                    "speaker": segment.get("speaker", "UNKNOWN")})
                body += f"[アプリで発話を確認]({app_url}/?{params})\n\n"
            self.write_note(page + ".md", f"source-{snapshot_id}-{index}", item_id, body)
        return refs

    def _publish_comparison(self, run: dict) -> None:
        """ResearchVault note for a multi-interview comparison, kept apart from every interview folder."""
        snapshot, result = self._read_package(run["id"])
        interviews = self.layout.load()["interviews"]
        members = snapshot.get("members", [])
        title = str(snapshot.get("title") or "グループインタビュー比較")
        note_id = f"comparison-{run['id']}"
        text = frontmatter(note_id, title, note_type="interview-comparison", analysis_id=run["id"],
                           conversation_ids=[member["conversation_id"] for member in members],
                           input_snapshot_id=run["snapshot_id"], created=run["created_at"],
                           review_status="unreviewed", tags=["graph/overview"])
        text += f"# {markdown(title)}\n\n{run['created_at']} に保存した比較です。各インタビューの分析とは別の実行として保存しています。\n\n"
        text += "## 比較したインタビュー\n\n"
        for member in members:
            record = interviews.get(member["conversation_id"])
            label = markdown(member.get("title"))
            text += "- " + (f"[[{record['hub'][:-3]}|{record['code']} {label}]]" if record else label)
            text += f"（revision {int(member.get('source_revision') or 0)}）\n"
        for method in result.get("methods", []):
            text += "\n## 見解\n\n" + "".join(f"- {markdown(s.get('title'))}：{markdown(s.get('text'))}\n"
                                              for s in method.get("summaries", []))
            for preview in method.get("previews", []):
                fields = preview["fields"]
                text += f"\n### {markdown(preview['dataset'])}（全{preview['total']}行・先頭10行まで）\n\n"
                text += "| " + " | ".join(markdown(f) for f in fields) + " |\n"
                text += "| " + " | ".join("---" for _ in fields) + " |\n"
                for row in preview["rows"]:
                    text += "| " + " | ".join(markdown(str(row.get(f, ""))[:160]).replace("\n", "<br>") for f in fields) + " |\n"
            text += "\n## 限界と追加確認\n\n" + "\n".join("- " + markdown(v) for v in method.get("limitations", [])) + "\n"
        text += "\n## 再現用ファイル\n\n" + "\n".join(
            f"- [{a['name']}]({run['app_url']}/api/analysis/artifacts/{a['id']})" for a in self.artifacts(run["id"])) + "\n"
        note_path = f"40-研究/インタビュー比較/comparison-{run['id']}.md"
        self.write_note(note_path, note_id, "", text)
        with self.connect() as conn:
            conn.execute("UPDATE analysis_runs SET vault_status='completed',note_path=?,error='' WHERE id=?",
                         (note_path, run["id"]))

    def _publish_research(self, run_id: str) -> dict:
        with STORE_LOCK:
            run = self.get(run_id)
            if not run or run["status"] != "completed": raise LookupError("完了した保存結果がありません。")
            try:
                if run["kind"] == "interview_comparison":
                    self._publish_comparison(run)
                    self._record_note_events(run_id)
                    return self.get(run_id)
                snapshot, result = self._read_package(run_id)
                item_id = run["item_id"]
                title = str(snapshot.get("title") or item_id)
                run_dir = self.layout.analysis_dir(item_id, title, run_id)
                originals = {s["id"]: s for s in snapshot.get("original_source", {}).get("segments", [])}
                source = [{**s, "text": originals.get(s["id"], s).get("text", "")}
                          for s in snapshot.get("segments", []) if not s.get("excluded")]
                refs = self.source_notes(source, item_id, title, run["app_url"])
                artifact_rows = self.export_artifacts(run_id)
                links = {a["name"]: f"[{a['name']}]({run['app_url']}" +
                    (a['url'] if a.get('generated') else f"/api/analysis/artifacts/{a['id']}") + ')' for a in artifact_rows}
                main = frontmatter(f"analysis-{run_id}", title + "：保存済み分析", conversation_id=item_id,
                                   analysis_id=run_id, input_snapshot_id=run["snapshot_id"],
                                   source_revision=run["source_revision"], analysis_revision=run["analysis_revision"],
                                   created=run["created_at"], review_status="unreviewed")
                main += f"# {markdown(title)}：保存済み分析\n\n{run['created_at']} の固定結果です。\n\n"
                main += "## 見解と分析手法\n\n"
                for method in result.get("methods", []):
                    method_id = method["method_id"]
                    if not re.fullmatch(r"[a-z_]+", method_id): raise ValueError("手法IDが不正です。")
                    target = f"{run_dir}/method-{method_id}"
                    main += f"- [[{target}|{method['title']}]]（{method['status']}）\n"
                    text = frontmatter(f"analysis-{run_id}-{method_id}", method["title"], analysis_id=run_id,
                                       conversation_id=item_id, method_id=method_id,
                                       method_version=method["method_version"], run_status=method["status"],
                                       review_status="unreviewed", input_snapshot_id=run["snapshot_id"])
                    text += f"# {markdown(method['title'])}\n\n状態：{markdown(method['status'])}\n\n"
                    text += f"[[{run_dir}/analysis-{run_id}|この実行の全体]]\n\n"
                    active_refs = refs
                    evidence = method.get("details", {}).get("evidence")
                    if evidence:
                        active_refs = self.source_notes(list(evidence.values()), item_id, title + "：AI生成時点", run["app_url"])
                    text += "## 見解・観察\n\n"
                    for summary in method.get("summaries", []):
                        text += f"### {markdown(summary.get('title'))}\n\n{markdown(summary.get('text'))}\n\n"
                    for finding in method.get("findings", []):
                        if not finding.get("segment_ids") or any(s not in active_refs for s in finding["segment_ids"]):
                            raise StoreConflict("見解の根拠を保存済み原文に対応付けられません。")
                        text += f"### {markdown(finding.get('title'))}\n\n{markdown(finding.get('text'))}\n\n"
                        text += "根拠：" + " / ".join(active_refs[s] for s in finding.get("segment_ids", []) if s in active_refs) + "\n\n"
                    for section in method.get("details", {}).get("sections", []):
                        text += f"### {markdown(section.get('title'))}\n\n"
                        for bullet in section.get("bullet_evidence", []):
                            if not bullet.get("segment_ids") or any(s not in active_refs for s in bullet["segment_ids"]):
                                raise StoreConflict("議題の根拠を保存済み原文に対応付けられません。")
                            text += f"- {markdown(bullet['text'])}\n"
                            text += "  根拠：" + " / ".join(active_refs[s] for s in bullet["segment_ids"]) + "\n"
                        if not section.get("bullet_evidence"):
                            text += "旧形式の議題です。発話IDによる根拠は未登録です。\n\n"
                            text += "\n".join("- " + markdown(b) for b in section.get("bullets", [])) + "\n"
                    if method_id == "ai_finishing":
                        details = method["details"]
                        text += "工程の結果：" + markdown(json.dumps(details.get("stages", {}), ensure_ascii=False)) + "\n\n"
                        original_refs = self.source_notes(details.get("original_segments", []), item_id, title + "：AI仕上げ前", run["app_url"])
                        text += f"校正・話者変更：{len(details.get('changes', []))}発話\n\n"
                        for change in details.get("changes", [])[:100]:
                            sid = change["segment_id"]
                            text += f"- 原文：{original_refs.get(sid, markdown(sid))} → 保存後：{refs.get(sid, markdown(sid))}\n"
                    if method_id == "kwic":
                        details = method["details"]
                        text += f"検索語：{markdown(details.get('query'))} / {details.get('total', 0)}件\n\n"
                        for hit in details.get("hits", [])[:50]:
                            text += f"- {markdown(hit['left'] + hit['match'] + hit['right'])}：{refs.get(hit['segment_id'], '')}\n"
                    for preview in method.get("previews", []):
                        text += f"\n### {markdown(preview['dataset'])}（全{preview['total']}行・先頭10行まで）\n\n"
                        fields = preview["fields"]
                        text += "| " + " | ".join(markdown(f) for f in fields) + " |\n"
                        text += "| " + " | ".join("---" for _ in fields) + " |\n"
                        for row in preview["rows"]:
                            text += "| " + " | ".join(markdown(str(row.get(f, ""))[:160]).replace("\n", "<br>").replace("\r", "") for f in fields) + " |\n"
                    text += "\n## 条件と全件データ\n\n"
                    text += f"分析単位：{markdown(method.get('analysis_unit'))}\n\n"
                    text += "解析器：" + markdown(json.dumps(method.get("engine", {}), ensure_ascii=False)) + "\n\n"
                    text += links["parameters.json"] + " / " + links["result.json"] + "\n\n"
                    for dataset in method.get("datasets", []):
                        table_meta = next((a for a in artifact_rows if a['name'] == f'tables/{dataset}.csv' and a.get('generated')), None)
                        if table_meta:
                            text += f"- 固定表：{table_meta['rows']}行 / 行hash `{table_meta['sha256']}`\n"
                        for extension, purpose in (("json", "型付き全件データ"), ("csv", "表計算・共有用")):
                            name = f"tables/{dataset}.{extension}"
                            if name in links: text += f"- {purpose}：{links[name]}\n"
                    text += "\n## 限界と追加確認\n\n" + "\n".join("- " + markdown(v) for v in method.get("limitations", [])) + "\n"
                    self.write_note(target + ".md", f"analysis-{run_id}-{method_id}", item_id, text,
                                    graph_kind="analysis_result", graph_scope="detail")
                tree_links = self.publish_graph_tree(run_id, item_id, title, run_dir, result.get("methods", []))
                if tree_links:
                    main += "\n## 可視化用の分析ツリー\n\n"
                    main += "アウトライン、分析種別、結果の順にグラフでたどれます。\n\n"
                    main += "\n".join("- " + value for value in tree_links) + "\n"
                main += "\n## 再現用ファイル\n\n" + "\n".join("- " + value for value in links.values()) + "\n"
                main += "\n研究者のメモはインタビューの概要から研究メモを開いて記録してください。\n"
                note_path = f"{run_dir}/analysis-{run_id}.md"
                self.write_note(note_path, f"analysis-{run_id}", item_id, main,
                                graph_kind="analysis", graph_scope="detail")
                with self.connect() as conn:
                    conn.execute("UPDATE analysis_runs SET vault_status='completed',note_path=?,error='' WHERE id=?", (note_path, run_id))
                # Generated Vaults were already attempted above; do not recursively
                # start a second publication while updating this Research index.
                self._publish_index(item_id)
                self._record_note_events(run_id)
            except Exception as exc:
                message = str(exc) if isinstance(exc, StoreConflict) else "Vaultへの保存を完了できませんでした。結果ファイルは保持しています。"
                with self.connect() as conn:
                    conn.execute("UPDATE analysis_runs SET vault_status='conflict',error=? WHERE id=?", (message, run_id))
            return self.get(run_id)

    def publish_graph_tree(self, run_id: str, item_id: str, title: str, run_dir: str,
                           methods: list[dict]) -> list[str]:
        """Create a compact, navigable graph tree for one immutable analysis run.

        The detailed method notes remain the audit trail.  These small notes are
        deliberately separate graph nodes so an Obsidian graph can show
        ``analysis group -> method -> result`` without rendering every CSV row.
        Outline sections are nodes too, because they are meaningful units a
        researcher can connect to themes and memos.
        """
        groups = {method_id: (group_id, group_title, description)
                  for group_id, group_title, description, method_ids in METHOD_GROUPS
                  for method_id in method_ids}
        grouped: dict[str, list[dict]] = {}
        for method in methods:
            method_id = str(method.get("method_id") or "")
            if method_id in groups:
                grouped.setdefault(groups[method_id][0], []).append(method)

        links: list[str] = []
        for group_id, group_title, description, _ in METHOD_GROUPS:
            selected = grouped.get(group_id, [])
            if not selected:
                continue
            group_path = graph_node_path(run_dir, f"分類-{group_id}", group_title, self.vault)
            method_paths = []
            for method in selected:
                method_id = str(method["method_id"])
                method_path = graph_node_path(run_dir, f"手法-{method_id}", str(method["title"]), self.vault)
                method_paths.append(method_path)
                result_path = f"{run_dir}/method-{method_id}.md"
                result_nodes = self._graph_result_nodes(run_dir, method)
                body = f"# 分析種別：{markdown(method['title'])}\n\n"
                body += f"[[{group_path[:-3]}|分類：{markdown(group_title)}]]\n\n"
                body += f"[[{result_path[:-3]}|この手法の詳細結果・根拠・条件]]\n\n"
                body += "## 結果\n\n"
                body += "\n".join("- [[" + path[:-3] + "]]" for path, _, _ in result_nodes) + "\n"
                if not result_nodes:
                    body += "- 保存時点では表示可能な結果がありません。\n"
                self.write_note(method_path, f"analysis-{run_id}-graph-method-{method_id}", item_id,
                                frontmatter(f"analysis-{run_id}-graph-method-{method_id}", method["title"],
                                            analysis_id=run_id, conversation_id=item_id,
                                            method_id=method_id, node_role="analysis_type") + body,
                                graph_kind="analysis_type", graph_scope="detail")
                for path, node_title, node_body in result_nodes:
                    kind = "outline" if method_id == "outline" else "analysis_result"
                    node_id = hashlib.sha256(path.encode()).hexdigest()[:16]
                    body = f"# {markdown(node_title)}\n\n[[{method_path[:-3]}|分析種別：{markdown(method['title'])}]]\n\n"
                    body += f"[[{result_path[:-3]}|詳細な結果・根拠・条件を開く]]\n\n" + node_body
                    self.write_note(path, f"analysis-{run_id}-graph-result-{node_id}", item_id,
                                    frontmatter(f"analysis-{run_id}-graph-result-{node_id}", node_title,
                                                analysis_id=run_id, conversation_id=item_id,
                                                method_id=method_id, node_role="outline_section" if kind == "outline" else "analysis_result") + body,
                                    graph_kind=kind, graph_scope="detail")
            body = f"# 分析分類：{markdown(group_title)}\n\n{markdown(description)}\n\n"
            body += "## 分析種別\n\n" + "\n".join("- [[" + path[:-3] + "]]" for path in method_paths) + "\n"
            self.write_note(group_path, f"analysis-{run_id}-graph-group-{group_id}", item_id,
                            frontmatter(f"analysis-{run_id}-graph-group-{group_id}", group_title,
                                        analysis_id=run_id, conversation_id=item_id,
                                        group_id=group_id, node_role="analysis_group") + body,
                            graph_kind="analysis_type", graph_scope="detail")
            links.append(f"[[{group_path[:-3]}|{markdown(group_title)}]]")
        return links

    def _graph_result_nodes(self, run_dir: str, method: dict) -> list[tuple[str, str, str]]:
        """Return bounded, human-readable leaves for a method's graph branch."""
        method_id = str(method["method_id"])
        nodes: list[tuple[str, str, str]] = []
        for index, section in enumerate(method.get("details", {}).get("sections", []), 1):
            title = str(section.get("title") or f"アウトライン {index}")
            body = "## アウトラインの内容\n\n"
            bullets = section.get("bullet_evidence") or []
            if bullets:
                body += "\n".join("- " + markdown(item.get("text")) for item in bullets) + "\n"
            else:
                body += "\n".join("- " + markdown(item) for item in section.get("bullets", [])) + "\n"
            nodes.append((graph_node_path(run_dir, f"アウトライン-{index:02d}", title, self.vault), "アウトライン：" + title, body))
        for index, finding in enumerate(method.get("findings", [])[:12], 1):
            title = str(finding.get("title") or f"見解 {index}")
            body = "## 結果の要約\n\n" + markdown(finding.get("text")) + "\n"
            nodes.append((graph_node_path(run_dir, f"結果-{method_id}-見解-{index:02d}", title, self.vault), "結果：" + title, body))
        for index, preview in enumerate(method.get("previews", [])[:12], 1):
            dataset = str(preview.get("dataset") or f"データ {index}")
            body = f"## {markdown(dataset)}\n\n全{preview.get('total', 0)}行のうち先頭{len(preview.get('rows', []))}行を表示します。\n\n"
            fields = preview.get("fields", [])[:4]
            for row in preview.get("rows", [])[:5]:
                values = " / ".join(markdown(str(row.get(field, ""))[:120]) for field in fields)
                body += "- " + values + "\n"
            nodes.append((graph_node_path(run_dir, f"結果-{method_id}-表-{index:02d}", dataset, self.vault), "結果：" + dataset, body))
        if not nodes:
            state = markdown(method.get("status") or "不明")
            nodes.append((graph_node_path(run_dir, f"結果-{method_id}-状態", "実行状態", self.vault), "結果：実行状態", "## 保存時点の状態\n\n" + state + "\n"))
        return nodes

    def publish_index(self, item_id: str) -> None:
        with STORE_LOCK:
            self.refresh_vaults(item_id)
            self._publish_index(item_id)

    def _publish_index(self, item_id: str) -> None:
        from .obsidian_layout import ANALYSIS_INDEX, link, method_table
        self.follow_moves(item_id)
        with self.connect() as conn:
            runs = [dict(r) for r in conn.execute("""SELECT * FROM analysis_runs
                WHERE item_id=? AND status='completed' AND note_path!=''
                ORDER BY created_at DESC,id DESC""", (item_id,)).fetchall()]
        if not runs: return
        snapshot, latest_result = self._read_package(runs[0]["id"])
        item_key = uuid.uuid5(uuid.NAMESPACE_URL, snapshot["library_id"] + item_id).hex
        title = str(snapshot.get("title") or item_id)
        note_id = f"conversation-{item_key}"
        text = frontmatter(note_id, title, note_type="conversation", conversation_id=item_id,
                           needs_update=bool(runs[0]["stale"]))
        text += f"# 分析まとめ\n\n[[{runs[0]['note_path'][:-3]}|最新の保存済み分析を開く]]\n\n"
        text += link(ANALYSIS_INDEX, "全インタビューの分析結果・手法別一覧") + "\n\n"
        # A later KWIC-only save must not hide text or emotion analyses.
        by_method = {}
        for run in runs:
            package = latest_result if run["id"] == runs[0]["id"] else self._read_package(run["id"])[1]
            run_dir = self.layout.analysis_dir(item_id, title, run["id"])
            for method in package.get("methods", []):
                method_id = method["method_id"]
                if not re.fullmatch(r"[a-z_]+", method_id): raise ValueError("手法IDが不正です。")
                path = f"{run_dir}/method-{method_id}.md"
                if method_id in by_method or not safe_path(self.vault, path).is_file(): continue
                by_method[method_id] = {"method_id": method_id, "title": method["title"],
                    "path": path, "status": method["status"], "stale": bool(run["stale"]),
                    "created_at": run["created_at"]}
        text += "## 手法別の分析結果\n\n各手法の最新の保存記録です。実行時点が異なる場合があるため、保存日時と状態を合わせて確認してください。\n\n"
        for _, group_title, description, method_ids in METHOD_GROUPS:
            selected = [by_method[key] for key in method_ids if key in by_method]
            text += "### " + group_title + "\n\n" + description + "\n\n"
            text += method_table(selected) + "\n" if selected else "この分類の保存記録はまだありません。\n\n"
        findings = [(method, finding) for method in latest_result.get("methods", [])
                    for finding in method.get("findings", [])]
        if findings:
            text += "## 最新の見解\n\n"
            run_dir = self.layout.analysis_dir(item_id, title, runs[0]["id"])
            for method, finding in findings[:5]:
                text += f"### {markdown(finding.get('title') or method['title'])}\n\n{markdown(finding.get('text'))}\n\n"
                text += f"[[{run_dir}/method-{method['method_id']}|根拠と分析条件]]\n\n"
        text += "## 保存履歴\n\n"
        for row in runs:
            status = "更新が必要" if row["stale"] else "保存時点の結果"
            text += f"- [[{row['note_path'][:-3]}|{row['created_at']} / {row['kind']}]]：{status}\n"
        summary = self.layout.note_path(item_id, title, "分析まとめ")
        self.write_note(summary, note_id, item_id, text, navigation=True)
        self.layout.update(item_id, title, {"analysis": summary}, analysis_methods=list(by_method.values()))
        # A dedicated generated index never overwrites the user's Home or guides.
        with self.connect() as conn:
            notes = conn.execute("SELECT path,note_id FROM obsidian_notes WHERE note_id LIKE 'conversation-%' ORDER BY path").fetchall()
        index = frontmatter("gurumoji-saved-analyses", "アプリから保存した分析", note_type="analysis-index")
        index += "# アプリから保存した分析\n\n" + "\n".join(f"- [[{n['path'][:-3]}]]" for n in notes) + "\n"
        self.write_note("90-運用/Gurumoji-SavedAnalyses.md", "gurumoji-saved-analyses", "", index, navigation=True)
