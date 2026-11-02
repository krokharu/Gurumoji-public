"""Offline ZIP handoff for Colab jobs; this module does not run a model or use Drive.

The local KnowledgeJobStore remains authoritative. Colab ZIPs are untrusted input
and may only return artifacts for the exact currently running local Job.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import tempfile
import time
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import contracts
from .job_store import ExpiredJobError, JobStoreError, KnowledgeJobStore

MAX_ZIP_MEMBERS = 512
MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_REQUEST_BYTES = 8 * 1024 * 1024
_HANDOFF_MANIFEST = "handoff.json"
_REQUEST_FILE = "request.json"
_RESULT_MANIFEST = "result.json"
_RESULT_PREFIX = "artifacts/"
_FORBIDDEN_TRANSPORT_FIELDS = frozenset({
    "answer_key", "answer_keys", "answer_key_hash", "gold", "gold_answer", "expected_answer",
    "reference_answer", "correct_answer", "solution", "case_text", "case_body",
})
COLAB_WORKER_SOURCE_PATHS = (
    "src/gurumoji/__init__.py",
    "src/gurumoji/knowledge_builder/__init__.py",
    "src/gurumoji/knowledge_builder/contracts.py",
    "src/gurumoji/knowledge_builder/job_store.py",
    "src/gurumoji/knowledge_builder/transport.py",
    "src/gurumoji/knowledge_builder/colab_worker.py",
    "src/gurumoji/knowledge_builder/colab_qwen3.py",
)


class TransportError(ValueError):
    """Invalid or stale local/Colab handoff. Error text contains no file paths."""


def _fail(message: str = "invalid Colab handoff") -> None:
    raise TransportError(message)


def _parse_canonical_json(data: bytes, *, max_bytes: int = MAX_MEMBER_BYTES) -> Any:
    if len(data) > max_bytes:
        _fail("handoff JSON exceeds size limit")
    try:
        value = json.loads(data.decode("utf-8"))
        if contracts.canonical_json(value) != data:
            _fail("handoff JSON is not canonical")
        contracts._reject_answer_material(value)
        return value
    except (UnicodeDecodeError, json.JSONDecodeError, contracts.ContractError):
        _fail("handoff JSON is invalid")


def _reject_transport_secret_fields(value: Any) -> None:
    if isinstance(value, dict):
        if any(str(key).lower() in _FORBIDDEN_TRANSPORT_FIELDS for key in value):
            _fail("answer-key material is forbidden in a Colab request")
        for child in value.values():
            _reject_transport_secret_fields(child)
    elif isinstance(value, list):
        for child in value:
            _reject_transport_secret_fields(child)


def _zip_info(name: str, data: bytes) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o600) << 16
    info.file_size = len(data)
    return info


def _deterministic_zip(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(files):
            archive.writestr(_zip_info(name, files[name]), files[name], compress_type=zipfile.ZIP_DEFLATED,
                             compresslevel=9)
    return output.getvalue()


def _deadline_active(job: dict) -> bool:
    try:
        deadline = datetime.fromisoformat(job["deadline"].replace("Z", "+00:00"))
        return deadline.astimezone(timezone.utc) > datetime.now(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        return False


_JOB_FIELDS = {
    "schema_version", "job_id", "generation", "attempt_id", "status", "created_at", "deadline",
    "input_manifest_sha256", "model_route", "model_id", "prompt_version", "compiler_version",
    "retry_limit", "retry_count", "directive_sha256",
}


def _active_colab_job(store: KnowledgeJobStore, job_id: str, *, allow_accepted: bool = False,
                      allow_late_commit: bool = False) -> dict:
    job = store.get_job(job_id)
    if job is None:
        _fail("local Job does not exist")
    try:
        contracts.validate_job({field: job[field] for field in _JOB_FIELDS})
    except contracts.ContractError:
        _fail("local Job record is invalid")
    if job["model_route"] != "colab":
        _fail("Job route is not colab")
    running = job["status"] == "running" and job["accepted_generation"] < job["generation"]
    accepted = (allow_accepted and job["status"] == "accepted" and
                job["accepted_generation"] == job["generation"])
    if not running and not accepted:
        _fail("Job is not an active unaccepted generation")
    if running and not allow_late_commit and not _deadline_active(job):
        _fail("Job deadline has expired")
    return job


def _validate_source_excerpt_request(job: dict, payload: Any) -> tuple[dict[str, dict], set[tuple[str, str]]]:
    payload = contracts._object(payload, {"schema_version", "kind", "task", "sources", "excerpts"},
                                 name="Colab source-excerpt request")
    if payload["schema_version"] != 1 or payload["kind"] != "colab_source_excerpt_request":
        _fail("unsupported request kind")
    task = contracts._object(payload["task"],
                             {"expert_id", "task_kind", "prompt_version", "prompt_template_sha256"},
                             {"expert_context", "worker_source_hashes"}, name="task descriptor")
    contracts._id(task["expert_id"], "expert_id")
    if task["task_kind"] not in {"knowledge_claim_generation", "knowledge_claim_review"}:
        _fail("unsupported task kind")
    if task["prompt_version"] != job["prompt_version"]:
        _fail("task prompt version differs from local Job")
    contracts._text(task["prompt_version"], "prompt_version", max_length=500)
    contracts._hash(task["prompt_template_sha256"], "prompt_template_sha256")
    if ("expert_context" in task) != ("worker_source_hashes" in task):
        _fail("task Expert context and pinned worker source hashes must appear together")
    if "expert_context" in task:
        context = contracts._object(task["expert_context"], {"definition", "definition_sha256"},
                                    name="task expert context")
        definition = contracts._object(context["definition"], {
            "expert_id", "definition_version", "title", "role", "scope", "out_of_scope",
            "analysis_unit", "required_inputs", "prohibited_conclusions",
        }, name="task Expert definition")
        if (definition["expert_id"] != task["expert_id"] or
                type(definition["definition_version"]) is not int or definition["definition_version"] < 1):
            _fail("task Expert definition does not match task expert ID")
        for field in ("title", "role", "analysis_unit"):
            contracts._text(definition[field], f"task Expert definition {field}", max_length=2_000)
        for field in ("scope", "required_inputs", "prohibited_conclusions"):
            values = definition[field]
            if (not isinstance(values, list) or len(values) > 100 or
                    any(not isinstance(item, str) or not item.strip() or len(item) > 2_000
                        for item in values)):
                _fail(f"task Expert definition {field} is invalid")
        if not isinstance(definition["out_of_scope"], list) or len(definition["out_of_scope"]) > 100:
            _fail("task Expert definition out_of_scope is invalid")
        for item in definition["out_of_scope"]:
            item = contracts._object(item, {"text", "handoff"}, name="out_of_scope entry")
            contracts._text(item["text"], "out_of_scope.text", max_length=2_000)
            if not isinstance(item["handoff"], str) or len(item["handoff"]) > 200:
                _fail("task Expert definition handoff is invalid")
        contracts._hash(context["definition_sha256"], "expert_context.definition_sha256")
        if contracts.sha256_json(definition) != context["definition_sha256"]:
            _fail("task Expert definition hash mismatch")
        if len(contracts.canonical_json(context)) > 64_000:
            _fail("task Expert context exceeds the size limit")
        source_hashes = task["worker_source_hashes"]
        if not isinstance(source_hashes, dict) or set(source_hashes) != set(COLAB_WORKER_SOURCE_PATHS):
            _fail("task worker source hash list does not match the pinned adapter file set")
        for path, digest in source_hashes.items():
            contracts._relative_path(path, "worker source path")
            contracts._hash(digest, "worker source SHA-256")
    if not isinstance(payload["sources"], list) or not payload["sources"]:
        _fail("request requires at least one Source")
    sources: dict[str, dict] = {}
    for record in payload["sources"]:
        source = contracts.validate_source(record)
        source_id = source["source_id"]
        if source_id in sources:
            _fail("duplicate Source input")
        if (source["rights"]["classification"] == "private" or
                source["access_scope"] == "local_private" or source["locator"]["kind"] == "local_uri"):
            _fail("private Source cannot be sent to colab")
        sources[source_id] = source
    if not isinstance(payload["excerpts"], list) or not payload["excerpts"]:
        _fail("request requires source-bound excerpts")
    permitted: set[tuple[str, str]] = set()
    for excerpt in payload["excerpts"]:
        excerpt = contracts._object(excerpt, {"source_id", "source_version", "source_sha256", "anchor_id",
                                              "extracted_text_sha256", "text"}, name="SourceExcerpt")
        source = sources.get(contracts._id(excerpt["source_id"], "excerpt.source_id"))
        if source is None or source["version"] != excerpt["source_version"] or source["sha256"] != excerpt["source_sha256"]:
            _fail("SourceExcerpt does not bind to its Source version")
        anchor_id = contracts._id(excerpt["anchor_id"], "excerpt.anchor_id")
        text_value = contracts._text(excerpt["text"], "excerpt.text", max_length=500_000)
        text_hash = hashlib.sha256(text_value.encode("utf-8")).hexdigest()
        if text_hash != excerpt["extracted_text_sha256"]:
            _fail("SourceExcerpt text hash mismatch")
        anchor = next((item for item in source["anchors"] if item["anchor_id"] == anchor_id), None)
        if anchor is None or anchor["extracted_text_sha256"] != text_hash:
            _fail("SourceExcerpt does not match Source anchor")
        binding = (source["source_id"], anchor_id)
        if binding in permitted:
            _fail("duplicate SourceExcerpt")
        permitted.add(binding)
    try:
        contracts.authorize_job_route(job, list(sources.values()), sources=sources, route="colab")
    except (contracts.ContractError, PermissionError):
        _fail("Source rights do not authorize Colab route")
    return sources, permitted


def export_colab_job(store: KnowledgeJobStore, job_id: str, request_payload: Any, *,
                     approved_sources: dict[str, dict] | None = None) -> bytes:
    """Create deterministic request ZIP for a running local Job fixed to route=colab."""
    try:
        job = _active_colab_job(store, job_id)
        request_data = contracts.canonical_json(request_payload)
        if len(request_data) > MAX_REQUEST_BYTES:
            _fail("request payload exceeds size limit")
        if hashlib.sha256(request_data).hexdigest() != job["input_manifest_sha256"]:
            _fail("request payload does not match immutable Job input hash")
        _reject_transport_secret_fields(request_payload)
        request_sources, _ = _validate_source_excerpt_request(job, request_payload)
        if not isinstance(approved_sources, dict) or not approved_sources:
            _fail("trusted approved Source registry is required")
        for source_id, source in request_sources.items():
            try:
                trusted = contracts.validate_source(approved_sources[source_id])
            except (KeyError, contracts.ContractError, TypeError):
                _fail("Source is absent from trusted approved registry")
            if trusted != source:
                _fail("request Source differs from trusted approved registry")
        handoff = {
            "schema_version": 1, "kind": "colab_request", "job": job,
            "request": {"path": _REQUEST_FILE, "size_bytes": len(request_data),
                        "sha256": hashlib.sha256(request_data).hexdigest()},
        }
        return _deterministic_zip({_HANDOFF_MANIFEST: contracts.canonical_json(handoff),
                                   _REQUEST_FILE: request_data})
    except TransportError:
        raise
    except (contracts.ContractError, OSError, TypeError, ValueError, PermissionError):
        _fail()


def _read_safe_zip(data: bytes) -> tuple[zipfile.ZipFile, dict[str, zipfile.ZipInfo]]:
    if not isinstance(data, bytes) or len(data) > MAX_TOTAL_BYTES:
        _fail("ZIP is missing or exceeds size limit")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data), "r")
        infos = archive.infolist()
        if not infos or len(infos) > MAX_ZIP_MEMBERS:
            _fail("ZIP member count is invalid")
        members: dict[str, zipfile.ZipInfo] = {}
        total = 0
        for info in infos:
            name = info.filename
            parts = name.rstrip("/").split("/")
            mode = info.external_attr >> 16
            if (not name or name.endswith("/") or "\\" in name or ":" in name or name.startswith("/")
                    or any(part in {"", ".", ".."} for part in parts) or name in members
                    or stat.S_ISLNK(mode) or info.is_dir() or info.flag_bits & 0x1
                    or stat.S_IFMT(mode) not in {0, stat.S_IFREG}):
                _fail("ZIP contains an unsafe member")
            if info.file_size > MAX_MEMBER_BYTES:
                _fail("ZIP member exceeds size limit")
            total += info.file_size
            if total > MAX_TOTAL_BYTES:
                _fail("ZIP uncompressed total exceeds size limit")
            members[name] = info
        return archive, members
    except (EOFError, OSError, RuntimeError, zipfile.BadZipFile):
        _fail("ZIP is malformed")


def _zip_read(archive: zipfile.ZipFile, members: dict[str, zipfile.ZipInfo], name: str) -> bytes:
    try:
        info = members[name]
        data = archive.read(info)
        if len(data) != info.file_size or len(data) > MAX_MEMBER_BYTES:
            _fail("ZIP member size mismatch")
        return data
    except (EOFError, KeyError, OSError, RuntimeError, zipfile.BadZipFile):
        _fail("ZIP member is unreadable")


def _validate_artifact_bytes(job: dict, commit: dict, artifact_data: dict[str, bytes],
                             request_sources: dict[str, dict], permitted: set[tuple[str, str]],
                             expert_id: str) -> None:
    sources: dict[str, dict] = {}
    claims: list[dict] = []
    for artifact in commit["artifacts"]:
        relative = artifact["path"]
        data = artifact_data[relative]
        if len(data) != artifact["size_bytes"] or hashlib.sha256(data).hexdigest() != artifact["sha256"]:
            _fail("artifact size or SHA-256 mismatch")
        record = _parse_canonical_json(data)
        if not isinstance(record, dict) or record.get("schema_version") != artifact["schema_version"]:
            _fail("artifact schema version mismatch")
        try:
            if artifact["record_type"] == "Source":
                source = contracts.validate_source(record)
                if source["source_id"] in sources:
                    _fail("duplicate Source artifact")
                if (source["rights"]["classification"] == "private" or
                        source["access_scope"] == "local_private" or source["locator"]["kind"] == "local_uri"):
                    _fail("private Source cannot be returned from colab")
                sources[source["source_id"]] = source
            else:
                claims.append(record)
        except contracts.ContractError:
            _fail("Source artifact is invalid")
    parsed_claims = []
    claim_ids = set()
    for record in claims:
        try:
            claim = contracts.validate_claim(record, sources)
            if claim["status"] != "candidate":
                _fail("Colab may return candidate Claims only")
            if claim["expert_id"] != expert_id or any(
                (item["source_id"], item["anchor_id"]) not in permitted for item in claim["evidence"]
            ):
                _fail("Claim is outside the authorized task excerpts")
            if claim["claim_id"] in claim_ids:
                _fail("duplicate Claim artifact")
            claim_ids.add(claim["claim_id"])
            parsed_claims.append(claim)
        except contracts.ContractError:
            _fail("Claim artifact is invalid")
    if not sources:
        _fail("Commit must include a Source")
    if sources != request_sources:
        _fail("returned Sources differ from authorized request Sources")
    try:
        contracts.authorize_job_route(job, [*sources.values(), *parsed_claims], sources=sources, route="colab")
    except (contracts.ContractError, PermissionError):
        _fail("Colab route is not authorized by artifact rights")


@contextmanager
def _generation_lock(store: KnowledgeJobStore, job_id: str, generation: int):
    """Cross-process lock for a single Job generation's staging/acceptance."""
    lock_root = store.root / "import-locks"
    lock_root.mkdir(parents=True, exist_ok=True)
    lock_path = lock_root / (hashlib.sha256(f"{job_id}:{generation}".encode()).hexdigest() + ".lock")
    with lock_path.open("a+b") as lock_file:
        lock_file.seek(0, os.SEEK_END)
        if lock_file.tell() == 0:
            lock_file.write(b"0")
            lock_file.flush()
        lock_file.seek(0)
        if os.name == "nt":
            import msvcrt
            while True:
                try:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _stage_matches(stage: Path, commit: dict, artifact_data: dict[str, bytes], store: KnowledgeJobStore,
                   job_id: str, generation: int) -> bool:
    """True only for an exact complete stage left by a crash before DB acceptance."""
    if not stage.is_dir() or stage.is_symlink():
        return False
    expected = {item["path"] for item in commit["artifacts"]}
    actual: set[str] = set()
    for path in stage.rglob("*"):
        if path.is_symlink() or not path.is_file():
            return False
        actual.add(path.relative_to(stage).as_posix())
    if actual != expected:
        return False
    try:
        for item in commit["artifacts"]:
            path = store._artifact_path(stage, item["path"])
            if path.read_bytes() != artifact_data[item["path"]]:
                return False
    except (OSError, JobStoreError):
        return False
    return True


