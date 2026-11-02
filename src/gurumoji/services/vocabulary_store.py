"""DB vocabulary and notation dictionary; JSON is only the Whisper copy."""
from __future__ import annotations

import json
from contextlib import contextmanager

from . import change_log
from .durable_files import atomic_write_text
from ..transcript_preparation import digest, now


def initialize(connection):
    change_log.initialize(connection)
    connection.execute("""CREATE TABLE IF NOT EXISTS vocabulary_terms (
        term TEXT PRIMARY KEY, position INTEGER NOT NULL, created_at TEXT NOT NULL)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS notation_variants (
        variant TEXT PRIMARY KEY, canonical TEXT NOT NULL, created_at TEXT NOT NULL)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS vocabulary_copy_metadata (
        id INTEGER PRIMARY KEY CHECK(id=1), last_terms_hash TEXT NOT NULL)""")


@contextmanager
def atomic(connection):
    connection.execute("SAVEPOINT vocabulary_save")
    try:
        yield
        connection.execute("RELEASE vocabulary_save")
    except BaseException:
        connection.execute("ROLLBACK TO vocabulary_save")
        connection.execute("RELEASE vocabulary_save")
        raise


def terms(connection):
    return tuple(row[0] for row in connection.execute("SELECT term FROM vocabulary_terms ORDER BY position"))


def variants(connection):
    return dict(connection.execute("SELECT variant, canonical FROM notation_variants ORDER BY variant"))


def save_terms(connection, values, *, origin="researcher", process="vocabulary_save", initial=False):
    with atomic(connection):
        before = list(terms(connection))
        after = list(values)
        if initial:
            change_log.capture(connection, "vocabulary_terms", "global", after, after)
        else:
            change_log.capture(connection, "vocabulary_terms", "global", before, after,
                               origin=origin, process=process)
        # Keep creation times of surviving terms and preserve explicit order.
        connection.executemany("DELETE FROM vocabulary_terms WHERE term=?", ((v,) for v in set(before) - set(after)))
        connection.executemany("""INSERT INTO vocabulary_terms VALUES (?, ?, ?)
            ON CONFLICT(term) DO UPDATE SET position=excluded.position""",
            ((term, position, now()) for position, term in enumerate(after)))


def save_variant(connection, variant, canonical):
    """Explicit add/change/delete only; removing a term never invokes this."""
    if not isinstance(variant, str) or not variant.strip() or len(variant) > 80:
        raise ValueError("表記は1〜80文字で指定してください。")
    if canonical is not None and (not isinstance(canonical, str) or not canonical.strip() or len(canonical) > 80):
        raise ValueError("正しい表記は1〜80文字で指定してください。")
    variant = variant.strip()
    with atomic(connection):
        before = variants(connection)
        after = dict(before)
        if canonical is None:
            after.pop(variant, None)
        else:
            after[variant] = canonical.strip()
        change_log.capture(connection, "notation_variants", "global", before, after, process="notation_dictionary_save")
        if canonical is None:
            connection.execute("DELETE FROM notation_variants WHERE variant=?", (variant,))
        else:
            connection.execute("""INSERT INTO notation_variants VALUES (?, ?, ?)
                ON CONFLICT(variant) DO UPDATE SET canonical=excluded.canonical""",
                (variant, canonical.strip(), now()))
    return after


class VocabularyStore:
    def __init__(self, connect, path, lock, normalize):
        self.connect, self.path, self.lock, self.normalize = connect, path, lock, normalize

    def load(self):
        with self.connect() as connection:
            return terms(connection)

    def _write_copy(self, values):
        try:
            atomic_write_text(self.path(), json.dumps({"version": 1, "terms": list(values)},
                              ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            raise OSError("登録語はDBへ保存済みですが、Whisper用の写しを更新できませんでした。") from exc
        with self.connect() as connection:
            connection.execute("INSERT OR REPLACE INTO vocabulary_copy_metadata VALUES (1, ?)", (digest(list(values)),))

    def _file_terms(self):
        try:
            payload = json.loads(self.path().read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        if not isinstance(payload, dict) or payload.get("version") != 1 or "terms" not in payload:
            raise ValueError("登録語の写しの形式が不正です。DBは変更していません。")
        return self.normalize(payload["terms"])

    def reconcile(self):
        """Explicit startup operation; malformed files are retained, never imported as empty."""
        with self.lock:
            file_values = self._file_terms()
            with self.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                current = terms(connection)
                history = change_log.rows(connection, "vocabulary_terms", "global")
                marker = connection.execute("SELECT last_terms_hash FROM vocabulary_copy_metadata WHERE id=1").fetchone()
                if not history:
                    current = file_values if file_values is not None else current
                    save_terms(connection, current, initial=True)
                elif file_values is not None and file_values != current:
                    # A failed copy write leaves the last observed copy intact.
                    # Only a changed file is an external edit, not that stale copy.
                    if marker is None or digest(list(file_values)) != marker[0]:
                        save_terms(connection, file_values, origin="rule", process="vocabulary_file_import")
                        current = file_values
                if file_values is not None:
                    connection.execute("INSERT OR REPLACE INTO vocabulary_copy_metadata VALUES (1, ?)",
                                       (digest(list(file_values)),))
                dictionary = variants(connection)
                change_log.capture(connection, "notation_variants", "global", dictionary, dictionary)
            self._write_copy(current)
            return current

    def save(self, values, *, notation_changes=None):
        values = self.normalize(values)
        if notation_changes is not None and not isinstance(notation_changes, dict):
            raise ValueError("表記辞書の変更は辞書形式で指定してください。")
        with self.lock:
            with self.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                save_terms(connection, values)
                for variant, canonical in (notation_changes or {}).items():
                    save_variant(connection, variant, canonical)
            self._write_copy(values)
        return values
