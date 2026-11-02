"""Deterministic descriptive networks and manual-code review candidates."""
from __future__ import annotations

import math
from collections import defaultdict

import networkx as nx

from ..analysis_core import EMBEDDING_STANDARD_V1, fingerprint, graph_node_id, validate_graph_edge
from ..transcript_preparation import valid_time
from . import segment_embeddings

VERSION = "analysis-networks-1"
CAUTION = "記述的な指標です。発話を独立標本とする検定や、影響・合意・因果関係の判定ではありません。"
CODING_CAUTION = "要確認の手がかりであり、コードの正誤の判定ではありません。研究者のコードは変更しません。"
CARDS = {
    "response_network": {
        "purpose": "話者間の発話の受け渡しを記述する", "analysis_unit": "話者交替",
        "inputs": ["conversation_dynamics.transitions", "conversation_speakers", "conversation_segments"],
        "conditions": "既知の話者2人以上、時刻のある対象発話間の話者交替3回以上",
        "parameters": {"min_speakers": 2, "min_transitions": 3},
        "calculation": "有向辺の重みは交替回数。相互性はΣmin(w_uv,w_vu)/全交替数。偏りは出辺の最多相手の割合。中心性は入出辺の重み合計/全交替数。",
        "limitations": [CAUTION, "時刻不明・除外・話者未確認を含む元の時間構造の制約を引き継ぎます。応答の意味は推定しません。"],
    },
    "cooccurrence_network": {
        "purpose": "共起する語のまとまりと中心語を記述する", "analysis_unit": "語・発話内の共起",
        "inputs": ["cooccurrence", "morphemes"], "conditions": "根拠を確認できる語2個以上、共起辺1本以上",
        "parameters": {"min_terms": 2, "min_edges": 1, "community_method": "greedy_modularity",
                       "weight": "cooccurrence_count", "resolution": 1.0},
        "calculation": "語と辺を辞書順に挿入する決定的な貪欲モジュラリティ法。中心性は重み付き次数/全辺重み。",
        "limitations": [CAUTION, "既存共起の上位語・最小回数・最大500辺の範囲内です。簡易解析と正式解析を区別します。語のまとまりは研究者が確定したテーマではありません。"],
    },
    "coding_consistency": {
        "purpose": "手動コードの意味のまとまりと確認候補を示す", "analysis_unit": "手動コード付き発話",
        "inputs": ["analysis_annotations_json", "segment_embeddings:standard-v1"],
        "conditions": "対象発話3件以上のコードが1つ以上。対象コードの全発話に現在の標準v1ベクトルが必要",
        "parameters": {"min_segments_per_code": 3, "other_code_margin": 0.1, "far_similarity": 0.35,
                       "own_centroid": "leave_one_out", "embedding_standard": EMBEDDING_STANDARD_V1},
        "calculation": "コサイン類似度。自コードは当該発話を除く平均ベクトル、他コードは全件平均。複数コードは自コードの最大類似度を比較。遠さは全対象コードとの最大類似度で判断。",
        "limitations": [CODING_CAUTION, CAUTION, "しきい値は確認候補を選ぶ実装上の目安です。コード3件未満は比較しません。ゼロの重心は算出不能とし、類似度0で補いません。"],
    },
}
FIELDS = {
    "response_nodes": ["node_id", "speaker", "speaker_name", "incoming", "outgoing", "reciprocity", "outgoing_bias", "strength_centrality", "evidence_segment_ids"],
    "response_edges": ["edge_id", "source", "target", "from_speaker", "to_speaker", "weight", "relation", "provenance", "method", "method_version", "input_hash", "evidence_segment_ids", "segment_ids"],
    "response_summary": ["speaker_count", "transition_count", "reciprocity", "missing_time_count", "unknown_speaker_count"],
    "cooccurrence_nodes": ["node_id", "term", "community", "degree", "strength", "strength_centrality", "evidence_segment_ids"],
    "cooccurrence_edges": ["edge_id", "source", "target", "term_a", "term_b", "weight", "relation", "provenance", "method", "method_version", "input_hash", "evidence_segment_ids", "segment_ids"],
    "cooccurrence_communities": ["community", "terms", "term_count", "evidence_segment_ids"],
    "consistency_codes": ["code_id", "label", "segment_count", "mean_similarity", "unscorable_count", "evidence_segment_ids"],
    "coding_consistency": ["segment_id", "text", "code_ids", "nearest_other_code", "own_similarity", "other_similarity", "max_similarity", "label", "score", "origin", "method_version", "model_name", "model_revision", "evidence_segment_ids"],
}
DATASETS = {
    "response_network": ["response_nodes", "response_edges", "response_summary"],
    "cooccurrence_network": ["cooccurrence_nodes", "cooccurrence_edges", "cooccurrence_communities"],
    "coding_consistency": ["consistency_codes", "coding_consistency"],
}
for _method, _card in CARDS.items():
    _card.update({"method_id": _method, "method_version": VERSION, "execution_kind": "builtin",
                  "output_fields": {name: FIELDS[name] for name in DATASETS[_method]},
                  "ui_entry": "分析 > 手法別", "reuse": "固定保存した実行を参照し、現在の入力変更は更新が必要と表示"})


