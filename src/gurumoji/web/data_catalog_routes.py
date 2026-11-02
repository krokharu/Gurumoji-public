"""Library attribute, tag and analysis-group HTTP adapters."""

from flask import jsonify, request

from ..services import data_catalog as catalog


def register_data_catalog_routes(app, *, database_connection, library_write_lock):
    def catalog_request(action, *, write=False, status=200):
        try:
            if write:
                with library_write_lock, database_connection() as db:
                    db.execute("BEGIN IMMEDIATE")
                    payload = request.get_json(silent=True)
                    if request.method != "DELETE" and not isinstance(payload, dict):
                        raise ValueError("入力形式を確認してください。")
                    result = action(db, payload or {})
            else:
                with database_connection() as db:
                    result = action(db, {})
            return jsonify(result), status
        except LookupError as exc:
            return jsonify(error=str(exc)), 404
        except (ValueError, TypeError) as exc:
            return jsonify(error=str(exc)), 400

    def get_catalog():
        return catalog_request(lambda db, p: catalog.catalog(db))

    def define_attribute():
        return catalog_request(catalog.save_definition, write=True)

    def conversation_attributes(item_id):
        if request.method == "GET":
            def read(db, p):
                catalog.require_items(db, [item_id])
                return {"attributes": catalog.attribute_values(db, item_id)}
            return catalog_request(read)
        def save(db, p):
            catalog.save_attributes(db, item_id, p.get("attributes"))
            return {"attributes": catalog.attribute_values(db, item_id)}
        return catalog_request(save, write=True)

    def create_tag():
        return catalog_request(catalog.save_tag, write=True, status=201)

    def create_group():
        return catalog_request(catalog.save_group, write=True, status=201)

    def change_entity(entity, identity):
        def change(db, p):
            if request.method == "PUT":
                return catalog.save_tag(db, p, identity) if entity == "tags" else catalog.save_group(db, p, identity)
            return catalog.delete_entity(db, entity, identity)
        return catalog_request(change, write=True)

    def assign_entity(entity, identity):
        def save(db, p):
            if not isinstance(p.get("remove", False), bool):
                raise ValueError("付与・解除の指定を確認してください。")
            catalog.assign(db, entity, identity, p.get("item_ids"), p.get("remove", False))
            return {"ok": True}
        return catalog_request(save, write=True)

    def preview_rule():
        def preview(db, p):
            rule = catalog.validate_rule(db, p.get("rule"))
            combine = all if rule["mode"] == "all" else any
            ids = [r[0] for r in db.execute("SELECT id FROM library_items ORDER BY id")
                   if combine(catalog.matches(db, r[0], c) for c in rule["conditions"])]
            return {"item_ids": ids, "item_count": len(ids)}
        # POST is read-only: a preview never creates a group.
        try:
            with database_connection() as db:
                payload = request.get_json(silent=True)
                if not isinstance(payload, dict):
                    raise ValueError("入力形式を確認してください。")
                return jsonify(preview(db, payload))
        except (ValueError, TypeError) as exc:
            return jsonify(error=str(exc)), 400

    app.add_url_rule('/api/library/catalog', 'get_data_catalog', get_catalog)
    app.add_url_rule('/api/library/attribute-definitions', 'define_attribute', define_attribute, methods=['PUT'])
    app.add_url_rule('/api/library/<item_id>/attributes', 'conversation_attributes', conversation_attributes, methods=['GET', 'PUT'])
    app.add_url_rule('/api/library/tags', 'create_conversation_tag', create_tag, methods=['POST'])
    app.add_url_rule('/api/library/data-groups', 'create_data_group', create_group, methods=['POST'])
    app.add_url_rule('/api/library/data-groups/preview', 'preview_data_group', preview_rule, methods=['POST'])
    for entity in ('tags', 'groups'):
        url = 'tags' if entity == 'tags' else 'data-groups'
        app.add_url_rule(f'/api/library/{url}/<identity>', f'change_catalog_{entity}',
                         lambda identity, entity=entity: change_entity(entity, identity), methods=['PUT', 'DELETE'])
        app.add_url_rule(f'/api/library/{url}/<identity>/members', f'assign_catalog_{entity}',
                         lambda identity, entity=entity: assign_entity(entity, identity), methods=['PUT'])
