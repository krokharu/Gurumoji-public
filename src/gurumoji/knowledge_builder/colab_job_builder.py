"""Create a one-excerpt, rights-checked Colab Qwen3 Claim job bundle."""
from __future__ import annotations

import hashlib
from pathlib import Path

from . import contracts, transport
from .colab_qwen3 import COMPILER_VERSION, MODEL_REFERENCE, PROMPT_VERSION, build_request_payload
from .job_store import KnowledgeJobStore

class ColabJobBuildError(ValueError):
    """An immutable Colab job package could not be created safely."""


def _fail(message: str) -> None:
    raise ColabJobBuildError(message)


def _worker_sources_zip() -> tuple[bytes, dict[str, str]]:
    repo_root = Path(__file__).resolve().parents[3]
    files: dict[str, bytes] = {}
    for relative in transport.COLAB_WORKER_SOURCE_PATHS:
        path = repo_root / relative
        if not path.is_file() or path.is_symlink():
            _fail("Colab worker source file is unavailable")
        files[relative] = path.read_bytes()
    manifest = {
        "schema_version": 1,
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())},
    }
    files["worker_sources_manifest.json"] = contracts.canonical_json(manifest)
    return transport._deterministic_zip(files), manifest["files"]


def build_colab_claim_job(store: KnowledgeJobStore, *, expert_definition: dict,
                          source: dict, excerpt: dict,
                          approved_sources: dict[str, dict],
                          ttl_seconds: int = 55 * 60, retry_limit: int = 2,
                          job_id: str | None = None) -> tuple[dict, bytes, bytes]:
    """Persist a Colab Job and return ``(job, upload_bundle, local_registry)``.

    ``local_registry`` is returned separately so the caller can retain it outside
    Drive and pass that local copy to ``import_colab_result`` later.
    """
    if not isinstance(approved_sources, dict) or not approved_sources:
        _fail("an independent approved Source registry is required")
    try:
        source = contracts.validate_source(source)
        trusted = contracts.validate_source(approved_sources[source["source_id"]])
    except (KeyError, contracts.ContractError, TypeError):
        _fail("Source is missing or invalid in the independent approved registry")
    if trusted != source:
        _fail("request Source differs from the independent approved registry")
    if type(ttl_seconds) is not int or not 60 <= ttl_seconds <= 55 * 60:
        _fail("Colab Job deadline must be between 1 and 55 minutes")
    if type(retry_limit) is not int or not 0 <= retry_limit <= 2:
        _fail("Colab Job retry limit must be between 0 and 2")

    request = build_request_payload(expert_definition, source, excerpt)
    job = store.create_job(
        request,
        model_route="colab",
        model_id=MODEL_REFERENCE,
        prompt_version=PROMPT_VERSION,
        compiler_version=COMPILER_VERSION,
        retry_limit=retry_limit,
        job_id=job_id,
        ttl_seconds=ttl_seconds,
    )
    request_zip = transport.export_colab_job(
        store, job["job_id"], request,
        approved_sources={source["source_id"]: trusted},
    )
    worker_zip, worker_hashes = _worker_sources_zip()
    if request["task"].get("worker_source_hashes") != worker_hashes:
        _fail("task worker hashes differ from the packaged Colab sources")
    registry = {"schema_version": 1, "sources": [trusted]}
    registry_bytes = contracts.canonical_json(registry)
    bundle_files = {
        "request.zip": request_zip,
        "approved_sources.json": registry_bytes,
        "worker_sources.zip": worker_zip,
    }
    manifest = {
        "schema_version": 1,
        "kind": "gurumoji_colab_job_bundle",
        "job_id": job["job_id"],
        "generation": job["generation"],
        "model_reference": MODEL_REFERENCE,
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(bundle_files.items())},
    }
    bundle_files["bundle_manifest.json"] = contracts.canonical_json(manifest)
    bundle_bytes = transport._deterministic_zip(bundle_files)
    return job, bundle_bytes, registry_bytes


def write_bundle_files(bundle_path: str | Path, registry_path: str | Path, *,
                       bundle_bytes: bytes, registry_bytes: bytes) -> None:
    """Create new local files without overwriting an existing job or registry."""
    bundle_target = Path(bundle_path).expanduser().absolute()
    registry_target = Path(registry_path).expanduser().absolute()
    if bundle_target == registry_target:
        _fail("bundle and local Source registry paths must be different")
    for target in (bundle_target, registry_target):
        if target.exists() or target.is_symlink():
            _fail("job output or approved registry already exists")
        parent = target.parent
        parent.mkdir(parents=True, exist_ok=True)
        if parent.is_symlink() or not parent.is_dir():
            _fail("job output parent is not a regular directory")
    for target, data in ((registry_target, registry_bytes), (bundle_target, bundle_bytes)):
        with target.open("xb") as stream:
            stream.write(data)
            stream.flush()
            import os
            os.fsync(stream.fileno())
