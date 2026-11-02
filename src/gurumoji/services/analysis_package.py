"""Version 2 fixed tables, database references and reconstructable result documents."""
from __future__ import annotations

import base64
import copy
import json
import sqlite3
import threading
from contextlib import closing

from ..analysis_core import canonical, fingerprint
from .derived_analysis_store import DerivedAnalysisStore, DATABASE


LABEL_TABLES = {"segment_classifications", "transformer_assignments", "segment_emotions",
                "segment_outliers", "backchannels", "coding_consistency", "transformer_outliers",
                "transformer_backchannels"}
_RECOVERY_LOCK = threading.Lock()
_RECOVERIES = {}


def graph_datasets(datasets, analysis):
    from ..analysis_core import graph_node_id, validate_graph_edge
    item_id = analysis['item']['id']
    segments = {s['id']: s for s in analysis.get('segments', [])}
    terms = {}
    for row in analysis.get('research', {}).get('linguistics', {}).get('morphemes', []):
        if not row.get('excluded'):
            terms.setdefault(row.get('normalized'), set()).add(row['segment_id'])
    updated = dict(datasets)
    for name in ('cooccurrence', 'interaction_links'):
        if name not in datasets:
            continue
        fields, rows = datasets[name]
        values = []
        for row in rows:
            if name == 'cooccurrence':
                evidence = terms.get(row['term_a'],set()) & terms.get(row['term_b'],set())
                source = graph_node_id('term', lemma=row['term_a'], pos='unknown')
                target = graph_node_id('term', lemma=row['term_b'], pos='unknown')
                provenance, relation, weight = 'rule', 'cooccurrence', row['cooccurrence_count']
            else:
                evidence = {row['source_segment_id'], row['target_segment_id']} & set(segments)
                source = graph_node_id('utt',item_id=item_id,segment_id=row['source_segment_id'])
                target = graph_node_id('utt',item_id=item_id,segment_id=row['target_segment_id'])
                provenance, relation, weight = 'researcher', row['relation'], 1
            edge = None
            if evidence:
                edge = validate_graph_edge({'source':source,'target':target,'relation':relation,'weight':weight,
                    'provenance':provenance,'method':name,
                    'method_version':str(analysis.get('algorithm_version') or 'unknown'),
                    'input_hash': fingerprint(analysis.get('segments', []))[7:],
                    'evidence_segment_ids': [graph_node_id('utt',item_id=item_id,segment_id=s) for s in sorted(evidence)]})
            values.append({**row,'graph_edge':edge,'graph_status':'recorded' if edge else 'missing_evidence'})
        updated[name] = ([*fields,'graph_edge','graph_status'],values)
    return updated


class MissingReference(ValueError):
    code = "missing_reference"

    def __init__(self, table, *, recoverable=False):
        super().__init__("参照先の行がありません（作り直しても一致しません）：" + table)
        self.table = table
        self.recoverable = recoverable


def initialize(connection):
    connection.execute('''CREATE TABLE IF NOT EXISTS analysis_package_inputs (
        run_id TEXT PRIMARY KEY, payload_hash TEXT NOT NULL)''')
    connection.execute('''CREATE TABLE IF NOT EXISTS segment_labels (
        run_id TEXT NOT NULL, item_id TEXT NOT NULL, segment_id TEXT NOT NULL,
        text_hash TEXT NOT NULL, method TEXT NOT NULL, method_version TEXT NOT NULL,
        label_kind TEXT NOT NULL, label TEXT, score REAL, rank INTEGER NOT NULL,
        origin TEXT NOT NULL, model TEXT NOT NULL, model_revision TEXT NOT NULL,
        input_hash TEXT NOT NULL, config_hash TEXT NOT NULL, result_hash TEXT NOT NULL,
        row_json TEXT NOT NULL, PRIMARY KEY(run_id,item_id,segment_id,method,label_kind,rank))''')
    columns = {r[1] for r in connection.execute('PRAGMA table_info(segment_labels)')}
    for column in ('prompt_version', 'prompt_hash'):
        if column not in columns:
            connection.execute(f"ALTER TABLE segment_labels ADD COLUMN {column} TEXT NOT NULL DEFAULT 'unknown'")


