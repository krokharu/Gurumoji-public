"""Deterministic ownership of frozen utterances, independent of inference."""
from __future__ import annotations

import copy
import math

from ..analysis_core import AnalysisContractError
from .model_context import digest

RULE_VERSION = 1


def valid_time(row):
    return (all(type(row.get(k)) in (int, float) and math.isfinite(row[k]) for k in ("start", "end"))
            and 0 <= row["start"] <= row["end"])


def make_interval(rows, first, last, *, dataset_version, parent_topic_id, method,
                  title="", parent_interval_id=None):
    owned = rows[first:last]
    visible = rows[max(0, first - 1):min(len(rows), last + 1)]
    ids = [row["evidence_id"] for row in owned]
    uids = [row["utterance_id"] for row in owned]
    identity = {"rule_version": RULE_VERSION, "dataset_version": dataset_version,
                "parent_topic_id": parent_topic_id, "owned_utterance_ids": uids}
    return {**identity, "interval_id": "interval_" + digest(identity)[:24],
            "parent_interval_id": parent_interval_id, "method": method,
            "title": title, "status": "ready" if all(valid_time(r) for r in owned) else "unprocessable",
            "reason": "" if all(valid_time(r) for r in owned) else "invalid_time",
            "start": owned[0]["start"] if owned and valid_time(owned[0]) else None,
            "end": max(r["end"] for r in owned) if owned and all(valid_time(r) for r in owned) else None,
            "owned_evidence_ids": ids, "ownership_sha256": digest(uids),
            "boundary_evidence_ids": [r["evidence_id"] for r in visible if r["evidence_id"] not in ids]}


def candidate_spans(rows, outline):
    """Accept explicit boundary candidates only; citations/timestamps are not bounds."""
    positions = {row["utterance_id"]: i for i, row in enumerate(rows)}
    candidates = []
    for section in (outline or {}).get("sections", []):
        if not isinstance(section, dict):
            continue
        first = positions.get(section.get("start_segment_id"))
        last = positions.get(section.get("end_segment_id"))
        if first is None or last is None or first > last:
            continue
        title = str(section.get("title", ""))
        topic = str(section.get("parent_topic_id") or "topic_" + digest(title)[:16])
        candidates.append((first, last + 1, topic, title))
    # Earlier boundary wins; ties prefer the shorter candidate. Clip overlaps
    # deterministically rather than counting an utterance twice.
    selected, cursor = [], 0
    for first, last, topic, title in sorted(set(candidates)):
        first = max(first, cursor)
        if first < last:
            selected.append((first, last, topic, title))
            cursor = last
    return selected


def build_partition(rows, outline, *, dataset_version, time_width=300, row_limit=24,
                    text_limit=6000, outline_method="existing", provenance=None):
    rows = [r for r in rows if not r.get("excluded")]
    if len({r["utterance_id"] for r in rows}) != len(rows):
        raise AnalysisContractError("発話IDが重複しています。", code="interval_identity_invalid")
    spans, cursor = [], 0
    for first, last, topic, title in candidate_spans(rows, outline):
        if cursor < first:
            spans.append((cursor, first, None, "", "time"))
        source_method = next((s.get("partition_method", outline_method) for s in (outline or {}).get("sections", [])
                              if isinstance(s, dict) and s.get("start_segment_id") == rows[first]["utterance_id"]), outline_method)
        spans.append((first, last, topic, title, source_method))
        cursor = last
    if cursor < len(rows):
        spans.append((cursor, len(rows), None, "", "time"))
    intervals = []
    for first, last, topic, title, method in spans:
        start = first
        while start < last:
            end = start + 1
            if valid_time(rows[start]):
                bucket = math.floor(rows[start]["start"] / time_width)
                while end < last and valid_time(rows[end]):
                    if method == "time" and math.floor(rows[end]["start"] / time_width) != bucket:
                        break
                    # Count boundary context as part of the actual packet.
                    visible = rows[max(0, start - 1):min(len(rows), end + 2)]
                    if len(visible) > row_limit or sum(len(r["text"]) for r in visible) > text_limit:
                        break
                    end += 1
            parent = topic or "time_" + digest([dataset_version, first, last])[:16]
            interval = make_interval(rows, start, end, dataset_version=dataset_version,
                                     parent_topic_id=parent, title=title, method=method)
            visible = rows[max(0, start - 1):min(len(rows), end + 1)]
            if interval["status"] == "ready" and (len(visible) > row_limit or sum(len(r["text"]) for r in visible) > text_limit):
                interval.update(status="unprocessable", reason="single_utterance_budget_exceeded")
            intervals.append(interval)
            start = end
    owned = [ref for interval in intervals for ref in interval["owned_evidence_ids"]]
    expected = [r["evidence_id"] for r in rows]
    if owned != expected or len(set(owned)) != len(owned):
        raise AnalysisContractError("区間の所属に欠落または重複があります。", code="interval_coverage_invalid")
    partition = {"version": RULE_VERSION, "dataset_version": dataset_version, "time_width": time_width,
                 "row_limit": row_limit, "text_limit": text_limit, "outline_sha256": digest(outline),
                 "provenance": copy.deepcopy(provenance or {}), "intervals": intervals,
                 "ownership_sha256": digest([r["utterance_id"] for r in rows]),
                 "target_evidence_ids": expected, "excluded_utterance_ids": [], "refinements": []}
    partition["sha256"] = digest(partition)
    return partition


def check_partition(partition, config, dataset_version):
    value = {k: v for k, v in partition.items() if k != "sha256"}
    if (digest(value) != partition.get("sha256") or partition.get("version") != RULE_VERSION
            or partition.get("dataset_version") != dataset_version
            or partition.get("time_width") != config["analysis_interval_seconds"]
            or partition.get("row_limit") != config["context_evidence_limit"]
            or partition.get("text_limit") != config["context_text_limit"]):
        raise AnalysisContractError("固定区間の版・設定・hashが一致しません。", code="interval_version_conflict")


def interval_scope(interval, *, blind=False):
    scope = copy.deepcopy(interval)
    scope.pop("status", None)
    scope.pop("reason", None)
    if blind:
        scope.pop("title", None)
    return scope


def progress(partition, tasks):
    """Never turn allocated, cancelled or budget-stopped work into completed work."""
    result = {"assigned_count": len(partition["target_evidence_ids"]), "roles": {}}
    for role in ("interpretation", "verification", "critic"):
        complete = set()
        for task in tasks:
            if task["role"] == role and task["phase"] == "initial_analysis" and task["status"] == "succeeded":
                scope = task["intent"].get("scope", {})
                provided = set(task.get("context_manifest", {}).get("provided_evidence_ids", []))
                complete.update(set(scope.get("owned_evidence_ids", [])) & provided)
        result["roles"][role] = {"processed_evidence_ids": sorted(complete),
                                 "unprocessed_evidence_ids": [r for r in partition["target_evidence_ids"] if r not in complete]}
    return result
