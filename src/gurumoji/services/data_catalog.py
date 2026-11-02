"""Attribute definitions, conversation tags and versioned analysis groups."""

from __future__ import annotations

import json
import math
import sqlite3
import unicodedata
import uuid
from typing import Any

from ..analysis_store import canonical, digest
from ..text_utils import utc_now_iso
from . import change_log


def initialize(db: sqlite3.Connection) -> None:
    change_log.initialize(db)
    for sql in (
        """CREATE TABLE IF NOT EXISTS attribute_definitions (
            key TEXT NOT NULL, scope TEXT NOT NULL, data_type TEXT NOT NULL,
            measurement_level TEXT NOT NULL, allowed_values_json TEXT NOT NULL DEFAULT '[]',
            description TEXT NOT NULL DEFAULT '', origin TEXT NOT NULL, version INTEGER NOT NULL,
            PRIMARY KEY(key, scope))""",
        """CREATE TABLE IF NOT EXISTS conversation_attributes (
            item_id TEXT NOT NULL, key TEXT NOT NULL, value_json TEXT NOT NULL,
            source TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(item_id,key))""",
        """CREATE TABLE IF NOT EXISTS speaker_attributes (
            speaker_id TEXT NOT NULL, key TEXT NOT NULL, value_json TEXT NOT NULL,
            PRIMARY KEY(speaker_id,key))""",
        """CREATE TABLE IF NOT EXISTS data_groups (
            group_id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
            kind TEXT NOT NULL, rule_json TEXT NOT NULL DEFAULT '{}', version INTEGER NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS data_group_members (
            group_id TEXT NOT NULL, item_id TEXT NOT NULL, added_at TEXT NOT NULL,
            PRIMARY KEY(group_id,item_id))""",
        """CREATE TABLE IF NOT EXISTS tags (
            tag_id TEXT PRIMARY KEY, name TEXT NOT NULL, normalized_name TEXT NOT NULL UNIQUE,
            color TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS conversation_tags (
            item_id TEXT NOT NULL, tag_id TEXT NOT NULL, added_at TEXT NOT NULL,
            PRIMARY KEY(item_id,tag_id))""",
    ):
        db.execute(sql)
    source = "CASE WHEN json_valid(attributes_json) THEN CASE WHEN json_type(attributes_json)='object' THEN attributes_json ELSE '{}' END ELSE '{}' END"
    select = f"""SELECT s.id,j.key, CASE j.type WHEN 'text' THEN json_quote(j.value)
        WHEN 'null' THEN 'null' WHEN 'true' THEN 'true' WHEN 'false' THEN 'false'
        ELSE CAST(j.value AS TEXT) END FROM speaker_registry s,json_each({source}) j"""
    discover = """INSERT OR IGNORE INTO attribute_definitions
        (key,scope,data_type,measurement_level,origin,version)
        SELECT DISTINCT key,'speaker','string','nominal','discovered',1 FROM speaker_attributes a
        WHERE NOT EXISTS (SELECT 1 FROM attribute_definitions d WHERE d.key=a.key AND d.scope='speaker')"""
    for event, clause in (("insert", "INSERT"), ("update", "UPDATE OF attributes_json,id")):
        old = "DELETE FROM speaker_attributes WHERE speaker_id=OLD.id;" if event == "update" else ""
        db.execute(f"""CREATE TRIGGER IF NOT EXISTS speaker_attributes_{event}_v1
            AFTER {clause} ON speaker_registry BEGIN {old}
            DELETE FROM speaker_attributes WHERE speaker_id=NEW.id;
            INSERT INTO speaker_attributes {select} WHERE s.id=NEW.id;
            {discover}; END""")
    db.execute("""CREATE TRIGGER IF NOT EXISTS speaker_attributes_delete_v1 AFTER DELETE ON speaker_registry
        BEGIN DELETE FROM speaker_attributes WHERE speaker_id=OLD.id; END""")
    if not db.execute("SELECT 1 FROM application_metadata WHERE key='data_catalog_version'").fetchone():
        db.execute(f"INSERT OR REPLACE INTO speaker_attributes {select}")
        db.execute(discover)
        db.execute("INSERT INTO application_metadata(key,value) VALUES ('data_catalog_version','1')")
    for table in ("conversation_attributes", "conversation_tags", "data_group_members"):
        db.execute(f"CREATE INDEX IF NOT EXISTS {table}_item_idx ON {table}(item_id)")
        for event in ("INSERT", "UPDATE", "DELETE"):
            refs = ["OLD.item_id", "NEW.item_id"] if event == "UPDATE" else ["OLD.item_id" if event == "DELETE" else "NEW.item_id"]
            db.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_stale_{event.lower()}_v1
                AFTER {event} ON {table} BEGIN UPDATE analysis_runs SET stale=1
                WHERE id IN (SELECT run_id FROM analysis_run_members WHERE item_id IN ({','.join(refs)}))
                OR id IN (SELECT r.run_id FROM analysis_run_groups r JOIN data_groups g ON g.group_id=r.group_id WHERE g.kind='rule'); END""")
        db.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_delete_v1 AFTER DELETE ON library_items
            BEGIN DELETE FROM {table} WHERE item_id=OLD.id; END""")
    for table, column, child in (("tags", "tag_id", "conversation_tags"), ("data_groups", "group_id", "data_group_members")):
        db.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_delete_v1 AFTER DELETE ON {table}
            BEGIN DELETE FROM {child} WHERE {column}=OLD.{column}; END""")
        db.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_stale_update_v1 AFTER UPDATE ON {table}
            BEGIN UPDATE analysis_runs SET stale=1 WHERE id IN (SELECT run_id FROM analysis_run_members
            WHERE item_id IN (SELECT item_id FROM {child} WHERE {column}=OLD.{column})); END""")
    for event in ('UPDATE', 'DELETE'):
        db.execute(f"""CREATE TRIGGER IF NOT EXISTS data_groups_runs_{event.lower()}_v1 AFTER {event} ON data_groups
            BEGIN UPDATE analysis_runs SET stale=1 WHERE id IN (SELECT run_id FROM analysis_run_groups WHERE group_id=OLD.group_id); END""")
    for event in ('INSERT', 'UPDATE', 'DELETE'):
        refs = ['OLD.group_id', 'NEW.group_id'] if event == 'UPDATE' else ['OLD.group_id' if event == 'DELETE' else 'NEW.group_id']
        db.execute(f"""CREATE TRIGGER IF NOT EXISTS data_group_members_version_{event.lower()}_v1 AFTER {event} ON data_group_members
            BEGIN UPDATE data_groups SET version=version+1,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE group_id IN ({','.join(refs)}); END""")
    for event in ("INSERT", "UPDATE"):
        db.execute(f"""CREATE TRIGGER IF NOT EXISTS conversation_attributes_defined_{event.lower()}_v1
            BEFORE {event} ON conversation_attributes WHEN NOT EXISTS
            (SELECT 1 FROM attribute_definitions WHERE key=NEW.key AND scope='conversation')
            BEGIN SELECT RAISE(ABORT,'undefined conversation attribute'); END""")
    db.execute("""CREATE TRIGGER IF NOT EXISTS attribute_definitions_stale_v1 AFTER UPDATE ON attribute_definitions
        BEGIN UPDATE analysis_runs SET stale=1 WHERE id IN (SELECT run_id FROM analysis_run_members); END""")
    for table, update in (('library_items', 'UPDATE OF segments_json,speaker_profiles_json'),
                          ('speaker_registry', 'UPDATE OF attributes_json')):
        for event, clause in (('insert', 'INSERT'), ('update', update), ('delete', 'DELETE')):
            db.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_rule_groups_{event}_v1 AFTER {clause} ON {table}
                BEGIN UPDATE analysis_runs SET stale=1 WHERE id IN
                (SELECT r.run_id FROM analysis_run_groups r JOIN data_groups g ON g.group_id=r.group_id WHERE g.kind='rule'); END""")


def name(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 120 or any(ord(c) < 32 for c in value):
        raise ValueError("名前は1〜120文字で入力してください。")
    return value.strip()


def definitions(db) -> list[dict]:
    return [{**dict(r), "allowed_values": json.loads(r["allowed_values_json"]),
             "type_status": "型未確定" if r["origin"] == "discovered" else "確定"}
            for r in db.execute("SELECT * FROM attribute_definitions ORDER BY scope,key")]


def valid_value(definition: dict, value: Any) -> bool:
    if value is None:
        return True
    kind = definition["data_type"]
    valid = {"string": isinstance(value, str), "number": type(value) in (int, float) and math.isfinite(value),
             "integer": type(value) is int, "boolean": type(value) is bool}.get(kind, False)
    allowed = json.loads(definition["allowed_values_json"])
    return valid and (not allowed or any(type(value) is type(v) and value == v for v in allowed))


def save_definition(db, payload: dict) -> dict:
    key, scope = name(payload.get("key")), payload.get("scope")
    kind, level = payload.get("data_type", "string"), payload.get("measurement_level", "nominal")
    if scope not in {"conversation", "speaker", "segment"} or kind not in {"string", "number", "integer", "boolean"} or level not in {"nominal", "ordinal", "interval", "ratio"}:
        raise ValueError("属性の対象・型・尺度を確認してください。")
    allowed = payload.get("allowed_values", [])
    if not isinstance(allowed, list) or len(allowed) > 1000:
        raise ValueError("許される値は配列で指定してください。")
    definition = {"data_type": kind, "allowed_values_json": "[]"}
    if any(v is None or not valid_value(definition, v) for v in allowed):
        raise ValueError("許される値の型が一致しません。")
    old = db.execute("SELECT * FROM attribute_definitions WHERE key=? AND scope=?", (key, scope)).fetchone()
    if old and payload.get("version") != old["version"]:
        raise ValueError("属性定義が更新されています。読み直してください。")
    with change_log.tracking(db, [("attribute_definitions", "global")], process="attribute_definition_save"):
        db.execute("""INSERT INTO attribute_definitions VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(key,scope) DO UPDATE SET data_type=excluded.data_type,
            measurement_level=excluded.measurement_level,allowed_values_json=excluded.allowed_values_json,
            description=excluded.description,origin=excluded.origin,version=excluded.version""",
            (key, scope, kind, level, canonical(allowed).decode(), str(payload.get("description", "")), "researcher", old["version"] + 1 if old else 1))
    return next(d for d in definitions(db) if d["key"] == key and d["scope"] == scope)


def require_items(db, item_ids) -> list[str]:
    if not isinstance(item_ids, list) or not 1 <= len(item_ids) <= 10000 or any(not isinstance(i, str) for i in item_ids):
        raise ValueError("対象の会話を選択してください。")
    ids = sorted(set(item_ids))
    for identity in ids:
        if not db.execute("SELECT 1 FROM library_items WHERE id=?", (identity,)).fetchone():
            raise LookupError("対象の会話が見つかりません。")
    return ids


def save_attributes(db, item_id: str, values: dict) -> None:
    require_items(db, [item_id])
    if not isinstance(values, dict):
        raise ValueError("属性はキーと値で指定してください。")
    for key, value in values.items():
        definition = db.execute("SELECT * FROM attribute_definitions WHERE key=? AND scope='conversation'", (key,)).fetchone()
        if not definition:
            raise ValueError(f"属性「{key}」の定義を先に作成してください。")
        if not valid_value(dict(definition), value):
            raise ValueError(f"属性「{key}」の型または許される値が一致しません。")
    with change_log.tracking(db, [("conversation_attributes", item_id)], process="conversation_attributes_save"):
        db.execute("DELETE FROM conversation_attributes WHERE item_id=?", (item_id,))
        db.executemany("INSERT INTO conversation_attributes VALUES (?,?,?,?,?)",
                       [(item_id, key, canonical(value).decode(), "researcher", utc_now_iso()) for key, value in values.items()])


def attribute_values(db, item_id: str) -> dict:
    return {r[0]: json.loads(r[1]) for r in db.execute("SELECT key,value_json FROM conversation_attributes WHERE item_id=? ORDER BY key", (item_id,))}


def save_tag(db, payload, tag_id=None) -> dict:
    label, now = name(payload.get("name")), utc_now_iso()
    identity = tag_id or uuid.uuid4().hex
    if tag_id and not db.execute("SELECT 1 FROM tags WHERE tag_id=?", (tag_id,)).fetchone():
        raise LookupError("タグが見つかりません。")
    normalized = unicodedata.normalize("NFKC", label).strip().casefold()
    try:
        with change_log.tracking(db, [("tags", identity)], process="tag_save"):
            db.execute("""INSERT INTO tags VALUES (?,?,?,?,?,?,?) ON CONFLICT(tag_id) DO UPDATE SET
                name=excluded.name,normalized_name=excluded.normalized_name,color=excluded.color,
                description=excluded.description,updated_at=excluded.updated_at""",
                (identity, label, normalized, str(payload.get("color", "")), str(payload.get("description", "")), now, now))
    except sqlite3.IntegrityError as exc:
        raise ValueError("同じ名前のタグがすでにあります。") from exc
    return dict(db.execute("SELECT * FROM tags WHERE tag_id=?", (identity,)).fetchone())


def validate_rule(db, rule) -> dict:
    if not isinstance(rule, dict) or rule.get("mode", "all") not in {"all", "any"} or not isinstance(rule.get("conditions"), list) or not 1 <= len(rule["conditions"]) <= 30:
        raise ValueError("条件を1〜30件指定してください。")
    result = {"mode": rule.get("mode", "all"), "conditions": []}
    from .conversation_projection import SPEAKER_FIELDS, SEGMENT_FIELDS
    for condition in rule["conditions"]:
        if not isinstance(condition, dict):
            raise ValueError("条件の形式を確認してください。")
        scope, key, op = condition.get("scope"), condition.get("key"), condition.get("op", "eq")
        if not isinstance(scope, str) or not isinstance(key, str) or not isinstance(op, str) or scope not in {"conversation", "speaker", "segment", "tag"} or op not in {"eq", "ne", "in", "exists", "gte", "lte"}:
            raise ValueError("条件の対象・比較方法を確認してください。")
        if scope == "tag":
            if not db.execute("SELECT 1 FROM tags WHERE tag_id=?", (key,)).fetchone() or op != "exists":
                raise ValueError("条件のタグを選択してください。")
        elif not (scope == "speaker" and key in SPEAKER_FIELDS or scope == "segment" and key in SEGMENT_FIELDS):
            if not db.execute("SELECT 1 FROM attribute_definitions WHERE key=? AND scope=?", (key, scope)).fetchone():
                raise ValueError("条件の属性が未定義です。")
            if scope == "segment":
                raise ValueError("発話の自由属性はまだ保存先がありません。")
        value = condition.get("value")
        if op == "in" and not isinstance(value, list) or op in {"gte", "lte"} and (type(value) not in (int, float) or not math.isfinite(value)):
            raise ValueError("条件の値を確認してください。")
        result["conditions"].append({"scope": scope, "key": key, "op": op, "value": value})
    canonical(result)
    return result


def save_group(db, payload, group_id=None) -> dict:
    label, kind, now = name(payload.get("name")), payload.get("kind", "manual"), utc_now_iso()
    if kind not in {"manual", "rule"}:
        raise ValueError("グループの種類を確認してください。")
    rule = validate_rule(db, payload.get("rule")) if kind == "rule" else {}
    old = db.execute("SELECT * FROM data_groups WHERE group_id=?", (group_id,)).fetchone() if group_id else None
    if group_id and not old:
        raise LookupError("グループが見つかりません。")
    if old and payload.get("version") != old["version"]:
        raise ValueError("グループが更新されています。読み直してください。")
    if old and old["kind"] != kind:
        raise ValueError("グループの種類は変更できません。")
    identity = group_id or uuid.uuid4().hex
    with change_log.tracking(db, [("data_groups", identity)], process="group_save"):
        db.execute("""INSERT INTO data_groups VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(group_id) DO UPDATE SET
            name=excluded.name,description=excluded.description,rule_json=excluded.rule_json,
            version=excluded.version,updated_at=excluded.updated_at""",
            (identity, label, str(payload.get("description", "")), kind, canonical(rule).decode(), old["version"] + 1 if old else 1, now, now))
    return group_public(db, db.execute("SELECT * FROM data_groups WHERE group_id=?", (identity,)).fetchone())


def assign(db, entity: str, identity: str, item_ids, remove=False) -> None:
    ids = require_items(db, item_ids)
    table, key, parent = ("conversation_tags", "tag_id", "tags") if entity == "tags" else ("data_group_members", "group_id", "data_groups")
    row = db.execute(f"SELECT * FROM {parent} WHERE {key}=?", (identity,)).fetchone()
    if not row:
        raise LookupError("タグまたはグループが見つかりません。")
    if entity == "groups" and row["kind"] != "manual":
        raise ValueError("条件グループの所属は条件から決まります。")
    targets = [("conversation_tags" if entity == "tags" else "data_group_members", i) for i in ids]
    if entity != "tags":
        targets.append(("data_groups", identity))
    with change_log.tracking(db, targets, process="catalog_unassign" if remove else "catalog_assign"):
        for item_id in ids:
            if remove:
                db.execute(f"DELETE FROM {table} WHERE item_id=? AND {key}=?", (item_id, identity))
            else:
                db.execute(f"INSERT OR IGNORE INTO {table}(item_id,{key},added_at) VALUES (?,?,?)", (item_id, identity, utc_now_iso()))


def delete_entity(db, entity: str, identity: str) -> dict:
    table, key, child, history_entity = (
        ("tags", "tag_id", "conversation_tags", "conversation_tags") if entity == "tags"
        else ("data_groups", "group_id", "data_group_members", "data_group_members")
    )
    if not db.execute(f"SELECT 1 FROM {table} WHERE {key}=?", (identity,)).fetchone():
        raise LookupError("タグまたはグループが見つかりません。")
    ids = [r[0] for r in db.execute(f"SELECT item_id FROM {child} WHERE {key}=?", (identity,))]
    count = len(ids) if entity == "tags" else len(members(db, identity))
    targets = [(table, identity), *((history_entity, i) for i in ids)]
    with change_log.tracking(db, targets, process="catalog_delete"):
        db.execute(f"DELETE FROM {table} WHERE {key}=?", (identity,))
    return {"ok": True, "unassigned_count": count}


def condition_values(db, item_id, condition) -> list:
    scope, key = condition["scope"], condition["key"]
    if scope == "conversation":
        row = db.execute("SELECT value_json FROM conversation_attributes WHERE item_id=? AND key=?", (item_id, key)).fetchone()
        return [json.loads(row[0])] if row else []
    if scope == "tag":
        return [True] if db.execute("SELECT 1 FROM conversation_tags WHERE item_id=? AND tag_id=?", (item_id, key)).fetchone() else []
    from .conversation_projection import SPEAKER_FIELDS, SEGMENT_FIELDS
    if scope == "speaker" and key not in SPEAKER_FIELDS:
        return [json.loads(r[0]) for r in db.execute("""SELECT a.value_json FROM speaker_attributes a
            JOIN conversation_speakers s ON s.global_speaker_id=a.speaker_id WHERE s.item_id=? AND a.key=?""", (item_id, key))]
    fields, table = (SPEAKER_FIELDS, "conversation_speakers") if scope == "speaker" else (SEGMENT_FIELDS, "conversation_segments")
    if key not in fields:
        raise ValueError("条件の列が未定義です。")
    return [r[0] for r in db.execute(f'SELECT "{key}" FROM {table} WHERE item_id=?', (item_id,))]


def matches(db, item_id, condition) -> bool:
    values, op, wanted = condition_values(db, item_id, condition), condition["op"], condition.get("value")
    if op == "exists":
        return any(v is not None for v in values)
    if op == "ne":
        return bool(values) and all(v is not None and v != wanted for v in values)
    for value in values:
        if value is None:
            continue
        if op == "eq" and type(value) is type(wanted) and value == wanted or op == "in" and any(type(value) is type(v) and value == v for v in wanted):
            return True
        if op in {"gte", "lte"} and type(value) in (int, float) and (value >= wanted if op == "gte" else value <= wanted):
            return True
    return False


def members(db, group_id: str) -> list[str]:
    group = db.execute("SELECT * FROM data_groups WHERE group_id=?", (group_id,)).fetchone()
    if not group:
        raise LookupError("グループが見つかりません。")
    if group["kind"] == "manual":
        return [r[0] for r in db.execute("SELECT item_id FROM data_group_members WHERE group_id=? ORDER BY item_id", (group_id,))]
    rule = json.loads(group["rule_json"])
    combine = all if rule["mode"] == "all" else any
    return [r[0] for r in db.execute("SELECT id FROM library_items ORDER BY id")
            if combine(matches(db, r[0], c) for c in rule["conditions"])]


def group_public(db, row) -> dict:
    ids = members(db, row["group_id"])
    return {**dict(row), "rule": json.loads(row["rule_json"]), "item_ids": ids, "item_count": len(ids)}


def catalog(db) -> dict:
    return {"definitions": definitions(db),
            "groups": [group_public(db, r) for r in db.execute("SELECT * FROM data_groups ORDER BY name,group_id")],
            "tags": [{**dict(r), "item_count": db.execute("SELECT count(*) FROM conversation_tags WHERE tag_id=?", (r["tag_id"],)).fetchone()[0]}
                     for r in db.execute("SELECT * FROM tags ORDER BY normalized_name")],
            "items": [{"id": r[0], "name": r[1], "attributes": attribute_values(db, r[0]),
                       "tag_ids": [v[0] for v in db.execute("SELECT tag_id FROM conversation_tags WHERE item_id=? ORDER BY tag_id", (r[0],))]}
                      for r in db.execute("SELECT id,source_name FROM library_items ORDER BY source_name,id")]}


def freeze(db, item_ids, *, group_ids=None, group_by=None) -> dict:
    ids = require_items(db, item_ids)
    groups = []
    for identity in sorted(set(group_ids or [])):
        row = db.execute("SELECT * FROM data_groups WHERE group_id=?", (identity,)).fetchone()
        if not row:
            raise LookupError("グループが見つかりません。")
        group = group_public(db, row)
        if group["item_ids"] != ids:
            raise ValueError("グループの対象集合が変わっています。再集計してください。")
        groups.append(group)
    if group_by is None:
        keys = []
        for identity in ids:
            row = db.execute("SELECT analysis_config_json FROM library_items WHERE id=?", (identity,)).fetchone()
            try:
                config = json.loads(row[0])
                key = config.get('group_by', '') if isinstance(config, dict) else ''
            except (TypeError, ValueError):
                key = ''
            if isinstance(key, str) and key.startswith('attribute:'):
                candidate = {'scope': 'speaker', 'key': key[len('attribute:'):]}
                if candidate not in keys:
                    keys.append(candidate)
    else:
        keys = group_by
    defs = definitions(db)
    if not isinstance(keys, list) or any(not isinstance(k, dict) or not any(d["scope"] == k.get("scope") and d["key"] == k.get("key") for d in defs) for k in keys) and group_by is not None:
        raise ValueError("グループ化の属性が未定義です。")
    refs = []
    for key in keys:
        definition = next((d for d in defs if d['scope'] == key['scope'] and d['key'] == key['key']), None)
        refs.append({**key, 'version': definition['version'] if definition else None,
                     'status': definition['type_status'] if definition else '定義なし'})
    items = []
    for identity in ids:
        tags = [dict(r) for r in db.execute("SELECT t.* FROM tags t JOIN conversation_tags c ON c.tag_id=t.tag_id WHERE c.item_id=? ORDER BY t.tag_id", (identity,))]
        from .speaker_registry import speaker_registry_public
        speakers = []
        for row in db.execute("SELECT * FROM conversation_speakers WHERE item_id=? ORDER BY speaker_label", (identity,)):
            registry = db.execute("SELECT * FROM speaker_registry WHERE id=?", (row['global_speaker_id'],)).fetchone()
            speakers.append({**dict(row), 'registry_profile': speaker_registry_public(registry) if registry else None,
                'attributes': {a[0]: json.loads(a[1]) for a in db.execute("SELECT key,value_json FROM speaker_attributes WHERE speaker_id=? ORDER BY key", (row['global_speaker_id'],))}})
        items.append({"item_id": identity, "attributes": attribute_values(db, identity), "tags": tags, "speakers": speakers})
    snapshot = {"version": 1, "groups": groups, "item_ids": ids, "members_hash": digest(ids),
                "group_by": keys, "definition_refs": refs, "definitions": defs, "items": items}
    return {**snapshot, "hash": digest(snapshot)}


def check(db) -> dict:
    issues = []
    for row in db.execute('SELECT * FROM conversation_attributes'):
        definition = db.execute("SELECT * FROM attribute_definitions WHERE scope='conversation' AND key=?", (row['key'],)).fetchone()
        try:
            valid = definition is not None and valid_value(dict(definition), json.loads(row['value_json']))
        except (TypeError, ValueError):
            valid = False
        if not valid:
            issues.append({'item_id': row['item_id'], 'key': row['key'], 'reason': 'attribute_value_mismatch'})
    for row in db.execute("SELECT * FROM speaker_registry"):
        try:
            source = json.loads(row["attributes_json"])
            if not isinstance(source, dict):
                raise ValueError
        except (TypeError, ValueError):
            issues.append({"speaker_id": row["id"], "reason": "invalid_attributes_json"})
            continue
        try:
            projected = {r[0]: json.loads(r[1]) for r in db.execute("SELECT key,value_json FROM speaker_attributes WHERE speaker_id=?", (row["id"],))}
        except (TypeError, ValueError):
            projected = None
        if source != projected:
            issues.append({"speaker_id": row["id"], "reason": "projection_mismatch"})
        for key, value in source.items():
            definition = db.execute("SELECT * FROM attribute_definitions WHERE key=? AND scope='speaker'", (key,)).fetchone()
            if not definition or not valid_value(dict(definition), value):
                issues.append({"speaker_id": row["id"], "key": key, "reason": "attribute_value_mismatch"})
    return {"ok": not issues, "issues": issues}