def input_hash(result, datasets):
    # Wall-clock rendering metadata is not part of inference identity.
    value, tables = copy.deepcopy(result), copy.deepcopy(datasets)
    if isinstance(value.get('analysis'), dict):
        value['analysis'].pop('generated_at', None)
    def stable(current):
        if isinstance(current, dict):
            rendered_row = ({'item_id', 'source_name', 'revision_count'} <= current.keys()
                            and str(current.get('algorithm_version', '')).startswith('focus-group-local-'))
            return {k:stable(v) for k,v in current.items() if not (rendered_row and k=='generated_at')}
        if isinstance(current, (list,tuple)):
            return [stable(v) for v in current]
        return current
    return fingerprint(stable({"result": value, "datasets": tables}))


def embedding_reference(store, snapshot, result):
    from . import segment_embeddings
    transformer = result.get('analysis', {}).get('transformer', {}).get('result') or {}
    vectors = transformer.get('vectors')
    if not vectors:
        return None
    rows = segment_embeddings.prepare_rows({'item': {'id': snapshot['conversation_id']},
        'segments': snapshot['segments']}, transformer)
    if not rows:
        raise ValueError('保存ベクトルのモデル版が不明です。')
    with store.connect() as connection:
        segment_embeddings.initialize(connection)
        segment_embeddings.write_rows(connection, rows)
    values = [{'item_id': r[0], 'segment_id': r[1], 'text_sha256': r[2], 'input_hash': r[3],
               'model_name': r[4], 'model_revision': r[5], 'dimensions': r[6], 'encoding': r[7],
               'vector': base64.b64encode(r[8]).decode()} for r in rows]
    keys = [[r[0],r[1],r[4],r[5],r[2]] for r in rows]
    return vectors, values, {'kind': 'segment_embeddings', 'version': 1, 'keys': keys,
        'keys_hash': fingerprint(keys), 'input_hashes': [r[3] for r in rows],
        'fields': list(values[0]), 'row_count': len(values), 'rows_hash': fingerprint(values)}


