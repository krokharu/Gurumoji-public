"""Reviewable group-analysis reports and CSV datasets."""

from __future__ import annotations

import csv
import io
import json
import math
from typing import Any

from .. import method_experts
from .. import transcript_preparation as preparation
from ..research_analysis import RESEARCH_CSV_FIELDS, research_csv_sources
from ..segment_classification import (
    CLASSIFICATION_FIELDS,
    CROSSTAB_FIELDS as SEGMENT_CLASSIFICATION_CROSSTAB_FIELDS,
    DIALOGUE_ACTS,
    classification_rows,
    crosstab_rows as segment_classification_crosstab_rows,
)
from ..transformer_analysis import TRANSFORMER_CSV_FIELDS, transformer_csv_sources
from .analysis_networks import FIELDS as NETWORK_FIELDS, csv_sources as network_csv_sources


def focus_group_analysis_report_markdown(analysis: dict[str, Any]) -> str:
    """Render a conservative report: facts and analyst interpretation stay separate."""
    plan = analysis.get("manual", {}).get("focus_group_plan", {})
    item = analysis.get("item", {})
    automatic = analysis.get("automatic", {})
    manual = analysis.get("manual", {})
    lines = [
        "# グループインタビュー分析レポート（下書き）",
        "",
        "## 研究目的と分析方針",
        "",
        f"- 研究目的: {item.get('session_profile', {}).get('objective') or '不明'}",
        f"- 研究質問: {analysis.get('config', {}).get('research_question') or '不明'}",
        f"- 方針の状態: {plan.get('status', '不明')}",
        f"- 前提: {plan.get('provisional_assumption', '不明')}",
        f"- 研究者が記録した手法選定理由: {plan.get('researcher_method_rationale', '未入力')}",
        "",
        "## データ確認結果",
        "",
    ]
    for entry in plan.get("data_inventory", []):
        lines.append(f"- {entry.get('item')}: {entry.get('value')}（{entry.get('status')}）")
    overview = automatic.get("overview", {})
    prepared = manual.get("preparation", {})
    reviewed_rows = {r["segment_id"]: r for r in prepared.get("rows", [])}
    seconds = overview.get("total_speaking_seconds")
    time_text = f"{seconds} 秒" if seconds is not None else "不明"
    timed, missing = overview.get("timed_turn_count"), overview.get("missing_time_turn_count")
    if timed is not None and missing is not None:
        time_text += f"（時刻あり {timed} 発話、時刻不明 {missing} 発話）"
    lines.extend([
        f"- 分析対象版: {prepared.get('input_version') or '未固定'} / source_hash: {prepared.get('source_hash', '不明')}",
        f"- 逐語録準備状態: {prepared.get('status', 'draft')}。本文照合と話者・順序の確認は別に管理する。",
        "- 引用はこの分析対象版の本文。取込原本・加工文とは区別し、未確認の本文を音声照合済みとは扱わない。",
    ])
    if prepared.get("analysis_needs_review"):
        lines.append("- 要再確認: 入力版または確認状態と分析の根拠が一致しないため、旧コード・相互作用を現在の本文の結果として提示しない。")
    lines.extend([
        "",
        "## 採用手法と役割",
        "",
    ])
    for method in plan.get("methods", []):
        lines.append(
            f"- {method.get('role')}：{method.get('method')} — {method.get('reason')} "
            f"データ充足: {method.get('data_sufficiency')}。限界: {method.get('limitation')}"
        )
    lines.extend(method_experts.report_lines(analysis.get("experts")))
    lines.extend([
        "",
        "## 分析単位と手順",
        "",
        f"- 分析単位: {plan.get('analysis_unit', '不明')}",
    ])
    for step in plan.get("procedure", []):
        lines.append(f"- {step}")
    lines.extend([
        "",
        "## 直接確認できるデータ概要",
        "",
        f"- 発話数: {overview.get('segment_count', 0)}、実参加人数: {prepared.get('participant_count') if prepared.get('participant_count') is not None else '不明'}、確認済み発言者数: {prepared.get('known_speaker_count', 0)}。",
        f"- 時間情報: 時刻あり発話の合計 {time_text}。",
        "- 以下のコード・相互作用の件数は記録済みの注釈数であり、重要性・代表性・支持人数を意味しない。",
        "",
        "## 内容に関する結果（コード済みの事実）",
        "",
    ])
    metrics = [
        metric for metric in manual.get("code_metrics", [])
        if int(metric.get("segment_count") or 0) > 0
    ]
    if prepared.get("analysis_needs_review"):
        metrics = []
    if metrics:
        segments = analysis.get("segments", [])
        for metric in metrics:
            group_count = metric.get("group_count")
            lines.append(
                f"- {metric.get('label')}: {metric.get('segment_count', 0)}発話、"
                f"{metric.get('speaker_count', 0)}話者、"
                f"{'不明' if group_count is None else group_count}グループ。"
            )
            evidence = [
                segment for segment in segments
                if metric.get("id") in segment.get("annotation", {}).get("codes", [])
                and not segment.get("excluded")
            ][:3]
            for segment in evidence:
                state = reviewed_rows.get(segment['id'], {}).get('text_status', 'unreviewed')
                lines.append(f"  - 根拠発話 {segment['id']}（分析対象版・本文確認: {state}）: {segment.get('text', '')}")
    else:
        lines.append("- コードが未入力または根拠が要再確認のため、内容に関する結果は出力しない。")
    lines.extend([
        "",
        "## 相互作用に関する所見（根拠発話リンク）",
        "",
    ])
    links = manual.get("interaction_links", [])
    if prepared.get("analysis_needs_review"):
        links = []
    if links:
        by_id = {str(segment.get("id") or ""): segment for segment in analysis.get("segments", [])}
        for link in links:
            if link.get("status") == "missing_target":
                lines.append(f"- 要再確認: {link.get('source_segment_id')} の参照先 {link.get('target_segment_id')} は削除済み。記録は保持。")
                continue
            lines.append(
                f"- {link.get('relation_label')}：{link.get('target_segment_id')} → "
                f"{link.get('source_segment_id')}（文脈発話ID: "
                f"{', '.join(link.get('context_segment_ids', []))}）"
            )
            for segment_id in link.get("context_segment_ids", []):
                segment = by_id.get(str(segment_id))
                if segment is None:
                    continue
                state = reviewed_rows.get(segment_id, {}).get('text_status', 'unreviewed')
                lines.append(f"  - #{segment.get('utterance_order')} {segment.get('speaker_name')} [{segment_id} / {state}]: {segment.get('text', '')}")
    else:
        lines.append("- 根拠発話を結ぶ相互作用リンクが未入力のため、意見形成・変化に関する所見はまだ出力しない。")
    lines.extend([
        "",
        "## 研究者の解釈（データ上の事実とは別）",
        "",
        manual.get("analyst_memo") or "- 研究者の解釈メモは未入力。",
        "",
        "## 反例・少数意見・限界",
        "",
        "- 反例・少数意見・矛盾する発言は、研究者がコードと原文を照合して記録する必要がある。未記録の沈黙や反論の不在を同意とは扱わない。",
        "- 音声・動画または精密な転記がなければ、声色、正確な沈黙時間、発話の重なり、表情は解釈しない。",
        "- AIによる候補、語彙集計、意味クラスタは研究者の確認前の補助情報であり、テーマ・概念・因果関係を確定しない。",
        "",
        "## 方法の参照文献",
        "",
    ])
    for reference in plan.get("references", []):
        lines.append(f"- [{reference.get('citation')}]({reference.get('url')})")
    lines.append("")
    return "\n".join(lines)