def _result(method, analysis, inputs, *, reason="", tables=None, coverage=None):
    return {"method_version": VERSION, "status": "not_applicable" if reason else "completed",
            "reason": reason, "card": CARDS[method], "engine": {"name": "networkx" if method != "coding_consistency" else "cosine-rules",
                "version": nx.__version__ if method != "coding_consistency" else VERSION},
            "input_hash": fingerprint({"item": analysis["item"]["id"],
                "source_revision": analysis["item"].get("revision_count"),
                "analysis_revision": analysis["item"].get("analysis_revision"),
                "segments": analysis["segments"], "inputs": inputs, "card": CARDS[method]}),
            "coverage": coverage or {}, "tables": tables or {name: [] for name in DATASETS[method]}}


def _edge(method, result, analysis, source, target, weight, ids):
    return validate_graph_edge({"source": source, "target": target, "weight": weight,
        "relation": "speaker_transition" if method == "response_network" else "cooccurrence",
        "provenance": "rule", "method": method, "method_version": VERSION,
        "input_hash": result["input_hash"][7:],
        "evidence_segment_ids": [graph_node_id("utt", item_id=analysis["item"]["id"], segment_id=sid) for sid in sorted(ids)]})


def response_network(analysis, speaker_ids=None, projected_ids=None):
    segments = [s for s in analysis["segments"] if not s.get("excluded")]
    transitions = analysis["automatic"]["transitions"]
    inputs = {"transitions": transitions, "speaker_ids": speaker_ids or {},
              "projected_ids": sorted(projected_ids) if projected_ids is not None else None}
    result = _result("response_network", analysis, inputs)
    if projected_ids is not None and any(s["id"] not in projected_ids for s in segments):
        return _result("response_network", analysis, inputs, reason="発話の展開表が入力と一致しません。整合検査を確認してください。")
    known = {s["speaker"] for s in segments if s.get("speaker") not in (None, "", "UNKNOWN")}
    timed = sorted((s for s in segments if s.get("valid_time", valid_time(s)) and valid_time(s)),
                   key=lambda s: (s["start"], s["end"], s["id"]))
    evidence = defaultdict(set)
    counts = defaultdict(int)
    for left, right in zip(timed, timed[1:]):
        a, b = left["speaker"], right["speaker"]
        if a != b and a in known and b in known:
            counts[a, b] += 1
            evidence[a, b].update((left["id"], right["id"]))
    supplied = {(r["from_speaker"], r["to_speaker"]): r["count"] for r in transitions
                if r["from_speaker"] in known and r["to_speaker"] in known}
    if dict(counts) != supplied:
        return _result("response_network", analysis, inputs, reason="話者交替の表と根拠発話が一致しません。再集計してください。")
    total = sum(counts.values())
    if len(known) < 2 or total < 3:
        return _result("response_network", analysis, inputs, reason="既知の話者2人以上・話者交替3回以上が必要です。")
    graph = nx.DiGraph()
    graph.add_nodes_from(sorted(known))
    for (a, b), weight in sorted(counts.items()):
        graph.add_edge(a, b, weight=weight)
    identifiers = {s: graph_node_id("spk", item_id=analysis["item"]["id"], speaker=s,
                                  participant_code=(speaker_ids or {}).get(s, "")) for s in sorted(known)}
    edges = [{**_edge("response_network", result, analysis, identifiers[a], identifiers[b], weight, evidence[a, b]),
              "from_speaker": a, "to_speaker": b, "segment_ids": sorted(evidence[a, b])}
             for (a, b), weight in sorted(counts.items())]
    nodes = []
    for speaker in sorted(known):
        incoming = graph.in_degree(speaker, weight="weight")
        outgoing = graph.out_degree(speaker, weight="weight")
        mutual = sum(min(counts.get((speaker, s), 0), counts.get((s, speaker), 0)) for s in known)
        nodes.append({"node_id": identifiers[speaker], "speaker": speaker,
            "speaker_name": next(s.get("speaker_name", speaker) for s in segments if s["speaker"] == speaker),
            "incoming": incoming, "outgoing": outgoing,
            "reciprocity": 2 * mutual / (incoming + outgoing) if incoming + outgoing else None,
            "outgoing_bias": max((v for (a, _), v in counts.items() if a == speaker), default=0) / outgoing if outgoing else None,
            "strength_centrality": (incoming + outgoing) / total,
            "evidence_segment_ids": sorted(s["id"] for s in segments if s["speaker"] == speaker)})
    summary = {"speaker_count": len(known), "transition_count": total,
        "reciprocity": sum(min(v, counts.get((b, a), 0)) for (a, b), v in counts.items()) / total,
        "missing_time_count": len(segments) - len(timed),
        "unknown_speaker_count": sum(s.get("speaker") not in known for s in segments)}
    result["tables"] = {"response_nodes": nodes, "response_edges": edges, "response_summary": [summary]}
    result["coverage"] = summary
    return result


