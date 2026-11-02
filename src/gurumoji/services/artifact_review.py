"""Pure contracts for a single, immutable finding used for counterexample review."""
from __future__ import annotations

from ..analysis_core import AnalysisContractError, fingerprint

VERSION = 1
MANIFEST_VERSION = 2
PURPOSE = "counterexample_review"


def reject(message, code="artifact_input_invalid"):
    raise AnalysisContractError(message, code=code)


def validate_source(run, task, meta, raw, scope, procedure):
    """No repair of old results, and no inference from a successful AI call."""
    if (task.get("run_id") != run["run_id"] or meta.get("run_id") != run["run_id"]
            or task.get("status") != "succeeded" or meta.get("validation_status") != "valid"
            or task.get("validation_status") != "valid" or task.get("stale") or meta.get("stale")
            or task.get("result_id") != meta.get("result_id") or meta.get("task_id") != task.get("task_id")
            or meta.get("attempt_id") != task.get("attempt_id")
            or task.get("role") != "interpretation" or meta.get("role") != "interpretation"
            or task.get("method_id") == "label-design-v1"
            or task.get("intent", {}).get("kind", "analysis") != "analysis"):
        reject("完了・形式確認済みの同じrunの解釈所見だけを点検できます。")
    if fingerprint(raw) != meta.get("raw_hash"):
        reject("先行所見の保存本文とhashが一致しません。", "result_integrity_mismatch")
    source_scope = task.get("intent", {}).get("scope", {})
    if not scope.get("interval_id") or source_scope != scope:
        reject("先行所見と担当区間が一致しません。")
    if (task.get("dataset_version") != run["input_hash"] or meta.get("dataset_version") != run["input_hash"]
            or scope.get("dataset_version") != run["input_hash"]
            or task.get("codebook_version") != run["codebook_version"]
            or task.get("label_dependent") and task.get("annotation_version") != run["annotation_version"]):
        reject("先行所見の入力・区間・定義版が一致しません。")
    claims = raw.get("claims")
    if not isinstance(claims, list) or not claims:
        reject("点検対象には根拠付き主張が必要です。")
    provided = task.get("context_manifest", {}).get("provided_evidence_ids", [])
    ids = []
    for claim in claims:
        if (not isinstance(claim, dict) or not isinstance(claim.get("claim_id"), str)
                or not claim["claim_id"].strip() or not isinstance(claim.get("text"), str)
                or not claim["text"].strip() or claim.get("kind") not in {"observation", "interpretation", "hypothesis"}
                or not isinstance(claim.get("evidence_ids"), list) or not claim["evidence_ids"]
                or any(ref not in provided for ref in claim["evidence_ids"])):
            reject("先行所見の主張ID・根拠・種別が不正です。")
        ids.append(claim["claim_id"])
    if len(ids) != len(set(ids)):
        reject("先行所見の主張IDが重複しています。")
    return {"version": VERSION, "run_id": run["run_id"], "task_id": task["task_id"],
            "result_id": meta["result_id"], "raw_hash": meta["raw_hash"], "schema_version": run["schema_version"],
            "claim_ids": sorted(ids), "interval": scope, "dataset_version": run["input_hash"],
            "annotation_version": task["annotation_version"] if task.get("label_dependent") else None,
            "codebook_version": task["codebook_version"], "source_manifest_hash": task.get("context_manifest_hash"),
            "source_provided_evidence_ids": provided, "purpose": PURPOSE,
            "source_coverage": task["context_manifest"].get("coverage", {}),
            "required_inputs": procedure["required_inputs"],
            "procedure": {k: procedure[k] for k in ("procedure_id", "version", "sha256")}}


