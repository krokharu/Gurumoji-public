"""Closed JSON contracts for expert knowledge production artifacts.

These validators intentionally reject unknown fields. Runtime and construction
records never carry evaluation case text or answer keys.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any, Iterable
from urllib.parse import urlsplit

SCHEMA_VERSION = 1
ROUTES = frozenset({"local", "colab", "remote_llm", "export"})
REMOTE_ROUTES = frozenset({"colab", "remote_llm", "export"})
RIGHTS_CLASSES = frozenset({"public", "licensed", "private"})
CLAIM_STATES = frozenset({"candidate", "approved", "rejected"})
CLAIM_TYPES = frozenset({"literature", "synthesis", "implementation_decision"})
_SHA256 = re.compile(r"\A[0-9a-f]{64}\Z")
_ID = re.compile(r"\A[a-zA-Z0-9][a-zA-Z0-9._:-]{0,199}\Z")
_INSTALLATION_ID = re.compile(r"\A[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}\Z")
_ANSWER_KEY_FIELDS = frozenset({
    "answer_key", "answer_keys", "answer_key_hash", "gold", "gold_answer",
    "expected_answer", "reference_answer", "case", "case_text", "case_body",
    "prompt", "prompt_text", "rendered_prompt", "rendered_request", "answer", "response",
    "completion", "question", "question_text", "input", "input_text",
})
EVALUATION_CATEGORIES = frozenset({
    "knowledge_coverage", "mandatory_items", "evidence_support", "knowledge_organization",
    "content_understanding", "applicability", "abstention", "citation_integrity",
    "privacy_leakage", "structure_integrity",
})
_EVALUATION_FAILURE_CODES = frozenset({
    "critical_misapplication", "critical_unsupported", "citation_integrity", "privacy_leakage",
    "schema_violation", "forbidden_action", "legacy_read_breakage", "other",
})
_EVALUATION_BLOCKING_CODES = frozenset({
    "schema_violation", "missing_evidence", "privacy_leakage", "forbidden_action",
    "legacy_read_breakage", "artifact_integrity", "evaluator_independence", "other",
})


class ContractError(ValueError):
    """A JSON object violates a closed versioned contract."""


def canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ContractError("value is not canonical JSON") from exc


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def local_record_id(installation_id: str, record_kind: str, original_id: str) -> str:
    """Return a path-free, stable ID scoped to one local installation."""
    if not isinstance(installation_id, str) or not _INSTALLATION_ID.fullmatch(installation_id):
        raise ContractError("installation_id is invalid")
    _choice(record_kind, {"source", "claim"}, "record_kind")
    _id(original_id, "original_id")
    digest = hashlib.sha256(canonical_json({"kind": record_kind, "id": original_id})).hexdigest()
    return f"local:{installation_id}:{record_kind}:{digest}"


def _object(value: Any, required: set[str], optional: set[str] = frozenset(), name: str = "object") -> dict:
    if not isinstance(value, dict):
        raise ContractError(f"{name} must be an object")
    missing = required - value.keys()
    extra = value.keys() - required - optional
    if missing or extra:
        raise ContractError(f"{name} fields mismatch (missing={sorted(missing)}, extra={sorted(extra)})")
    return value


def _text(value: Any, name: str, *, max_length: int = 20000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ContractError(f"{name} must be a non-empty string of at most {max_length} characters")
    return value


def _id(value: Any, name: str) -> str:
    value = _text(value, name, max_length=200)
    if not _ID.fullmatch(value):
        raise ContractError(f"{name} has an invalid identifier")
    return value


def _hash(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ContractError(f"{name} must be a lowercase SHA-256 hex digest")
    return value


def _version(value: Any, name: str = "schema_version") -> None:
    if type(value) is not int or value != SCHEMA_VERSION:
        raise ContractError(f"{name} must equal {SCHEMA_VERSION}")


def _choice(value: Any, choices: set | frozenset, name: str) -> None:
    if not isinstance(value, str) or value not in choices:
        raise ContractError(f"{name} is invalid")


def _relative_path(value: Any, name: str) -> str:
    value = _text(value, name, max_length=1000)
    path = PurePosixPath(value)
    if "\\" in value or ":" in value or path.is_absolute() or any(
            part in {"", ".", ".."} for part in value.split("/")):
        raise ContractError(f"{name} must remain within its artifact root")
    return value


def _timestamp(value: Any, name: str) -> None:
    value = _text(value, name, max_length=64)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractError(f"{name} must include a timezone")


def _rights(value: Any, name: str = "rights") -> dict:
    obj = _object(value, {"classification", "allowed_routes"}, name=name)
    _choice(obj["classification"], RIGHTS_CLASSES, f"{name}.classification")
    routes = obj["allowed_routes"]
    if not isinstance(routes, list) or any(not isinstance(route, str) or route not in ROUTES for route in routes) \
            or len(set(routes)) != len(routes):
        raise ContractError(f"{name}.allowed_routes must be unique recognized routes")
    if obj["classification"] == "private" and not set(routes).issubset({"local"}):
        raise ContractError(f"{name}: private rights may authorize only the local route")
    return obj


def validate_source(value: Any) -> dict:
    obj = _object(value, {"schema_version", "source_id", "version", "sha256", "title", "source_type",
                          "locator", "access_scope", "license", "anchors", "rights"},
                  {"authors", "publication_year", "adaptation_notice", "license_url"},
                  name="Source")
    _version(obj["schema_version"])
    _id(obj["source_id"], "source_id")
    _text(obj["version"], "version", max_length=500)
    _hash(obj["sha256"], "sha256")
    _text(obj["title"], "title", max_length=1000)
    if "authors" in obj:
        authors = obj["authors"]
        if (not isinstance(authors, list) or len(authors) > 100 or
                any(not isinstance(author, str) or not author.strip() or len(author) > 500 for author in authors) or
                len(set(authors)) != len(authors)):
            raise ContractError("authors must be a unique array of non-empty names")
    if "publication_year" in obj and obj["publication_year"] is not None:
        if type(obj["publication_year"]) is not int or not 1000 <= obj["publication_year"] <= 9999:
            raise ContractError("publication_year must be a four-digit year or null")
    if "adaptation_notice" in obj and obj["adaptation_notice"] is not None:
        _text(obj["adaptation_notice"], "adaptation_notice", max_length=1000)
    _choice(obj["source_type"], {"paper", "web", "book", "standard", "implementation", "other"}, "source_type")
    locator = _object(obj["locator"], {"kind", "value"}, name="Source locator")
    _choice(locator["kind"], {"doi", "url", "local_uri"}, "locator.kind")
    locator_value = _text(locator["value"], "locator.value", max_length=4000)
    if locator["kind"] == "doi" and not locator_value.lower().startswith("10."):
        raise ContractError("DOI locator must begin with a DOI registrant prefix")
    if locator["kind"] == "url":
        parsed = urlsplit(locator_value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ContractError("URL locator must be an absolute HTTP(S) URL")
    if locator["kind"] == "local_uri" and not locator_value.lower().startswith("file:"):
        raise ContractError("local_uri locator must use the file URI scheme")
    _choice(obj["access_scope"], {"full_text", "abstract", "bibliographic", "official_page", "local_private"},
            "access_scope")
    license_record = _object(obj["license"], {"license_id", "terms"}, name="Source license")
    _text(license_record["license_id"], "license.license_id", max_length=500)
    _text(license_record["terms"], "license.terms", max_length=4000)
    if "license_url" in obj:
        license_url = _object(obj["license_url"], {"kind", "value"}, name="Source license_url")
        if license_url["kind"] != "https":
            raise ContractError("license_url.kind must equal https")
        license_url_value = _text(license_url["value"], "license_url.value", max_length=4000)
        parsed_license_url = urlsplit(license_url_value)
        if (parsed_license_url.scheme != "https" or not parsed_license_url.netloc
                or parsed_license_url.username or parsed_license_url.password
                or any(ord(char) < 32 for char in license_url_value)):
            raise ContractError("license_url must be an absolute HTTPS URL")
    anchors = obj["anchors"]
    if not isinstance(anchors, list):
        raise ContractError("Source anchors must be an array")
    anchor_ids = set()
    for anchor in anchors:
        anchor = _object(anchor, {"anchor_id", "kind", "start", "end", "extracted_text_sha256"},
                         name="Source anchor")
        anchor_id = _id(anchor["anchor_id"], "anchor.anchor_id")
        if anchor_id in anchor_ids:
            raise ContractError("Source anchor IDs must be unique")
        anchor_ids.add(anchor_id)
        _choice(anchor["kind"], {"page", "paragraph", "section", "timestamp", "character_range"}, "anchor.kind")
        _text(anchor["start"], "anchor.start", max_length=500)
        _text(anchor["end"], "anchor.end", max_length=500)
        _hash(anchor["extracted_text_sha256"], "anchor.extracted_text_sha256")
    _rights(obj["rights"])
    return obj


def claim_review_target(value: dict) -> str:
    """Hash reviewed claim content, excluding mutable approval metadata."""
    return sha256_json({key: item for key, item in value.items() if key not in {"reviewer", "status"}})


def validate_claim(value: Any, sources: dict[str, dict] | None = None) -> dict:
    obj = _object(value, {
        "schema_version", "claim_id", "expert_id", "claim", "applicability", "exceptions", "claim_type",
        "evidence", "contradictions", "status", "provenance", "rights", "reviewer",
    }, name="Claim")
    _version(obj["schema_version"])
    _id(obj["claim_id"], "claim_id")
    _id(obj["expert_id"], "expert_id")
    _text(obj["claim"], "claim")
    for field in ("applicability", "exceptions", "contradictions"):
        if not isinstance(obj[field], list) or any(not isinstance(item, str) for item in obj[field]):
            raise ContractError(f"{field} must be an array of strings")
    _choice(obj["claim_type"], CLAIM_TYPES, "claim_type")
    evidence = obj["evidence"]
    if not isinstance(evidence, list) or not evidence:
        raise ContractError("evidence must contain at least one source span")
    source_rights: list[set[str]] = []
    for index, item in enumerate(evidence):
        item = _object(item, {"source_id", "source_version", "source_sha256", "anchor_id", "span",
                              "extracted_text_sha256", "transform_history"}, name=f"evidence[{index}]")
        source_id = _id(item["source_id"], f"evidence[{index}].source_id")
        _text(item["source_version"], f"evidence[{index}].source_version", max_length=500)
        source_hash = _hash(item["source_sha256"], f"evidence[{index}].source_sha256")
        anchor_id = _id(item["anchor_id"], f"evidence[{index}].anchor_id")
        _hash(item["extracted_text_sha256"], f"evidence[{index}].extracted_text_sha256")
        span = _object(item["span"], {"kind", "start", "end"}, name=f"evidence[{index}].span")
        _choice(span["kind"], {"page", "paragraph", "section", "timestamp", "character_range"}, "span.kind")
        _text(span["start"], "span.start", max_length=500)
        _text(span["end"], "span.end", max_length=500)
        history = item["transform_history"]
        if not isinstance(history, list):
            raise ContractError("transform_history must be an array")
        for step in history:
            step = _object(step, {"operation", "tool", "version", "output_sha256"}, name="transform step")
            for field in ("operation", "tool", "version"):
                _text(step[field], f"transform.{field}", max_length=500)
            _hash(step["output_sha256"], "transform.output_sha256")
        if sources is not None:
            source = sources.get(source_id)
            if source is None:
                raise ContractError(f"claim cites an unknown Source: {source_id}")
            validate_source(source)
            if source["version"] != item["source_version"] or source["sha256"] != source_hash:
                raise ContractError(f"claim cites a stale Source version: {source_id}")
            anchor = next((entry for entry in source["anchors"] if entry["anchor_id"] == anchor_id), None)
            if anchor is None:
                raise ContractError(f"claim cites an unknown Source anchor: {anchor_id}")
            if (anchor["kind"], anchor["start"], anchor["end"], anchor["extracted_text_sha256"]) != (
                    span["kind"], span["start"], span["end"], item["extracted_text_sha256"]):
                raise ContractError("claim evidence span does not match its Source master anchor")
            source_rights.append(set(source["rights"]["allowed_routes"]))
    provenance = _object(obj["provenance"], {"method", "created_at"}, name="provenance")
    _text(provenance["method"], "provenance.method", max_length=500)
    _timestamp(provenance["created_at"], "provenance.created_at")
    claim_rights = _rights(obj["rights"])
    if sources is not None:
        cited_sources = [sources[item["source_id"]] for item in evidence]
        source_routes = set.intersection(*(set(source["rights"]["allowed_routes"]) for source in cited_sources))
        if not set(claim_rights["allowed_routes"]).issubset(source_routes):
            raise ContractError("claim routes exceed the intersection of cited Source rights")
        restriction_rank = {"public": 0, "licensed": 1, "private": 2}
        min_classification = max(restriction_rank[source["rights"]["classification"]]
                                 for source in cited_sources)
        if restriction_rank[claim_rights["classification"]] < min_classification:
            raise ContractError("claim rights classification is broader than cited Source rights")
    _choice(obj["status"], CLAIM_STATES, "claim status")
    reviewer = _object(obj["reviewer"], {"identity", "reviewed_at", "target_sha256"}, name="reviewer")
    _text(reviewer["identity"], "reviewer.identity", max_length=500)
    _timestamp(reviewer["reviewed_at"], "reviewer.reviewed_at")
    _hash(reviewer["target_sha256"], "reviewer.target_sha256")
    if reviewer["target_sha256"] != claim_review_target(obj):
        raise ContractError("reviewer target hash does not match the reviewed Claim")
    return obj


def local_adoption_review_target(value: dict) -> str:
    """Hash the separate Local Papers adoption decision, excluding its reviewer envelope."""
    return sha256_json({key: item for key, item in value.items() if key != "reviewer"})


def validate_local_adoption(value: Any) -> dict:
    adoption = _object(value, {
        "schema_version", "installation_id", "base_pack_root_sha256", "claim_id",
        "claim_sha256", "source_versions", "status", "reviewer",
    }, name="Local Papers adoption")
    _version(adoption["schema_version"])
    if (not isinstance(adoption["installation_id"], str) or
            not _INSTALLATION_ID.fullmatch(adoption["installation_id"])):
        raise ContractError("adoption installation_id is invalid")
    _hash(adoption["base_pack_root_sha256"], "adoption.base_pack_root_sha256")
    _id(adoption["claim_id"], "adoption.claim_id")
    _hash(adoption["claim_sha256"], "adoption.claim_sha256")
    if not isinstance(adoption["source_versions"], list) or not adoption["source_versions"]:
        raise ContractError("adoption source_versions must be a non-empty array")
    source_ids = []
    for item in adoption["source_versions"]:
        item = _object(item, {"source_id", "version", "sha256", "source_record_sha256"},
                       name="adoption source version")
        source_ids.append(_id(item["source_id"], "adoption source_id"))
        _text(item["version"], "adoption source version", max_length=500)
        _hash(item["sha256"], "adoption source sha256")
        _hash(item["source_record_sha256"], "adoption source record sha256")
    if len(set(source_ids)) != len(source_ids) or source_ids != sorted(source_ids):
        raise ContractError("adoption source_versions must be unique and sorted by source_id")
    _choice(adoption["status"], {"approved", "revoked"}, "adoption.status")
    reviewer = _object(adoption["reviewer"], {"identity", "reviewed_at", "target_sha256"},
                       name="adoption reviewer")
    _text(reviewer["identity"], "adoption reviewer identity", max_length=500)
    _timestamp(reviewer["reviewed_at"], "adoption reviewer reviewed_at")
    _hash(reviewer["target_sha256"], "adoption reviewer target_sha256")
    if reviewer["target_sha256"] != local_adoption_review_target(adoption):
        raise ContractError("adoption reviewer target hash does not match the reviewed decision")
    return adoption


def validate_local_adoption_binding(value: Any, *, claim: dict, sources: dict[str, dict],
                                    installation_id: str, base_pack_root_sha256: str) -> dict:
    adoption = validate_local_adoption(value)
    if (adoption["status"] != "approved" or adoption["installation_id"] != installation_id or
            adoption["base_pack_root_sha256"] != base_pack_root_sha256 or
            adoption["claim_id"] != claim["claim_id"] or
            adoption["claim_sha256"] != sha256_json(claim)):
        raise ContractError("Local Papers adoption does not bind the approved Claim and pinned roots")
    if adoption["reviewer"]["identity"] == claim["reviewer"]["identity"]:
        raise ContractError("Local Papers adoption requires a separate reviewer identity")
    cited_source_ids = sorted({item["source_id"] for item in claim["evidence"]})
    expected_versions = [{"source_id": source_id, "version": sources[source_id]["version"],
                          "sha256": sources[source_id]["sha256"],
                          "source_record_sha256": sha256_json(sources[source_id])}
                         for source_id in cited_source_ids]
    if adoption["source_versions"] != expected_versions:
        raise ContractError("Local Papers adoption does not match current cited Source records")
    return adoption


def validate_job(value: Any) -> dict:
    obj = _object(value, {"schema_version", "job_id", "generation", "attempt_id", "status", "created_at",
                          "deadline", "input_manifest_sha256", "model_route", "model_id", "prompt_version",
                          "compiler_version", "retry_limit", "retry_count", "directive_sha256"}, name="Job")
    _version(obj["schema_version"])
    _id(obj["job_id"], "job_id")
    if type(obj["generation"]) is not int or obj["generation"] < 1:
        raise ContractError("generation must be a positive integer")
    _id(obj["attempt_id"], "attempt_id")
    _choice(obj["status"], {"queued", "running", "accepted", "expired", "cancelled"}, "job status")
    _timestamp(obj["created_at"], "created_at")
    _timestamp(obj["deadline"], "deadline")
    _hash(obj["input_manifest_sha256"], "input_manifest_sha256")
    _choice(obj["model_route"], ROUTES, "model_route")
    for field in ("model_id", "prompt_version", "compiler_version"):
        _text(obj[field], field, max_length=500)
    if type(obj["retry_limit"]) is not int or obj["retry_limit"] < 0:
        raise ContractError("retry_limit must be a non-negative integer")
    if type(obj["retry_count"]) is not int or not 0 <= obj["retry_count"] <= obj["retry_limit"]:
        raise ContractError("retry_count must be within retry_limit")
    expected = job_directive_hash(obj)
    _hash(obj["directive_sha256"], "directive_sha256")
    if obj["directive_sha256"] != expected:
        raise ContractError("Job directive hash mismatch")
    return obj


def job_directive_hash(value: dict) -> str:
    fields = ("job_id", "generation", "attempt_id", "input_manifest_sha256", "model_route", "model_id",
              "prompt_version", "compiler_version", "retry_limit", "retry_count", "deadline")
    return sha256_json({key: value[key] for key in fields})


def validate_commit(value: Any) -> dict:
    obj = _object(value, {"schema_version", "job_id", "generation", "attempt_id", "directive_sha256",
                          "complete", "created_at", "artifacts", "manifest_sha256"}, name="Commit")
    _version(obj["schema_version"])
    _id(obj["job_id"], "job_id")
    if type(obj["generation"]) is not int or obj["generation"] < 1:
        raise ContractError("generation must be a positive integer")
    _id(obj["attempt_id"], "attempt_id")
    _hash(obj["directive_sha256"], "directive_sha256")
    if obj["complete"] is not True:
        raise ContractError("Commit must be marked complete")
    _timestamp(obj["created_at"], "created_at")
    artifacts = obj["artifacts"]
    if not isinstance(artifacts, list) or not artifacts:
        raise ContractError("Commit must list at least one artifact")
    seen = set()
    for artifact in artifacts:
        artifact = _object(artifact, {"path", "size_bytes", "sha256", "record_type", "schema_version"},
                           name="artifact")
        path = _relative_path(artifact["path"], "artifact.path")
        if path in seen:
            raise ContractError("Commit artifact paths must be unique")
        seen.add(path)
        if type(artifact["size_bytes"]) is not int or artifact["size_bytes"] < 0:
            raise ContractError("artifact.size_bytes must be a non-negative integer")
        _hash(artifact["sha256"], "artifact.sha256")
        _choice(artifact["record_type"], {"Source", "Claim"}, "artifact.record_type")
        _version(artifact["schema_version"], "artifact.schema_version")
    _hash(obj["manifest_sha256"], "manifest_sha256")
    unsigned = {key: item for key, item in obj.items() if key != "manifest_sha256"}
    if sha256_json(unsigned) != obj["manifest_sha256"]:
        raise ContractError("Commit manifest hash mismatch")
    return obj


def _reject_answer_material(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in _ANSWER_KEY_FIELDS:
                raise ContractError("evaluation case text and answer keys are forbidden in runtime records")
            _reject_answer_material(item)
    elif isinstance(value, list):
        for item in value:
            _reject_answer_material(item)


def validate_evaluation(value: Any) -> dict:
    obj = _object(value, {
        "schema_version", "evaluation_id", "expert_id", "pack_root_sha256", "suite_id", "suite_sha256",
        "rubric_version", "rubric_sha256", "model_config_sha256", "prompt_template_sha256",
        "renderer_version", "rendered_request_sha256", "rendered_request_set_sha256",
        "repeat_index", "run_id", "case_ids",
        "critical_claim_population_total", "critical_claim_population_ids", "critical_claim_population_sha256",
        "critical_claim_reviewed_ids", "critical_claim_unsupported_ids",
        "noncritical_claim_population_total", "noncritical_claim_population_ids",
        "noncritical_claim_population_sha256", "noncritical_claim_reviewed_ids",
        "knowledge_checklists", "categories", "critical_failures", "blocking_violations", "verdict", "created_at",
    }, name="Evaluation")
    _reject_answer_material(obj)
    _version(obj["schema_version"])
    _id(obj["evaluation_id"], "evaluation_id")
    _id(obj["expert_id"], "expert_id")
    _hash(obj["pack_root_sha256"], "pack_root_sha256")
    _id(obj["suite_id"], "suite_id")
    for field in ("suite_sha256", "rubric_sha256", "model_config_sha256", "prompt_template_sha256",
                  "rendered_request_sha256", "rendered_request_set_sha256"):
        _hash(obj[field], field)
    for field in ("rubric_version", "renderer_version"):
        _text(obj[field], field, max_length=200)
    if type(obj["repeat_index"]) is not int or obj["repeat_index"] not in {1, 2}:
        raise ContractError("repeat_index must be 1 or 2; each repeat is an independent record")
    _id(obj["run_id"], "run_id")
    case_ids = obj["case_ids"]
    if (not isinstance(case_ids, list) or len(case_ids) != 40 or
            any(not isinstance(item, str) or not _ID.fullmatch(item) for item in case_ids) or
            len(set(case_ids)) != len(case_ids)):
        raise ContractError("final evaluation requires 40 unique opaque case IDs")
    def opaque_id_list(field: str, *, maximum: int = 100_000) -> list[str]:
        values = obj[field]
        if (not isinstance(values, list) or len(values) > maximum or
                any(not isinstance(item, str) or not _ID.fullmatch(item) for item in values) or
                len(set(values)) != len(values)):
            raise ContractError(f"{field} must be a bounded array of unique opaque IDs")
        return values

    critical_population_ids = opaque_id_list("critical_claim_population_ids")
    critical_reviewed_ids = opaque_id_list("critical_claim_reviewed_ids")
    critical_unsupported_ids = opaque_id_list("critical_claim_unsupported_ids")
    critical_population_total = obj["critical_claim_population_total"]
    if type(critical_population_total) is not int or critical_population_total != len(critical_population_ids):
        raise ContractError("critical claim population count does not match its IDs")
    _hash(obj["critical_claim_population_sha256"], "critical_claim_population_sha256")
    if sha256_json(sorted(critical_population_ids)) != obj["critical_claim_population_sha256"]:
        raise ContractError("critical claim population hash mismatch")
    if set(critical_reviewed_ids) != set(critical_population_ids):
        raise ContractError("every critical claim must be reviewed")
    if not set(critical_unsupported_ids).issubset(critical_population_ids):
        raise ContractError("unsupported critical claim IDs must belong to the critical population")

    noncritical_population_ids = opaque_id_list("noncritical_claim_population_ids")
    noncritical_reviewed_ids = opaque_id_list("noncritical_claim_reviewed_ids", maximum=60)
    noncritical_population_total = obj["noncritical_claim_population_total"]
    if type(noncritical_population_total) is not int or noncritical_population_total != len(noncritical_population_ids):
        raise ContractError("noncritical claim population count does not match its IDs")
    if set(critical_population_ids).intersection(noncritical_population_ids):
        raise ContractError("critical and noncritical claim populations must be disjoint")
    _hash(obj["noncritical_claim_population_sha256"], "noncritical_claim_population_sha256")
    if sha256_json(sorted(noncritical_population_ids)) != obj["noncritical_claim_population_sha256"]:
        raise ContractError("noncritical claim population hash mismatch")
    expected_noncritical_sample = min(60, noncritical_population_total)
    if (len(noncritical_reviewed_ids) != expected_noncritical_sample or
            not set(noncritical_reviewed_ids).issubset(noncritical_population_ids)):
        raise ContractError("noncritical sample must be min(60,population) unique population IDs")

    categories = obj["categories"]
    if not isinstance(categories, dict) or set(categories) != EVALUATION_CATEGORIES:
        raise ContractError("categories must contain the closed evaluation rubric")
    for category, counts in categories.items():
        counts = _object(counts, {"passed", "total"}, name=f"category {category}")
        minimum_total = 0 if category == "evidence_support" else 1
        if (type(counts["passed"]) is not int or type(counts["total"]) is not int or
                not 0 <= counts["passed"] <= counts["total"] or not minimum_total <= counts["total"] <= 10000):
            raise ContractError("category passed/total counts are invalid")
    if categories["content_understanding"]["total"] != 15:
        raise ContractError("content_understanding final denominator must be 15")
    if categories["applicability"]["total"] != 15:
        raise ContractError("applicability final denominator must be 15")
    if categories["abstention"]["total"] != 10:
        raise ContractError("abstention final denominator must be 10")
    if categories["evidence_support"] != {
        "passed": categories["evidence_support"]["passed"], "total": expected_noncritical_sample
    } or categories["evidence_support"]["total"] != len(noncritical_reviewed_ids):
        raise ContractError("evidence_support score must bind the sampled noncritical claim IDs")

    checklists = obj["knowledge_checklists"]
    checklist_categories = {"knowledge_coverage", "mandatory_items", "knowledge_organization"}
    if not isinstance(checklists, dict) or set(checklists) != checklist_categories:
        raise ContractError("knowledge_checklists must bind the closed checklist categories")
    for category, checklist in checklists.items():
        checklist = _object(checklist, {"population_ids", "population_sha256", "passed_item_ids"},
                            name=f"{category} checklist")
        population_ids = checklist["population_ids"]
        passed_item_ids = checklist["passed_item_ids"]
        for field, items in (("population_ids", population_ids), ("passed_item_ids", passed_item_ids)):
            if (not isinstance(items, list) or len(items) > 10000 or
                    any(not isinstance(item, str) or not _ID.fullmatch(item) for item in items) or
                    len(set(items)) != len(items)):
                raise ContractError(f"{category}.{field} must contain unique opaque IDs")
        if not population_ids or not set(passed_item_ids).issubset(population_ids):
            raise ContractError(f"{category} checklist population or passed IDs are invalid")
        _hash(checklist["population_sha256"], f"{category}.population_sha256")
        if sha256_json(sorted(population_ids)) != checklist["population_sha256"]:
            raise ContractError(f"{category} checklist population hash mismatch")
        if categories[category] != {"passed": len(passed_item_ids), "total": len(population_ids)}:
            raise ContractError(f"{category} counts do not match checklist IDs")
    for category in ("citation_integrity", "privacy_leakage", "structure_integrity"):
        if categories[category]["total"] != 40:
            raise ContractError(f"{category} final denominator must be 40 cases")

    critical_failures = obj["critical_failures"]
    if not isinstance(critical_failures, list) or len(critical_failures) > 100_000:
        raise ContractError("critical_failures must be a bounded array")
    for failure in critical_failures:
        failure = _object(failure, {"category", "code"}, {"case_id", "evidence_item_id"}, name="critical failure")
        _choice(failure["category"], EVALUATION_CATEGORIES, "critical failure category")
        _choice(failure["code"], _EVALUATION_FAILURE_CODES, "critical failure code")
        if "case_id" not in failure and "evidence_item_id" not in failure:
            raise ContractError("critical failure requires an opaque case or evidence item ID")
        if "case_id" in failure:
            _id(failure["case_id"], "critical failure case_id")
            if failure["case_id"] not in case_ids:
                raise ContractError("critical failure case_id is not in this run")
        if "evidence_item_id" in failure:
            _id(failure["evidence_item_id"], "critical failure evidence_item_id")
            if failure["evidence_item_id"] not in critical_population_ids:
                raise ContractError("critical failure evidence ID is not in critical claim population")
        if failure["code"] == "critical_unsupported" and (
            failure["category"] != "evidence_support" or "evidence_item_id" not in failure or
            failure["evidence_item_id"] not in critical_unsupported_ids
        ):
            raise ContractError("critical unsupported failure must bind a listed unsupported critical claim")
        if failure["code"] == "critical_misapplication" and failure["category"] != "applicability":
            raise ContractError("critical misapplication must be classified under applicability")
    unsupported_failure_ids = {failure.get("evidence_item_id") for failure in critical_failures
                               if failure["code"] == "critical_unsupported"}
    if unsupported_failure_ids != set(critical_unsupported_ids):
        raise ContractError("unsupported critical claim IDs and critical failures must match")
    blockers = obj["blocking_violations"]
    if not isinstance(blockers, list) or len(blockers) > 1000:
        raise ContractError("blocking_violations must be a bounded array")
    for violation in blockers:
        violation = _object(violation, {"case_id", "code"}, name="blocking violation")
        _id(violation["case_id"], "blocking violation case_id")
        _choice(violation["code"], _EVALUATION_BLOCKING_CODES, "blocking violation code")
        if violation["case_id"] not in case_ids:
            raise ContractError("blocking violation must refer to an opaque case_id in this run")

    expected_verdict = evaluation_verdict(obj)
    _choice(obj["verdict"], {"pass", "fail"}, "verdict")
    if obj["verdict"] != expected_verdict:
        raise ContractError("Evaluation verdict does not match the deterministic gate")
    _timestamp(obj["created_at"], "created_at")
    return obj


def evaluation_verdict(value: dict) -> str:
    """Apply per-expert, per-repeat thresholds. Records are never pooled."""
    categories = value["categories"]
    thresholds = {
        "knowledge_coverage": (90, 100),
        "mandatory_items": (100, 100),
        "evidence_support": (95, 100),
        "knowledge_organization": (95, 100),
        "content_understanding": (90, 100),
        "citation_integrity": (100, 100),
        "privacy_leakage": (100, 100),  # passed means a case has no privacy leakage
        "structure_integrity": (100, 100),
    }
    passed = not value["critical_failures"] and not value["blocking_violations"]
    for category, (minimum_percent, _unused) in thresholds.items():
        counts = categories[category]
        passed = passed and counts["passed"] * 100 >= counts["total"] * minimum_percent
    applicability = categories["applicability"]
    passed = passed and applicability["passed"] >= 14
    abstention = categories["abstention"]
    passed = passed and abstention["passed"] == 10
    return "pass" if passed else "fail"


def compute_local_overlay_root_sha256(*, installation_id: str, base_pack_root_sha256: str,
                                      commits: list[dict], claim_ids: list[str],
                                      source_ids: list[str], files: list[dict]) -> str:
    """Bind a private overlay to one installation and one exact Base Pack."""
    if not isinstance(installation_id, str) or not _INSTALLATION_ID.fullmatch(installation_id):
        raise ContractError("installation_id is invalid")
    _hash(base_pack_root_sha256, "base_pack_root_sha256")
    overlay_files = sorted(
        [{key: item[key] for key in ("path", "size_bytes", "sha256", "role")}
         for item in files if item.get("role") in {"knowledge_source", "knowledge_claim", "knowledge_adoption"}],
        key=lambda item: item["path"],
    )
    return sha256_json({
        "installation_id": installation_id,
        "base_pack_root_sha256": base_pack_root_sha256,
        "commits": sorted(commits, key=lambda item: (item["job_id"], item["generation"], item["manifest_sha256"])),
        "claim_ids": sorted(claim_ids),
        "source_ids": sorted(source_ids),
        "files": overlay_files,
    })


def validate_pack_manifest(value: Any) -> dict:
    obj = _object(value, {"schema_version", "pack_id", "flavor", "stage", "distribution_route", "compiler_version", "experts", "commits",
                          "claim_ids", "source_ids", "files", "base_root_sha256", "overlay_root_sha256",
                          "root_sha256"}, {"installation_id", "base_pack_root_sha256"}, name="Pack manifest")
    _version(obj["schema_version"])
    _id(obj["pack_id"], "pack_id")
    _choice(obj["flavor"], {"base", "local_papers"}, "pack flavor")
    _choice(obj["stage"], {"internal_candidate"}, "stage")
    _choice(obj["distribution_route"], ROUTES, "distribution_route")
    _text(obj["compiler_version"], "compiler_version", max_length=200)
    if not isinstance(obj["experts"], list) or not obj["experts"]:
        raise ContractError("experts must be a non-empty array")
    for expert in obj["experts"]:
        expert = _object(expert, {"expert_id", "source_note_sha256", "definition_sha256"}, name="Pack expert")
        _id(expert["expert_id"], "expert_id")
        _hash(expert["source_note_sha256"], "source_note_sha256")
        _hash(expert["definition_sha256"], "definition_sha256")
    if len({expert["expert_id"] for expert in obj["experts"]}) != len(obj["experts"]):
        raise ContractError("expert IDs must be unique")
    _hash(obj["base_root_sha256"], "base_root_sha256")
    expected_base_root = sha256_json([
        {"expert_id": expert["expert_id"], "source_note_sha256": expert["source_note_sha256"],
         "definition_sha256": expert["definition_sha256"]}
        for expert in sorted(obj["experts"], key=lambda item: item["expert_id"])
    ])
    if expected_base_root != obj["base_root_sha256"]:
        raise ContractError("Base root hash does not match pinned expert source and definition hashes")
    if obj["flavor"] == "base" and obj["overlay_root_sha256"] is not None:
        raise ContractError("Base Pack must not have an overlay root")
    if obj["flavor"] == "base" and ({"installation_id", "base_pack_root_sha256"} & obj.keys()):
        raise ContractError("Base Pack must not include Local Papers pin fields")
    if obj["flavor"] == "local_papers":
        if "installation_id" not in obj or "base_pack_root_sha256" not in obj:
            raise ContractError("Local Papers Pack requires installation and exact Base Pack pins")
        if not isinstance(obj["installation_id"], str) or not _INSTALLATION_ID.fullmatch(obj["installation_id"]):
            raise ContractError("installation_id is invalid")
        _hash(obj["base_pack_root_sha256"], "base_pack_root_sha256")
        if obj["distribution_route"] != "local":
            raise ContractError("Local Papers Pack may use only the local route")
        if len(obj["experts"]) != 17:
            raise ContractError("Local Papers Pack must pin all 17 Base expert definitions")
        _hash(obj["overlay_root_sha256"], "overlay_root_sha256")
    for field in ("claim_ids", "source_ids"):
        values = obj[field]
        if not isinstance(values, list) or any(not isinstance(item, str) or not _ID.fullmatch(item) for item in values):
            raise ContractError(f"{field} must contain stable IDs")
        if len(set(values)) != len(values):
            raise ContractError(f"{field} must be unique")
    if not obj["claim_ids"] or not obj["source_ids"]:
        raise ContractError("Pack requires at least one Claim and Source")
    if obj["flavor"] == "local_papers":
        claim_namespace = f"local:{obj['installation_id']}:claim:"
        source_namespace = f"local:{obj['installation_id']}:source:"
        if any(not item.startswith(claim_namespace) or len(item) == len(claim_namespace)
               for item in obj["claim_ids"]):
            raise ContractError("Local Papers Claim IDs must be namespaced to the installation")
        if any(not item.startswith(source_namespace) or len(item) == len(source_namespace)
               for item in obj["source_ids"]):
            raise ContractError("Local Papers Source IDs must be namespaced to the installation")
    elif any(item.startswith("local:") for item in (*obj["claim_ids"], *obj["source_ids"])):
        raise ContractError("Local Papers namespaced IDs are forbidden in Base Pack")
    if not isinstance(obj["commits"], list) or not obj["commits"]:
        raise ContractError("Pack must reference at least one accepted Commit")
    for commit in obj["commits"]:
        commit = _object(commit, {"job_id", "generation", "manifest_sha256"}, name="Pack commit reference")
        _id(commit["job_id"], "commit.job_id")
        if type(commit["generation"]) is not int or commit["generation"] < 1:
            raise ContractError("commit generation must be positive")
        _hash(commit["manifest_sha256"], "commit.manifest_sha256")
    if not isinstance(obj["files"], list) or not obj["files"]:
        raise ContractError("Pack files must be a non-empty array")
    seen = set()
    for item in obj["files"]:
        item = _object(item, {"path", "size_bytes", "sha256", "role"}, {"expert_id"}, name="Pack file")
        path = _relative_path(item["path"], "pack file path")
        if path in seen:
            raise ContractError("Pack file paths must be unique")
        seen.add(path)
        if type(item["size_bytes"]) is not int or item["size_bytes"] < 0:
            raise ContractError("Pack file size must be non-negative")
        _hash(item["sha256"], "pack file hash")
        _choice(item["role"], {"knowledge_claim", "knowledge_source", "knowledge_adoption", "expert_definition"},
                "pack file role")
        if item["role"] == "expert_definition":
            _id(item.get("expert_id"), "pack expert definition expert_id")
        elif "expert_id" in item:
            raise ContractError("expert_id is valid only for expert_definition files")
    roles = [item["role"] for item in obj["files"]]
    if roles.count("knowledge_source") != 1 or roles.count("knowledge_claim") != 1:
        raise ContractError("Pack must contain one Source file and one Claim file")
    if obj["flavor"] == "local_papers" and roles.count("knowledge_adoption") != 1:
        raise ContractError("Local Papers Pack must contain one adoption record file")
    if obj["flavor"] == "base" and "knowledge_adoption" in roles:
        raise ContractError("Local Papers adoption records are forbidden in Base Pack")
    if obj["flavor"] == "local_papers":
        expected_overlay_root = compute_local_overlay_root_sha256(
            installation_id=obj["installation_id"],
            base_pack_root_sha256=obj["base_pack_root_sha256"],
            commits=obj["commits"], claim_ids=obj["claim_ids"], source_ids=obj["source_ids"],
            files=obj["files"],
        )
        if expected_overlay_root != obj["overlay_root_sha256"]:
            raise ContractError("Local Papers overlay root does not match its Base pin and local records")
    _hash(obj["root_sha256"], "root_sha256")
    unsigned = {key: item for key, item in obj.items() if key != "root_sha256"}
    if sha256_json(unsigned) != obj["root_sha256"]:
        raise ContractError("Pack root hash mismatch")
    return obj


def validate_record(record_type: str, value: Any, sources: dict[str, dict] | None = None) -> dict:
    validators = {"Source": validate_source, "Claim": lambda item: validate_claim(item, sources),
                  "Evaluation": validate_evaluation}
    try:
        return validators[record_type](value)
    except KeyError as exc:
        raise ContractError("unsupported artifact record type") from exc


def _require_export_attribution(source: dict) -> None:
    if not source.get("authors"):
        raise PermissionError("export requires explicit author attribution")
    if source["source_type"] == "paper" and source.get("publication_year") is None:
        raise PermissionError("export requires publication year for paper sources")
    if "license_url" not in source:
        raise PermissionError("export requires an HTTPS license URL")
    if not source.get("adaptation_notice"):
        raise PermissionError("export requires an explicit adaptation notice")


def authorize_route(records: Iterable[dict], route: str, *, sources: dict[str, dict] | None = None) -> None:
    """Fail closed before remote send unless every record and cited source permits route."""
    if route not in ROUTES:
        raise ContractError("unknown route")
    source_map = sources or {}
    for record in records:
        if record.get("schema_version") == SCHEMA_VERSION and "evidence" in record:
            validate_claim(record, source_map)
            for evidence in record["evidence"]:
                source = source_map[evidence["source_id"]]
                if route == "export":
                    _require_export_attribution(source)
                if route not in source["rights"]["allowed_routes"]:
                    raise PermissionError(f"route {route} is not allowed by source {evidence['source_id']}")
        elif "rights" in record:
            validate_source(record)
            if route == "export":
                _require_export_attribution(record)
        else:
            raise ContractError("route authorization accepts only Source or Claim records")
        if route not in record["rights"]["allowed_routes"]:
            raise PermissionError(f"route {route} is not allowed by record")




def authorize_job_route(job: dict, records: Iterable[dict], *, sources: dict[str, dict], route: str) -> None:
    """Authorize the requested destination against the immutable Job directive and all rights."""
    fields = {key: job[key] for key in (
        "schema_version", "job_id", "generation", "attempt_id", "status", "created_at", "deadline",
        "input_manifest_sha256", "model_route", "model_id", "prompt_version", "compiler_version",
        "retry_limit", "retry_count", "directive_sha256",
    )}
    validate_job(fields)
    if route != fields["model_route"]:
        raise ContractError("requested route does not match the fixed Job model route")
    authorize_route(records, route, sources=sources)
