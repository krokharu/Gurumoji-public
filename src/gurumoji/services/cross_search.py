"""Local cross-conversation FTS and exact vector-neighbour index, read-only queries."""
from __future__ import annotations

import json
import sqlite3
import threading

from ..analysis_core import EMBEDDING_STANDARD_V1
from .. import transcript_preparation as preparation
from ..text_utils import json_load
from . import segment_embeddings

_CACHE = {}
_LOCK = threading.RLock()


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS cross_search_documents (
        id INTEGER PRIMARY KEY, item_id TEXT NOT NULL, segment_id TEXT NOT NULL,
        ordinal INTEGER NOT NULL, text TEXT NOT NULL, UNIQUE(item_id,segment_id))''')
    db.execute("INSERT OR IGNORE INTO application_metadata VALUES ('cross_search_epoch','0')")
    fts_existed = db.execute("SELECT 1 FROM sqlite_master WHERE name='cross_search_fts'").fetchone()
    try:
        db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS cross_search_fts USING fts5(text,content='cross_search_documents',content_rowid='id',tokenize='trigram')")
        for suffix, event, body in (
            ('insert','INSERT',"INSERT INTO cross_search_fts(rowid,text) VALUES (NEW.id,NEW.text);"),
            ('delete','DELETE',"INSERT INTO cross_search_fts(cross_search_fts,rowid,text) VALUES ('delete',OLD.id,OLD.text);"),
            ('update','UPDATE',"INSERT INTO cross_search_fts(cross_search_fts,rowid,text) VALUES ('delete',OLD.id,OLD.text); INSERT INTO cross_search_fts(rowid,text) VALUES (NEW.id,NEW.text);"),
        ):
            db.execute(f'CREATE TRIGGER IF NOT EXISTS cross_search_fts_{suffix} AFTER {event} ON cross_search_documents BEGIN {body} END')
        if not fts_existed:
            db.execute("INSERT INTO cross_search_fts(cross_search_fts) VALUES ('rebuild')")
        available='fts5-trigram'
    except sqlite3.OperationalError:
        available='substring-fallback'
    source="CASE WHEN json_valid(NEW.segments_json) THEN CASE WHEN json_type(NEW.segments_json)='array' THEN NEW.segments_json ELSE '[]' END ELSE '[]' END"
    value="CASE WHEN j.type='object' THEN j.value ELSE '{}' END"
    insert=f'''INSERT OR IGNORE INTO cross_search_documents(item_id,segment_id,ordinal,text)
        SELECT NEW.id,json_extract({value},'$.id'),CAST(j.key AS INTEGER),json_extract({value},'$.text')
        FROM json_each({source}) j WHERE json_type({value},'$.id')='text'
        AND json_type({value},'$.text')='text' AND length(json_extract({value},'$.id'))>0;'''
    epoch="UPDATE application_metadata SET value=CAST(value AS INTEGER)+1 WHERE key='cross_search_epoch';"
    db.execute(f'CREATE TRIGGER IF NOT EXISTS cross_search_input_insert AFTER INSERT ON library_items BEGIN {insert} {epoch} END')
    db.execute(f'''CREATE TRIGGER IF NOT EXISTS cross_search_input_update AFTER UPDATE OF segments_json ON library_items
        WHEN NEW.segments_json<>OLD.segments_json BEGIN DELETE FROM cross_search_documents WHERE item_id=OLD.id; {insert} {epoch} END''')
    db.execute(f'CREATE TRIGGER IF NOT EXISTS cross_search_input_delete AFTER DELETE ON library_items BEGIN DELETE FROM cross_search_documents WHERE item_id=OLD.id; {epoch} END')
    for table in ('segment_embeddings','transcript_preparations'):
        for event in ('INSERT','UPDATE','DELETE'):
            db.execute(f'CREATE TRIGGER IF NOT EXISTS cross_search_epoch_{table}_{event.lower()} AFTER {event} ON {table} BEGIN {epoch} END')
    db.execute('DROP TRIGGER IF EXISTS cross_search_annotation_epoch')
    db.execute(f'''CREATE TRIGGER cross_search_annotation_epoch AFTER UPDATE OF
        analysis_config_json,analysis_annotations_json,speaker_profiles_json,speaker_names_json,revision_count,analysis_revision
        ON library_items BEGIN {epoch} END''')
    db.execute('CREATE INDEX IF NOT EXISTS segment_embeddings_coordinates ON segment_embeddings(model_name,model_revision,dimensions,item_id,segment_id)')
    marker=db.execute("SELECT value FROM application_metadata WHERE key='cross_search_index_version'").fetchone()
    if not marker:
        # Reuse the exact trigger body to backfill without changing library rows.
        old=db.execute('SELECT id,segments_json FROM library_items').fetchall()
        for row in old:
            for index,segment in enumerate(json_load(row['segments_json'],[])):
                if isinstance(segment,dict) and isinstance(segment.get('id'),str) and segment['id'] and isinstance(segment.get('text'),str):
                    db.execute('INSERT OR IGNORE INTO cross_search_documents(item_id,segment_id,ordinal,text) VALUES (?,?,?,?)',
                        (row['id'],segment['id'],index,segment['text']))
        db.execute("INSERT INTO application_metadata VALUES ('cross_search_index_version','1')")
    db.execute("INSERT INTO application_metadata VALUES ('cross_search_engine',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(available,))


def live_input(db,row,*,row_segments,row_profiles,row_session):
    from .group_analysis import _analysis_timeline,row_analysis_config,row_analysis_annotation_state
    segments=row_segments(row)
    names=json_load(row['speaker_names_json'],{})
    config=row_analysis_config(row)
    annotations,_=row_analysis_annotation_state(row,segments,config)
    timeline,*_= _analysis_timeline(segments,prepared=preparation.view(db,row,segments),
        original_segments={},original_segments_status='unavailable',annotations=annotations,
        profiles=row_profiles(row,segments,names),speaker_names=names,session_profile=row_session(row),
        excluded_speakers=set(config['excluded_speakers']))
    return {'item':{'id':row['id'],'revision_count':row['revision_count'],'analysis_revision':row['analysis_revision']},'segments':timeline}


def text_search(db,query,builder,*,limit=50,offset=0):
    if not isinstance(query,str) or not 1<=len(query.strip())<=500 or not 1<=limit<=100 or not 0<=offset<=1000000:
        raise ValueError('検索語・ページ指定を確認してください。')
    query=query.strip()
    engine=db.execute("SELECT value FROM application_metadata WHERE key='cross_search_engine'").fetchone()[0]
    if engine=='fts5-trigram' and len(query)>=3:
        candidates=db.execute('''SELECT d.* FROM cross_search_fts f JOIN cross_search_documents d ON d.id=f.rowid
            WHERE cross_search_fts MATCH ? ORDER BY bm25(cross_search_fts),d.item_id,d.ordinal LIMIT 10001''',
            ('"'+query.replace('"','""')+'"',)).fetchall()
    else:
        candidates=db.execute('SELECT * FROM cross_search_documents WHERE instr(lower(text),lower(?))>0 ORDER BY item_id,ordinal LIMIT 10001',(query,)).fetchall()
        engine='substring-fallback'
    inputs={}; matches=[]
    for candidate in candidates[:10000]:
        item_id=candidate['item_id']
        if item_id not in inputs:
            source=db.execute('SELECT * FROM library_items WHERE id=?',(item_id,)).fetchone()
            inputs[item_id]=builder(db,source) if source else None
        analysis=inputs[item_id]
        segment=next((s for s in analysis['segments'] if s['id']==candidate['segment_id']),None) if analysis else None
        if segment and not segment.get('excluded') and query.casefold() in segment['text'].casefold():
            matches.append({'item_id':item_id,'segment_id':segment['id'],'text':segment['text'],
                'speaker':segment.get('speaker_name'),'start':segment.get('start'),
                'source_revision':analysis['item']['revision_count'],'analysis_revision':analysis['item']['analysis_revision']})
    return {'engine':engine,'query':query,'matches':matches[offset:offset+limit],
        'pagination':{'offset':offset,'limit':limit,'total':len(matches),'has_more':offset+limit<len(matches)},
        'scan_truncated':len(candidates)>10000,'source_policy':'current_included_segments','ai_started':False}


def similar_search(db,item_id,segment_id,builder,*,limit=20):
    import numpy as np
    from sklearn.neighbors import NearestNeighbors
    if not 1<=limit<=100: raise ValueError('検索件数は1〜100で指定してください。')
    identity=db.execute("SELECT value FROM application_metadata WHERE key='library_id'").fetchone()[0]
    epoch=db.execute("SELECT value FROM application_metadata WHERE key='cross_search_epoch'").fetchone()[0]
    database = db.execute('PRAGMA database_list').fetchone()[2]
    key=(database or db,identity,epoch)
    with _LOCK:
        entry=_CACHE.get(key)
        if entry is None:
            vectors=[]; entries=[]
            sources=db.execute('SELECT * FROM library_items WHERE id IN (SELECT DISTINCT item_id FROM segment_embeddings) ORDER BY id').fetchall()
            for source in sources:
                analysis=builder(db,source)
                segments={s['id']:s for s in analysis['segments']}
                for row in segment_embeddings.read_current(db,analysis):
                    if row['stale']: continue
                    segment=segments[row['segment_id']]
                    vectors.append(np.frombuffer(row['vector'],dtype=np.int8).astype(np.float32))
                    entries.append({'item_id':source['id'],'segment_id':row['segment_id'],'text':segment['text'],
                        'speaker':segment.get('speaker_name'),'start':segment.get('start'),'input_hash':row['input_hash'],
                        'source_revision':source['revision_count'],'analysis_revision':source['analysis_revision']})
                    if len(vectors)>20000: raise ValueError('ベクトル索引は20000発話が上限です。対象集合を絞る必要があります。')
            if not vectors: raise ValueError('現在版の標準ベクトルがありません。Transformer分析を実行してください。')
            matrix=np.vstack(vectors)
            index=NearestNeighbors(metric='cosine',algorithm='brute',n_jobs=1).fit(matrix)
            entry=(matrix,index,entries)
            _CACHE.clear(); _CACHE[key]=entry
        matrix,index,entries=entry
        target=next((i for i,e in enumerate(entries) if e['item_id']==item_id and e['segment_id']==segment_id),None)
        if target is None: raise ValueError('基準発話の標準ベクトルが欠落または古くなっています。再計算してください。')
        distances,indices=index.kneighbors(matrix[target:target+1],n_neighbors=len(entries))
        matches=[{**entries[int(i)],'similarity':float(1-distance)} for distance,i in zip(distances[0],indices[0]) if entries[int(i)]['item_id']!=item_id]
        matches.sort(key=lambda row:(-row['similarity'],row['item_id'],row['segment_id']))
    return {'engine':'exact-cosine-neighbour-index','reference':{'item_id':item_id,'segment_id':segment_id},
        'embedding_standard':EMBEDDING_STANDARD_V1,'indexed_rows':len(entries),'matches':matches[:limit],
        'limitations':'意味の近さは合意・因果・重要性を示しません。','ai_started':False}
