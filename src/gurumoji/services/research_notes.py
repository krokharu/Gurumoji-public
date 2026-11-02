"""Explicit, hash-guarded imports of researcher-owned Markdown; files are never written."""
from __future__ import annotations

import difflib
import hashlib
import json
import yaml
from pathlib import Path

from ..analysis_core import fingerprint
from ..text_utils import utc_now_iso
from . import change_log

KINDS = {'research-memo', 'interpretation', 'code-proposal', 'research_memo', 'code_proposal'}


class UniqueKeysLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    mapping={}
    for key_node,value_node in node.value:
        key=loader.construct_object(key_node,deep=deep)
        if key in mapping: raise ValueError('研究ノートのfrontmatterに重複キーがあります。')
        mapping[key]=loader.construct_object(value_node,deep=deep)
    return mapping


UniqueKeysLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,unique_mapping)


def initialize(db):
    change_log.initialize(db)
    db.execute('''CREATE TABLE IF NOT EXISTS researcher_note_imports (
        note_id TEXT PRIMARY KEY, item_id TEXT NOT NULL, source_hash TEXT NOT NULL,
        value_json TEXT NOT NULL, version INTEGER NOT NULL, updated_at TEXT NOT NULL)''')


def candidates(store, item_id):
    from ..obsidian_layout import unpack
    root = store.vault.resolve()
    layout = store.layout.load()
    record = layout.get('interviews', {}).get(item_id, {})
    folder = root / record.get('folder', '__not_registered__')
    paths = list(folder.rglob('*.md')) if folder.is_dir() else []
    # Explicit conversation IDs support separately located interpretation/proposal notes.
    paths += list(root.glob('*.md')) if root.is_dir() else []
    seen, result = set(), []
    for path in sorted(set(paths)):
        if any(part in {'.trash', '99-Archive', '履歴'} for part in path.relative_to(root).parts):
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('Vault外を参照する研究ノートは取り込めません。')
        if path.stat().st_size > 2*1024*1024:
            continue
        raw = path.read_bytes()
        text = raw.decode('utf-8-sig')
        if text.startswith('---\n') or text.startswith('---\r\n'):
            parts=text.splitlines()
            end=next((i for i,line in enumerate(parts[1:],1) if line.strip()=='---'),None)
            if end is not None: yaml.load('\n'.join(parts[1:end]),Loader=UniqueKeysLoader)
        props, body = unpack(text)
        if props.get('note_type') not in KINDS or props.get('managed_by') not in (None, 'researcher'):
            continue
        if props.get('conversation_id', item_id if path.is_relative_to(folder) else None) != item_id:
            continue
        note_id = props.get('note_id')
        if not note_id and props['note_type'] in {'research-memo', 'research_memo'} and path.is_relative_to(folder):
            note_id = 'research-memo-' + fingerprint([store.library_id(), item_id])[:24]
        if not isinstance(note_id, str) or not note_id or len(note_id)>160 or note_id in seen:
            raise ValueError('研究ノートのnote_idが欠落または重複しています。')
        seen.add(note_id)
        result.append({'note_id':note_id, 'note_type':props['note_type'], 'title':str(props.get('title') or path.stem),
            'relative_path':str(path.relative_to(root)), 'source_hash':hashlib.sha256(raw).hexdigest(),
            'text':text, 'body':body, 'review_status':'researcher_note' if 'memo' in props['note_type'] else 'pending'})
    return result


def preview(store, item_id):
    result=[]
    with store.connect() as db:
        for candidate in candidates(store, item_id):
            row=db.execute('SELECT * FROM researcher_note_imports WHERE note_id=?',(candidate['note_id'],)).fetchone()
            if row and row['item_id'] != item_id:
                raise ValueError('研究ノートIDが別の会話と競合しています。')
            before=json.loads(row['value_json']) if row else {}
            diff=list(difflib.unified_diff(before.get('text','').splitlines(),candidate['text'].splitlines(),lineterm=''))
            result.append({key:value for key,value in candidate.items() if key not in {'text','body'}} |
                {'base_hash':fingerprint(before),'changed':not row or row['source_hash']!=candidate['source_hash'],
                 'version':row['version'] if row else 0,'diff':diff[:200],'diff_lines':len(diff),'diff_truncated':len(diff)>200})
    return {'notes':result,'mode':'preview','source_ownership':'researcher','ai_started':False}


def apply_import(store, item_id, requests):
    if not isinstance(requests,list) or not requests or len(requests)>100 or any(not isinstance(entry,dict) for entry in requests):
        raise ValueError('取り込む研究ノートを1〜100件指定してください。')
    selected={row['note_id']:row for row in candidates(store,item_id)}
    imported=[]
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        for request in requests:
            candidate=selected.get(request.get('note_id'))
            if not candidate or candidate['source_hash']!=request.get('source_hash'):
                raise ValueError('プレビュー後に研究ノートが更新されています。再確認してください。')
            row=db.execute('SELECT * FROM researcher_note_imports WHERE note_id=?',(candidate['note_id'],)).fetchone()
            if row and row['item_id']!=item_id:
                raise ValueError('研究ノートIDが別の会話と競合しています。')
            before=json.loads(row['value_json']) if row else {}
            if fingerprint(before)!=request.get('base_hash'):
                raise ValueError('取込履歴が更新されています。再確認してください。')
            after={key:value for key,value in candidate.items() if key not in {'relative_path','body'}}
            change_log.capture(db,'researcher_note',candidate['note_id'],before,after,
                origin='researcher',process='explicit_obsidian_import')
            version=(row['version'] if row else 0)+int(before!=after)
            db.execute('''INSERT INTO researcher_note_imports VALUES (?,?,?,?,?,?)
                ON CONFLICT(note_id) DO UPDATE SET source_hash=excluded.source_hash,value_json=excluded.value_json,
                    version=excluded.version,updated_at=excluded.updated_at''',
                (candidate['note_id'],item_id,candidate['source_hash'],json.dumps(after,ensure_ascii=False),version,utc_now_iso()))
            imported.append({'note_id':candidate['note_id'],'version':version,'review_status':candidate['review_status']})
    return {'imported':imported,'ai_started':False,'source_files_changed':False}


def list_imports(store,item_id):
    sources={note['note_id']:note for note in candidates(store,item_id)}
    with store.connect() as db:
        return {'notes':[{'note_id':row['note_id'],'version':row['version'],**json.loads(row['value_json']),
            'source_status':'missing' if row['note_id'] not in sources else
                'current' if sources[row['note_id']]['source_hash']==row['source_hash'] else 'changed'}
            for row in db.execute('SELECT * FROM researcher_note_imports WHERE item_id=? ORDER BY note_id',(item_id,))]}
