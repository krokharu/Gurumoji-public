"""Adapters between the fixed analysis pipeline and the existing analyses.

The pipeline runs on an immutable snapshot of one conversation; these
functions build that snapshot, adapt existing methods to pipeline steps and
ask the O01 planning adviser (Transformer or an LLM) for a plan candidate."""

from __future__ import annotations

import sqlite3
import json
from typing import Any, Callable

from .. import analysis_plan_advisor
from ..analysis_core import AnalysisContractError, fingerprint
from ..analysis_method_registry import method_results
from .group_analysis import analysis_csv_rows


PIPELINE_METHOD_DATASETS = {
    "participation": ("speakers", "groups", "summary", "observations"),
    "conversation_dynamics": ("transitions", "gaps", "overlaps", "timeline"),
}

# Sections used by the pipeline methods, measurement, O01 and final save.
# Saved classifications/Transformer views are retained until separately proved equivalent.
SNAPSHOT_V2_SECTIONS = (
    "schema_version", "generated_at", "algorithm_version", "config", "segments",
    "item.id", "item.source_name", "item.revision_count", "item.analysis_revision", "item.analysis_updated_at",
    "automatic.overview", "automatic.balance", "automatic.moderator", "automatic.data_quality",
    "automatic.speaker_metrics", "automatic.transitions", "automatic.long_gaps", "automatic.overlap_candidates",
    "automatic.keywords", "automatic.emotions", "automatic.time_bins", "automatic.groups", "automatic.observations",
    "manual.codebook", "manual.code_metrics", "manual.interaction_summary", "manual.case_code_matrix", "manual.context_checks",
)


def _has_section(analysis, path):
    value = analysis
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return False
        value = value[part]
    return True


def validate_pipeline_snapshot(snapshot):
    """Keep legacy inline inputs readable; reject incomplete/tampered v2 at intake."""
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("analysis"), dict):
        raise AnalysisContractError("固定入力の形式が正しくありません。", code="invalid_snapshot")
    version = snapshot.get("schema_version", 1)
    if version not in (1, 2):
        raise AnalysisContractError("固定入力の版に対応していません。", code="invalid_snapshot")
    if version == 2:
        analysis = snapshot["analysis"]
        valid = (snapshot.get("sections") == list(SNAPSHOT_V2_SECTIONS)
                 and all(_has_section(analysis, key) for key in SNAPSHOT_V2_SECTIONS)
                 and isinstance(analysis["segments"], list)
                 and all(isinstance(analysis[key], dict) for key in ("item", "config", "automatic", "manual"))
                 and isinstance(snapshot.get("archive_snapshot"), dict)
                 and all(isinstance(segment, dict) and isinstance(segment.get("annotation"), dict)
                         and all(key in segment for key in
                                 ("id", "start", "end", "duration", "speaker", "speaker_name", "role", "text"))
                         for segment in analysis["segments"])
                 and snapshot.get("analysis_hash") == fingerprint(analysis))
        if not valid:
            raise AnalysisContractError("固定入力の必要な節またはhashが一致しません。", code="invalid_snapshot")
    return snapshot


def _source_outline(row):
    try:
        value = json.loads(row["outline_json"] or "null") if "outline_json" in row.keys() else None
        return value if isinstance(value, dict) else None
    except (ValueError, TypeError):
        return None


