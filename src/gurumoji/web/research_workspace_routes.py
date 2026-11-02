"""Explicit researcher imports, recoverable Vault actions, and local search."""
from functools import wraps
import yaml

from flask import Blueprint, jsonify, request

from ..services import research_notes, vault_operations, cross_search, external_analysis


def register_research_workspace_routes(app, *, store, connect, find_item, write_lock,
        backup, local_allowed, row_segments, row_profiles, row_session):
    routes = Blueprint('research_workspace', __name__)

    def guarded(function):
        @wraps(function)
        def call(*args, **kwargs):
            try:
                item_id = kwargs.get('item_id')
                if item_id and find_item(item_id) is None:
                    return jsonify(error='対象の会話が見つかりません。'), 404
                return jsonify(function(*args, **kwargs))
            except (ValueError, TypeError, KeyError, LookupError, yaml.YAMLError):
                return jsonify(error='入力・参照先が無効、またはプレビュー後に更新されています。再確認してください。'), 409
            except (OSError, UnicodeError):
                return jsonify(error='ファイルを読み取れません。元データを維持して停止しました。'), 409
        return call

    def local():
        if not local_allowed():
            raise ValueError('Vault操作はローカル接続から実行してください。')

    def body():
        value=request.get_json()
        if not isinstance(value,dict): raise ValueError('JSONオブジェクトを指定してください。')
        return value

    @routes.get('/api/library/<item_id>/research-notes')
    @guarded
    def notes(item_id):
        local()
        return research_notes.list_imports(store(), item_id)

    @routes.post('/api/library/<item_id>/research-notes/preview')
    @guarded
    def notes_preview(item_id):
        local()
        return research_notes.preview(store(), item_id)

    @routes.post('/api/library/<item_id>/research-notes/import')
    @guarded
    def notes_import(item_id):
        local()
        with write_lock:
            return research_notes.apply_import(store(), item_id, body().get('notes'))

    @routes.post('/api/library/<item_id>/analysis/external')
    @guarded
    def external(item_id):
        with write_lock:
            saved = external_analysis.register(store(), item_id, body(), app_url=request.host_url.rstrip('/'))
        return {'run':store().public(saved, local=local_allowed()),'review_status':'pending','ai_started':False}

    @routes.get('/api/vaults/roots')
    @guarded
    def roots():
        local()
        catalog = store().vaults.load()
        return {'roots':{kind:catalog['vaults'][kind]['root'].split('/')[-1] for kind in ('input','visualization','orchestrator')}}

    @routes.post('/api/vaults/roots/preview')
    @guarded
    def roots_preview():
        local()
        return vault_operations.root_plan(store().vaults, body().get('roots'))

    @routes.post('/api/vaults/roots/apply')
    @guarded
    def roots_apply():
        local()
        with write_lock:
            return vault_operations.change_roots(store().vaults, body(), backup)

    @routes.post('/api/vaults/roots/rollback')
    @guarded
    def roots_rollback():
        local()
        with write_lock:
            return vault_operations.rollback_roots(store().vaults)

    @routes.post('/api/vaults/publication/preview')
    @guarded
    def publication_preview():
        local()
        return vault_operations.publication_plan(store())

    @routes.post('/api/vaults/publication/apply')
    @guarded
    def publication_apply():
        local()
        with write_lock:
            return vault_operations.publish_legacy(store(), body(), backup)

    def builder(db, row):
        return cross_search.live_input(db,row,row_segments=row_segments,row_profiles=row_profiles,row_session=row_session)

    @routes.get('/api/library/search/segments')
    @guarded
    def search():
        with connect() as db:
            return cross_search.text_search(db,request.args.get('q',''),builder,
                limit=int(request.args.get('limit',50)),offset=int(request.args.get('offset',0)))

    @routes.get('/api/library/search/similar')
    @guarded
    def similar():
        with connect() as db:
            return cross_search.similar_search(db,request.args.get('item_id',''),request.args.get('segment_id',''),builder,
                limit=int(request.args.get('limit',20)))

    app.register_blueprint(routes)
