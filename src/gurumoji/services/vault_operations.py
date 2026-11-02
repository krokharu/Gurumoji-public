"""Recoverable, copy-first Vault root changes and explicit legacy publication."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import shutil

from ..analysis_core import fingerprint
from .durable_files import write_durably


def inventory(root):
    root=Path(root)
    if root.is_symlink() or getattr(root,'is_junction',lambda:False)():
        raise ValueError('リンク・junctionをVaultの保存先にはできません。')
    entries={}
    if root.exists():
        for path in sorted(root.rglob('*')):
            if path.is_symlink() or getattr(path,'is_junction',lambda:False)() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError('Vault外へのリンクがあるため保存先を変更できません。')
            if path.is_file():
                entries[path.relative_to(root).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    return entries


def safe_root(registry, root):
    root = Path(root)
    boundary = registry.data.resolve()
    if not root.resolve().is_relative_to(boundary):
        raise ValueError('Vaultの保存先がデータ領域外を参照しています。')
    for path in (root, *root.parents):
        if path == registry.data.parent: break
        if path.is_symlink() or getattr(path,'is_junction',lambda:False)():
            raise ValueError('保存先または親フォルダーにリンクがあります。')
    inventory(root)


def root_plan(registry, roots):
    if not isinstance(roots,dict) or not roots or any(kind not in {'input','visualization','orchestrator'} for kind in roots):
        raise ValueError('Input・Visualization・Orchestratorの保存先名を指定してください。')
    data=registry.load()
    changed=copy.deepcopy(data)
    entries=[]
    for kind,folder in roots.items():
        if not isinstance(folder,str) or not re.fullmatch('[A-Za-z0-9_-]{1,60}',folder) or folder=='ResearchVault':
            raise ValueError('保存先名は英数字・ハイフン・下線の独立フォルダーにしてください。')
        changed['vaults'][kind]['root']='obsidian/'+folder
        source,target=registry.root(kind,data),registry.root(kind,changed)
        safe_root(registry, source)
        safe_root(registry, target)
        if source.resolve()==target.resolve(): continue
        if target.exists() and any(target.iterdir()):
            raise ValueError('保存先にファイルがあります。空の独立フォルダーを選んでください。')
        entries.append({'kind':kind,'from':data['vaults'][kind]['root'],'to':changed['vaults'][kind]['root'],
            'files':inventory(source)})
    all_roots=[registry.root(kind,changed).resolve() for kind in ('input','visualization','orchestrator')]
    if len(set(all_roots))!=3: raise ValueError('Vaultの保存先が重複しています。')
    plan={'schema_version':1,'catalog_hash':fingerprint(data),'roots':roots,'entries':entries,'source_retained':True}
    return {**plan,'plan_hash':fingerprint(plan),'file_count':sum(len(e['files']) for e in entries)}


def change_roots(registry, plan, backup):
    from ..vault_registry import VAULT_LOCK
    from ..analysis_store import STORE_LOCK
    from ..obsidian_layout import LAYOUT_LOCK
    with STORE_LOCK,LAYOUT_LOCK,VAULT_LOCK:
        current=root_plan(registry,plan.get('roots'))
        if current['plan_hash']!=plan.get('plan_hash'):
            raise ValueError('プレビュー後にVaultが更新されています。再確認してください。')
        backup_result=backup()
        before=registry.load(); after=copy.deepcopy(before)
        marker=registry.catalog_file.parent/'vault-root-change.json'
        state={'status':'copying','plan':current,'previous_catalog':before,'backup':backup_result}
        for entry in current['entries']:
            after['vaults'][entry['kind']]['root']=entry['to']
        state['next_catalog']=after
        write_durably(marker,json.dumps(state,ensure_ascii=False,indent=2).encode())
        for entry in current['entries']:
            source=registry.data/entry['from']; target=registry.data/entry['to']
            safe_root(registry, source)
            safe_root(registry, target)
            target.mkdir(parents=True,exist_ok=True)
            for relative,digest in entry['files'].items():
                origin,destination=source/relative,target/relative
                if hashlib.sha256(origin.read_bytes()).hexdigest()!=digest:
                    raise ValueError('移行中に元のVaultが更新されました。元の保存先を維持します。')
                destination.parent.mkdir(parents=True,exist_ok=True)
                if destination.exists(): raise ValueError('コピー先に別のファイルが現れました。停止します。')
                shutil.copy2(origin,destination)
            if inventory(target)!=entry['files'] or inventory(source)!=entry['files']:
                raise ValueError('移行前後のhashが一致しません。元の保存先を維持します。')
        if fingerprint(registry.load())!=current['catalog_hash']:
            raise ValueError('移行中にVault台帳が更新されました。元の保存先を維持します。')
        registry.save(after)
        state['status']='completed'
        write_durably(marker,json.dumps(state,ensure_ascii=False,indent=2).encode())
        return {'status':'completed','file_count':current['file_count'],'source_retained':True,'backup':backup_result}


def rollback_roots(registry):
    from ..vault_registry import VAULT_LOCK
    marker=registry.catalog_file.parent/'vault-root-change.json'
    with VAULT_LOCK:
        state=json.loads(marker.read_text(encoding='utf-8'))
        if state.get('status') not in {'completed', 'copying'}:
            return {'status':'unchanged','source_retained':True}
        for entry in state['plan']['entries']:
            if inventory(registry.data/entry['from'])!=entry['files']:
                raise ValueError('元のVaultが変わっています。自動で戻せません。')
        current=registry.load()
        active = [current['vaults'][entry['kind']]['root'] for entry in state['plan']['entries']]
        if active == [entry['from'] for entry in state['plan']['entries']]:
            state['status']='rolled_back'
            write_durably(marker,json.dumps(state,ensure_ascii=False,indent=2).encode())
            return {'status':'rolled_back','copied_files_retained':True}
        for entry in state['plan']['entries']:
            if current['vaults'][entry['kind']]['root']!=entry['to'] or inventory(registry.data/entry['to'])!=entry['files']:
                raise ValueError('切替後に更新されています。自動で戻せません。')
        # Preserve other Vaults' newly registered notes and unrelated metadata.
        restored=copy.deepcopy(current)
        for entry in state['plan']['entries']:
            restored['vaults'][entry['kind']]['root']=entry['from']
        registry.save(restored)
        state['status']='rolled_back'
        write_durably(marker,json.dumps(state,ensure_ascii=False,indent=2).encode())
        return {'status':'rolled_back','copied_files_retained':True}


def publication_plan(store):
    with store.connect() as db:
        rows=[dict(row) for row in db.execute("SELECT id,item_id,fingerprint FROM analysis_runs WHERE status='completed' ORDER BY id")]
    return {'runs':rows,'plan_hash':fingerprint(rows),'researcher_notes_retained':True,'ai_started':False}


def publish_legacy(store,plan,backup):
    current=publication_plan(store)
    if current['plan_hash']!=plan.get('plan_hash'):
        raise ValueError('保存結果が更新されています。計画を再確認してください。')
    for row in current['runs']:
        store.verified_package(row['id'])
    backup_result=backup()
    outcomes=[]
    for row in current['runs']:
        outcomes.append({'run_id':row['id'],'outputs':store.publish_vaults(row['id'])})
    return {'outcomes':outcomes,'backup':backup_result,'researcher_notes_retained':True,'ai_started':False}