def cooccurrence_network(analysis, linguistics):
    pairs = linguistics["cooccurrence"]
    included = {s["id"] for s in analysis["segments"] if not s.get("excluded")}
    term_ids = defaultdict(set)
    for row in linguistics["morphemes"]:
        if row.get("is_content") and not row.get("excluded") and row["segment_id"] in included:
            term_ids[row["normalized"]].add(row["segment_id"])
    inputs = {"pairs": sorted(pairs, key=lambda r: (r["term_a"], r["term_b"])),
              "term_ids": {k: sorted(v) for k, v in sorted(term_ids.items())},
              "coverage": linguistics["coverage"], "engine": linguistics["engine"]}
    result = _result("cooccurrence_network", analysis, inputs, coverage=linguistics["coverage"])
    graph = nx.Graph()
    graph.add_nodes_from(sorted({r[k] for r in pairs for k in ("term_a", "term_b")}))
    for row in inputs["pairs"]:
        a, b, weight = row["term_a"], row["term_b"], row["cooccurrence_count"]
        ids = term_ids[a] & term_ids[b]
        if a == b or type(weight) is not int or weight < 1 or len(ids) != weight or graph.has_edge(a, b):
            return _result("cooccurrence_network", analysis, inputs, reason="共起の辺と形態素の根拠が一致しません。再解析してください。")
        graph.add_edge(a, b, weight=weight)
    if len(graph) < 2 or graph.number_of_edges() < 1:
        return _result("cooccurrence_network", analysis, inputs, reason="語2個以上・共起辺1本以上が必要です。")
    communities = sorted((sorted(c) for c in nx.community.greedy_modularity_communities(graph, weight="weight", resolution=1.0)), key=lambda c: tuple(c))
    membership = {term: index for index, terms in enumerate(communities, 1) for term in terms}
    total = graph.size(weight="weight")
    nodes = [{"node_id": graph_node_id("term", lemma=t, pos="unknown"), "term": t,
        "community": membership[t], "degree": graph.degree(t), "strength": graph.degree(t, weight="weight"),
        "strength_centrality": graph.degree(t, weight="weight") / total,
        "evidence_segment_ids": sorted(term_ids[t])} for t in sorted(graph)]
    edges = [{**_edge("cooccurrence_network", result, analysis, graph_node_id("term", lemma=a, pos="unknown"),
        graph_node_id("term", lemma=b, pos="unknown"), graph[a][b]["weight"], term_ids[a] & term_ids[b]),
        "term_a": a, "term_b": b, "segment_ids": sorted(term_ids[a] & term_ids[b])} for a, b in sorted(graph.edges())]
    result["tables"] = {"cooccurrence_nodes": nodes, "cooccurrence_edges": edges,
        "cooccurrence_communities": [{"community": i, "terms": terms, "term_count": len(terms),
            "evidence_segment_ids": sorted(set().union(*(term_ids[t] for t in terms)))} for i, terms in enumerate(communities, 1)]}
    result["engine"]["parser"] = linguistics["engine"]
    return result


def _unit(vector):
    length = math.sqrt(sum(v*v for v in vector))
    return [v / length for v in vector] if length else None


def _similarity(vector, centroid):
    unit = _unit(centroid)
    return max(-1.0, min(1.0, sum(a*b for a, b in zip(vector, unit)))) if unit else None


