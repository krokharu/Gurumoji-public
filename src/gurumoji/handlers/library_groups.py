"""Transactional library-group commands, independent from Flask."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class LibraryGroups:
    connection: Callable[[], Any]
    lock: Any
    now: Callable[[], str]
    normalize_name: Callable[[Any], str]

    def create(self, value: Any) -> dict[str, Any]:
        name = self.normalize_name(value)
        now, group_id = self.now(), uuid.uuid4().hex
        try:
            with self.lock, self.connection() as connection:
                connection.execute(
                    "INSERT INTO library_groups (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (group_id, name, now, now),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("同じ名前のグループがすでにあります。") from exc
        return {"id": group_id, "name": name, "item_count": 0, "created_at": now, "updated_at": now}

    def assign(self, item_id: str, group_id: Any) -> dict[str, str]:
        if not isinstance(group_id, str):
            raise ValueError("グループの指定が不正です。")
        group_id = group_id.strip()
        with self.lock, self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT id FROM library_items WHERE id = ?", (item_id,)).fetchone() is None:
                raise LookupError("データが見つかりません。")
            name = ""
            if group_id:
                row = connection.execute("SELECT name FROM library_groups WHERE id = ?", (group_id,)).fetchone()
                if row is None:
                    raise LookupError("グループが見つかりません。")
                name = str(row["name"])
            connection.execute("UPDATE library_items SET group_id = ? WHERE id = ?", (group_id, item_id))
        return {"item_id": item_id, "group_id": group_id, "group_name": name}

    def rename(self, group_id: str, value: Any) -> dict[str, Any]:
        name, now = self.normalize_name(value), self.now()
        try:
            with self.lock, self.connection() as connection:
                cursor = connection.execute(
                    "UPDATE library_groups SET name = ?, updated_at = ? WHERE id = ?",
                    (name, now, group_id),
                )
                if cursor.rowcount == 0:
                    raise LookupError("グループが見つかりません。")
                count = connection.execute(
                    "SELECT COUNT(*) AS item_count FROM library_items WHERE group_id = ?", (group_id,)
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            raise ValueError("同じ名前のグループがすでにあります。") from exc
        return {"id": group_id, "name": name, "item_count": int(count["item_count"] or 0), "updated_at": now}

    def delete(self, group_id: str) -> dict[str, Any]:
        with self.lock, self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT name FROM library_groups WHERE id = ?", (group_id,)).fetchone()
            if row is None:
                raise LookupError("グループが見つかりません。")
            cursor = connection.execute("UPDATE library_items SET group_id = '' WHERE group_id = ?", (group_id,))
            connection.execute("DELETE FROM library_groups WHERE id = ?", (group_id,))
        return {"ok": True, "name": str(row["name"]), "unassigned_count": int(cursor.rowcount or 0)}
