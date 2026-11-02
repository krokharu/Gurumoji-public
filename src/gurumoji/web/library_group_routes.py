"""HTTP adapters for library groups; the transactions live in handlers.library_groups."""

from __future__ import annotations

from typing import Any

from flask import Flask, jsonify, request

from ..handlers.library_groups import LibraryGroups
from ..text_utils import clean_single_line, utc_now_iso
from .data_catalog_routes import register_data_catalog_routes


def register_library_group_routes(
    app: Flask,
    *,
    database_connection: Any,
    library_write_lock: Any,
) -> None:
    register_data_catalog_routes(app, database_connection=database_connection, library_write_lock=library_write_lock)
    def create_library_group():
        payload = request.get_json(silent=True)
        try:
            group = library_groups().create(payload.get("name") if isinstance(payload, dict) else None)
        except ValueError as exc:
            status = 409 if str(exc) == "同じ名前のグループがすでにあります。" else 400
            return jsonify({"error": str(exc)}), status
        return jsonify(group), 201

    def update_library_group(group_id: str):
        payload = request.get_json(silent=True)
        try:
            group = library_groups().rename(group_id, payload.get("name") if isinstance(payload, dict) else None)
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            status = 409 if str(exc) == "同じ名前のグループがすでにあります。" else 400
            return jsonify({"error": str(exc)}), status
        return jsonify(group)

    def delete_library_group(group_id: str):
        try:
            return jsonify(library_groups().delete(group_id))
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404

    def assign_library_group(item_id: str):
        payload = request.get_json(silent=True)
        try:
            group = library_groups().assign(
                item_id, payload.get("group_id") if isinstance(payload, dict) else None,
            )
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(group)

    def normalized_library_group_name(value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("グループ名を入力してください。")
        name = clean_single_line(value, 80)
        if not name:
            raise ValueError("グループ名を入力してください。")
        return name

    def library_groups() -> LibraryGroups:
        return LibraryGroups(
            connection=database_connection,
            lock=library_write_lock,
            now=utc_now_iso,
            normalize_name=normalized_library_group_name,
        )

    # Keep established endpoint names: the security hook and the
    # route-map snapshot depend on them.
    endpoints = (
        ('/api/library/groups', 'create_library_group', create_library_group, 'POST'),
        ('/api/library/groups/<group_id>', 'update_library_group', update_library_group, 'PUT'),
        ('/api/library/groups/<group_id>', 'delete_library_group', delete_library_group, 'DELETE'),
        ('/api/library/<item_id>/group', 'assign_library_group', assign_library_group, 'PUT'),
    )
    for rule, endpoint, view, method in endpoints:
        app.add_url_rule(rule, endpoint, view, methods=[method])