ANALYSIS_CSV_FIELDS: dict[str, list[str]] = {
    "prepared_turns": preparation.FIELDS,
    "speakers": [
        "speaker", "speaker_name", "role", "turn_count", "speaking_seconds",
        "speaking_percent", "participant_percent", "average_turn_seconds",
        "characters", "characters_per_minute", "question_candidates",
        "first_start", "last_end", "included_in_balance", "emotion_counts",
        "code_counts", "timed_turn_count", "missing_time_turn_count", "timed_characters",
        "role_status", "observed_roles",
    ],
    "transitions": [
        "from_speaker", "from_name", "from_role", "to_speaker", "to_name",
        "to_role", "count", "average_gap_seconds", "overlap_candidates",
    ],
    "gaps": ["start", "end", "seconds", "previous_name", "next_name"],
    "overlaps": [
        "start", "end", "seconds", "from_speaker", "from_name",
        "to_speaker", "to_name",
    ],
    "keywords": ["term", "count", "by_speaker"],
    "emotions": [
        "speaker", "speaker_name", "model", "model_name", "label", "emotion",
        "count", "seconds", "timed_turn_count", "missing_time_turn_count",
    ],
    "timeline": [
        "index", "start", "end", "speaking_seconds", "turn_count", "speakers",
    ],
    "codes": [
        "id", "label", "description", "include_example", "exclude_example", "category", "theme",
        "color", "segment_count", "speaking_seconds", "characters",
        "speaker_count", "group_count", "important_count", "timed_turn_count", "missing_time_turn_count",
    ],
    "codebook_history": ["version", "changed_at", "reason", "summary"],
    "groups": [
        "group", "speaker_count", "turn_count", "speaking_seconds",
        "speaking_percent", "characters", "timed_turn_count", "missing_time_turn_count",
        "role_aggregation_status",
    ],
    "coded_segments": [
        "segment_id", "group_id", "utterance_order", "start", "end", "duration", "speaker", "speaker_name",
        "role", "text", "original_text", "original_text_available", "original_text_status",
        "previous_segment_id", "next_segment_id", "code_ids", "code_labels", "categories", "themes",
        "interaction_tags", "elicitation", "interaction_links", "dialogue_act",
        "dialogue_act_label", "importance_score", "review_score", "sensitivity_score",
        "classification_status", "classification_note", "memo", "important", "excluded", "valid_time",
    ],
    "analysis_units": [
        "segment_id", "group_id", "utterance_order", "start", "end", "duration", "speaker", "speaker_name",
        "role", "text", "original_text", "original_text_available", "original_text_status",
        "previous_segment_id", "next_segment_id", "code_ids", "code_labels", "categories", "themes",
        "interaction_tags", "elicitation", "interaction_links", "dialogue_act",
        "dialogue_act_label", "importance_score", "review_score", "sensitivity_score",
        "classification_status", "classification_note", "memo", "important", "excluded", "valid_time",
    ],
    "interactions": ["tag", "label", "count"],
    "interaction_links": [
        "status", "analysis_needs_review",
        "relation", "relation_label", "source_segment_id", "source_order", "source_speaker",
        "source_speaker_name", "source_role", "source_text", "target_segment_id", "target_order",
        "target_speaker", "target_speaker_name", "target_role", "target_text", "context_segment_ids",
        "context_truncated", "evidence_memo",
    ],
    "case_matrix": ["speaker", "speaker_name", "role", "codes"],
    "context": ["id", "label", "ready", "kind"],
    "summary": ["section", "metric", "value"],
    "observations": ["level", "label", "message"],
    "analysis_plan": ["section", "item", "status", "value", "role", "data_sufficiency", "reason", "limitation"],
    "important_quotes": [
        "segment_id", "start", "end", "speaker", "speaker_name", "role", "text",
        "code_labels", "memo", "excluded", "valid_time",
    ],
    "segment_classifications": CLASSIFICATION_FIELDS,
    "segment_classification_crosstabs": SEGMENT_CLASSIFICATION_CROSSTAB_FIELDS,
}
ANALYSIS_CSV_FIELDS.update(RESEARCH_CSV_FIELDS)
ANALYSIS_CSV_FIELDS.update(TRANSFORMER_CSV_FIELDS)
ANALYSIS_CSV_FIELDS.update(NETWORK_FIELDS)


