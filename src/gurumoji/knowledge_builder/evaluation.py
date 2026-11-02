"""Deterministic score-record builder and per-expert, per-repeat gate.

This is not a complete evaluator: it validates evaluator-produced counts and
hashes but does not run suites or judge semantic grounding. Semantic source support requires separate licensed,
evaluator-only spans, which current Source anchors do not contain. Evaluation
suite questions, answers and keys must remain outside runtime records and the
builder/job store.
"""
from __future__ import annotations

import hashlib
from typing import Any

from . import contracts


def model_config_sha256(config: Any) -> str:
    """Hash the closed model revision/quantization/context/sampling descriptor."""
    config = contracts._object(config, {"model_revision", "quantization", "context_tokens", "sampling"},
                               name="model config")
    contracts._text(config["model_revision"], "model_revision", max_length=500)
    contracts._text(config["quantization"], "quantization", max_length=200)
    if type(config["context_tokens"]) is not int or not 1 <= config["context_tokens"] <= 10_000_000:
        raise contracts.ContractError("context_tokens is invalid")
    sampling = contracts._object(config["sampling"],
                                 {"temperature", "top_p", "top_k", "seed", "max_tokens"},
                                 name="sampling config")
    for field in ("temperature", "top_p"):
        value = sampling[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 2:
            raise contracts.ContractError(f"sampling.{field} is invalid")
    if sampling["top_p"] > 1:
        raise contracts.ContractError("sampling.top_p must be at most 1")
    if sampling["top_k"] is not None and (type(sampling["top_k"]) is not int or sampling["top_k"] < 0):
        raise contracts.ContractError("sampling.top_k is invalid")
    if sampling["seed"] is not None and type(sampling["seed"]) is not int:
        raise contracts.ContractError("sampling.seed is invalid")
    if type(sampling["max_tokens"]) is not int or not 1 <= sampling["max_tokens"] <= config["context_tokens"]:
        raise contracts.ContractError("sampling.max_tokens is invalid")
    return hashlib.sha256(contracts.canonical_json(config)).hexdigest()


def build_evaluation_record(value: dict) -> dict:
    """Compute the deterministic verdict and validate one independent run."""
    required = {
        "schema_version", "evaluation_id", "expert_id", "pack_root_sha256", "suite_id", "suite_sha256",
        "rubric_version", "rubric_sha256", "model_config_sha256", "prompt_template_sha256",
        "renderer_version", "rendered_request_sha256", "rendered_request_set_sha256",
        "repeat_index", "run_id", "case_ids", "critical_claim_population_total",
        "critical_claim_population_ids", "critical_claim_population_sha256", "critical_claim_reviewed_ids",
        "critical_claim_unsupported_ids", "noncritical_claim_population_total",
        "noncritical_claim_population_ids", "noncritical_claim_population_sha256",
        "noncritical_claim_reviewed_ids", "knowledge_checklists", "categories",
        "critical_failures", "blocking_violations", "created_at",
    }
    contracts._object(value, required, name="Evaluation input")
    candidate = {**value, "verdict": "fail"}
    candidate["verdict"] = contracts.evaluation_verdict(candidate)
    return contracts.validate_evaluation(candidate)


def validate_evaluation_record(value: Any) -> dict:
    return contracts.validate_evaluation(value)


def validate_repeat_pair(first: Any, second: Any) -> tuple[dict, dict]:
    """Validate two passing independent runs without pooling their scores.

    This check is a prerequisite only; it does not create a release approval.
    """
    first = contracts.validate_evaluation(first)
    second = contracts.validate_evaluation(second)
    if {first["repeat_index"], second["repeat_index"]} != {1, 2}:
        raise contracts.ContractError("repeat pair must contain repeat indices 1 and 2")
    if first["verdict"] != "pass" or second["verdict"] != "pass":
        raise contracts.ContractError("both independent repeats must pass")
    if first["evaluation_id"] == second["evaluation_id"] or first["run_id"] == second["run_id"]:
        raise contracts.ContractError("repeat pair must have distinct evaluation and run IDs")
    same_fields = (
        "expert_id", "pack_root_sha256", "suite_id", "suite_sha256", "rubric_version", "rubric_sha256",
        "model_config_sha256", "prompt_template_sha256", "renderer_version", "rendered_request_set_sha256",
    )
    if any(first[field] != second[field] for field in same_fields):
        raise contracts.ContractError("repeat pair configuration or input binding mismatch")
    if set(first["case_ids"]) != set(second["case_ids"]):
        raise contracts.ContractError("repeat pair case sets differ")
    for field in ("critical_claim_population_ids", "critical_claim_reviewed_ids",
                  "noncritical_claim_population_ids", "noncritical_claim_reviewed_ids"):
        if set(first[field]) != set(second[field]):
            raise contracts.ContractError("repeat pair evidence audit item sets differ")
    if first["knowledge_checklists"] != second["knowledge_checklists"]:
        raise contracts.ContractError("repeat pair knowledge checklist differs")
    return (first, second) if first["repeat_index"] == 1 else (second, first)
