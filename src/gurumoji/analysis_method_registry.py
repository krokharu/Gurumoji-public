"""Versioned output contracts for saved text-analysis results."""
from __future__ import annotations

REGISTRY_VERSION = "text-analysis-store-13"

COMMON_EXPORT_FIELDS = {
    "schema_version", "item_id", "source_name", "revision_count", "analysis_revision",
    "analysis_updated_at", "generated_at", "algorithm_version",
    "input_version", "source_hash", "analysis_needs_review",
}

PREVIEW_FIELD_PRIORITIES = {
    "response_nodes": ["speaker_name", "incoming", "outgoing", "reciprocity", "outgoing_bias", "strength_centrality"],
    "response_edges": ["from_speaker", "to_speaker", "weight", "segment_ids"],
    "cooccurrence_nodes": ["term", "community", "degree", "strength", "strength_centrality"],
    "cooccurrence_edges": ["term_a", "term_b", "weight", "segment_ids"],
    "coding_consistency": ["segment_id", "label", "code_ids", "nearest_other_code", "own_similarity", "other_similarity"],
    "segment_classifications": [
        "utterance_order", "speaker_name", "manual_dialogue_act_label",
        "template_dialogue_act_label", "llm_dialogue_act_label",
        "llm_importance_score", "llm_review_score", "llm_sensitivity_score",
    ],
    "segment_classification_crosstabs": [
        "table_label", "row_value", "column_value", "count",
    ],
    "transformer_topics": [
        "topic_id", "label", "origin", "keywords", "segment_count", "speaker_count",
        "backchannel_count", "average_similarity", "representative_segment_ids",
    ],
    "transformer_assignments": [
        "speaker_name", "topic_label", "start", "end", "similarity", "text", "segment_id",
    ],
    "transformer_backchannels": [
        "speaker_name", "kind", "text", "topic_label", "responds_to_speaker_name",
        "time_gap", "link_method", "segment_id",
    ],
    "transformer_backchannel_rates": [
        "speaker_name", "speaker_group", "topic_label", "opportunity_count",
        "responded_target_count", "response_rate_percent", "backchannel_count",
        "backchannels_per_100_opportunities",
    ],
    "transformer_backchannel_tests": [
        "test", "dimension", "n", "p_value", "effect_size", "status",
        "interpretation", "assumption_note",
    ],
    "transformer_speaker_results": [
        "speaker_name", "result_label", "topic_label", "confidence", "basis",
        "matched_cues", "evidence_texts", "evidence_segment_ids",
    ],
}


def preview_fields(dataset: str, fields: list[str]) -> list[str]:
    selected = [field for field in PREVIEW_FIELD_PRIORITIES.get(dataset, []) if field in fields]
    selected.extend(field for field in fields if field not in COMMON_EXPORT_FIELDS and field not in selected)
    return selected[:8]