def label_reference(store, run, name, fields, rows, snapshot, result):
    keys = []
    metadata = []
    segments = {s.get("id"): s for s in snapshot.get("segments", [])}
    method_version = str(result.get("algorithms", {}).get("segment_classification")
                         or result.get("algorithms", {}).get("transformer") or "unknown")
    engine = (result.get("analysis", {}).get("transformer", {}).get("result") or {}).get("engine", {})
    with store.connect() as connection:
        for index, row in enumerate(rows):
            sid = str(row.get("segment_id") or "")
            if not sid:
                raise ValueError("推論行の発話IDがありません。")
            text = row.get("text", segments.get(sid, {}).get("text", ""))
            key = [run["id"], str(row.get("item_id") or run["item_id"]), sid, name, name, index]
            keys.append(key)
            row_json = canonical(row).decode()
            existing = connection.execute('''SELECT row_json FROM segment_labels
                WHERE run_id=? AND item_id=? AND segment_id=? AND method=? AND label_kind=? AND rank=?''', key).fetchone()
            if existing:
                if existing[0] != row_json:
                    raise ValueError("同じ実行IDに異なる推論結果は保存できません。")
                metadata.append(tuple(connection.execute('''SELECT text_hash,method_version,label,score,origin,
                    model,model_revision,input_hash,config_hash,prompt_version,prompt_hash FROM segment_labels
                    WHERE run_id=? AND item_id=? AND segment_id=? AND method=? AND label_kind=? AND rank=?''', key).fetchone()))
                continue
            prompt_version = str(result.get('prompt_version') or result.get('finishing', {}).get('prompt_version')
                                 or method_version)
            connection.execute('''INSERT INTO segment_labels
                (run_id,item_id,segment_id,text_hash,method,method_version,label_kind,label,score,rank,
                 origin,model,model_revision,input_hash,config_hash,result_hash,row_json,prompt_version,prompt_hash)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (key[0], key[1], sid, fingerprint(text), name, str(row.get("method_version") or method_version), name,
                 str(row.get("label") or row.get("llm_dialogue_act") or row.get("topic_label") or ""),
                 row.get("score", row.get("llm_dialogue_act_confidence")), index,
                 str(row.get("origin") or ('ai_draft' if row.get('llm_model') or row.get('model_name') or run['model'] else 'rule')),
                 str(row.get("model_name") or row.get('llm_model') or run["model"]),
                 str(row.get("model_revision") or engine.get("revision") or "unknown"),
                 fingerprint({"snapshot": snapshot, "source": run["input_fingerprint"]}),
                 fingerprint({"parameters": result.get("parameters", {}), "algorithms": result.get("algorithms", {})}),
                 fingerprint(row), row_json, prompt_version, fingerprint({'version': prompt_version,
                    'algorithms': result.get('algorithms', {}), 'parameters': result.get('parameters', {})})))
            metadata.append(tuple(connection.execute('''SELECT text_hash,method_version,label,score,origin,
                model,model_revision,input_hash,config_hash,prompt_version,prompt_hash FROM segment_labels
                WHERE run_id=? AND item_id=? AND segment_id=? AND method=? AND label_kind=? AND rank=?''', key).fetchone()))
    return {"kind": "segment_labels", "version": 1, "run_id": run["id"],
            "keys": keys, "keys_hash": fingerprint(keys), "fields": fields,
            'metadata_hash': fingerprint(metadata),
            "row_count": len(rows), "rows_hash": fingerprint(rows)}


def lexical_reference(store, name, fields, rows, snapshot, result):
    from .. import research_analysis as research
    database = store.root.parent / DATABASE
    cache = DerivedAnalysisStore(database)
    bindings = []
    grouped = {}
    for row in rows:
        grouped.setdefault(row.get("segment_id"), []).append(row)
    segments = {s.get("id"): s for s in snapshot.get("segments", [])}
    expected_algorithm = (result.get('algorithms', {}).get('research')
                          or result.get('analysis', {}).get('research', {}).get('algorithm_version'))
    for sid, exported in grouped.items():
        segment = segments.get(sid)
        if segment is None:
            raise ValueError("派生解析の発話IDが固定入力にありません。")
        text = str(segment.get("text") or "")
        # Existing F1 rows are reused. A direct archive call can populate the same cache.
        if not database.exists():
            with research.derived_storage(database):
                research.build_research_linguistics({"segments": list(segments.values()), "config": snapshot.get("config", {})})
        found = None
        with closing(cache._connect()) as connection:
            candidates = connection.execute("SELECT parse_key,analyzer_json,rows_hash,config_hash FROM segment_parses WHERE text_hash=?",
                                            (fingerprint(text),)).fetchall()
            for key, analyzer_json, parse_hash, config_hash in candidates:
                if expected_algorithm and json.loads(analyzer_json).get('algorithm') != expected_algorithm:
                    continue
                neutral = [json.loads(r[0]) for r in connection.execute(
                    f"SELECT row_json FROM {name} WHERE parse_key=? ORDER BY ordinal", (key,))]
                if len(neutral) != len(exported) or not neutral:
                    continue
                extras = {k: v for k, v in exported[0].items() if k not in neutral[0]}
                reconstructed = [{**r, **extras} for r in neutral]
                if canonical(reconstructed) == canonical(exported):
                    config = {"stop_words": sorted(research._clean_stop_words(snapshot.get('config', {})))}
                    analyzer = json.loads(analyzer_json)
                    if analyzer["engine"] == "sudachi":
                        config["split_mode"] = str(snapshot.get("config", {}).get("morph_split_mode") or "C")
                    if fingerprint(config) != config_hash:
                        continue
                    found = {"key": key, "segment_id": sid, "analyzer": analyzer, "config": config,
                             "parse_hash": parse_hash, "extras": extras}
                    break
        if found is None:
            raise ValueError("保存する派生解析行を既存F1の版に照合できません。")
        bindings.append(found)
    keys = [b["key"] for b in bindings]
    return {"kind": name, "version": 1, "bindings": bindings, "keys_hash": fingerprint(keys),
            "fields": fields, "row_count": len(rows), "rows_hash": fingerprint(rows)}


def resolve(store, name, reference, snapshot):
    rows = []
    kind = reference["kind"]
    try:
        if kind == "segment_labels":
            keys = reference["keys"]
            metadata = []
            if fingerprint(keys) != reference["keys_hash"] or any(k[0] != reference["run_id"] for k in keys):
                raise ValueError("推論行の鍵が一致しません。")
            with store.connect() as connection:
                for index, key in enumerate(keys):
                    saved = connection.execute('''SELECT row_json,result_hash FROM segment_labels
                        WHERE run_id=? AND item_id=? AND segment_id=? AND method=? AND label_kind=? AND rank=?''', key).fetchone()
                    if saved is None:
                        raise MissingReference(name)
                    row = json.loads(saved[0])
                    if fingerprint(row) != saved[1]:
                        raise MissingReference(name)
                    rows.append(row)
                    metadata.append(tuple(connection.execute('''SELECT text_hash,method_version,label,score,origin,
                        model,model_revision,input_hash,config_hash,prompt_version,prompt_hash FROM segment_labels
                        WHERE run_id=? AND item_id=? AND segment_id=? AND method=? AND label_kind=? AND rank=?''', key).fetchone()))
            if fingerprint(metadata) != reference['metadata_hash']:
                raise MissingReference(name)
        elif kind == 'segment_embeddings':
            keys = reference['keys']
            if fingerprint(keys) != reference['keys_hash']:
                raise MissingReference(name)
            with store.connect() as connection:
                for key in keys:
                    saved = connection.execute('''SELECT item_id,segment_id,text_sha256,input_hash,
                        model_name,model_revision,dimensions,encoding,vector FROM segment_embeddings
                        WHERE item_id=? AND segment_id=? AND model_name=? AND model_revision=? AND text_sha256=?''', key).fetchone()
                    if saved is None:
                        raise MissingReference(name)
                    row = dict(zip(reference['fields'], saved))
                    row['vector'] = base64.b64encode(row['vector']).decode()
                    row['input_hash'] = reference['input_hashes'][len(rows)]
                    rows.append(row)
        elif kind in {"morphemes", "dependencies"}:
            database = store.root.parent / DATABASE
            bindings = reference["bindings"]
            if bindings and not database.exists():
                raise MissingReference(name, recoverable=True)
            cache = DerivedAnalysisStore(database)
            segments = {s.get("id"): s for s in snapshot.get("segments", [])}
            if fingerprint([b["key"] for b in bindings]) != reference["keys_hash"]:
                raise ValueError("派生解析の鍵が一致しません。")
            for binding in bindings:
                text = str(segments[binding["segment_id"]].get("text") or "")
                if cache.key(text, binding["analyzer"], binding["config"]) != binding["key"]:
                    raise ValueError("派生解析の入力が一致しません。")
                parsed = cache.read(text, binding["analyzer"], binding["config"], readonly=True)
                if parsed is None or fingerprint(parsed) != binding["parse_hash"]:
                    raise MissingReference(name, recoverable=True)
                rows.extend({**r, **binding["extras"]} for r in parsed[0 if kind == "morphemes" else 1])
        else:
            raise ValueError("参照の種類に対応していません。")
        if len(rows) != reference["row_count"] or fingerprint(rows) != reference["rows_hash"]:
            raise MissingReference(name, recoverable=kind in {"morphemes", "dependencies"})
    except (sqlite3.Error, OSError, KeyError, ValueError) as exc:
        if isinstance(exc, MissingReference):
            raise
        raise MissingReference(name, recoverable=kind in {"morphemes", "dependencies"}) from exc
    return rows


def recover_lexical(store, references, snapshot):
    from .. import research_analysis as research
    segments = {s.get("id"): s for s in snapshot.get("segments", [])}
    rebuilt = {}
    for name, reference in references.items():
        if reference["kind"] not in {"morphemes", "dependencies"}:
            continue
        for binding in reference["bindings"]:
            if binding["key"] in rebuilt:
                continue
            analyzer, config = binding["analyzer"], binding["config"]
            engine = analyzer["engine"]
            text = str(segments[binding["segment_id"]].get("text") or "")
            stop = set(config.get("stop_words", []))
            if engine == "ginza":
                model, _ = research._load_ginza()
                if model is None or research._parser_identity(engine, model) != analyzer:
                    raise MissingReference(name)
                parsed = research._analyze_with_ginza([{"text": text}], model, stop)
            elif research._parser_identity(engine) != analyzer:
                raise MissingReference(name)
            elif engine == "sudachi":
                model, _ = research._load_sudachi()
                if model is None:
                    raise MissingReference(name)
                values, count = research._analyze_with_sudachi([{"text": text}], model, config["split_mode"], stop)
                parsed = (values, [], count)
            elif engine == "fallback":
                values, count = research._analyze_with_fallback([{"text": text}], stop)
                parsed = (values, [], count)
            else:
                raise MissingReference(name)
            neutral = tuple([{k: v for k, v in r.items() if k not in research._row_common({})} for r in part]
                            for part in parsed[:2]) + (parsed[2],)
            if fingerprint(neutral) != binding["parse_hash"]:
                raise MissingReference(name)
            rebuilt[binding["key"]] = (text, analyzer, config, neutral)
    cache = DerivedAnalysisStore(store.root.parent / DATABASE)
    # All hashes pass before any row is restored. Corrupt existing rows remain evidence.
    for text, analyzer, config, parsed in rebuilt.values():
        cache.restore(text, analyzer, config, parsed, fingerprint(parsed))


def schedule_recovery(store, run_id, references, snapshot):
    key = (str(store.root.resolve()), fingerprint(references))
    with _RECOVERY_LOCK:
        state = _RECOVERIES.get(key)
        if state and state['status'] != 'ready':
            return state["status"]
        state = {"status": "rebuilding"}
        _RECOVERIES[key] = state
    def work():
        try:
            recover_lexical(store, references, snapshot)
            store.verified_package(run_id)
            state["status"] = "ready"
        except Exception:
            state["status"] = "missing_reference"
    thread = threading.Thread(target=work, daemon=True, name="analysis-reference-recovery")
    state['thread'] = thread
    thread.start()
    return "rebuilding"


def compact_document(value, datasets, vectors=None, snapshot=None):
    """Replace matching row lists, including projections/previews, with fixed table references."""
    inputs = {}
    def index_inputs(current, path):
        if isinstance(current, (list,dict)) and current:
            inputs[fingerprint(current)] = path
            if isinstance(current,dict):
                for k,v in current.items():
                    index_inputs(v, path + [k])
    if snapshot is not None:
        index_inputs(snapshot, [])
    def walk(current):
        if isinstance(current,dict) and set(current) in ({'$input'}, {'$vectors'}, {'$literal'},
                {'$table','keys','limit'}, {'$label_row','index','shape'}):
            return {'$literal': copy.deepcopy(current)}
        if isinstance(current,(dict,list)) and current:
            path = inputs.get(fingerprint(current))
            if path is not None:
                return {'$input': path}
        if isinstance(current, list):
            if current and all(isinstance(r, dict) for r in current):
                if ('segment_classifications' in datasets and all('segment_id' in r for r in current)
                        and any(isinstance(r.get('llm'), dict) or isinstance(r.get('template'), dict) for r in current)):
                    label_rows = datasets['segment_classifications'][1]
                    by_id = {r['segment_id']: (i,r) for i,r in enumerate(label_rows)}
                    if all(r['segment_id'] in by_id for r in current):
                        def shape(part, row, prefix=''):
                            if isinstance(part, dict):
                                return {k: shape(v,row,prefix+k+'_') for k,v in part.items()}
                            field = prefix[:-1]
                            field = {'manual_codes': 'manual_code_ids'}.get(field,field)
                            if field in row and canonical(row[field]) == canonical(part):
                                return {'$cell': field}
                            return part
                        return [{'$label_row':'segment_classifications', 'index':by_id[r['segment_id']][0],
                                 'shape':shape(r,by_id[r['segment_id']][1])} for r in current]
                keys = list(dict.fromkeys(k for row in current for k in row))
                for name, (_, rows) in datasets.items():
                    if len(current) > len(rows):
                        continue
                    projected = [{k: r[k] for k in keys if k in r} for r in rows[:len(current)]]
                    if canonical(projected) == canonical(current):
                        return {"$table": name, "keys": keys, "limit": len(current)}
            return [walk(v) for v in current]
        if isinstance(current, dict):
            if vectors is not None and current == vectors:
                return {'$vectors': 'segment_embeddings'}
            return {k: walk(v) for k, v in current.items()}
        return current
    return walk(value)


def expand_document(value, tables, snapshot=None):
    if isinstance(value, dict):
        if set(value) == {'$literal'}:
            return copy.deepcopy(value['$literal'])
        if set(value) == {'$label_row','index','shape'}:
            row = tables[value['$label_row']]['rows'][value['index']]['values']
            def restore(shape):
                if isinstance(shape,dict):
                    if set(shape) == {'$cell'}:
                        return copy.deepcopy(row[shape['$cell']])
                    return {k: restore(v) for k,v in shape.items()}
                return shape
            return restore(value['shape'])
        if set(value) == {'$input'}:
            current = snapshot
            for key in value['$input']:
                current = current[key]
            return copy.deepcopy(current)
        if set(value) == {'$vectors'}:
            rows = [r['values'] for r in tables[value['$vectors']]['rows']]
            return {'encoding': 'base64-int8', 'scale': 127, 'dimensions': rows[0]['dimensions'],
                'segment_ids': [r['segment_id'] for r in rows],
                'data': base64.b64encode(b''.join(base64.b64decode(r['vector']) for r in rows)).decode()}
        if set(value) == {"$table", "keys", "limit"}:
            rows = [r["values"] for r in tables[value["$table"]]["rows"]]
            if type(value["limit"]) is not int or not 0 <= value["limit"] <= len(rows):
                raise ValueError("文書の固定表参照が正しくありません。")
            return [{k: row[k] for k in value["keys"] if k in row} for row in rows[:value["limit"]]]
        return {k: expand_document(v, tables, snapshot) for k, v in value.items()}
    if isinstance(value, list):
        return [expand_document(v, tables, snapshot) for v in value]
    return value
