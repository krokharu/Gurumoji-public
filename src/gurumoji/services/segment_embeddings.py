"""Conversation vector cache. Transaction ownership stays with the existing job."""
from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from ..analysis_core import EMBEDDING_STANDARD_V1, validate_embedding_compatibility
from ..transformer_analysis import transformer_embedding_fingerprint


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def initialize(connection: Any) -> None:
    connection.execute('''CREATE TABLE IF NOT EXISTS segment_embeddings (
        item_id TEXT NOT NULL, segment_id TEXT NOT NULL,
        text_sha256 TEXT NOT NULL, input_hash TEXT NOT NULL,
        model_name TEXT NOT NULL, model_revision TEXT NOT NULL,
        dimensions INTEGER NOT NULL CHECK(dimensions > 0),
        encoding TEXT NOT NULL, vector BLOB NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY(item_id, segment_id, model_name, model_revision, text_sha256)
    )''')
    connection.execute('''INSERT OR IGNORE INTO application_metadata(key, value)
        VALUES (?, ?)''', ('embedding_standard_v1', json.dumps(EMBEDDING_STANDARD_V1, sort_keys=True)))


def prepare_rows(analysis: dict, result: dict) -> list[tuple]:
    """Validate before writing; legacy results with unknown revision stay JSON-only."""
    engine = result.get('engine') or {}
    if not isinstance(engine, dict):
        raise ValueError('発話ベクトルのモデル情報が正しくありません。')
    if engine.get('revision') in (None, ''):
        return []
    payload = result.get('vectors') or {}
    if not isinstance(payload, dict):
        raise ValueError('発話ベクトルの形式が正しくありません。')
    dimensions = payload.get('dimensions')
    identifiers = payload.get('segment_ids')
    if (not isinstance(engine.get('name'), str) or not engine['name'].strip()
            or not isinstance(engine['revision'], str) or not engine['revision'].strip()
            or type(dimensions) is not int or dimensions <= 0
            or payload.get('encoding') != 'base64-int8' or payload.get('scale') != 127
            or not isinstance(identifiers, list) or not identifiers
            or any(not isinstance(value, str) or not value for value in identifiers)
            or len(set(identifiers)) != len(identifiers)
            or engine.get('dimensions', dimensions) != dimensions):
        raise ValueError('発話ベクトルの形式・モデル・次元が正しくありません。')
    try:
        raw = base64.b64decode(payload.get('data', ''), validate=True)
    except (TypeError, ValueError) as exc:
        raise ValueError('発話ベクトルのbase64が正しくありません。') from exc
    if len(raw) != len(identifiers) * dimensions or b'\x80' in raw:
        raise ValueError('発話ベクトルの件数またはint8 scale 127が正しくありません。')
    segments = analysis.get('segments', [])
    by_id = {row['id']: row for row in segments if row.get('id')}
    if len(by_id) != len([row for row in segments if row.get('id')]):
        raise ValueError('入力の発話IDが重複しています。')
    expected = transformer_embedding_fingerprint(analysis, model=engine['name'], revision=engine['revision'])
    if result.get('embedding_fingerprint') != expected:
        raise ValueError('発話ベクトルの入力hashが一致しません。')
    item_id = analysis.get('item', {}).get('id')
    created_at = result.get('generated_at')
    if not isinstance(item_id, str) or not item_id or not isinstance(created_at, str) or not created_at:
        raise ValueError('会話IDまたは生成日時がありません。')
    rows = []
    for index, identifier in enumerate(identifiers):
        segment = by_id.get(identifier)
        if segment is None or segment.get('excluded') or not isinstance(segment.get('text'), str):
            raise ValueError('発話ベクトルの根拠IDが入力の対象発話と一致しません。')
        vector = raw[index*dimensions:(index+1)*dimensions]
        if not any(vector):
            raise ValueError('ゼロの発話ベクトルは保存できません。')
        rows.append((item_id, identifier, text_sha256(segment['text']), expected,
                     engine['name'], engine['revision'], dimensions, 'int8-scale-127', vector, created_at))
    return rows


def write_rows(connection: Any, rows: list[tuple]) -> None:
    """No commit: vector cache, result JSON and request status commit together."""
    for row in rows:
        existing = connection.execute('''SELECT input_hash,dimensions,encoding,vector
            FROM segment_embeddings WHERE item_id=? AND segment_id=? AND model_name=?
            AND model_revision=? AND text_sha256=?''', (row[0],row[1],row[4],row[5],row[2])).fetchone()
        if existing is not None and tuple(existing)[1:] != (row[6],row[7],row[8]):
            raise ValueError('同じ発話ベクトルの版に異なる値は保存できません。')
    connection.executemany('''INSERT INTO segment_embeddings
        (item_id,segment_id,text_sha256,input_hash,model_name,model_revision,
         dimensions,encoding,vector,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(item_id,segment_id,model_name,model_revision,text_sha256)
        DO UPDATE SET input_hash=excluded.input_hash''', rows)


def read_current(connection: Any, analysis: dict, *, standard: dict | None = None) -> list[dict]:
    """Read only, select one coordinate system and mark stale text/context explicitly."""
    standard = EMBEDDING_STANDARD_V1 if standard is None else standard
    cursor = connection.execute('''SELECT * FROM segment_embeddings WHERE item_id=?
        AND model_name=? AND model_revision=? ORDER BY segment_id,text_sha256''',
        (analysis['item']['id'], standard['model_name'], standard['model_revision']))
    rows = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
    if not rows and connection.execute('SELECT 1 FROM segment_embeddings WHERE item_id=? LIMIT 1',
                                       (analysis['item']['id'],)).fetchone():
        raise ValueError('埋め込み標準が一致しません。対象会話を再計算してください。')
    validate_embedding_compatibility(rows, standard=standard)
    for row in rows:
        if (not isinstance(row['vector'], bytes) or len(row['vector']) != row['dimensions']
                or b'\x80' in row['vector'] or not any(row['vector'])):
            raise ValueError('保存済み発話ベクトルが破損しています。再計算してください。')
    by_id = {row.get('id'): row for row in analysis.get('segments', [])}
    current_hash = transformer_embedding_fingerprint(analysis, model=standard['model_name'],
                                                       revision=standard['model_revision'])
    for row in rows:
        segment = by_id.get(row['segment_id'])
        row['stale'] = (segment is None or bool(segment.get('excluded'))
            or row['text_sha256'] != text_sha256(str(segment.get('text') or ''))
            or row['input_hash'] != current_hash)
    return rows