def validate_decisions(raw, candidates, *, prior=()):
    rows = raw.get("artifact_decisions", [])
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        reject("候補の利用判断は配列です。", "artifact_decision_invalid")
    index = {c["result_id"]: c for c in candidates}
    known = []
    uses = []
    for row in rows:
        rid = row.get("result_id")
        if (rid not in index or row.get("disposition") not in {"use", "skip", "defer"}
                or not isinstance(row.get("reason"), str) or not row["reason"].strip()
                or row.get("purpose") != PURPOSE or row.get("interval_id") != index[rid]["interval_id"]):
            reject("提示候補・三択・理由・用途・区間が必要です。", "artifact_decision_invalid")
        if row["disposition"] == "defer" and any(not isinstance(row.get(k), str) or not row[k].strip()
                for k in ("missing", "release_condition", "next_action")):
            reject("保留には不足・解除条件・次の作業が必要です。", "artifact_decision_invalid")
        if row["disposition"] == "use":
            if not isinstance(row.get("expected_output"), str) or not row["expected_output"].strip():
                reject("利用判断には期待する出力が必要です。", "artifact_decision_invalid")
            previous = next((p for p in reversed(list(prior)) if p["result_id"] == rid), None)
            if previous and previous["disposition"] == "defer" and previous.get("information_hash") == index[rid]["information_hash"]:
                reject("保留解除に必要な新情報がありません。", "artifact_decision_invalid")
            uses.append(row)
        known.append(rid)
    if len(known) != len(set(known)) or set(known) != set(index):
        reject("提示候補の判断に欠落・重複・提示外IDがあります。", "artifact_decision_invalid")
    intents = raw.get("intents", [])
    reviews = [i for i in intents if i.get("kind") == "finding_review"]
    if (len(intents) > 1 or len(uses) > 1 or len(reviews) != len(uses)
            or reviews and (reviews[0].get("review_target_result_id") != uses[0]["result_id"]
                           or reviews[0].get("artifact_purpose") != PURPOSE
                           or reviews[0].get("role") != "interpretation"
                           or reviews[0].get("interval_ids") != [uses[0]["interval_id"]])):
        reject("useと1件の正式レビュー依頼を同じ判断で結び付けてください。", "artifact_decision_invalid")


def validate_review_output(raw, binding, manifest):
    if (not isinstance(raw.get("summary"), str) or not raw["summary"].strip()
            or not isinstance(raw.get("limitations"), str) or not raw["limitations"].strip()
            or not isinstance(raw.get("missing_inputs"), list)
            or any(not isinstance(v, str) or not v.strip() for v in raw["missing_inputs"])):
        reject("点検の要約・限界・不足一覧を明示してください。", "artifact_output_invalid")
    if raw.get("label_patches") != [] or raw.get("analysis_requests") != [] or raw.get("label_definitions"):
        reject("反例点検はラベルを変更せず追加依頼を発注しません。", "artifact_output_invalid")
    verdicts = raw.get("claim_verdicts")
    if not isinstance(verdicts, list):
        reject("主張別の判定が必要です。", "artifact_output_invalid")
    claims = []
    delivered = set(manifest["provided_evidence_ids"])
    coverage = manifest.get("coverage", {})
    for row in verdicts:
        if (not isinstance(row, dict) or row.get("result_id") != binding["result_id"]
                or row.get("raw_hash") != binding["raw_hash"] or row.get("claim_id") not in binding["claim_ids"]
                or row.get("verdict") not in {"counterexample", "not_found_in_scope", "insufficient"}
                or not isinstance(row.get("reason"), str) or not row["reason"].strip()
                or not isinstance(row.get("evidence_ids"), list)
                or any(not isinstance(ref, str) or ref not in delivered for ref in row["evidence_ids"])):
            reject("主張別判定の対象・理由・配送済み原文が不正です。", "artifact_output_invalid")
        if row["verdict"] != "insufficient" and not row["evidence_ids"]:
            reject("反例と範囲内未検出には原文根拠が必要です。", "artifact_output_invalid")
        if row["verdict"] == "not_found_in_scope" and (not coverage.get("complete")
                or not binding.get("source_coverage", {}).get("complete")
                or not set(binding["interval"]["owned_evidence_ids"]).issubset(delivered)
                or raw.get("missing_inputs")):
            reject("不完全な入力では範囲内の反例なしと判定できません。", "artifact_output_invalid")
        claims.append(row["claim_id"])
    if len(claims) != len(set(claims)) or set(claims) != set(binding["claim_ids"]):
        reject("全主張へ過不足なく1件ずつ判定してください。", "artifact_output_invalid")


def review_progress(raw):
    """Exclude derivative IDs/hashes; compare only actual checks and limitations."""
    return fingerprint({"verdicts": sorted([{"claim_id": r["claim_id"], "verdict": r["verdict"],
        "evidence_ids": sorted(set(r["evidence_ids"])), "reason": r["reason"]}
        for r in raw.get("claim_verdicts", [])], key=lambda r: r["claim_id"]),
        "missing_inputs": raw.get("missing_inputs", []), "limitations": raw.get("limitations", "")})