def coding_consistency(analysis, rows, *, reason=""):
    segments = {s["id"]: s for s in analysis["segments"] if not s.get("excluded") and s.get("text", "").strip()}
    codes = {c["id"]: c for c in analysis["manual"]["codebook"]}
    members = {code: sorted(sid for sid in segments if code in analysis["annotations"].get(sid, {}).get("codes", [])) for code in sorted(codes)}
    eligible = {code: ids for code, ids in members.items() if len(ids) >= 3}
    current = {r["segment_id"]: r for r in rows if not r["stale"] and r["segment_id"] in segments}
    inputs = {"members": members, "codebook": analysis["manual"]["codebook"],
              "vectors": [{k: (list(v) if isinstance(v, bytes) else v) for k, v in r.items()}
              for _, r in sorted(current.items())]}
    if reason or not eligible:
        return _result("coding_consistency", analysis, inputs, reason=reason or "対象発話3件以上の手動コードが必要です。")
    target = sorted(set().union(*map(set, eligible.values())))
    if any(sid not in current for sid in target):
        return _result("coding_consistency", analysis, inputs, reason="現在の埋め込み標準v1ベクトルが不足しています。Transformer分析で再計算してください。")
    vectors = {sid: _unit([v if v < 128 else v - 256 for v in current[sid]["vector"]]) for sid in target}
    sums = {code: [sum(vectors[sid][j] for sid in ids) for j in range(EMBEDDING_STANDARD_V1["dimensions"])] for code, ids in eligible.items()}
    own = {}
    code_rows = []
    for code, ids in eligible.items():
        similarities = []
        for sid in ids:
            score = _similarity(vectors[sid], [a-b for a, b in zip(sums[code], vectors[sid])])
            own[code, sid] = score
            if score is not None:
                similarities.append(score)
        code_rows.append({"code_id": code, "label": codes[code]["label"], "segment_count": len(ids),
            "mean_similarity": sum(similarities) / len(similarities) if similarities else None,
            "unscorable_count": len(ids) - len(similarities), "evidence_segment_ids": ids})
    flags = []
    unscorable = 0
    for sid in target:
        assigned = sorted(code for code, ids in eligible.items() if sid in ids)
        scores = {code: own[code, sid] if code in assigned else _similarity(vectors[sid], sums[code]) for code in eligible}
        if any(score is None for score in scores.values()):
            unscorable += 1
            continue
        best_own = max(scores[c] for c in assigned)
        other = sorted((c for c in eligible if c not in assigned), key=lambda c: (-scores[c], c))
        nearest = other[0] if other else None
        reasons = []
        if nearest and scores[nearest] > best_own + 0.1:
            reasons.append("closer_other_code")
        if max(scores.values()) < 0.35:
            reasons.append("far_from_all_codes")
        if reasons:
            flags.append({"segment_id": sid, "text": segments[sid]["text"], "code_ids": assigned,
                "nearest_other_code": nearest, "own_similarity": best_own,
                "other_similarity": scores[nearest] if nearest else None, "max_similarity": max(scores.values()),
                "label": ";".join(reasons), "score": max(scores.values()), "origin": "rule",
                "method_version": VERSION, "model_name": EMBEDDING_STANDARD_V1["model_name"],
                "model_revision": EMBEDDING_STANDARD_V1["model_revision"], "evidence_segment_ids": [sid]})
    return _result("coding_consistency", analysis, inputs,
        tables={"consistency_codes": code_rows, "coding_consistency": flags},
        coverage={"coded_segment_count": len(target), "eligible_code_count": len(eligible),
                  "insufficient_codes": sorted(set(codes) - set(eligible)), "unscorable_segment_count": unscorable})


def attach_foundations(analysis, connection, registry_profiles):
    item_id = analysis["item"]["id"]
    projected_ids = {r[0] for r in connection.execute("SELECT segment_id FROM conversation_segments WHERE item_id=?", (item_id,))}
    identities = {}
    for label, global_id in connection.execute("SELECT speaker_label,global_speaker_id FROM conversation_speakers WHERE item_id=?", (item_id,)):
        code = registry_profiles.get(global_id, {}).get("participant_code")
        if code:
            identities[label] = code
    result = {"response_network": response_network(analysis, identities, projected_ids)}
    try:
        rows = segment_embeddings.read_current(connection, analysis)
        result["coding_consistency"] = coding_consistency(analysis, rows)
    except ValueError as exc:
        result["coding_consistency"] = coding_consistency(analysis, [], reason=str(exc))
    analysis["local_methods"] = result


def csv_sources(analysis):
    results = analysis.get("local_methods") or {}
    return {name: (results.get(method) or {}).get("tables", {}).get(name, [])
            for method, names in DATASETS.items() for name in names}
