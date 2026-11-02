"""Offline Colab worker boundary for synthetic or injected Claim generation.

This prototype has no model, Drive, or network client. It validates the P5 request
bundle and an explicit Source authority, then delegates only task metadata and
hashed SourceExcerpt records to an injected callable. Evaluation suites and
answer keys are never accepted as worker inputs or outputs.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable

from . import contracts
from . import transport

MAX_GENERATED_CLAIMS = 100


def _worker_fail(message: str = "invalid Colab worker request") -> None:
    raise transport.TransportError(message)


def _trusted_sources(request_sources: dict[str, dict], approved_sources: Any) -> None:
    if not isinstance(approved_sources, dict) or not approved_sources:
        _worker_fail("trusted approved Source registry is required")
    for source_id, source in request_sources.items():
        try:
            trusted = contracts.validate_source(approved_sources[source_id])
        except (KeyError, contracts.ContractError, TypeError):
            _worker_fail("Source is absent from trusted approved registry")
        if trusted != source:
            _worker_fail("request Source differs from trusted approved registry")


def _validate_job(job_value: Any) -> dict:
    if not isinstance(job_value, dict):
        _worker_fail("handoff Job is invalid")
    fields = {
        "schema_version", "job_id", "generation", "attempt_id", "status", "created_at", "deadline",
        "input_manifest_sha256", "model_route", "model_id", "prompt_version", "compiler_version",
        "retry_limit", "retry_count", "directive_sha256",
    }
    try:
        job = contracts.validate_job({field: job_value[field] for field in fields})
    except (KeyError, contracts.ContractError, TypeError):
        _worker_fail("handoff Job is invalid")
    if (job["status"] != "running" or job["model_route"] != "colab" or
            job_value.get("accepted_generation", 0) >= job["generation"]):
        _worker_fail("Job is not an active Colab generation")
    if not transport._deadline_active(job):
        _worker_fail("Job deadline has expired")
    return job


def _artifact(path: str, record_type: str, value: dict) -> tuple[dict, bytes]:
    data = contracts.canonical_json(value)
    return ({"path": path, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
             "record_type": record_type, "schema_version": value["schema_version"]}, data)


def run_colab_worker(request_zip: bytes, *, approved_sources: dict[str, dict],
                     generate: Callable[[dict, list[dict]], list[dict]]) -> bytes:
    """Run an injected local generator and return an untrusted result ZIP.

    `generate(task, excerpts)` receives no PDF/body beyond the explicitly hashed
    excerpts. Its result must be candidate Claim objects; Sources always come
    from `approved_sources`. The caller must still import results through the
    local P5 adapter, which is the only acceptance authority.
    """
    archive = None
    try:
        archive, members = transport._read_safe_zip(request_zip)
        if set(members) != {transport._HANDOFF_MANIFEST, transport._REQUEST_FILE}:
            _worker_fail("request ZIP member set is invalid")
        handoff = transport._parse_canonical_json(
            transport._zip_read(archive, members, transport._HANDOFF_MANIFEST))
        handoff = contracts._object(handoff, {"schema_version", "kind", "job", "request"},
                                    name="handoff envelope")
        if handoff["schema_version"] != 1 or handoff["kind"] != "colab_request":
            _worker_fail("handoff kind is invalid")
        job = _validate_job(handoff["job"])
        request_ref = contracts._object(handoff["request"], {"path", "size_bytes", "sha256"},
                                        name="request reference")
        if request_ref["path"] != transport._REQUEST_FILE:
            _worker_fail("request path is invalid")
        request_data = transport._zip_read(archive, members, transport._REQUEST_FILE)
        if (len(request_data) != request_ref["size_bytes"] or
                hashlib.sha256(request_data).hexdigest() != request_ref["sha256"] or
                request_ref["sha256"] != job["input_manifest_sha256"]):
            _worker_fail("request hash does not match Job input")
        payload = transport._parse_canonical_json(request_data, max_bytes=transport.MAX_REQUEST_BYTES)
        transport._reject_transport_secret_fields(payload)
        sources, permitted = transport._validate_source_excerpt_request(job, payload)
        _trusted_sources(sources, approved_sources)

        task = json.loads(contracts.canonical_json(payload["task"]))
        excerpts = json.loads(contracts.canonical_json(payload["excerpts"]))
        if not callable(generate):
            _worker_fail("generator callable is required")
        generated = generate(task, excerpts)
        if not isinstance(generated, list) or len(generated) > MAX_GENERATED_CLAIMS:
            _worker_fail("generator must return a bounded Claim list")
        if not transport._deadline_active(job):
            _worker_fail("Job deadline expired during generation")
        contracts._reject_answer_material(generated)

        claims: dict[str, dict] = {}
        for raw_claim in generated:
            claim = contracts.validate_claim(raw_claim, sources)
            if claim["status"] != "candidate":
                _worker_fail("worker may return candidate Claims only")
            if claim["expert_id"] != task["expert_id"]:
                _worker_fail("Claim expert does not match task")
            if any((evidence["source_id"], evidence["anchor_id"]) not in permitted
                   for evidence in claim["evidence"]):
                _worker_fail("Claim evidence is outside requested excerpts")
            if claim["claim_id"] in claims:
                _worker_fail("duplicate Claim ID")
            claims[claim["claim_id"]] = claim
        try:
            contracts.authorize_job_route(job, [*sources.values(), *claims.values()],
                                           sources=sources, route="colab")
        except (contracts.ContractError, PermissionError):
            _worker_fail("Source or Claim rights do not authorize Colab route")

        artifacts: list[dict] = []
        files: dict[str, bytes] = {}
        for source_id in sorted(sources):
            filename = hashlib.sha256(source_id.encode("utf-8")).hexdigest()
            descriptor, data = _artifact(f"sources/{filename}.json", "Source", sources[source_id])
            artifacts.append(descriptor)
            files[descriptor["path"]] = data
        for claim_id in sorted(claims):
            filename = hashlib.sha256(claim_id.encode("utf-8")).hexdigest()
            descriptor, data = _artifact(f"claims/{filename}.json", "Claim", claims[claim_id])
            artifacts.append(descriptor)
            files[descriptor["path"]] = data
        commit = {"schema_version": 1, "job_id": job["job_id"], "generation": job["generation"],
                  "attempt_id": job["attempt_id"], "directive_sha256": job["directive_sha256"],
                  "complete": True, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
                      "+00:00", "Z"), "artifacts": artifacts}
        commit["manifest_sha256"] = contracts.sha256_json(commit)
        commit = contracts.validate_commit(commit)
        remote_job = {field: job[field] for field in (
            "job_id", "generation", "attempt_id", "directive_sha256", "input_manifest_sha256",
            "model_route", "deadline")}
        result = {"schema_version": 1, "kind": "colab_result", "job": remote_job, "commit": commit}
        files[transport._REQUEST_FILE] = request_data
        files[transport._RESULT_MANIFEST] = contracts.canonical_json(result)
        return transport._deterministic_zip({transport._RESULT_MANIFEST: files.pop(transport._RESULT_MANIFEST),
                                              **{transport._REQUEST_FILE: files.pop(transport._REQUEST_FILE)},
                                              **{transport._RESULT_PREFIX + path: value
                                                 for path, value in files.items()}})
    except transport.TransportError:
        raise
    except (contracts.ContractError, KeyError, TypeError, ValueError, PermissionError):
        _worker_fail()
    except Exception:
        _worker_fail("injected generator failed")
    finally:
        if archive is not None:
            archive.close()