METHODS = [
    ("autonomous_analysis", "自律探索分析・Core／Handler", ["autonomous_summary"]),
    ("local_insights", "ローカル見解", ["insights"]),
    ("speaker_characteristics", "話者別特徴語", ["characteristic_terms"]),
    ("transformer_topics", "Transformerテーマ分析", ["transformer_topics", "transformer_assignments", "transformer_speakers", "transformer_timeline", "transformer_outliers", "transformer_backchannels", "transformer_backchannel_speakers", "transformer_backchannel_rates", "transformer_backchannel_tests", "transformer_speaker_results"]),
    ("participation", "発話量・参加バランス", ["speakers", "groups", "summary", "observations"]),
    ("conversation_dynamics", "会話の時間構造", ["transitions", "gaps", "overlaps", "timeline"]),
    ("response_network", "応答関係ネットワーク", ["response_nodes", "response_edges", "response_summary"]),
    ("cooccurrence_network", "共起ネットワークの構造", ["cooccurrence_nodes", "cooccurrence_edges", "cooccurrence_communities"]),
    ("coding_consistency", "コーディングの一貫性チェック", ["consistency_codes", "coding_consistency"]),
    ("morphology", "形態素・品詞", ["morphemes", "pos_frequency"]),
    ("syntax", "係り受け", ["dependencies"]),
    ("lexical_frequency", "語彙頻度", ["term_frequency", "keywords"]),
    ("cooccurrence", "共起", ["cooccurrence"]),
    ("descriptive_statistics", "記述統計・度数", ["descriptives", "frequencies"]),
    ("group_statistics", "クロス集計・群間比較", ["crosstabs", "statistical_tests"]),
    ("correlation", "相関", ["correlations"]),
    ("qualitative_coding", "手動コード・重要引用", ["prepared_turns", "analysis_plan", "analysis_units", "codes", "codebook_history", "coded_segments", "case_matrix", "interactions", "interaction_links", "important_quotes", "context"]),
    ("ai_insights", "AI見解・下書き", ["insights"]),
    ("audio_emotion", "音声感情推定", ["emotions"]),
    ("outline", "議題・アウトライン", []),
    ("kwic", "文脈検索", ["kwic"]),
    ("ai_finishing", "AI仕上げ・変更記録", ["ai_changes", "ai_jev_comparison"]),
    ("segment_classification", "発話種別・重要度・要確認・機密らしさ", ["segment_classifications", "segment_classification_crosstabs"]),
    # Saved as their own runs: never mixed into a single conversation's text analysis.
    ("meeting_minutes", "会議議事録・タスク候補", ["meeting_tasks", "meeting_decisions", "meeting_speaker_activity"]),
    ("interview_comparison", "グループインタビュー比較", ["comparison_interviews", "comparison_common_terms", "comparison_characteristic_terms", "comparison_codes", "comparison_emotions"]),
]
SEPARATE_RUN_METHODS = {"meeting_minutes", "interview_comparison", "segment_classification", "autonomous_analysis"}

# Navigation categories describe the implemented methods, not external engines.
METHOD_GROUPS = [
    ("text", "KH Coder系・計量テキスト分析",
     "語彙頻度・共起・特徴語・文脈を比較します。KH Coderの考え方を参照した独自実装で、KH Coder本体の出力ではありません。",
     ("local_insights", "morphology", "syntax", "lexical_frequency", "cooccurrence", "cooccurrence_network", "speaker_characteristics", "kwic")),
    ("transformer", "Transformer系・意味分析",
     "多言語E5による本文テーマ分析と、HuBERT・wav2vec 2.0による音声感情推定を確認します。",
     ("transformer_topics", "audio_emotion")),
    ("ai", "生成AI・アウトライン・仕上げ",
     "AI見解、議題・アウトライン、文字起こしの仕上げ記録を確認します。",
     ("ai_insights", "outline", "ai_finishing", "autonomous_analysis")),
    ("statistics", "統計・群間比較",
     "記述統計、クロス集計、群間比較、相関を確認します。",
     ("descriptive_statistics", "group_statistics", "correlation")),
    ("conversation", "会話構造・参加バランス",
     "発話量、話者交替、間、重なりなど会話の構造を確認します。",
     ("participation", "conversation_dynamics", "response_network", "segment_classification")),
    ("qualitative", "質的分析・コード・引用",
     "手動コードと重要引用を、元の発言や文脈と合わせて確認します。",
     ("qualitative_coding", "coding_consistency")),
    ("meeting", "会議・議事録",
     "会議モードの発話から、タスク候補・決定事項候補・発話量をルールで抽出した記録です。担当・期限は元発話で確認します。",
     ("meeting_minutes",)),
    ("comparison", "グループインタビュー横断比較",
     "複数回のインタビューを、発話量・共通語・特徴語・手動コード・感情ラベルで記述的に並べた比較です。",
     ("interview_comparison",)),
]

METHOD_STATUS_LABELS = {
    "completed": "結果あり", "empty": "データなし", "not_run": "未実行",
    "unavailable": "利用不可", "fallback": "簡易解析", "stale": "更新が必要",
    "partial": "一部完了", "not_applicable": "適用外",
}