def import_colab_result(store: KnowledgeJobStore, archive_bytes: bytes, *,
                        approved_sources: dict[str, dict] | None = None) -> dict:
    """Validate an untrusted result ZIP, stage exact artifacts, and accept its Commit locally."""
    archive = None
    try:
        archive, members = _read_safe_zip(archive_bytes)
        if _RESULT_MANIFEST not in members or _REQUEST_FILE not in members:
            _fail("result manifest is missing")
        request_data = _zip_read(archive, members, _REQUEST_FILE)
        request_payload = _parse_canonical_json(request_data, max_bytes=MAX_REQUEST_BYTES)
        result_data = _zip_read(archive, members, _RESULT_MANIFEST)
        result = _parse_canonical_json(result_data)
        result = contracts._object(result, {"schema_version", "kind", "job", "commit"}, name="result envelope")
        if result["schema_version"] != 1 or result["kind"] != "colab_result":
            _fail("result envelope version or kind is invalid")
        remote_job = contracts._object(result["job"], {
            "job_id", "generation", "attempt_id", "directive_sha256", "input_manifest_sha256",
            "model_route", "deadline",
        }, name="result Job binding")
        local_job = _active_colab_job(store, remote_job["job_id"], allow_accepted=True,
                                      allow_late_commit=True)
        fields = ("job_id", "generation", "attempt_id", "directive_sha256", "input_manifest_sha256",
                  "model_route", "deadline")
        if any(remote_job[field] != local_job[field] for field in fields):
            _fail("result does not match the active local Job directive")
        if hashlib.sha256(request_data).hexdigest() != local_job["input_manifest_sha256"]:
            _fail("result request does not match immutable local input")
        request_sources, permitted = _validate_source_excerpt_request(local_job, request_payload)
        if not isinstance(approved_sources, dict) or not approved_sources:
            _fail("trusted approved Source registry is required")
        for source_id, source in request_sources.items():
            try:
                trusted = contracts.validate_source(approved_sources[source_id])
            except (KeyError, contracts.ContractError, TypeError):
                _fail("Source is absent from trusted approved registry")
            if trusted != source:
                _fail("request Source differs from trusted approved registry")
        commit = contracts.validate_commit(result["commit"])
        try:
            commit_created = datetime.fromisoformat(commit["created_at"].replace("Z", "+00:00"))
            job_created = datetime.fromisoformat(local_job["created_at"].replace("Z", "+00:00"))
            job_deadline = datetime.fromisoformat(local_job["deadline"].replace("Z", "+00:00"))
        except (ValueError, TypeError, AttributeError):
            _fail("Commit creation time is invalid")
        if not job_created <= commit_created <= job_deadline:
            _fail("Commit was not created within the local Job deadline")
        if (commit["job_id"] != local_job["job_id"] or commit["generation"] != local_job["generation"]
                or commit["attempt_id"] != local_job["attempt_id"]
                or commit["directive_sha256"] != local_job["directive_sha256"]):
            _fail("Commit does not match the active local Job directive")

        expected_members = {_RESULT_MANIFEST, _REQUEST_FILE,
                            *(_RESULT_PREFIX + item["path"] for item in commit["artifacts"])}
        if set(members) != expected_members:
            _fail("ZIP member set does not match Commit artifacts")
        artifact_data: dict[str, bytes] = {}
        for artifact in commit["artifacts"]:
            if artifact["size_bytes"] > MAX_MEMBER_BYTES:
                _fail("Commit artifact exceeds transport limit")
            artifact_data[artifact["path"]] = _zip_read(archive, members, _RESULT_PREFIX + artifact["path"])
        _validate_artifact_bytes(local_job, commit, artifact_data, request_sources, permitted,
                                 request_payload["task"]["expert_id"])

        with _generation_lock(store, local_job["job_id"], local_job["generation"]):
            # Re-read the local authority under the lock; another importer may have accepted.
            current = _active_colab_job(store, local_job["job_id"], allow_accepted=True,
                                        allow_late_commit=True)
            if any(current[field] != local_job[field] for field in fields):
                _fail("local Job changed during import")
            if current["status"] == "accepted":
                accepted = store.accepted_commit(current["job_id"], current["generation"])
                if accepted["manifest_sha256"] != commit["manifest_sha256"]:
                    _fail("accepted generation cannot be replaced")
                return store.accept_commit(current["job_id"], current["generation"], commit,
                                           allow_late_colab_commit=True)

            stage = store.staging_dir(current["job_id"], current["generation"])
            if not stage.is_dir() or stage.is_symlink():
                _fail("active staging directory is invalid")
            # A complete exact stage may remain if the process crashed between atomic adoption and DB CAS.
            if any(stage.iterdir()):
                if not _stage_matches(stage, commit, artifact_data, store, current["job_id"], current["generation"]):
                    _fail("staging contains partial or altered data")
                return store.accept_commit(current["job_id"], current["generation"], commit,
                                           allow_late_colab_commit=True)

            temp_stage = Path(tempfile.mkdtemp(prefix=".colab-stage-", dir=store.staging_root))
            try:
                for artifact in commit["artifacts"]:
                    target = store._artifact_path(temp_stage, artifact["path"])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open("xb") as stream:
                        stream.write(artifact_data[artifact["path"]])
                        stream.flush()
                        os.fsync(stream.fileno())
                # The generation directory is known empty under the lock. Remove only that empty directory,
                # then atomically adopt the fully prepared tree. Never remove nonempty stage data.
                if any(stage.iterdir()):
                    _fail("staging changed during import")
                stage.rmdir()
                os.replace(temp_stage, stage)
                temp_stage = None
                return store.accept_commit(current["job_id"], current["generation"], commit,
                                           allow_late_colab_commit=True)
            finally:
                if temp_stage is not None:
                    import shutil
                    shutil.rmtree(temp_stage, ignore_errors=True)
    except TransportError:
        raise
    except ExpiredJobError:
        _fail("local Job expired before Commit acceptance")
    except (contracts.ContractError, JobStoreError, OSError, TypeError, ValueError, KeyError, PermissionError):
        _fail()
    finally:
        if archive is not None:
            archive.close()
