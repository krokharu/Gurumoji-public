"""Pure contracts and decisions for the milestone analysis pipeline.

This module deliberately has no Flask, SQLite, filesystem, environment, or
provider imports.  The HTTP/command adapters normalize requests, this module
decides whether they are admissible, and ``analysis_pipeline`` performs the
durable work.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any


CONTRACT_VERSION = "analysis-core-1"
TRANSITION_VERSION = "analysis-transitions-3-1"
DECISION_VERSION = "analysis-decisions-3-1"
PIPELINE_VERSION = "analysis-pipeline-1"
TERMINAL_SUCCESS = frozenset({"committed", "reused", "not_applicable"})
ACTIVE_STEP_STATES = ("checking", "ready", "running", "validating", "persisting", "cancelling")
REUSABLE_STEPS = frozenset({"participation", "conversation_dynamics", "manual_measurement"})
PIPELINE_STATES = frozenset({
    "accepted", "running", "waiting", "cancelling", "completed", "failed",
    "cancelled",
})
STEP_STATES = frozenset({
    "planned", "checking", "ready", "running", "validating", "persisting",
    "committed", "reused", "waiting_resource", "awaiting_input", "retry_wait",
    "blocked", "failed", "cancelling", "cancelled", "interrupted",
    "not_applicable",
})
MILESTONE_STATES = frozenset({
    "pending", "active", "waiting", "committed", "failed", "cancelled",
})
PUBLICATION_STATES = frozenset({
    "pending", "publishing", "published", "failed", "conflict", "unknown",
    "not_selected",
})
WAIT_REASONS = frozenset({
    "data", "definition", "retry", "resource", "remote_unknown", "storage",
    "publication",
})

ALLOWED_TRANSITIONS = {
    "pipeline": {
        "accepted": {"running", "waiting", "cancelling", "failed"},
        "running": {"waiting", "cancelling", "completed", "failed"},
        "waiting": {"accepted", "cancelling", "failed"},
        "cancelling": {"cancelled", "failed"},
        "completed": set(), "failed": set(), "cancelled": set(),
    },
    "step": {
        "planned": {"checking", "cancelled"},
        "checking": {"ready", "failed", "interrupted", "not_applicable", "cancelled", "reused"},
        "ready": {"running", "failed", "interrupted", "cancelled"},
        "waiting_resource": set(),
        "running": {"validating", "failed", "cancelling",
                    "interrupted"},
        "validating": {"persisting", "failed", "cancelling", "interrupted"},
        "persisting": {"committed", "failed", "cancelling", "interrupted"},
        "retry_wait": set(), "awaiting_input": set(), "blocked": set(),
        "cancelling": {"cancelled", "failed", "interrupted"},
        "interrupted": set(),
        "committed": set(), "reused": set(), "failed": set(),
        "cancelled": set(), "not_applicable": set(),
    },
    "milestone": {
        "pending": {"active", "cancelled"},
        "active": {"waiting", "committed", "failed", "cancelled"},
        "waiting": {"active", "failed", "cancelled"},
        "committed": set(), "failed": set(), "cancelled": set(),
    },
    "publication": {
        "pending": {"publishing", "not_selected"},
        "publishing": {"published", "failed", "conflict", "unknown"},
        "failed": {"publishing"}, "conflict": {"publishing"},
        "unknown": {"publishing"}, "published": {"publishing"}, "not_selected": set(),
    },
}

RESERVED_STATES = {"step": frozenset({"waiting_resource", "awaiting_input", "retry_wait", "blocked"})}
# These IDs describe the checks made by Runtime at the existing execution
# boundaries. A new attempt always starts at planned; old reports never reopen it.
_TARGET_GUARDS = {
    "pipeline": {"accepted": "recovery.valid", "running": "execution.accepted",
                 "waiting": "execution.wait", "cancelling": "cancel.requested",
                 "cancelled": "cancel.settled", "failed": "execution.failed",
                 "completed": "pipeline.complete"},
    "step": {"checking": "attempt.current", "ready": "eligibility.allowed",
             "running": "execution.ready", "validating": "report.received",
             "persisting": "artifact.valid", "committed": "artifact.persisted",
             "not_applicable": "eligibility.not_applicable", "failed": "execution.failed",
             "cancelling": "cancel.requested", "cancelled": "cancel.settled",
             "interrupted": "process.restarted", "reused": "step.reuse_verified"},
    "publication": {"publishing": "publication.retry", "not_selected": "publication.unselected",
                    "published": "publication.confirmed", "failed": "publication.failed",
                    "conflict": "publication.conflict", "unknown": "publication.unknown"},
    "milestone": {"active": "parents.committed", "waiting": "execution.wait",
                  "committed": "steps.committed", "failed": "execution.failed",
                  "cancelled": "cancel.settled"},
}
TRANSITION_GUARDS = {
    machine: {(current, target):
              ("process.restarted" if machine == "pipeline" and current == "accepted" and target == "waiting"
               else _TARGET_GUARDS[machine][target])
              for current, targets in states.items() for target in targets}
    for machine, states in ALLOWED_TRANSITIONS.items()
}


def transition_guard(machine: str, current: str, target: str) -> str:
    return TRANSITION_GUARDS.get(machine, {}).get((current, target), "")


def state_machine_contracts() -> dict[str, Any]:
    """Export the sole transition authority for the design contract and tests."""
    return {machine: {
        "rule_version": TRANSITION_VERSION,
        "states": list(states),
        "reserved": sorted(RESERVED_STATES.get(machine, ())),
        "transitions": [{"from": current, "to": target, "guard": guards[(current, target)]}
                        for current, targets in states.items() for target in sorted(targets)],
    } for machine, states in ALLOWED_TRANSITIONS.items()
       for guards in [TRANSITION_GUARDS[machine]]}

CAPABILITIES = {
    "methods": {
        "participation": {"status": "available", "milestone": "M2", "llm": False},
        "conversation_dynamics": {"status": "available", "milestone": "M2", "llm": False},
        "manual_measurement": {
            "status": "available", "milestone": "M5", "llm": False,
            "definition_methods": {
                "frequency": {"inference_scope": "descriptive"},
                "descriptive": {"inference_scope": "descriptive"},
            },
        },
        "outline": {"status": "unavailable", "reason": "初回範囲では既存確定アウトラインの閲覧のみです。"},
        "stance": {"status": "unavailable", "reason": "立場推定は未提供です。"},
        "interview_evaluation": {"status": "unavailable", "reason": "JEV8軸はEVALゲート未完了です。"},
        "inferential_statistics": {"status": "unavailable", "reason": "初回範囲は記述集計のみです。"},
    },
    "exports": {
        "json": {"status": "available"},
        "csv": {"status": "available"},
        "zip": {"status": "available"},
        "xlsx": {"status": "available", "source": "verified_typed_package"},
        "sav": {"status": "available", "source": "verified_typed_package", "container": "zip"},
        "static_image": {"status": "available", "formats": ["svg", "png"], "dataset_required": True},
    },
    "llm_roles": {
        "manual": {"status": "available", "external": False},
        "all": {"status": "unavailable", "reason": "初回pipelineは外部LLMを呼びません。"},
    },
    "planning_roles": {
        "o01": {"status": "available", "engines": ["transformer", "lmstudio", "openai", "google"]},
    },
}

DEFINITION_TYPES = frozenset({"string", "number", "boolean", "category"})
MEASUREMENT_LEVELS = frozenset({"nominal", "ordinal", "interval", "ratio"})
SOURCE_COLUMNS = frozenset({
    "speaker", "speaker_name", "role", "text", "duration", "characters",
    "question_candidate",
})
MEASUREMENT_RULES = frozenset({
    "identity", "text_length", "nonempty", "duration", "boolean_true",
})
SUPPORTED_METHODS = frozenset(CAPABILITIES["methods"]["manual_measurement"]["definition_methods"])


class AnalysisContractError(ValueError):
    """A structurally valid request that violates an analysis contract."""

    def __init__(self, message: str, *, code: str = "invalid_request", field: str = ""):
        super().__init__(message)
        self.code = code
        self.field = field


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


EMBEDDING_STANDARD_V1 = {
    "standard_id": "embedding-standard-v1",
    "model_name": "intfloat/multilingual-e5-small",
    "model_revision": "614241f622f53c4eeff9890bdc4f31cfecc418b3",
    "dimensions": 384, "encoding": "int8-scale-127",
    "query_prefix": "query: ", "passage_prefix": "passage: ",
}


def validate_embedding_compatibility(values: list[dict[str, Any]], *,
                                     standard: dict[str, Any] | None = None) -> dict[str, Any]:
    """Accept one explicitly versioned coordinate system, never mixed vectors."""
    expected = EMBEDDING_STANDARD_V1 if standard is None else standard
    keys = ("model_name", "model_revision", "dimensions", "encoding")
    if (any(not isinstance(expected.get(key), str) or not expected[key] for key in
            ("model_name", "model_revision", "encoding"))
            or type(expected.get("dimensions")) is not int or expected["dimensions"] <= 0):
        raise AnalysisContractError("埋め込み標準の設定が正しくありません。", code="embedding_standard_invalid")
    for value in values:
        if (not isinstance(value, dict) or any(value.get(key) != expected[key] for key in keys)
                or type(value.get("dimensions")) is not int):
            raise AnalysisContractError("埋め込み標準が一致しません。同じモデル・版で再計算してください。",
                                        code="embedding_standard_mismatch")
    return dict(expected)


def definition_identity(definition: dict[str, Any]) -> str:
    """Same normalized definition body as the immutable execution binding."""
    return fingerprint(validate_definition(definition, require_version=True))


def group_definitions_by_hash(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group frozen definitions across conversations after verifying every hash."""
    groups: dict[str, dict[str, Any]] = {}
    seen = set()
    for snapshot in snapshots:
        item_id = snapshot.get("item_id")
        _graph_component(item_id)
        payload = validate_definition(snapshot.get("payload"), require_version=True)
        digest = definition_identity(payload)
        if snapshot.get("definition_hash") != digest:
            raise AnalysisContractError("固定定義のhashが一致しません。", code="definition_hash_mismatch")
        member = (item_id, payload["definition_id"])
        if member in seen:
            raise AnalysisContractError("集計対象の会話・定義が重複しています。", code="definition_member_duplicate")
        seen.add(member)
        group = groups.setdefault(digest, {"definition_hash": digest, "definition": payload, "members": []})
        group["members"].append({"item_id": item_id, "definition_id": payload["definition_id"]})
    return [{**groups[key], "members": sorted(groups[key]["members"], key=lambda row: (row["item_id"], row["definition_id"]))}
            for key in sorted(groups)]