def method_status_label(method: dict) -> str:
    status = METHOD_STATUS_LABELS.get(method.get("status"), str(method.get("status") or "状態不明"))
    return status + ("／入力変更後・再確認が必要" if method.get("stale") else "")


def transformer_note_content(result: dict) -> tuple[list[dict], list[dict]]:
    """Create searchable summaries and evidence-linked findings for the Vault note."""
    findings: list[dict] = []
    summaries: list[dict] = []
    mode = str(result.get("parameters", {}).get("mode") or "auto")
    mode_labels = {"auto": "自動（silhouetteで選択）", "candidate": "候補から研究者が選択",
                   "manual": "研究者が定義したテーマへの割り当て"}
    coverage = result.get("coverage", {})
    summaries.append({
        "title": "テーマの決め方",
        "text": (
            f"{mode_labels.get(mode, mode)}。テーマ{coverage.get('topic_count', 0)}件、"
            f"対象{coverage.get('segment_count', 0)}発話。"
            + (f"未割当{coverage.get('unassigned_segment_count', 0)}件、"
               f"上位2テーマの差が小さい境界例{coverage.get('low_margin_segment_count', 0)}件。"
               "割り当ては意味の近さによる候補で、テーマの妥当性を確かめた結果ではありません。"
               if mode == "manual" else "")
        ),
    })
    for topic in result.get("topics", []):
        segment_ids = [str(value) for value in topic.get("representative_segment_ids", []) if value]
        if segment_ids:
            origin = ("研究者が定義したテーマ" if topic.get("origin") == "manual"
                      else "特徴語による仮ラベル")
            findings.append({
                "title": f"テーマ {topic.get('topic_id', '')}：{topic.get('label', '')}",
                "text": (
                    f"{origin}。{topic.get('segment_count', 0)}発話、"
                    f"{topic.get('speaker_count', 0)}話者、"
                    f"相づち{topic.get('backchannel_count', 0)}件。"
                ),
                "segment_ids": segment_ids,
            })
    kind_labels = {"agreement": "同意的応答", "continuer": "継続促進",
                   "confirmation": "確認", "courtesy": "謝意"}
    for row in result.get("backchannels", []):
        segment_ids = [str(value) for value in (
            row.get("segment_id"), row.get("responds_to_segment_id"),
        ) if value]
        if segment_ids:
            findings.append({
                "title": f"相づち：{row.get('speaker_name', row.get('speaker', ''))}／{row.get('topic_label', '紐付けなし')}",
                "text": (
                    f"種類：{kind_labels.get(row.get('kind'), row.get('kind', '応答'))}。"
                    f"相づち本文：{row.get('text', '')}。"
                    f"応答先：{row.get('responds_to_speaker_name') or '推定できず'}。"
                ),
                "segment_ids": segment_ids,
            })
    for row in result.get("speaker_results", []):
        segment_ids = [str(value) for value in row.get("evidence_segment_ids", []) if value]
        if segment_ids:
            findings.append({
                "title": f"話者別リザルト：{row.get('speaker_name', row.get('speaker', ''))}／{row.get('result_label', '')}",
                "text": f"対象話題：{row.get('topic_label', '紐付けなし')}。{row.get('basis', '')}",
                "segment_ids": segment_ids,
            })
    for row in result.get("backchannel_rates", []):
        if row.get("scope") != "overall" or row.get("speaker_group") != "participant":
            continue
        rate = row.get("response_rate_percent")
        summaries.append({
            "title": f"相づち応答率：{row.get('speaker_name', row.get('speaker', ''))}",
            "text": (
                f"反応機会{row.get('opportunity_count', 0)}件、応答した対象発話"
                f"{row.get('responded_target_count', 0)}件、応答率"
                f"{'算出不能' if rate is None else str(rate) + '%'}、相づち総数{row.get('backchannel_count', 0)}件。"
            ),
        })
    for row in result.get("backchannel_tests", []):
        p_value = row.get("p_value")
        effect = row.get("effect_size")
        summaries.append({
            "title": f"相づち統計：{row.get('test', '')}",
            "text": (
                f"状態：{row.get('status', '')}。p値：{'算出不能' if p_value is None else p_value}。"
                f"Cramér's V：{'算出不能' if effect is None else effect}。"
                f"{row.get('interpretation', '')} {row.get('assumption_note', '')}"
            ),
        })
    return findings, summaries