def analysis_csv_safe(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    if isinstance(value, (dict, list, tuple)):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if not isinstance(value, str):
        return value
    visible = value.lstrip(" \t\r\n")
    if visible.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def analysis_csv_rows(
    analysis: dict[str, Any],
    dataset: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    automatic = analysis["automatic"]
    manual = analysis["manual"]
    code_labels = {
        str(item["id"]): str(item["label"]) for item in manual["codebook"]
    }
    code_details = {str(item["id"]): item for item in manual["codebook"]}
    coded_segments = []
    analysis_units = []
    important_quotes = []
    for segment in analysis["segments"]:
        annotation = segment["annotation"]
        labels = [
            code_labels.get(str(code_id), str(code_id))
            for code_id in annotation.get("codes", [])
        ]
        categories = list(dict.fromkeys(
            str(code_details.get(str(code_id), {}).get("category") or "")
            for code_id in annotation.get("codes", [])
            if str(code_details.get(str(code_id), {}).get("category") or "")
        ))
        themes = list(dict.fromkeys(
            str(code_details.get(str(code_id), {}).get("theme") or "")
            for code_id in annotation.get("codes", [])
            if str(code_details.get(str(code_id), {}).get("theme") or "")
        ))
        valid_time = bool(segment.get("valid_time", preparation.valid_time(segment)))
        row = {
            "segment_id": segment["id"],
            "group_id": segment.get("group_id", "不明"),
            "utterance_order": segment.get("utterance_order", ""),
            "start": segment["start"] if valid_time else None,
            "end": segment["end"] if valid_time else None,
            "duration": segment["duration"] if valid_time else None,
            "valid_time": valid_time,
            "speaker": segment["speaker"],
            "speaker_name": segment["speaker_name"],
            "role": segment["role"],
            "text": segment["text"],
            "original_text": segment.get("original_text", ""),
            "original_text_available": segment.get("original_text_available", False),
            "original_text_status": segment.get("original_text_status", "unavailable"),
            "previous_segment_id": segment.get("previous_segment_id", ""),
            "next_segment_id": segment.get("next_segment_id", ""),
            "code_ids": annotation.get("codes", []),
            "code_labels": labels,
            "categories": categories,
            "themes": themes,
            "interaction_tags": annotation.get("interaction_tags", []),
            "elicitation": annotation.get("elicitation", "unknown"),
            "interaction_links": annotation.get("interaction_links", []),
            "dialogue_act": annotation.get("dialogue_act", ""),
            "dialogue_act_label": DIALOGUE_ACTS.get(annotation.get("dialogue_act", ""), ""),
            "importance_score": annotation.get("importance_score"),
            "review_score": annotation.get("review_score"),
            "sensitivity_score": annotation.get("sensitivity_score"),
            "classification_status": annotation.get("classification_status", "unreviewed"),
            "classification_note": annotation.get("classification_note", ""),
            "memo": annotation.get("memo", ""),
            "important": annotation.get("important", False),
            "excluded": segment.get("excluded", False),
        }
        analysis_units.append(row)
        if any((
            row["code_ids"], row["interaction_tags"], row["memo"],
            row["elicitation"] != "unknown", row["interaction_links"],
            row["important"], row["excluded"],
            row["dialogue_act"], row["importance_score"] is not None,
            row["review_score"] is not None, row["sensitivity_score"] is not None,
            row["classification_status"] != "unreviewed", row["classification_note"],
        )):
            coded_segments.append(row)
        if row["important"] and not row["excluded"]:
            important_quotes.append(row)
    summary_rows = [
        {"section": section, "metric": key, "value": value}
        for section, values in (
            ("overview", automatic["overview"]),
            ("balance", automatic["balance"]),
            ("moderator", automatic["moderator"]),
            ("data_quality", automatic["data_quality"]),
        )
        for key, value in values.items()
    ]
    plan = manual.get("focus_group_plan", {})
    plan_rows = [
        {
            "section": "data_inventory", "item": row.get("item", ""),
            "status": row.get("status", ""), "value": row.get("value", ""),
            "role": "", "data_sufficiency": "", "reason": "", "limitation": "",
        }
        for row in plan.get("data_inventory", [])
    ]
    plan_rows.extend(
        {
            "section": "method", "item": row.get("method", ""), "status": "", "value": "",
            "role": row.get("role", ""), "data_sufficiency": row.get("data_sufficiency", ""),
            "reason": row.get("reason", ""), "limitation": row.get("limitation", ""),
        }
        for row in plan.get("methods", [])
    )
    sources: dict[str, list[dict[str, Any]]] = {
        "prepared_turns": manual.get("preparation", {}).get("rows", []),
        "speakers": automatic["speaker_metrics"],
        "transitions": automatic["transitions"],
        "gaps": automatic["long_gaps"],
        "overlaps": automatic["overlap_candidates"],
        "keywords": automatic["keywords"],
        "emotions": automatic["emotions"],
        "timeline": automatic["time_bins"],
        "codes": manual["code_metrics"],
        "codebook_history": manual.get("codebook_history", []),
        "groups": automatic["groups"],
        "coded_segments": coded_segments,
        "analysis_units": analysis_units,
        "interactions": manual["interaction_summary"],
        "interaction_links": manual.get("interaction_links", []),
        "case_matrix": manual["case_code_matrix"],
        "context": manual["context_checks"],
        "summary": summary_rows,
        "observations": automatic["observations"],
        "analysis_plan": plan_rows,
        "important_quotes": important_quotes,
        "segment_classifications": classification_rows(
            analysis.get("segment_classification", {}).get("result")
        ),
        "segment_classification_crosstabs": segment_classification_crosstab_rows(
            analysis.get("segment_classification", {}).get("result")
        ),
    }
    if dataset in RESEARCH_CSV_FIELDS:
        sources.update(research_csv_sources(analysis))
    sources.update(transformer_csv_sources(analysis.get("transformer", {}).get("result")))
    sources.update(network_csv_sources(analysis))
    if dataset not in ANALYSIS_CSV_FIELDS:
        raise ValueError("出力する分析データの種類が正しくありません。")
    common = {
        "schema_version": analysis["schema_version"],
        "item_id": analysis["item"]["id"],
        "source_name": analysis["item"]["source_name"],
        "revision_count": analysis["item"]["revision_count"],
        "analysis_revision": analysis["item"]["analysis_revision"],
        "analysis_updated_at": analysis["item"]["analysis_updated_at"],
        "generated_at": analysis["generated_at"],
        "algorithm_version": analysis["algorithm_version"],
        "input_version": manual.get("preparation", {}).get("input_version"),
        "source_hash": manual.get("preparation", {}).get("source_hash"),
        "analysis_needs_review": manual.get("preparation", {}).get("analysis_needs_review", True),
    }
    transformer_result = analysis.get("transformer", {}).get("result") or {}
    if dataset.startswith("transformer_") and transformer_result:
        provenance = transformer_result.get("source_provenance") or {}
        stale = bool(analysis.get("transformer", {}).get("stale"))
        # Never give historical results the identity/review state of today's input.
        # Legacy results have only partial provenance: missing fields stay missing.
        common.update({
            "current_source_name": common["source_name"],
            "source_name": provenance.get("source_name"),
            "current_revision_count": common["revision_count"],
            "current_analysis_revision": common["analysis_revision"],
            "current_input_version": common["input_version"], "current_source_hash": common["source_hash"],
            "schema_version": transformer_result.get("schema_version"),
            "generated_at": transformer_result.get("generated_at"),
            "algorithm_version": transformer_result.get("algorithm_version"),
            "revision_count": provenance.get("source_revision", transformer_result.get("source_revision")),
            "analysis_revision": provenance.get("analysis_revision", transformer_result.get("analysis_revision")),
            "analysis_updated_at": provenance.get("analysis_updated_at"),
            "input_version": provenance.get("input_version"), "source_hash": provenance.get("source_hash"),
            "analysis_needs_review": bool(stale or provenance.get("analysis_needs_review", True)),
            "result_stale": stale, "provenance_status": "recorded" if provenance else "legacy_unknown",
            "result_fingerprint": transformer_result.get("fingerprint"),
            "embedding_fingerprint": transformer_result.get("embedding_fingerprint"),
            "request_id": transformer_result.get("request_id"),
            "model_name": transformer_result.get("engine", {}).get("name"),
            "model_revision": transformer_result.get("engine", {}).get("revision"),
            "generated_config": provenance.get("config"), "generated_parameters": transformer_result.get("parameters"),
            "interpretation_status": "unverified_candidate", "researcher_review_required": True,
        })
    rows = [{**common, **dict(value)} for value in sources[dataset]]
    fields = list(dict.fromkeys([*common, *ANALYSIS_CSV_FIELDS[dataset]]))
    return fields, rows


def analysis_csv_content(analysis: dict[str, Any], dataset: str) -> bytes:
    fields, rows = analysis_csv_rows(analysis, dataset)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: analysis_csv_safe(row.get(key)) for key in fields})
    return ("\ufeff" + stream.getvalue()).encode("utf-8")
