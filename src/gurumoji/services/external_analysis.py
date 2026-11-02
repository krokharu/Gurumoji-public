"""Register inert external results against an existing verified input snapshot."""
from __future__ import annotations

import json
import re
import uuid

from ..analysis_core import fingerprint


def register(store, item_id, payload, *, app_url='http://127.0.0.1:7860'):
    if not isinstance(payload, dict):
        raise ValueError('外部分析結果をJSONオブジェクトで指定してください。')
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode('utf-8')) > 5*1024*1024:
        raise ValueError('外部分析結果は5MiB以下にしてください。')
    source = store.get(payload.get('source_run_id', ''))
    if not source or source['item_id'] != item_id or source['status'] != 'completed':
        raise ValueError('この会話の固定分析をsource_run_idに指定してください。')
    snapshot = store.readable_package(source['id'])[0]
    if payload.get('snapshot_id') != source['snapshot_id']:
        raise ValueError('外部結果の入力スナップショットが一致しません。')
    segments=snapshot.get('segments',snapshot.get('analysis',{}).get('segments',[]))
    ids={s['id'] for s in segments if isinstance(s,dict) and isinstance(s.get('id'),str) and not s.get('excluded')}
    evidence = payload.get('evidence_segment_ids')
    if not isinstance(evidence, list) or any(not isinstance(s, str) or s not in ids for s in evidence):
        raise ValueError('根拠発話IDが固定入力に存在しません。')
    method, version = payload.get('method'), payload.get('version')
    if not isinstance(method, str) or not method.strip() or len(method)>200 or not isinstance(version, str) or not version.strip() or len(version)>200:
        raise ValueError('外部分析の手法名と版を指定してください。')
    tables = payload.get('tables')
    if not isinstance(tables, dict) or not 1<=len(tables)<=30:
        raise ValueError('外部結果の表を1〜30件指定してください。')
    datasets = {}
    for name, table in tables.items():
        if not re.fullmatch('[a-z_]{1,60}', name) or not isinstance(table, dict):
            raise ValueError('表名は小文字英字と下線で指定してください。')
        fields, rows = table.get('fields'), table.get('rows')
        if (not isinstance(fields, list) or not 1<=len(fields)<=100 or any(not isinstance(f,str) or not f or len(f)>200 for f in fields)
                or len(set(fields))!=len(fields) or not isinstance(rows,list) or len(rows)>100000
                or any(not isinstance(row,dict) or not set(row).issubset(fields) for row in rows)):
            raise ValueError('外部結果の列・行形式が正しくありません。')
        datasets[name] = (fields, rows)
    scientific_payload={key:value for key,value in payload.items() if key!='request_id'}
    result = {'schema_version':1,'parameters':{'source_run_id':source['id'],'external_method':method,'external_version':version,
        'external_parameters':payload.get('parameters',{})},'external_payload':scientific_payload,
        'algorithms':{'external_registration':'1'},'review_status':'pending',
        'evidence_segment_ids':evidence,'external_payload_hash':fingerprint(scientific_payload),
        'methods':[{'method_id':'external_analysis','title':method,'status':'unreviewed',
            'limitations':['研究者による妥当性確認前の外部結果です。'],'datasets':list(tables)}]}
    return store.save(item_id=item_id,kind='external_analysis',snapshot=snapshot,result=result,datasets=datasets,
        request_id=payload.get('request_id') or uuid.uuid4().hex,input_fingerprint=source['input_fingerprint'],
        source_revision=source['source_revision'],analysis_revision=source['analysis_revision'],app_url=app_url,publish=False)