def method_results(analysis: dict, datasets: dict, *, outline: dict | None = None,
                   finishing: dict | None = None, kwic: dict | None = None,
                   meeting: dict | None = None, comparison: dict | None = None,
                   classification: dict | None = None) -> list[dict]:
    research = analysis.get("research", {})
    engine = research.get("linguistics", {}).get("engine", {})
    insights = analysis.get("insights", {})
    results = []
    optional = {"autonomous_analysis": None, "kwic": kwic, "ai_finishing": finishing, "meeting_minutes": meeting,
                "interview_comparison": comparison, "segment_classification": classification}
    for key, title, tables in METHODS:
        if key in optional and optional[key] is None:
            continue
        findings = []
        summaries = []
        details = {}
        if key == "local_insights": findings = insights.get("local", [])
        if key == "ai_insights":
            details = insights.get("ai") or {}
            findings = details.get("findings", [])
        if key == "outline": details = outline or {}
        if key == "ai_finishing": details = finishing or {}
        if key == "kwic": details = kwic or {}
        if key == "meeting_minutes":
            details = meeting or {}
            counts = details.get("analysis", {})
            summaries = [{"title": "抽出件数", "text": (
                f"タスク候補{counts.get('task_count', 0)}件、期限の言及{counts.get('due_count', 0)}件、"
                f"決定事項候補{counts.get('decision_count', 0)}件。")}]
            summaries += [{"title": "サマリー", "text": value} for value in details.get("summary", [])[:5]]
        if key == "interview_comparison":
            details = comparison or {}
            summaries = [{"title": "比較の種類", "text": (
                ("同じ比較グループの比較" if details.get("same_content") else "異なる内容を含む探索的比較")
                + f"。{len(details.get('interviews', []))}回を比較。")}]
        if key == "segment_classification":
            details = classification or {}
            counts = details.get("summary", {}) if isinstance(details, dict) else {}
            summaries = [{"title": "分類・確認候補", "text": (
                f"対象{counts.get('segment_count', 0)}発話、手動確認済み"
                f"{counts.get('manual_reviewed_count', 0)}件、Jev重要度高"
                f"{counts.get('high_importance_count', 0)}件、要確認高"
                f"{counts.get('high_review_count', 0)}件、機密らしさ高"
                f"{counts.get('high_sensitivity_count', 0)}件。"
            )}]
        selected = [name for name in tables if name in datasets]
        count = sum(len(datasets[name][1]) for name in selected)
        state = "completed" if count or findings or details else "empty"
        if key in {"participation", "conversation_dynamics"} and not any(
            not segment.get("excluded") for segment in analysis.get("segments", [])
        ):
            # Fixed summary rows describe the schema, not observed input.
            state = "empty"
        if key in {"ai_insights", "outline"} and not details: state = "not_run"
        if key == "transformer_topics":
            details = analysis.get("transformer", {})
            if not details.get("result"):
                state = "not_run"
            elif details.get("stale"):
                state = "stale"
            if details.get("result"):
                findings, summaries = transformer_note_content(details["result"])
        if key == "segment_classification" and not details:
            state = "not_run"
        if key == "ai_insights" and insights.get("stale"): state = "stale"
        if key == "outline" and details.get("evidence"):
            current = {s['id']: s for s in analysis.get('segments', []) if not s.get('excluded')}
            if any(sid not in current or any(current[sid].get(k) != evidence.get(k) for k in ('text', 'speaker', 'start', 'end'))
                   for sid, evidence in details['evidence'].items()): state = "stale"
        if key in {"morphology", "lexical_frequency", "cooccurrence", "speaker_characteristics"} and engine.get("status") == "fallback":
            state = "fallback"
        if key == "syntax" and (not engine.get("syntax") or str(engine["syntax"]).startswith("利用不可")):
            state = "unavailable"
        if key == "ai_finishing" and "failed" in details.get("stages", {}).values(): state = "partial"
        method_engine = engine if key in {"morphology", "syntax", "lexical_frequency", "cooccurrence", "speaker_characteristics"} else {}
        limitations = research.get("limitations", analysis.get("cautions", []))
        if key == "participation":
            # The snapshot's computation version wins, including pre-upgrade snapshots.
            method_engine = {"name": "local-participation", "version": analysis.get("algorithm_version")}
            overview = analysis.get("automatic", {}).get("overview", {})
            timed, missing = overview.get("timed_turn_count"), overview.get("missing_time_turn_count")
            if timed is not None and missing is not None:
                summaries = [{"title": "時刻の範囲", "text": (
                    f"時刻あり{timed}発話、時刻不明{missing}発話。時間は時刻あり発話の小計。"
                    "割合・均等度は対象集合に時刻欠測がなく、総時間が正のときだけ算出します。"
                )}]
        if key == "participation" and analysis.get("automatic", {}).get("overview", {}).get("mixed_role_speaker_count"):
            summaries.append({"title": "役割混在", "text": "役割混在: 同じ話者に複数の役割があります。全体時間は保持し、役割に依存する参加者・司会・役割別集計は算出しません。"})
        if key == "transformer_topics" and details.get("result"):
            method_engine = details["result"].get("engine", {})
            limitations = details["result"].get("limitations", limitations)
        if key in {"descriptive_statistics", "group_statistics", "correlation"}:
            method_engine = research.get("statistics", {}).get("engine", {})
            if key in {"group_statistics", "correlation"} and method_engine.get("status") == "unavailable": state = "unavailable"
        unit = {"morphology": "形態素", "syntax": "形態素間の係り受け", "kwic": "出現箇所",
                "speaker_characteristics": "本文のある対象発話", "meeting_minutes": "発話（タスク・決定事項の候補）",
                "interview_comparison": "インタビュー（セッション）"}.get(key, research.get("analysis_unit", "発話"))
        if key == "meeting_minutes":
            limitations = ["タスク・担当・優先度・期限・決定事項は規則で抽出した候補です。元発話を確認してから利用してください。"]
        if key == "interview_comparison":
            limitations = list(details.get("cautions", []))
        if key == "transformer_topics" and details.get("result"):
            unit = details["result"].get("analysis_unit", unit)
        if key == "segment_classification":
            unit = "発話"
            result = details.get("result") or {}
            method_engine = {
                "template": "deterministic-rules",
                "llm": (result.get("sources") or {}).get("llm", {}),
                "transformer": (result.get("sources") or {}).get("transformer", {}),
            }
            limitations = list(result.get("limitations", limitations))
        local = (analysis.get("local_methods") or {}).get(key)
        if key in {"response_network", "cooccurrence_network", "coding_consistency"}:
            from .services.analysis_networks import CARDS, VERSION
            details = local or {}
            state = local["status"] if local else "not_run"
            unit = CARDS[key]["analysis_unit"]
            limitations = CARDS[key]["limitations"]
            method_engine = details.get("engine", {})
            summaries = [{"title": "適用条件", "text": CARDS[key]["conditions"]},
                         {"title": "計算法", "text": CARDS[key]["calculation"]}]
            if details.get("reason"):
                summaries.append({"title": "適用外の理由", "text": details["reason"]})
        previews = [{"dataset": name, "fields": preview_fields(name, datasets[name][0]),
                     "rows": datasets[name][1][:10], "total": len(datasets[name][1])}
                    for name in selected if datasets[name][1] and key not in {"local_insights", "ai_insights", "kwic", "ai_finishing"}]
        results.append({"method_id": key, "method_version": REGISTRY_VERSION, "title": title,
                        "status": state, "datasets": selected, "findings": findings,
                        "summaries": summaries, "details": details, "previews": previews,
                        "analysis_unit": unit, "engine": method_engine,
                        "limitations": limitations})
        if local:
            results[-1]["method_version"] = VERSION
    return results