def run_analysis_pipeline_method(step_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    """Adapt one existing method to the fixed pipeline snapshot."""
    if step_id not in PIPELINE_METHOD_DATASETS:
        raise ValueError("未対応の分析stepです。")
    analysis = snapshot["analysis"]
    datasets = {
        name: analysis_csv_rows(analysis, name)
        for name in PIPELINE_METHOD_DATASETS[step_id]
    }
    methods = method_results(analysis, datasets)
    method = next((value for value in methods if value["method_id"] == step_id), None)
    if method is None:
        raise ValueError(f"{step_id}の既存分析結果を構築できません。")
    return {
        "method": method,
        "datasets": {
            name: {"fields": fields, "rows": rows}
            for name, (fields, rows) in datasets.items()
        },
    }


def make_analysis_pipeline_adapters(
    *,
    archive_snapshot: Any,
    archive_source_stamp: Any,
    call_ai_json: Any,
    configured_ai_credentials: Any,
    encode_transformer_texts: Any,
    group_analysis_for_row: Any,
    load_token_config: Any,
) -> tuple[Callable[..., Any], ...]:
    def build_analysis_pipeline_snapshot(row: sqlite3.Row, *, schema_version: int = 2) -> dict[str, Any]:
        """Capture one immutable input and its existing-analysis adapter view."""
        before = archive_source_stamp(row)
        if schema_version not in (1, 2):
            raise ValueError("Unsupported pipeline snapshot version")
        analysis = group_analysis_for_row(row, include_research_rows=schema_version == 1)
        archived = archive_snapshot(row, analysis)
        after = archive_source_stamp(row)
        if before != after:
            raise AnalysisContractError("入力固定中に準備状態または話者台帳が更新されました。再確認してください。", code="revision_conflict")
        snapshot = {
            "schema_version": schema_version,
            "input_hash": before,
            "source_revision": int(row["revision_count"] or 0),
            "analysis_revision": int(row["analysis_revision"] or 0),
            "analysis": analysis,
            "archive_snapshot": archived,
            "source_outline": _source_outline(row),
        }
        if schema_version == 2:
            snapshot.update(sections=list(SNAPSHOT_V2_SECTIONS), analysis_hash=fingerprint(analysis))
        return snapshot

    def advise_analysis_plan(snapshot: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        """Run the selected O01 adviser on a small, nonverbatim context packet."""
        context = analysis_plan_advisor.planning_context(
            snapshot["analysis"], payload.get("objective", "")
        )
        if context["included_segment_count"] < 1:
            raise AnalysisContractError("分析できる発話がありません。", code="no_valid_input")
        engine = payload.get("engine", "transformer")
        policy = payload.get("provider_policy", "local_only")
        if not isinstance(policy, str) or policy not in {"local_only", "cloud_allowed"}:
            raise AnalysisContractError("送信方針が正しくありません。", code="provider_unavailable")
        if engine == "transformer":
            if policy != "local_only":
                raise AnalysisContractError("Transformer計画候補はlocal_onlyで生成してください。", code="provider_unavailable")
            candidate, model_info = analysis_plan_advisor.transformer_candidate(
                context, encode_transformer_texts
            )
            provider, model = "local_transformer", model_info["name"]
        elif engine == "llm":
            provider = payload.get("provider", "lmstudio")
            if not isinstance(provider, str) or provider not in {"lmstudio", "openai", "google"}:
                raise AnalysisContractError("計画担当のLLMを選択してください。", code="provider_unavailable")
            if provider == "lmstudio" and policy != "local_only":
                raise AnalysisContractError("ローカルLLMはlocal_onlyで生成してください。", code="provider_unavailable")
            if provider != "lmstudio" and policy != "cloud_allowed":
                raise AnalysisContractError("クラウドLLMにはcloud_allowedが必要です。", code="provider_unavailable")
            config = load_token_config()
            api_key, configured_model = configured_ai_credentials(config, provider)
            model = payload.get("model") or configured_model
            if not isinstance(model, str) or not model.strip() or len(model) > 200 or "\n" in model or "\r" in model:
                raise AnalysisContractError("計画担当のモデルを指定してください。", code="provider_unavailable")
            model = model.strip()
            if provider != "lmstudio" and not api_key:
                raise AnalysisContractError("選択したLLMのAPIキーが未設定です。", code="provider_unavailable")
            base_url = config.lmstudio_base_url if provider == "lmstudio" else ""
            candidate = analysis_plan_advisor.llm_candidate(
                context,
                lambda system, prompt, schema: call_ai_json(
                    provider, api_key, model, system, prompt, "analysis_plan_o01", schema,
                    base_url=base_url,
                ),
            )
        else:
            raise AnalysisContractError("計画担当のエンジンが正しくありません。", code="method_unavailable")
        return {
            "version": analysis_plan_advisor.ADVISOR_VERSION,
            "source_revision": snapshot["source_revision"],
            "analysis_revision": snapshot["analysis_revision"],
            "input_hash": snapshot["input_hash"],
            "objective": context["objective"],
            "engine": engine, "provider": provider, "model": model,
            **candidate,
        }

    return (build_analysis_pipeline_snapshot, advise_analysis_plan)


def make_staged_initial_builder(*, archive_snapshot, archive_source_stamp, group_analysis_for_row,
                                derived_database=None):
    """Use the same calculation/serialization functions with durable boundaries.

    Only ``base`` reads preparation/registry state; the runtime verifies the
    source stamp before and after every stage. Later stages consume the frozen
    row and committed outputs, never the UI/process research cache.
    """
    import copy
    import json
    from .. import method_experts
    from ..analysis_insights import INSIGHT_VERSION, build_content_analysis
    from ..orchestration_initial import InitialStage
    from ..research_analysis import (
        RESEARCH_ALGORITHM_VERSION, assemble_research_analysis,
        build_research_linguistics, build_research_statistics, enrich_research_analysis,
        derived_storage,
    )
    from .group_analysis import GROUP_ANALYSIS_ALGORITHM_VERSION, finish_group_analysis
    from .analysis_networks import VERSION as NETWORK_VERSION

    class FrozenExpertCatalog(method_experts.ExpertCatalog):
        def __init__(self, frozen):
            self.frozen = frozen

        def index(self):
            return self.frozen["index"]

        def definition(self, expert_id):
            value = self.frozen["entries"][expert_id]
            if "error" in value:
                raise method_experts.ExpertDefinitionError(value["error"])
            return value["definition"]

        def knowledge(self, expert_id, definition):
            return self.frozen["entries"][expert_id]["knowledge"]

    def freeze_experts(analysis):
        catalog = method_experts.default_catalog()
        index = catalog.index()
        entries = {}
        for method in analysis.get("manual", {}).get("focus_group_plan", {}).get("methods", []):
            expert_id = next((key for key, entry in index.items()
                              if method.get("method_id") in entry["analysis_method_ids"]), None)
            if expert_id and expert_id not in entries:
                try:
                    definition = catalog.definition(expert_id)
                    entries[expert_id] = {"definition": definition, "knowledge": catalog.knowledge(expert_id, definition)}
                except (method_experts.ExpertDefinitionError, OSError) as exc:
                    entries[expert_id] = {"error": str(exc)}
        # YAML dates are represented as their unchanged ISO text on persistence.
        return json.loads(json.dumps({"index": index, "entries": entries}, ensure_ascii=False, default=str))

    class StagedInitialBuilder:
        version = f"initial-stages-1:{GROUP_ANALYSIS_ALGORITHM_VERSION}:{RESEARCH_ALGORITHM_VERSION}:{INSIGHT_VERSION}:{NETWORK_VERSION}"
        stages = (
            InitialStage("base", "入力固定・参加量と時間", f"{GROUP_ANALYSIS_ALGORITHM_VERSION}:{NETWORK_VERSION}"),
            InitialStage("linguistics", "形態素・語彙・共起", str(RESEARCH_ALGORITHM_VERSION)),
            InitialStage("statistics", "数量・統計", str(RESEARCH_ALGORITHM_VERSION)),
            InitialStage("content", "内容集計", str(INSIGHT_VERSION)),
            InitialStage("snapshot", "全結果の固定"),
        )

        def freeze(self, row):
            return dict(row)

        def run_stage(self, stage_id, row, outputs):
            if stage_id == "base":
                analysis = group_analysis_for_row(row, include_research_rows=True, defer_research=True)
                return {"analysis": analysis, "experts": freeze_experts(analysis)}
            analysis = copy.deepcopy(outputs["base"]["analysis"])
            if stage_id == "linguistics":
                if derived_database is not None:
                    with derived_storage(derived_database()):
                        return build_research_linguistics(analysis)
                return build_research_linguistics(analysis)
            linguistics = outputs["linguistics"]
            if stage_id == "statistics":
                return build_research_statistics(analysis, linguistics)
            if stage_id == "content":
                return build_content_analysis(analysis, linguistics["morphemes"])
            if stage_id != "snapshot":
                raise ValueError("Unknown initial stage")
            research = assemble_research_analysis(linguistics, outputs["statistics"], outputs["content"])
            analysis = enrich_research_analysis(analysis, include_rows=True, research_result=research)
            analysis["executed"] = True
            analysis = finish_group_analysis(analysis, row, expert_catalog=FrozenExpertCatalog(outputs["base"]["experts"]))
            return {"schema_version": 1, "input_hash": archive_source_stamp(row),
                    "source_revision": int(row["revision_count"] or 0),
                    "analysis_revision": int(row["analysis_revision"] or 0),
                    "analysis": analysis, "archive_snapshot": archive_snapshot(row, analysis),
                    "source_outline": _source_outline(row)}

    return StagedInitialBuilder()
