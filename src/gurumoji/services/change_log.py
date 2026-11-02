"""Append-only researcher-data history. Call inside the current-value transaction."""
from __future__ import annotations

import json
from contextlib import contextmanager
from copy import deepcopy

from ..transcript_preparation import digest, encode, now, _same_json

# entity_id is a conversation ID only for these explicitly reserved entities.
# Global vocabulary and speaker registry histories are never conversation rows.
CONVERSATION_ENTITIES = ("conversation", "analysis_annotations", "analysis_config",
                         "conversation_attributes", "conversation_tags",
                         "analysis_definitions", "data_group_members")


def initialize(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS change_log (
        entity TEXT NOT NULL, entity_id TEXT NOT NULL, seq INTEGER NOT NULL,
        origin TEXT NOT NULL, ops_json TEXT NOT NULL, base_hash TEXT NOT NULL,
        after_hash TEXT NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY(entity, entity_id, seq))""")


def operations(before, after):
    if isinstance(before, dict) and isinstance(after, dict):
        return ([{"op": "unset", "key": key} for key in sorted(before.keys() - after.keys())]
                + [{"op": "set", "key": key, "value": deepcopy(value)}
                   for key, value in after.items()
                   if key not in before or not _same_json(before[key], value)])
    return [] if _same_json(before, after) else [{"op": "replace", "value": deepcopy(after)}]


def apply(value, ops):
    value = deepcopy(value)
    for op in ops:
        if op["op"] == "replace":
            value = deepcopy(op["value"])
        elif op["op"] == "set" and isinstance(value, dict):
            value[op["key"]] = deepcopy(op["value"])
        elif op["op"] == "unset" and isinstance(value, dict):
            del value[op["key"]]
        else:
            raise ValueError("Unknown change-log operation")
    return value


def reconstruct(changes, *, empty=None):
    value = {} if empty is None else deepcopy(empty)
    for seq, row in enumerate(changes, 1):
        payload = json.loads(row["ops_json"])
        if row["seq"] != seq or payload["version"] != 1 or digest(value) != row["base_hash"]:
            raise ValueError("Change-log sequence or base hash mismatch")
        value = apply(value, payload["ops"])
        if digest(value) != row["after_hash"]:
            raise ValueError("Change-log result hash mismatch")
    return value


def rows(connection, entity, entity_id):
    return [dict(row) for row in connection.execute(
        "SELECT * FROM change_log WHERE entity=? AND entity_id=? ORDER BY seq", (entity, entity_id))]


def capture(connection, entity, entity_id, before, after, *, origin="researcher", process="save"):
    if origin not in {"researcher", "ai", "rule"}:
        raise ValueError("Unknown change origin")
    history = rows(connection, entity, entity_id)
    if history:
        if digest(reconstruct(history)) != digest(before):
            raise ValueError("Current data does not match change history")
    else:
        # Preserve existing values without inventing their past provenance.
        _append(connection, entity, entity_id, 1, {}, before, "rule", "initial_state")
    if not _same_json(before, after):
        seq = len(history) + 1 if history else 2
        _append(connection, entity, entity_id, seq, before, after, origin, process)


def _append(connection, entity, entity_id, seq, before, after, origin, process):
    payload = {"version": 1, "process": process, "ops": operations(before, after)}
    if process == "initial_state":
        payload["past_origin"] = "unknown"
    if digest(apply(before, payload["ops"])) != digest(after):
        raise ValueError("Change-log replay mismatch")
    connection.execute("INSERT INTO change_log VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (entity, entity_id, seq, origin, encode(payload), digest(before), digest(after), now()))


def conversation_condition():
    return "entity_id=? AND entity IN (" + ",".join("?" for _ in CONVERSATION_ENTITIES) + ")"


def conversation_parameters(item_id):
    return (item_id, *CONVERSATION_ENTITIES)


def current(connection, entity, entity_id):
    """Read exact stored values, including unknown JSON fields and row metadata."""
    if entity in {"analysis_annotations", "analysis_config"}:
        column = entity + "_json"
        cursor = connection.execute(f"SELECT {column} FROM library_items WHERE id=?", (entity_id,))
        row = cursor.fetchone()
        return {column: row[0]} if row else {}
    tables = {
        "speaker_registry": ("speaker_registry", "id", None),
        "analysis_definitions": ("analysis_definitions", "item_id", "definition_id"),
        "conversation_attributes": ("conversation_attributes", "item_id", "key"),
        "conversation_tags": ("conversation_tags", "item_id", "tag_id"),
        "data_group_members": ("data_group_members", "item_id", "group_id"),
        "tags": ("tags", "tag_id", None),
        "data_groups": ("data_groups", "group_id", None),
    }
    if entity == "attribute_definitions" and entity_id == "global":
        cursor = connection.execute("SELECT * FROM attribute_definitions ORDER BY scope,key")
        names = [c[0] for c in cursor.description]
        return {encode([r[1], r[0]]): dict(zip(names, r)) for r in cursor}
    if entity not in tables:
        raise ValueError("Unknown researcher-data entity")
    table, column, key = tables[entity]
    cursor = connection.execute(f"SELECT * FROM {table} WHERE {column}=?", (entity_id,))
    names = [c[0] for c in cursor.description]
    records = [dict(zip(names, r)) for r in cursor]
    return {r[key]: r for r in records} if key else (records[0] if records else {})


@contextmanager
def tracking(connection, targets, *, origin="researcher", process="save"):
    """Keep current rows, trigger side effects and history in one savepoint."""
    if not connection.in_transaction:
        connection.execute("BEGIN IMMEDIATE")
    connection.execute("SAVEPOINT researcher_change")
    try:
        before = {target: current(connection, *target) for target in dict.fromkeys(targets)}
        yield
        for target, value in before.items():
            capture(connection, *target, value, current(connection, *target), origin=origin, process=process)
        connection.execute("RELEASE researcher_change")
    except BaseException:
        connection.execute("ROLLBACK TO researcher_change")
        connection.execute("RELEASE researcher_change")
        raise


def fix_initial_states(connection, *, dry_run=True):
    """Explicit legacy switch only; never called by initialization or GET."""
    if not dry_run and not connection.in_transaction:
        connection.execute("BEGIN IMMEDIATE")
    connection.execute("SAVEPOINT researcher_initial_states")
    try:
        targets = []
        for entity, table, column in (
            ("analysis_annotations", "library_items", "id"),
            ("analysis_config", "library_items", "id"),
            ("analysis_definitions", "analysis_definitions", "item_id"),
            ("speaker_registry", "speaker_registry", "id"),
            ("conversation_attributes", "library_items", "id"),
            ("conversation_tags", "library_items", "id"),
            ("data_group_members", "library_items", "id"),
            ("tags", "tags", "tag_id"), ("data_groups", "data_groups", "group_id"),
        ):
            targets.extend((entity, r[0]) for r in connection.execute(f"SELECT DISTINCT {column} FROM {table}"))
        targets.append(("attribute_definitions", "global"))
        report = {"targets": len(targets), "unrecorded": 0, "dry_run": dry_run}
        # A failed validation rolls back every initial state in this snapshot.
        for target in targets:
            value, history = current(connection, *target), rows(connection, *target)
            if history:
                if digest(reconstruct(history)) != digest(value):
                    raise ValueError("Current data does not match change history")
            else:
                report["unrecorded"] += 1
                if not dry_run:
                    capture(connection, *target, value, value)
        connection.execute("RELEASE researcher_initial_states")
    except BaseException:
        connection.execute("ROLLBACK TO researcher_initial_states")
        connection.execute("RELEASE researcher_initial_states")
        raise
    return report
