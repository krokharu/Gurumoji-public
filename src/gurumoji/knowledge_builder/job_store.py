"""Single-writer SQLite state and CAS acceptance for offline knowledge jobs."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

from . import contracts


class JobStoreError(RuntimeError):
    """Base error for job state and acceptance conflicts."""


class StaleGenerationError(JobStoreError):
    pass


class DuplicateAcceptanceError(JobStoreError):
    pass


class ExpiredJobError(JobStoreError):
    pass


class UnacceptedCommitError(JobStoreError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class KnowledgeJobStore:
    """A local ledger rooted below an explicitly configured data directory.

    Evaluation data is intentionally not an input to this store. It holds only
    evaluation metrics and opaque case IDs; case content and answer keys belong
    to a separately isolated evaluator process and access principal.
    """

    def __init__(self, data_dir: str | Path):
        if data_dir is None or not str(data_dir).strip():
            raise ValueError("data_dir must be explicitly configured")
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.root = self.data_dir / "knowledge_builder"
        self.staging_root = self.root / "staging"
        self.db_path = self.root / "state.sqlite3"
        self.root.mkdir(parents=True, exist_ok=True)
        self.staging_root.mkdir(parents=True, exist_ok=True)
        self._assert_within(self.root, self.data_dir)
        self._assert_within(self.staging_root, self.root)
        self._initialize()

    @staticmethod
    def _assert_within(path: Path, root: Path) -> Path:
        resolved_root = root.resolve()
        resolved = path.resolve()
        if not resolved.is_relative_to(resolved_root):
            raise JobStoreError("path escapes configured data directory")
        return resolved

    def _connect(self) -> sqlite3.Connection:
        if self.db_path.is_symlink() or getattr(self.db_path, "is_junction", lambda: False)():
            raise JobStoreError("SQLite file may not be a link")
        self._assert_within(self.db_path, self.root)
        connection = sqlite3.connect(self.db_path, timeout=20, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=20000")
        return connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS knowledge_jobs (
                    job_id TEXT PRIMARY KEY,
                    generation INTEGER NOT NULL,
                    attempt_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    deadline TEXT NOT NULL,
                    input_manifest_sha256 TEXT NOT NULL,
                    model_route TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    compiler_version TEXT NOT NULL,
                    retry_limit INTEGER NOT NULL,
                    retry_count INTEGER NOT NULL,
                    directive_sha256 TEXT NOT NULL,
                    accepted_generation INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS knowledge_commits (
                    job_id TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    manifest_sha256 TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    staging_relative TEXT NOT NULL,
                    accepted_at TEXT NOT NULL,
                    PRIMARY KEY(job_id, generation),
                    FOREIGN KEY(job_id) REFERENCES knowledge_jobs(job_id)
                );
                CREATE TABLE IF NOT EXISTS knowledge_packs (
                    pack_id TEXT PRIMARY KEY,
                    root_sha256 TEXT NOT NULL UNIQUE,
                    manifest_json TEXT NOT NULL,
                    package_relative TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)

    def _job_id(self, job_id: str) -> str:
        return contracts._id(job_id, "job_id")

    def _stage_for(self, job_id: str, generation: int) -> Path:
        digest = hashlib.sha256(job_id.encode("utf-8")).hexdigest()
        stage = self.staging_root / digest / str(generation)
        self._assert_no_links(stage, self.staging_root)
        self._assert_within(stage, self.staging_root)
        return stage

    @staticmethod
    def _assert_no_links(path: Path, root: Path) -> None:
        current = root
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise JobStoreError("staging root may not be a link")
        try:
            parts = path.relative_to(root).parts
        except ValueError as exc:
            raise JobStoreError("path escapes staging root") from exc
        for part in parts:
            current = current / part
            if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
                raise JobStoreError("artifact path may not traverse a link")

    def pack_staging_dir(self, pack_id: str) -> Path:
        """Return the fixed directory where a candidate Pack's files are staged."""
        pack_id = self._job_id(pack_id)
        digest = hashlib.sha256(pack_id.encode("utf-8")).hexdigest()
        directory = self.staging_root / "packs" / digest
        self._assert_no_links(directory, self.staging_root)
        self._assert_within(directory, self.staging_root)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def create_job(self, request: Any, *, model_route: str, model_id: str, prompt_version: str,
                   compiler_version: str, retry_limit: int, job_id: str | None = None,
                   ttl_seconds: int = 3600) -> dict:
        if type(ttl_seconds) is not int or ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be a positive integer")
        job_id = self._job_id(job_id or uuid.uuid4().hex)
        now = _utc_now()
        record = {
            "schema_version": contracts.SCHEMA_VERSION, "job_id": job_id, "generation": 1,
            "attempt_id": uuid.uuid4().hex,
            "status": "running", "created_at": _iso(now),
            "deadline": _iso(now + timedelta(seconds=ttl_seconds)),
            "input_manifest_sha256": contracts.sha256_json(request), "model_route": model_route,
            "model_id": model_id, "prompt_version": prompt_version, "compiler_version": compiler_version,
            "retry_limit": retry_limit, "retry_count": 0,
        }
        record["directive_sha256"] = contracts.job_directive_hash(record)
        contracts.validate_job(record)
        stage = self._stage_for(job_id, 1)
        stage.mkdir(parents=True, exist_ok=False)
        try:
            with self._transaction() as connection:
                connection.execute("""INSERT INTO knowledge_jobs
                    (job_id,generation,attempt_id,status,created_at,deadline,input_manifest_sha256,model_route,model_id,
                     prompt_version,compiler_version,retry_limit,retry_count,directive_sha256,accepted_generation)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
                    (job_id, record["generation"], record["attempt_id"], record["status"], record["created_at"],
                     record["deadline"], record["input_manifest_sha256"], record["model_route"], record["model_id"],
                     record["prompt_version"], record["compiler_version"], record["retry_limit"],
                     record["retry_count"], record["directive_sha256"]))
        except Exception:
            # Preserve an existing staging tree: only remove this newly-created empty one.
            try:
                stage.rmdir()
                stage.parent.rmdir()
            except OSError:
                pass
            raise
        return record

    def begin_generation(self, job_id: str, request: Any, *, ttl_seconds: int = 3600) -> dict:
        """Create a new generation, superseding prior work and making its commit stale."""
        job_id = self._job_id(job_id)
        if type(ttl_seconds) is not int or ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be a positive integer")
        now = _utc_now()
        with self._transaction() as connection:
            row = connection.execute("SELECT * FROM knowledge_jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise LookupError("job not found")
            for pack_row in connection.execute("SELECT manifest_json FROM knowledge_packs"):
                pack_manifest = json.loads(pack_row["manifest_json"])
                if any(reference.get("job_id") == job_id for reference in pack_manifest.get("commits", [])):
                    raise JobStoreError("job is frozen because an accepted Commit is referenced by a Pack")
            if row["retry_count"] >= row["retry_limit"]:
                raise JobStoreError("job retry limit reached")
            generation = int(row["generation"]) + 1
            deadline = _iso(now + timedelta(seconds=ttl_seconds))
            attempt_id = uuid.uuid4().hex
            input_manifest_sha256 = contracts.sha256_json(request)
            directive = {"job_id": job_id, "generation": generation, "attempt_id": attempt_id,
                         "input_manifest_sha256": input_manifest_sha256, "model_route": row["model_route"],
                         "model_id": row["model_id"], "prompt_version": row["prompt_version"],
                         "compiler_version": row["compiler_version"], "retry_limit": row["retry_limit"],
                         "retry_count": row["retry_count"] + 1, "deadline": deadline}
            directive_sha256 = contracts.job_directive_hash(directive)
            self._stage_for(job_id, generation).mkdir(parents=True, exist_ok=False)
            connection.execute("""UPDATE knowledge_jobs SET generation=?,attempt_id=?,status='running',created_at=?,
                deadline=?,input_manifest_sha256=?,retry_count=?,directive_sha256=? WHERE job_id=?""",
                (generation, attempt_id, _iso(now), deadline, input_manifest_sha256, directive["retry_count"],
                 directive_sha256, job_id))
        record = {"schema_version": contracts.SCHEMA_VERSION, **directive,
                  "status": "running", "created_at": _iso(now), "directive_sha256": directive_sha256}
        return contracts.validate_job(record)

    def staging_dir(self, job_id: str, generation: int) -> Path:
        job_id = self._job_id(job_id)
        if type(generation) is not int or generation < 1:
            raise ValueError("generation must be a positive integer")
        path = self._stage_for(job_id, generation)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_job(self, job_id: str) -> dict | None:
        job_id = self._job_id(job_id)
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT * FROM knowledge_jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            return None
        return {"schema_version": contracts.SCHEMA_VERSION, "job_id": row["job_id"],
                "generation": row["generation"], "attempt_id": row["attempt_id"], "status": row["status"],
                "created_at": row["created_at"], "deadline": row["deadline"],
                "input_manifest_sha256": row["input_manifest_sha256"], "model_route": row["model_route"],
                "model_id": row["model_id"], "prompt_version": row["prompt_version"],
                "compiler_version": row["compiler_version"], "retry_limit": row["retry_limit"],
                "retry_count": row["retry_count"], "directive_sha256": row["directive_sha256"],
                "accepted_generation": row["accepted_generation"]}

    def _artifact_path(self, stage: Path, relative: str) -> Path:
        if not isinstance(relative, str) or "\\" in relative or ":" in relative:
            raise JobStoreError("artifact path must be a relative POSIX path")
        posix = PurePosixPath(relative)
        if posix.is_absolute() or not posix.parts or any(
                part in {"", ".", ".."} for part in relative.split("/")):
            raise JobStoreError("artifact path escapes generation staging")
        target = stage.joinpath(*posix.parts)
        self._assert_no_links(stage, self.staging_root)
        self._assert_no_links(target, self.staging_root)
        resolved_stage = self._assert_within(stage, self.staging_root)
        return self._assert_within(target, resolved_stage)

    def _read_and_validate_artifacts(self, job_id: str, generation: int, manifest: dict) -> list[tuple[str, dict]]:
        stage = self._stage_for(job_id, generation)
        self._assert_within(stage, self.staging_root)
        payloads: list[tuple[str, dict]] = []
        for artifact in manifest["artifacts"]:
            path = self._artifact_path(stage, artifact["path"])
            if not path.is_file():
                raise JobStoreError("declared artifact does not exist")
            data = path.read_bytes()
            if len(data) != artifact["size_bytes"]:
                raise JobStoreError("artifact byte size mismatch")
            if hashlib.sha256(data).hexdigest() != artifact["sha256"]:
                raise JobStoreError("artifact SHA-256 mismatch")
            try:
                record = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise JobStoreError("artifact is not UTF-8 JSON") from exc
            if not isinstance(record, dict):
                raise JobStoreError("artifact must be a JSON object")
            if contracts.canonical_json(record) != data:
                raise JobStoreError("artifact JSON is not canonical")
            if record.get("schema_version") != artifact["schema_version"]:
                raise JobStoreError("artifact schema version mismatch")
            payloads.append((artifact["record_type"], record))
        sources: dict[str, dict] = {}
        for record_type, record in payloads:
            if record_type == "Source":
                source = contracts.validate_source(record)
                if source["source_id"] in sources:
                    raise JobStoreError("duplicate Source ID in Commit")
                sources[source["source_id"]] = source
        claim_ids = set()
        for record_type, record in payloads:
            if record_type == "Claim":
                claim = contracts.validate_claim(record, sources=sources)
                if claim["claim_id"] in claim_ids:
                    raise JobStoreError("duplicate Claim ID in Commit")
                claim_ids.add(claim["claim_id"])
            elif record_type != "Source":
                raise JobStoreError("unsupported artifact record type")
        return payloads

    def accept_commit(self, job_id: str, generation: int, manifest: dict, *,
                      allow_late_colab_commit: bool = False) -> dict:
        job_id = self._job_id(job_id)
        if type(generation) is not int or generation < 1:
            raise ValueError("generation must be a positive integer")
        manifest = contracts.validate_commit(manifest)
        if manifest["job_id"] != job_id or manifest["generation"] != generation:
            raise JobStoreError("Commit does not match requested job generation")
        expired = False
        with self._transaction() as connection:
            row = connection.execute("SELECT * FROM knowledge_jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise LookupError("job not found")
            if generation != row["generation"]:
                raise StaleGenerationError("job generation is stale")
            if manifest["attempt_id"] != row["attempt_id"] or manifest["directive_sha256"] != row["directive_sha256"]:
                raise StaleGenerationError("Commit does not match the active attempt and Job directive")
            existing = connection.execute("SELECT manifest_sha256,accepted_at FROM knowledge_commits WHERE job_id=? AND generation=?",
                                          (job_id, generation)).fetchone()
            if existing is not None:
                if generation != row["accepted_generation"] or row["status"] != "accepted":
                    raise StaleGenerationError("only the current accepted generation can be retried")
                if existing["manifest_sha256"] != manifest["manifest_sha256"]:
                    raise DuplicateAcceptanceError("generation already has a different accepted Commit")
                self._read_and_validate_artifacts(job_id, generation, manifest)
                # A transport retry for the exact already-accepted manifest is idempotent.
                accepted_at = existing["accepted_at"]
            elif generation <= row["accepted_generation"]:
                raise DuplicateAcceptanceError("generation already has an accepted Commit")
            elif row["status"] != "running":
                raise StaleGenerationError("job generation is stale or not running")
            else:
                now = _utc_now()
                deadline = datetime.fromisoformat(row["deadline"].replace("Z", "+00:00"))
                if now >= deadline:
                    commit_created = datetime.fromisoformat(manifest["created_at"].replace("Z", "+00:00"))
                    job_created = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
                    late_colab_result = (
                        allow_late_colab_commit and row["model_route"] == "colab" and
                        job_created <= commit_created <= deadline
                    )
                    if not late_colab_result:
                        connection.execute("UPDATE knowledge_jobs SET status='expired' WHERE job_id=?", (job_id,))
                        expired = True
                if not expired:
                    self._read_and_validate_artifacts(job_id, generation, manifest)
                    accepted_at = _iso(now)
                    stage_rel = self._stage_for(job_id, generation).relative_to(self.root).as_posix()
                    connection.execute("""INSERT INTO knowledge_commits
                        (job_id,generation,manifest_sha256,manifest_json,staging_relative,accepted_at)
                        VALUES(?,?,?,?,?,?)""", (job_id, generation, manifest["manifest_sha256"],
                                                    contracts.canonical_json(manifest).decode("utf-8"),
                                                    stage_rel, accepted_at))
                    connection.execute("""UPDATE knowledge_jobs SET status='accepted',accepted_generation=?
                        WHERE job_id=? AND generation=? AND accepted_generation<?""",
                        (generation, job_id, generation, generation))
                    if connection.execute("SELECT changes()").fetchone()[0] != 1:
                        raise DuplicateAcceptanceError("generation acceptance lost its compare-and-swap")
        if expired:
            raise ExpiredJobError("job expired before Commit acceptance")
        return {"job_id": job_id, "generation": generation, "manifest_sha256": manifest["manifest_sha256"],
                "accepted_at": accepted_at}

    def accepted_commit(self, job_id: str, generation: int | None = None) -> dict:
        job_id = self._job_id(job_id)
        job = self.get_job(job_id)
        if job is None:
            raise LookupError("job not found")
        accepted_generation = job["accepted_generation"]
        if accepted_generation == 0 or (generation is not None and generation != accepted_generation):
            raise UnacceptedCommitError("only the current accepted generation can be read")
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT * FROM knowledge_commits WHERE job_id=? AND generation=?",
                                     (job_id, accepted_generation)).fetchone()
        if row is None:
            raise LookupError("accepted Commit not found")
        manifest = contracts.validate_commit(json.loads(row["manifest_json"]))
        self._read_and_validate_artifacts(job_id, accepted_generation, manifest)
        return manifest

    def _verify_pack_files(self, directory: Path, manifest: dict) -> None:
        experts = {item["expert_id"]: item["definition_sha256"] for item in manifest["experts"]}
        seen_experts = set()
        pack_records = {"Source": {}, "Claim": {}, "LocalAdoption": {}}
        for file_record in manifest["files"]:
            path = self._artifact_path(directory, file_record["path"])
            if not path.is_file():
                raise JobStoreError("declared Pack file does not exist")
            data = path.read_bytes()
            if len(data) != file_record["size_bytes"] or hashlib.sha256(data).hexdigest() != file_record["sha256"]:
                raise JobStoreError("Pack file size or SHA-256 mismatch")
            role = file_record["role"]
            if role == "runtime":
                raise JobStoreError("arbitrary runtime files are forbidden in Pack")
            if any(part in path.name.lower() for part in ("answer_key", "answer-key", "gold-answer", "evaluator")):
                raise JobStoreError("evaluator-private material is forbidden in Pack files")
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise JobStoreError("Pack files must be UTF-8") from exc
            # Inspect every file for answer-key-shaped structured data, independent of role.
            structured = []
            try:
                structured = [json.loads(text)]
            except json.JSONDecodeError:
                if role in {"knowledge_source", "knowledge_claim", "knowledge_adoption"}:
                    try:
                        structured = [json.loads(line) for line in text.splitlines() if line.strip()]
                    except json.JSONDecodeError as exc:
                        raise JobStoreError("Pack JSONL could not be parsed") from exc
            for record in structured:
                try:
                    contracts._reject_answer_material(record)
                except contracts.ContractError as exc:
                    raise JobStoreError("answer material is forbidden in Pack files") from exc
            if role == "expert_definition":
                expert_id = file_record["expert_id"]
                if expert_id not in experts or experts[expert_id] != file_record["sha256"] or expert_id in seen_experts:
                    raise JobStoreError("expert definition does not match Pack expert hash")
                if len(structured) != 1 or not isinstance(structured[0], dict) or structured[0].get("expert_id") != expert_id:
                    raise JobStoreError("expert definition JSON must identify its manifest expert")
                seen_experts.add(expert_id)
            elif role == "knowledge_claim":
                if not structured:
                    raise JobStoreError("Pack Claim JSONL must contain records")
                for record in structured:
                    try:
                        claim = contracts.validate_claim(record)
                    except contracts.ContractError as exc:
                        raise JobStoreError("Pack claim file contains an invalid Claim") from exc
                    if claim["claim_id"] in pack_records["Claim"]:
                        raise JobStoreError("duplicate Claim ID in Pack files")
                    pack_records["Claim"][claim["claim_id"]] = claim
            elif role == "knowledge_source":
                if not structured:
                    raise JobStoreError("Pack Source JSONL must contain records")
                for record in structured:
                    try:
                        source = contracts.validate_source(record)
                    except contracts.ContractError as exc:
                        raise JobStoreError("Pack source file contains an invalid Source") from exc
                    if source["source_id"] in pack_records["Source"]:
                        raise JobStoreError("duplicate Source ID in Pack files")
                    pack_records["Source"][source["source_id"]] = source
            elif role == "knowledge_adoption":
                if manifest["flavor"] != "local_papers" or not structured:
                    raise JobStoreError("Local Papers adoption records are valid only in an overlay Pack")
                for record in structured:
                    try:
                        adoption = contracts.validate_local_adoption(record)
                    except contracts.ContractError as exc:
                        raise JobStoreError("Pack adoption file contains an invalid review record") from exc
                    claim_id = adoption["claim_id"]
                    if claim_id in pack_records["LocalAdoption"]:
                        raise JobStoreError("duplicate Local Papers adoption record")
                    pack_records["LocalAdoption"][claim_id] = adoption
        if seen_experts != set(experts):
            raise JobStoreError("each Pack expert must have exactly one definition file")
        return pack_records

    def _verify_pack_sidecar(self, directory: Path, manifest: dict) -> None:
        path = self._artifact_path(directory, "pack-manifest.json")
        if not path.is_file():
            raise JobStoreError("Pack manifest sidecar is missing")
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise JobStoreError("Pack manifest sidecar cannot be read") from exc
        if data != contracts.canonical_json(manifest):
            raise JobStoreError("Pack manifest sidecar does not match the validated manifest")

    def _accepted_pack_commit(self, connection: sqlite3.Connection, reference: dict) -> tuple[dict, list[tuple[str, dict]]]:
        row = connection.execute("""SELECT c.* FROM knowledge_commits c
            JOIN knowledge_jobs j USING(job_id)
            WHERE c.job_id=? AND c.generation=? AND c.generation=j.accepted_generation""",
            (reference["job_id"], reference["generation"])).fetchone()
        if row is None or row["manifest_sha256"] != reference["manifest_sha256"]:
            raise UnacceptedCommitError("Pack references a Commit that is not currently accepted")
        manifest = contracts.validate_commit(json.loads(row["manifest_json"]))
        payloads = self._read_and_validate_artifacts(reference["job_id"], reference["generation"], manifest)
        if any(record_type == "Claim" and record["status"] != "approved" for record_type, record in payloads):
            raise JobStoreError("Pack may include only approved Claims")
        return manifest, payloads

    def _authorize_pack_commits(self, connection: sqlite3.Connection, manifest: dict) -> None:
        if len(manifest["experts"]) != 17:
            raise JobStoreError("Pack must include all 17 pinned expert definitions")
        if manifest["flavor"] == "local_papers":
            if manifest["distribution_route"] != "local":
                raise JobStoreError("Local Papers Pack is local-route only")
            rows = connection.execute(
                "SELECT manifest_json FROM knowledge_packs WHERE root_sha256=?",
                (manifest["base_pack_root_sha256"],),
            ).fetchall()
            if len(rows) != 1:
                raise JobStoreError("Local Papers Pack must pin one registered Base Pack root")
            base_manifest = contracts.validate_pack_manifest(json.loads(rows[0]["manifest_json"]))
            if (base_manifest["flavor"] != "base" or
                    base_manifest["root_sha256"] != manifest["base_pack_root_sha256"] or
                    base_manifest["base_root_sha256"] != manifest["base_root_sha256"] or
                    contracts.canonical_json(base_manifest["experts"]) !=
                    contracts.canonical_json(manifest["experts"])):
                raise JobStoreError("Local Papers Pack expert definitions differ from its pinned Base Pack")
            self._authorize_pack_commits(connection, base_manifest)
        elif manifest["flavor"] != "base":
            raise JobStoreError("unsupported Pack flavor")
        records = []
        for reference in manifest["commits"]:
            _, payloads = self._accepted_pack_commit(connection, reference)
            records.extend(payloads)
        source_records = [record for kind, record in records if kind == "Source"]
        claim_records = [record for kind, record in records if kind == "Claim"]
        sources = {record["source_id"]: record for record in source_records}
        if len(sources) != len(source_records):
            raise JobStoreError("duplicate Source IDs across Pack Commits")
        claim_ids = [record["claim_id"] for record in claim_records]
        if len(set(claim_ids)) != len(claim_ids):
            raise JobStoreError("duplicate Claim IDs across Pack Commits")
        if manifest["flavor"] == "base" and any(
                record["rights"]["classification"] == "private" or
                record["access_scope"] == "local_private" or
                record["locator"]["kind"] == "local_uri" or
                set(record["rights"]["allowed_routes"]) == {"local"}
                for record in source_records):
            raise JobStoreError("private or local paper Source is forbidden in Base Pack")
        if set(manifest["source_ids"]) != set(sources) or set(manifest["claim_ids"]) != set(claim_ids):
            raise JobStoreError("Pack IDs do not match accepted Commit records")
        if manifest["flavor"] == "local_papers":
            base_records = self._verify_pack_files(
                self.pack_staging_dir(base_manifest["pack_id"]), base_manifest)
            if (set(sources) & set(base_records["Source"]) or
                    set(claim_ids) & set(base_records["Claim"])):
                raise JobStoreError("Local Papers record IDs collide with the pinned Base Pack")
        pack_records = self._verify_pack_files(self.pack_staging_dir(manifest["pack_id"]), manifest)
        expert_ids = {expert["expert_id"] for expert in manifest["experts"]}
        if any(claim["expert_id"] not in expert_ids for claim in pack_records["Claim"].values()):
            raise JobStoreError("Pack Claim references an expert absent from the Pack manifest")
        for kind, expected in (("Source", sources), ("Claim", {record["claim_id"]: record for record in claim_records})):
            actual = pack_records[kind]
            if set(actual) != set(expected) or any(
                    contracts.canonical_json(actual[key]) != contracts.canonical_json(expected[key]) for key in expected):
                raise JobStoreError(f"Pack {kind} records do not match accepted Commit artifacts")
        approved_claims = claim_records
        if not approved_claims:
            raise JobStoreError("Pack must reference at least one approved Claim")
        for kind, record in records:
            try:
                contracts.authorize_route([record], manifest["distribution_route"], sources=sources)
            except (contracts.ContractError, PermissionError) as exc:
                raise JobStoreError(f"Pack distribution route is not authorized: {exc}") from exc
        if manifest["flavor"] == "local_papers":
            adoptions = pack_records["LocalAdoption"]
            overlay_claims = pack_records["Claim"]
            if set(adoptions) != set(overlay_claims):
                raise JobStoreError("each Local Papers Claim must have one adoption record")
            for claim_id, adoption in adoptions.items():
                try:
                    contracts.validate_local_adoption_binding(
                        adoption, claim=overlay_claims[claim_id], sources=pack_records["Source"],
                        installation_id=manifest["installation_id"],
                        base_pack_root_sha256=manifest["base_pack_root_sha256"],
                    )
                except (contracts.ContractError, KeyError, TypeError) as exc:
                    raise JobStoreError("Local Papers adoption is stale or does not match its Claim") from exc

    def register_pack(self, manifest: dict) -> dict:
        manifest = contracts.validate_pack_manifest(manifest)
        package_dir = self.pack_staging_dir(manifest["pack_id"])
        self._verify_pack_sidecar(package_dir, manifest)
        self._verify_pack_files(package_dir, manifest)
        with self._transaction() as connection:
            self._authorize_pack_commits(connection, manifest)
            try:
                package_relative = package_dir.relative_to(self.root).as_posix()
                connection.execute("""INSERT INTO knowledge_packs
                    (pack_id,root_sha256,manifest_json,package_relative,created_at) VALUES(?,?,?,?,?)""",
                                   (manifest["pack_id"], manifest["root_sha256"],
                                    contracts.canonical_json(manifest).decode("utf-8"), package_relative,
                                    _iso(_utc_now())))
            except sqlite3.IntegrityError as exc:
                raise JobStoreError("Pack ID or root already exists") from exc
        return {"pack_id": manifest["pack_id"], "root_sha256": manifest["root_sha256"],
                "stage": manifest["stage"]}

    def get_pack(self, pack_id: str, *, expected_root_sha256: str | None = None) -> dict:
        pack_id = self._job_id(pack_id)
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT * FROM knowledge_packs WHERE pack_id=?", (pack_id,)).fetchone()
        if row is None:
            raise LookupError("Pack not found")
        manifest = contracts.validate_pack_manifest(json.loads(row["manifest_json"]))
        if expected_root_sha256 is not None and expected_root_sha256 != manifest["root_sha256"]:
            raise JobStoreError("requested Pack root does not match stored root")
        if row["root_sha256"] != manifest["root_sha256"]:
            raise JobStoreError("stored Pack root hash mismatch")
        package_dir = self._assert_within(self.root / row["package_relative"], self.staging_root)
        self._verify_pack_sidecar(package_dir, manifest)
        self._verify_pack_files(package_dir, manifest)
        with self._transaction() as connection:
            self._authorize_pack_commits(connection, manifest)
        return manifest
