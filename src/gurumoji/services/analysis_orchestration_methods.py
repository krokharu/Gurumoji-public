"""Allowlisted deterministic computations for Handler-issued statistics tasks."""
from __future__ import annotations

from collections import defaultdict
import math
from typing import Any

from .analysis_pipeline_adapters import run_analysis_pipeline_method

LABEL_FIELDS = frozenset({"codes", "code", "theme", "sentiment", "dialogue_act",
                          "importance", "review", "category"})


def run_orchestration_method(method_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    if method_id != "label_frequency":
        return run_analysis_pipeline_method(method_id, snapshot)
    task = snapshot["orchestration_task"]
    labels = snapshot["orchestration_labels"]
    field = task["intent"].get("label_field") or "codes"
    if field not in LABEL_FIELDS:
        raise ValueError("未対応のラベル項目です。")
    selected = task["intent"].get("evidence_ids") or []
    evidence = [row for row in snapshot["evidence"] if not row["excluded"]]
    if selected:
        if not set(selected) <= {row["evidence_id"] for row in evidence}:
            raise ValueError("指定範囲に除外済み・存在しない発話が含まれます。")
        evidence = [row for row in evidence if row["evidence_id"] in selected]
    if not evidence:
        raise ValueError("集計対象の発話がありません。")
    groups: dict[str, list[str]] = defaultdict(list)
    missing = []
    for row in evidence:
        value = labels.get(row["utterance_id"], {}).get(field)
        if value is None or value == "" or value == []:
            missing.append(row["evidence_id"])
            continue
        values = value if isinstance(value, list) else [value]
        categories = set()
        for category in values:
            if isinstance(category, str):
                category = category.strip()
                if category:
                    categories.add(category)
            elif type(category) is bool:
                categories.add("true" if category else "false")
            elif type(category) in {int, float} and math.isfinite(category):
                categories.add(str(category))
            else:
                raise ValueError("ラベル値の型が集計対象外です。")
        if not categories:
            missing.append(row["evidence_id"])
        for category in categories:
            groups[category].append(row["evidence_id"])
    denominator = len(evidence)
    rows = [{"label": category, "count": len(ids), "denominator": denominator,
             "proportion": len(ids) / denominator, "evidence_ids": ids}
            for category, ids in sorted(groups.items(), key=lambda pair: (-len(pair[1]), pair[0]))]
    return {
        "summary": f"固定ラベル版{task['annotation_version']}の{field}を対象{denominator}発話で再集計。欠測{len(missing)}発話。",
        "claims": [], "method_id": "label_frequency", "method_version": "label-frequency-1",
        "research_mode": "exploratory", "dataset_version": task["dataset_version"],
        "annotation_version": task["annotation_version"], "codebook_version": task["codebook_version"],
        "label_field": field, "denominator": denominator, "missing_count": len(missing),
        "missing_evidence_ids": missing, "rows": rows,
        "manifest": {"kind": "deterministic_code", "method_version": "label-frequency-1",
                     "analysis_unit": "utterance", "scope": "selected" if selected else "all_included",
                     "evidence_ids": [row["evidence_id"] for row in evidence],
                     "dataset_version": task["dataset_version"],
                     "annotation_version": task["annotation_version"], "codebook_version": task["codebook_version"]},
        "limitations": ["複数ラベルの度数合計は発話数を超える場合があります。",
                        "欠測を含む対象発話全体を分母に固定しています。",
                        "記述集計であり、人物属性・因果関係や統計的確認を示しません。"],
    }