def _graph_component(value: Any) -> str:
    if (not isinstance(value, str) or not value or value != value.strip()
            or any(ord(character) < 32 or ord(character) == 127 for character in value)):
        raise AnalysisContractError("グラフIDの要素が正しくありません。", code="graph_id_invalid")
    return value.replace("%", "%25").replace(":", "%3A")


def graph_node_id(kind: str, *, item_id: str = "", segment_id: str = "",
                  participant_code: str = "", speaker: str = "", lemma: str = "", pos: str = "",
                  definition_hash: str = "", claim_id: str = "") -> str:
    """Canonical IDs; callers resolve participant_code against speaker_registry."""
    if kind == "utt":
        parts = (item_id, segment_id)
    elif kind == "spk":
        parts = (participant_code,) if participant_code else (item_id, speaker)
    elif kind == "term":
        parts = (lemma, pos)
    elif kind == "def":
        if not isinstance(definition_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", definition_hash):
            raise AnalysisContractError("定義hashが正しくありません。", code="graph_id_invalid")
        parts = (definition_hash,)
    elif kind == "clm":
        parts = (claim_id,)
    else:
        raise AnalysisContractError("未対応の節点種別です。", code="graph_id_invalid")
    return kind + ":" + ":".join(_graph_component(value) for value in parts)


def validate_graph_node_id(value: Any) -> str:
    if not isinstance(value, str):
        raise AnalysisContractError("節点IDは文字列で指定してください。", code="graph_id_invalid")
    parts = value.split(":")
    counts = {"utt": {3}, "spk": {2, 3}, "term": {3}, "def": {2}, "clm": {2}}
    if len(parts) not in counts.get(parts[0], set()):
        raise AnalysisContractError("節点IDの形式が正しくありません。", code="graph_id_invalid")
    for part in parts[1:]:
        decoded = part.replace("%3A", ":").replace("%25", "%")
        if _graph_component(decoded) != part:
            raise AnalysisContractError("節点IDの符号化が正しくありません。", code="graph_id_invalid")
    if parts[0] == "def" and not re.fullmatch(r"[0-9a-f]{64}", parts[1]):
        raise AnalysisContractError("定義節点のhashが正しくありません。", code="graph_id_invalid")
    return value


def validate_graph_edge(value: Any, *, evidence_ids: set[str] | None = None) -> dict[str, Any]:
    """Provenance is part of edge identity; AI drafts cannot alias researcher edges."""
    if not isinstance(value, dict):
        raise AnalysisContractError("辺はJSONオブジェクトで指定してください。", code="graph_edge_invalid")
    result = {key: value.get(key) for key in ("source", "target", "relation", "weight", "provenance",
              "method", "method_version", "input_hash", "evidence_segment_ids")}
    for key in ("source", "target"):
        validate_graph_node_id(result[key])
    for key in ("relation", "method", "method_version"):
        _graph_component(result[key])
    if (not isinstance(result["provenance"], str) or result["provenance"] not in {"rule", "ai_draft", "researcher"}
            or type(result["weight"]) not in (int, float) or not math.isfinite(result["weight"])
            or not isinstance(result["input_hash"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", result["input_hash"])):
        raise AnalysisContractError("辺の出所・重み・入力hashが正しくありません。", code="graph_edge_invalid")
    evidence = result["evidence_segment_ids"]
    if not isinstance(evidence, list) or not evidence:
        raise AnalysisContractError("辺の根拠発話IDがありません。", code="graph_evidence_invalid")
    for identifier in evidence:
        validate_graph_node_id(identifier)
        if not identifier.startswith("utt:") or evidence_ids is not None and identifier not in evidence_ids:
            raise AnalysisContractError("辺の根拠発話IDが対象集合にありません。", code="graph_evidence_invalid")
    result["evidence_segment_ids"] = sorted(set(evidence))
    result["edge_id"] = "edge:" + fingerprint(result)
    if "edge_id" in value and value["edge_id"] != result["edge_id"]:
        raise AnalysisContractError("辺IDと内容が一致しません。", code="graph_edge_id_mismatch")
    return result


def core_decision(action: str, reason: str | None, affected: list[str], *,
                  facts: Any, context: dict[str, Any], rule: str,
                  transitions: list[dict[str, str]] | None = None,
                  resume_condition: str | None = None, **derived: Any) -> dict[str, Any]:
    """Return a Schema CoreDecision and separately guarded effects; no I/O."""
    pid = str(context.get("pipeline_id", "unbound"))
    facts = {"observed": facts, "pipeline": {key: context[key] for key in
             ("status", "generation", "cancel_requested", "wait_reason", "plan_hash") if key in context}}
    fact_hash = fingerprint(facts)
    plan_hash = str(context.get("plan_hash", ""))
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", plan_hash):
        plan_hash = fingerprint(context.get("plan", {}))
    value = {
        "decision_id": "decision." + fingerprint({"rule": rule, "facts": facts,
            "pipeline": pid, "generation": context.get("generation"), "action": action})[7:],
        "pipeline_id": "pipeline." + pid, "step_id": affected[0] if len(affected) == 1 else None,
        "plan_ref": {"id": "plan." + pid, "revision": CONTRACT_VERSION, "sha256": plan_hash[7:]},
        "rule_refs": [{"id": rule, "version": DECISION_VERSION}],
        "fact_refs": [{"id": "facts." + fact_hash[7:], "revision": str(context.get("generation", 1)),
                       "sha256": fact_hash[7:]}],
        "reason_code": reason, "action": action, "affected_steps": affected,
        "resume_condition": resume_condition,
    }
    return {"decision": value, "facts": facts, "transitions": transitions or [], **derived}


def step_facts(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: s[key] for key in ("step_id", "status", "milestone", "attempt", "generation", "attempt_id")
             if key in s} for s in steps]


def decision_transition(machine: str, current: str, target: str) -> dict[str, str]:
    guard = transition_guard(machine, current, target)
    validate_transition(machine, current, target, guard)
    return {"machine": machine, "from": current, "to": target, "guard_id": guard}


def decide_dispatch(steps: list[dict[str, Any]], specs: dict[str, Any], milestone: str,
                    context: dict[str, Any]) -> dict[str, Any]:
    pending = [s for s in steps if s["milestone"] == milestone and s["status"] not in TERMINAL_SUCCESS]
    by_id = {s["step_id"]: s for s in steps}
    ready = [s["step_id"] for s in pending if s["status"] not in {"failed", "cancelled"}
             and all(by_id.get(p, {}).get("status") in TERMINAL_SUCCESS
                     for p in specs[s["step_id"]].get("parents", []))]
    action = "release_gate" if not pending else "dispatch" if ready else "fail"
    return core_decision(action, "PARENT_INCOMPLETE" if pending and not ready else None,
        ready, facts={"milestone": milestone, "steps": step_facts(steps), "specs": specs}, context=context,
        rule="execution.parents", transitions=[decision_transition("step", by_id[s]["status"], "checking")
                                               for s in ready], milestone=milestone)


def decide_applicability(step_id: str, spec: dict[str, Any], *, has_definitions: bool,
                         has_targets: bool, context: dict[str, Any]) -> dict[str, Any]:
    excluded = bool(spec.get("allow_not_applicable") and (step_id in {"outline_scope", "comparison_scope"}
        or step_id == "manual_measurement" and not has_definitions
        or step_id == "publish_result" and not has_targets))
    return core_decision("mark_not_applicable" if excluded else "dispatch", "NOT_SELECTED" if excluded else None,
        [step_id], facts={"spec": spec, "has_definitions": has_definitions, "has_targets": has_targets},
        context=context, rule="eligibility.plan", transitions=[decision_transition("step", "checking",
            "not_applicable" if excluded else "ready")])


ERROR_REASONS = {"publication_failed": "PUBLICATION_FAILED", "no_valid_input": "EMPTY_EFFECTIVE_DATASET",
                 "step_unavailable": "METHOD_UNSUPPORTED", "parent_incomplete": "PARENT_INCOMPLETE",
                 "binding_conflict": "PROTOCOL_MISMATCH", "provider_unavailable": "AUTH_OR_POLICY",
                 "execution_failed": "UNKNOWN_EXECUTION_FAILURE"}


def decide_failure(errors: list[dict[str, str]], *, cancelled: bool,
                   context: dict[str, Any], unexpected: bool = False) -> dict[str, Any]:
    # Preserve Runtime's legacy fallback explicitly, without inventing retryability.
    codes = {e["code"] for e in errors}
    reason = ("USER_CANCELLED" if cancelled else "PUBLICATION_FAILED" if "publication_failed" in codes
              else ERROR_REASONS.get(errors[0]["code"], "UNKNOWN_EXECUTION_FAILURE") if errors else "UNKNOWN_EXECUTION_FAILURE")
    action = "cancel" if cancelled else "fail" if unexpected else "retry"
    target = "cancelling" if cancelled else "failed" if unexpected else "waiting"
    current = context.get("status", "running")
    return core_decision(action, reason, [e["step_id"] for e in errors if e.get("step_id")],
        facts={"errors": errors, "cancelled": cancelled, "unexpected": unexpected}, context=context,
        rule="execution.failure", transitions=[] if current == target else [decision_transition("pipeline", current, target)],
        resume_condition="explicit_retry" if action == "retry" else None,
        wait_reason="publication" if reason == "PUBLICATION_FAILED" else "retry")


def decide_cancel_step(step: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    current = step["status"]
    transitions = []
    if current not in TERMINAL_SUCCESS | {"failed", "cancelled", "interrupted"}:
        if "cancelled" not in ALLOWED_TRANSITIONS["step"][current]:
            transitions.append(decision_transition("step", current, "cancelling"))
            current = "cancelling"
        transitions.append(decision_transition("step", current, "cancelled"))
    return core_decision("cancel", "USER_CANCELLED", [step["step_id"]] if transitions else [],
        facts={"step": step_facts([step])[0]}, context=context, rule="cancel.settle_step", transitions=transitions)


def decide_failed_attempt(step: dict[str, Any], *, error_code: str, cancelled: bool,
                          context: dict[str, Any]) -> dict[str, Any]:
    if cancelled:
        return decide_cancel_step(step, context)
    return core_decision("fail", ERROR_REASONS.get(error_code, "UNKNOWN_EXECUTION_FAILURE"), [step["step_id"]],
        facts={"step": step_facts([step])[0], "error_code": error_code}, context=context, rule="execution.failed_attempt",
        transitions=[decision_transition("step", step["status"], "failed")])


def decide_cancel_pipeline(context: dict[str, Any]) -> dict[str, Any]:
    current = context["status"]
    transitions = [] if current == "cancelling" else [decision_transition("pipeline", current, "cancelling")]
    transitions.append(decision_transition("pipeline", "cancelling", "cancelled"))
    return core_decision("cancel", "USER_CANCELLED", [], facts=context, context=context,
                         rule="cancel.settle_pipeline", transitions=transitions)


def decide_restart_step(step: dict[str, Any], *, cancelled: bool, context: dict[str, Any]) -> dict[str, Any]:
    if cancelled:
        return decide_cancel_step(step, context)
    active = step["status"] in ACTIVE_STEP_STATES
    return core_decision("reconcile", "PROCESS_RESTART", [step["step_id"]] if active else [],
        facts={"step": step_facts([step])[0]}, context=context, rule="recovery.interrupt_step",
        transitions=[decision_transition("step", step["status"], "interrupted")] if active else [])


def decide_completion(publications: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
    complete = all(p["status"] in {"published", "not_selected"} for p in publications)
    return core_decision("commit" if complete else "reconcile", None if complete else "PUBLICATION_FAILED", [],
        facts=publications, context=context, rule="pipeline.publications",
        transitions=[decision_transition("pipeline", "running", "completed" if complete else "waiting")],
        resume_condition=None if complete else "explicit_publication_retry")


def decide_restart(context: dict[str, Any]) -> dict[str, Any]:
    cancelled = bool(context["cancel_requested"] or context["status"] == "cancelling")
    current = context["status"]
    transitions = ([decision_transition("pipeline", current, "cancelling")] if cancelled and current != "cancelling" else [])
    transitions.append(decision_transition("pipeline", "cancelling" if cancelled else current,
                                          "cancelled" if cancelled else "waiting"))
    return core_decision("cancel" if cancelled else "reconcile", "USER_CANCELLED" if cancelled else "PROCESS_RESTART", [],
        facts=context, context=context, rule="recovery.restart", transitions=transitions,
        resume_condition=None if cancelled else "explicit_resume")


def decide_retry(steps: list[dict[str, Any]], context: dict[str, Any], *, target: str | None,
                 restart_pending: bool) -> dict[str, Any]:
    candidates = [s for s in steps if s["status"] in {"failed", "interrupted", "cancelled"}
                  and (not target or s["step_id"] == target)]
    if context["wait_reason"] == "publication" and not candidates:
        candidates = [s for s in steps if s["step_id"] == "publish_result"]
    resume_planned = (context["status"] == "waiting" and context["wait_reason"] == "retry" and restart_pending
        and (any(s["status"] == "planned" for s in steps) or bool(steps) and all(s["status"] in TERMINAL_SUCCESS for s in steps)))
    error = ("retry_in_progress" if any(s["status"] in ACTIVE_STEP_STATES for s in steps)
             else "nothing_to_retry" if not candidates and not resume_planned
             else "retry_limit_reached" if any(int(s["attempt"]) >= 3 for s in candidates) else "")
    return core_decision("fail" if error else "retry", "RETRY_EXHAUSTED" if error == "retry_limit_reached"
        else "RETRY_UNAVAILABLE" if error else None, [s["step_id"] for s in candidates],
        facts={"steps": step_facts(steps), "target": target, "restart": restart_pending}, context=context,
        rule="retry.attempt_budget", transitions=[] if error else [decision_transition("pipeline", context["status"], "accepted")],
        error_code=error)


def derive_milestone_status(steps: list[dict[str, Any]]) -> str:
    statuses = [s["status"] for s in steps]
    if statuses and all(s in TERMINAL_SUCCESS for s in statuses):
        return "committed"
    for outcome, values in (("failed", {"failed"}), ("active", set(ACTIVE_STEP_STATES)), ("cancelled", {"cancelled"})):
        if any(s in values for s in statuses):
            return outcome
    return "pending"


def derive_allowed_actions(context: dict[str, Any], steps: list[dict[str, Any]], *, restart_pending: bool = False) -> list[str]:
    if restart_pending:
        return ["cancel"] if recovery_error(steps) else ["resume"]
    if context["status"] in {"accepted", "running", "waiting"}:
        actions = ["cancel"]
        if context["status"] == "waiting" and any(s["status"] in {"failed", "interrupted"} for s in steps):
            actions.append("retry_failed")
        if context["wait_reason"] == "publication":
            actions.append("retry_publication")
        return actions
    return ["view_results"] if context["status"] == "completed" else []


def recovery_error(steps: list[dict[str, Any]]) -> str:
    return "retry_limit_reached" if any(s["status"] in {"failed", "interrupted", "cancelled"}
                                       and s["attempt"] >= 3 for s in steps) else ""


def step_reuse_key(*, library: str, item_id: str, spec: dict[str, Any], analysis_hash: str,
                   registry_version: str, algorithm_version: Any, definition_hashes: list[str]) -> str:
    if spec["step_id"] not in REUSABLE_STEPS:
        return ""
    return fingerprint({"library": library, "item_id": item_id, "step_id": spec["step_id"], "spec": spec,
        "analysis_hash": analysis_hash, "reuse_hash_rule": "analysis-content-1", "registry_version": registry_version, "pipeline_version": PIPELINE_VERSION,
        "algorithm_version": algorithm_version,
        "definition_hashes": definition_hashes if spec["step_id"] == "manual_measurement" else []})


def reuse_analysis_hash(analysis: dict[str, Any]) -> str:
    """Ignore only the adapter capture clock, never source/model/result versions.

    snapshot.analysis_hash continues to verify the entire frozen snapshot.
    Copied CSV metadata retains the original calculation time and artifact hash.
    """
    return fingerprint({key: value for key, value in analysis.items() if key != "generated_at"})


def decide_reuse(step_id: str, reuse_key: str, candidates: list[dict[str, Any]], *,
                 mode: str, context: dict[str, Any]) -> dict[str, Any]:
    selected = None
    if mode == "auto" and reuse_key and step_id in REUSABLE_STEPS:
        for candidate in candidates:
            try:
                artifact = json.loads(candidate["artifact_json"])
                valid = candidate["artifact_hash"] == fingerprint(artifact)
            except (ValueError, TypeError):
                continue
            if candidate["status"] == "committed" and candidate["reuse_key"] == reuse_key and valid:
                selected = candidate
                break
    candidate_facts = [{key: c.get(key) for key in ("attempt_id", "status", "reuse_key", "artifact_hash")}
                       for c in candidates]
    return core_decision("reuse" if selected else "dispatch", "REUSED_COMMITTED_STEP" if selected else None,
        [step_id], facts={"reuse_key": reuse_key, "mode": mode, "candidates": candidate_facts,
                         "selected": selected["attempt_id"] if selected else None}, context=context,
        rule="reuse.verified_artifact", transitions=[decision_transition("step", "checking", "reused" if selected else "ready")],
        candidate=selected)


def validate_transition(machine: str, current: str, target: str, guard_id: str) -> None:
    if machine not in ALLOWED_TRANSITIONS:
        raise AnalysisContractError("状態機械が正しくありません。", code="unknown_machine")
    if not isinstance(guard_id, str) or not re.fullmatch(r"[a-z][a-z0-9_.-]{2,80}", guard_id):
        raise AnalysisContractError("状態遷移にはguard IDが必要です。", code="missing_guard")
    if target not in ALLOWED_TRANSITIONS[machine].get(current, set()):
        raise AnalysisContractError(
            f"許可されていない状態遷移です: {machine} {current} -> {target}",
            code="invalid_transition",
        )
    if guard_id != transition_guard(machine, current, target):
        raise AnalysisContractError("状態遷移のguard IDが正本と一致しません。", code="invalid_guard")


def validate_definition(value: Any, *, require_version: bool = False) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AnalysisContractError("定義はJSONオブジェクトで指定してください。", field="definition")
    result = {key: item for key, item in value.items() if key not in {
        "status", "revision", "updated_at", "last_trial", "expected_revision", "expected_trial",
    }}
    required_text = ("definition_id", "name", "description", "unit_of_analysis",
                     "output_column", "data_type", "measurement_level", "measurement_rule")
    for key in required_text:
        if not isinstance(result.get(key), str) or not result[key].strip():
            raise AnalysisContractError(f"{key}を指定してください。", field=key)
        result[key] = result[key].strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{2,63}", result["definition_id"]):
        raise AnalysisContractError("definition_idが正しくありません。", field="definition_id")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{1,62}", result["output_column"]):
        raise AnalysisContractError("出力列名は英数字と_で指定してください。", field="output_column")
    if result["output_column"] in {"segment_id", "speaker", "speaker_name"} or "__missing_reason" in result["output_column"]:
        raise AnalysisContractError("根拠列・欠測理由列は出力列に使えません。", code="output_column_conflict", field="output_column")
    columns = result.get("source_columns")
    if not isinstance(columns, list) or not columns or any(not isinstance(column, str) or column not in SOURCE_COLUMNS for column in columns):
        raise AnalysisContractError("対応していない入力列が含まれています。", field="source_columns")
    if len(set(columns)) != 1:
        raise AnalysisContractError("現在の測定規則は1種類の入力列だけを扱います。", code="source_columns_unsupported", field="source_columns")
    if result["data_type"] not in DEFINITION_TYPES:
        raise AnalysisContractError("data_typeが正しくありません。", field="data_type")
    if result["measurement_level"] not in MEASUREMENT_LEVELS:
        raise AnalysisContractError("尺度水準が正しくありません。", field="measurement_level")
    if result["measurement_rule"] not in MEASUREMENT_RULES:
        raise AnalysisContractError("測定規則が正しくありません。", field="measurement_rule")
    method = result.get("method", "frequency")
    if not isinstance(method, str) or method not in SUPPORTED_METHODS:
        raise AnalysisContractError("初回範囲で利用できない分析手法です。", code="method_unavailable", field="method")
    if method == "descriptive" and result["data_type"] != "number":
        raise AnalysisContractError("記述統計にはnumber型が必要です。", code="incompatible_type", field="data_type")
    if result["data_type"] in {"string", "category", "boolean"} and result["measurement_level"] not in {"nominal", "ordinal"}:
        raise AnalysisContractError("文字・カテゴリ・真偽値には名義または順序尺度を指定してください。", code="incompatible_scale", field="measurement_level")
    if method == "descriptive" and result["measurement_level"] not in {"interval", "ratio"}:
        raise AnalysisContractError(
            "名義・順序尺度へ記述統計の平均を適用できません。frequencyを選択してください。",
            code="incompatible_scale", field="method",
        )
    if result["measurement_rule"] in {"text_length", "duration"} and result["data_type"] != "number":
        raise AnalysisContractError("この測定規則のdata_typeはnumberです。", field="data_type")
    if result["measurement_rule"] == "duration" and "duration" not in columns:
        raise AnalysisContractError("duration規則にはduration列が必要です。", field="source_columns")
    if result["measurement_rule"] == "text_length" and "text" not in columns:
        raise AnalysisContractError("text_length規則にはtext列が必要です。", field="source_columns")
    if result["measurement_rule"] in {"nonempty", "boolean_true"} and result["data_type"] != "boolean":
        raise AnalysisContractError("この測定規則のdata_typeはbooleanです。", code="incompatible_type", field="data_type")
    if result["measurement_rule"] == "nonempty" and columns[0] not in {"text", "speaker", "speaker_name", "role"}:
        raise AnalysisContractError("nonempty規則は文字列の入力列に対応しています。", code="source_columns_unsupported", field="source_columns")
    if result["measurement_rule"] == "boolean_true" and columns[0] != "question_candidate":
        raise AnalysisContractError("boolean_true規則にはquestion_candidate列が必要です。", code="source_columns_unsupported", field="source_columns")
    supported_behavior = {"unit_of_analysis": "segment", "missing_rule": "null_with_reason",
                          "aggregation": "none", "denominator": "all_included_segments"}
    for field, supported in supported_behavior.items():
        if result.get(field, supported) != supported:
            raise AnalysisContractError(f"現在対応している{field}は{supported}です。", code="definition_behavior_unsupported", field=field)
        result[field] = supported
    levels = result.get("levels", [])
    if levels is not None and not isinstance(levels, list):
        raise AnalysisContractError("levelsは配列で指定してください。", field="levels")
    result["method"] = method
    result["source_columns"] = list(dict.fromkeys(columns))
    result["levels"] = list(levels or [])
    result["missing_rule"] = str(result.get("missing_rule") or "null_with_reason")
    result["aggregation"] = str(result.get("aggregation") or "none")
    result["denominator"] = str(result.get("denominator") or "all_included_segments")
    version = result.get("version") if require_version else result.get("version", 1)
    if type(version) is not int or version < 1:
        raise AnalysisContractError("定義versionは1以上の整数で指定してください。", code="definition_version_invalid", field="version")
    result["version"] = version
    return result


def validate_definitions(values: list[dict[str, Any]], *, require_version: bool = True) -> list[dict[str, Any]]:
    """Protect evidence IDs, missingness columns, and every output namespace."""
    normalized = [validate_definition(value, require_version=require_version) for value in values]
    ids: set[str] = set()
    columns: set[str] = set()
    for value in normalized:
        identifier, column = value["definition_id"], value["output_column"]
        names = {column, column + "__missing_reason"}
        if identifier in ids or names & columns:
            raise AnalysisContractError("定義IDまたは出力列が重複しています。", code="output_column_conflict", field="definition_ids")
        ids.add(identifier)
        columns.update(names)
    return normalized


def validate_label_definitions(values: Any, *, evidence_ids: set[str]) -> None:
    """Validate specialist-authored draft coding scales, not executable measurements.

    Manual measurement_rule supports deterministic source columns only; these
    qualitative drafts must never be installed as executable/adopted definitions.
    """
    def invalid():
        raise AnalysisContractError("初回の専門家によるラベル・尺度定義が不足または不正です。",
                                    code="initial_label_definitions_invalid")
    if not isinstance(values, list) or not 1 <= len(values) <= 12:
        invalid()
    identifiers = set()
    for value in values:
        if not isinstance(value, dict):
            invalid()
        for key in ("definition_id", "name", "description", "measurement_justification", "decision_rule", "missing_criteria"):
            if not isinstance(value.get(key), str) or not value[key].strip():
                invalid()
        identifier = value["definition_id"]
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{2,63}", identifier) or identifier in identifiers:
            invalid()
        identifiers.add(identifier)
        if (type(value.get("version")) is not int or value["version"] != 1
                or value.get("unit_of_analysis") != "utterance" or value.get("missing_rule") != "null_with_reason"):
            invalid()
        level, dtype = value.get("measurement_level"), value.get("data_type")
        if not isinstance(level, str) or not isinstance(dtype, str) or level not in MEASUREMENT_LEVELS or dtype not in {"category", "number", "boolean"}:
            invalid()
        if level == "ordinal" and dtype != "number":
            invalid()
        method = value.get("recommended_analysis")
        if not isinstance(method, str) or method not in {"frequency", "ordinal_distribution", "descriptive"}:
            invalid()
        if ((method == "ordinal_distribution" and level != "ordinal")
                or (method == "descriptive" and level not in {"interval", "ratio"})):
            invalid()
        if not isinstance(value.get("unit"), str):
            invalid()
        if level in {"interval", "ratio"} and (dtype != "number" or not value["unit"].strip()):
            invalid()
        refs = value.get("evidence_ids")
        if not isinstance(refs, list) or not 1 <= len(refs) <= 80 or any(not isinstance(ref, str) or ref not in evidence_ids for ref in refs):
            invalid()
        levels = value.get("levels")
        if not isinstance(levels, list) or len(levels) > 50 or (level in {"nominal", "ordinal"} and len(levels) < 2):
            invalid()
        seen, numeric = set(), []
        for entry in levels:
            if not isinstance(entry, dict) or any(not isinstance(entry.get(key), str) or not entry[key].strip()
                                                  for key in ("meaning", "criteria")):
                invalid()
            item = entry.get("value")
            if isinstance(item, str) and item.strip().casefold() in {"欠測", "未読", "missing", "null", "none", "n/a"}:
                invalid()
            if ((dtype == "category" and (not isinstance(item, str) or not item.strip()))
                    or (dtype == "boolean" and type(item) is not bool)
                    or (dtype == "number" and (type(item) not in {int, float} or not math.isfinite(item)))):
                invalid()
            identity = ("number", item) if dtype == "number" else canonical(item)
            if identity in seen:
                invalid()
            seen.add(identity)
            if dtype == "number":
                if level == "ratio" and item < 0:
                    invalid()
                numeric.append(item)
        if level == "ordinal" and dtype == "number" and numeric != sorted(numeric):
            invalid()


def eligibility_assessment(definitions: list[dict[str, Any]], *, segment_count: int) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.append({
        "dimension": "computability", "severity": "hard",
        "outcome": "pass" if segment_count > 0 else "fail",
        "reason_code": "input_available" if segment_count > 0 else "no_valid_input",
    })
    capability = CAPABILITIES["methods"].get("manual_measurement", {})
    for definition in definitions:
        method = definition.get("method", "frequency")
        method_capability = capability.get("definition_methods", {}).get(method, {}) if isinstance(method, str) else {}
        descriptive = (capability.get("status") == "available"
                       and method_capability.get("inference_scope") == "descriptive")
        checks.append({
            "dimension": "inference_validity", "severity": "hard",
            "outcome": "pass" if descriptive else "unknown",
            "reason_code": "descriptive_scope_only" if descriptive else "inference_validity_unknown",
            "definition_id": definition["definition_id"],
        })
        checks.append({
            "dimension": "precision", "severity": "warning",
            "outcome": "unknown", "reason_code": "precision_not_predefined",
            "definition_id": definition["definition_id"],
        })
    blocked = any(
        check["severity"] == "hard" and check["outcome"] in {"fail", "unknown"}
        for check in checks
    )
    return {
        "contract": "EligibilityAssessment", "contract_version": CONTRACT_VERSION,
        "execution": "blocked" if blocked else "allowed",
        "inference_scope": "none" if blocked else "descriptive",
        "status": "ineligible" if blocked else (
            "eligible_with_warnings" if any(c["severity"] == "warning" and c["outcome"] != "pass" for c in checks)
            else "eligible"
        ),
        "checks": checks,
    }


def validate_planning_proposal(
    proposal: Any, *, input_hash: str, source_revision: int,
    analysis_revision: int, provider_policy: str,
) -> dict[str, Any]:
    """Accept O01 advice as a bounded annotation, never as executable steps."""
    from .analysis_plan_advisor import ADVISOR_VERSION, normalize_candidate

    if not isinstance(proposal, dict) or proposal.get("version") != ADVISOR_VERSION:
        raise AnalysisContractError("計画候補の版が正しくありません。", code="invalid_proposal")
    if (proposal.get("input_hash") != input_hash
            or proposal.get("source_revision") != source_revision
            or proposal.get("analysis_revision") != analysis_revision):
        raise AnalysisContractError("計画候補の入力版が変わっています。再提案してください。", code="revision_conflict")
    engine = proposal.get("engine")
    provider = proposal.get("provider")
    model = proposal.get("model")
    if not isinstance(engine, str) or engine not in {"transformer", "llm"} or not isinstance(model, str) or not model.strip() or len(model) > 200:
        raise AnalysisContractError("計画候補の実行モデルが正しくありません。", code="invalid_proposal")
    if not isinstance(provider, str):
        raise AnalysisContractError("計画候補の実行先が正しくありません。", code="invalid_proposal")
    if engine == "transformer" and provider != "local_transformer":
        raise AnalysisContractError("Transformer計画候補の実行先が正しくありません。", code="invalid_proposal")
    if engine == "llm" and provider not in {"lmstudio", "openai", "google"}:
        raise AnalysisContractError("計画候補のLLMが正しくありません。", code="invalid_proposal")
    if provider in {"openai", "google"} and provider_policy != "cloud_allowed":
        raise AnalysisContractError("クラウドLLMにはcloud_allowedが必要です。", code="provider_unavailable")
    objective = proposal.get("objective")
    if not isinstance(objective, str) or not 3 <= len(objective.strip()) <= 500:
        raise AnalysisContractError("計画候補の分析目的が正しくありません。", code="invalid_proposal")
    return {
        "version": ADVISOR_VERSION, "input_hash": input_hash,
        "source_revision": source_revision, "analysis_revision": analysis_revision,
        "engine": engine, "provider": provider, "model": model.strip(),
        "objective": objective.strip(), **normalize_candidate(proposal),
    }


PUBLICATION_TARGETS = ("input", "orchestrator", "visualization")
EFFECTIVE_PUBLICATION_WRITERS = ("research", *PUBLICATION_TARGETS)


def validate_publication_targets(value: Any) -> list[str]:
    # The existing publisher is one four-Vault operation, not independent writers.
    if (not isinstance(value, list) or any(not isinstance(target, str) for target in value)
            or value and (len(value) != len(PUBLICATION_TARGETS) or set(value) != set(PUBLICATION_TARGETS))):
        raise AnalysisContractError("公開先は空配列またはinput・orchestrator・visualizationの全3件を指定してください。", field="publication_targets")
    return list(PUBLICATION_TARGETS) if value else []


def build_plan_envelope(
    *, item_id: str, source_revision: int, analysis_revision: int,
    input_fingerprint: str, payload: dict[str, Any], definitions: list[dict[str, Any]],
    segment_count: int,
) -> dict[str, Any]:
    reuse = payload.get("reuse", "auto")
    if not isinstance(reuse, str) or reuse not in {"auto", "none"}:
        raise AnalysisContractError("reuseはautoまたはnoneです。", field="reuse")
    mode = payload.get("mode", "automatic")
    if mode not in {"automatic", "manual"}:
        raise AnalysisContractError("modeはautomaticまたはmanualです。", field="mode")
    research = payload.get("research_protocol") or {"classification": "exploratory"}
    if not isinstance(research, dict) or research.get("classification", "exploratory") not in {
        "exploratory", "confirmatory",
    }:
        raise AnalysisContractError("研究区分が正しくありません。", field="research_protocol")
    research = dict(research)
    research.setdefault("classification", "exploratory")
    if research["classification"] == "confirmatory" and research.get("preregistered") is not True:
        raise AnalysisContractError(
            "検証的分析には事前固定した仮説・規則が必要です。",
            code="confirmatory_not_predefined", field="research_protocol",
        )
    targets = validate_publication_targets(payload.get("publication_targets", list(PUBLICATION_TARGETS)))
    provider_policy = payload.get("provider_policy", "local_only")
    if not isinstance(provider_policy, str) or provider_policy not in {"local_only", "cloud_allowed"}:
        raise AnalysisContractError(
            "送信方針が正しくありません。", code="provider_unavailable",
            field="provider_policy",
        )
    proposal = payload.get("planning_proposal")
    if proposal is not None:
        proposal = validate_planning_proposal(
            proposal, input_hash=input_fingerprint, source_revision=source_revision,
            analysis_revision=analysis_revision, provider_policy=provider_policy,
        )
    if provider_policy == "cloud_allowed" and (
        proposal is None or proposal["provider"] not in {"openai", "google"}
    ):
        raise AnalysisContractError("local_only が既定です。クラウド送信方針には選択したLLMの計画候補が必要です。", code="provider_unavailable")
    normalized_definitions = validate_definitions(definitions)
    assessment = eligibility_assessment(normalized_definitions, segment_count=segment_count)
    steps = [
        {"step_id": "freeze_input", "milestone": "M0", "required": True, "parents": []},
        {"step_id": "outline_scope", "milestone": "M1", "required": False, "allow_not_applicable": True, "parents": ["freeze_input"]},
        {"step_id": "participation", "milestone": "M2", "required": True, "parents": ["freeze_input"]},
        {"step_id": "conversation_dynamics", "milestone": "M2", "required": True, "parents": ["freeze_input"]},
        {"step_id": "chart_specs", "milestone": "M3", "required": True, "parents": ["participation", "conversation_dynamics"]},
        {"step_id": "execution_binding", "milestone": "M4", "required": True, "parents": ["chart_specs"]},
        {"step_id": "manual_measurement", "milestone": "M5", "required": bool(normalized_definitions), "allow_not_applicable": not normalized_definitions, "parents": ["execution_binding"]},
        {"step_id": "comparison_scope", "milestone": "M6", "required": False, "allow_not_applicable": True, "parents": ["manual_measurement"]},
        {"step_id": "save_result", "milestone": "M7", "required": True, "parents": ["comparison_scope"]},
        {"step_id": "publish_result", "milestone": "M7", "required": bool(targets), "allow_not_applicable": not targets, "parents": ["save_result"]},
    ]
    envelope = {
        "contract": "PlanEnvelope", "contract_version": CONTRACT_VERSION,
        "item_id": item_id, "source_revision": int(source_revision),
        "analysis_revision": int(analysis_revision), "input_hash": input_fingerprint,
        "mode": mode, "provider_policy": provider_policy, "reuse": reuse,
        "research_protocol": research, "publication_targets": targets,
        "effective_publication_writers": list(EFFECTIVE_PUBLICATION_WRITERS) if targets else [],
        "capability_scope": {
            "selected": ["participation", "conversation_dynamics", "manual_measurement"],
            "catalog_version": CONTRACT_VERSION,
        },
        "binding_slots": [
            {"slot_id": f"definition:{value['definition_id']}", "allowed_methods": [value["method"]],
             "output_column": value["output_column"], "required": True}
            for value in normalized_definitions
        ],
        "steps": steps, "eligibility": assessment,
    }
    if proposal is not None:
        envelope["planning_proposal"] = proposal
    envelope["plan_hash"] = fingerprint(envelope)
    return envelope


def build_execution_binding(envelope: dict[str, Any], definitions: list[dict[str, Any]]) -> dict[str, Any]:
    values = validate_definitions(definitions)
    by_id = {value["definition_id"]: value for value in values}
    revisions = {value["definition_id"]: original.get("revision")
                 for value, original in zip(values, definitions)}
    resolved = []
    snapshots = {}
    for slot in envelope.get("binding_slots", []):
        definition_id = str(slot["slot_id"]).split(":", 1)[-1]
        definition = by_id.get(definition_id)
        if definition is None:
            raise AnalysisContractError(
                f"必須の定義slotが未解決です: {definition_id}",
                code="unresolved_binding", field="definition_ids",
            )
        if definition["method"] not in slot["allowed_methods"]:
            raise AnalysisContractError("M0の許容範囲外の手法です。", code="binding_out_of_scope")
        revision = revisions[definition_id]
        if revision is not None and (type(revision) is not int or revision < 1):
            raise AnalysisContractError("定義revisionが正しくありません。", code="revision_conflict")
        snapshots[definition_id] = {"payload": definition, "definition_hash": fingerprint(definition),
                                    "revision": revision, "status": "adopted"}
        resolved.append({
            "slot_id": slot["slot_id"], "definition_id": definition_id,
            "definition_version": definition["version"], "definition_revision": revision,
            "definition_hash": fingerprint(definition), "method": definition["method"],
            "output_column": definition["output_column"],
        })
    return {
        "contract": "ExecutionBinding", "contract_version": "analysis-binding-2",
        "plan_hash": envelope["plan_hash"], "resolved": resolved,
        "research_classification": envelope["research_protocol"]["classification"],
        "definition_snapshots": snapshots,
        "binding_hash": fingerprint({"resolved": resolved, "definition_snapshots": snapshots}),
    }


def capability_catalog() -> dict[str, Any]:
    return {"version": CONTRACT_VERSION, "capabilities": CAPABILITIES}
