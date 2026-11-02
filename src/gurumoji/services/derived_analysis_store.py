"""Append-only, content-addressed morphology rows, rebuildable from text."""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3

from ..analysis_core import canonical, fingerprint


DATABASE = "analysis-derived.sqlite3"


class DerivedAnalysisError(ValueError):
    pass


class DerivedAnalysisStore:
    def __init__(self, database: Path):
        self.database = Path(database)

    def _connect(self):
        self.database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database, timeout=30)
        try:
            connection.execute("CREATE TABLE IF NOT EXISTS segment_parses ("
                               "parse_key TEXT PRIMARY KEY, text_hash TEXT NOT NULL, "
                               "analyzer_json TEXT NOT NULL, config_hash TEXT NOT NULL, "
                               "rows_hash TEXT NOT NULL, sentence_count INTEGER NOT NULL)")
            for table in ("morphemes", "dependencies"):
                connection.execute(f"CREATE TABLE IF NOT EXISTS {table} ("
                                   "parse_key TEXT NOT NULL, ordinal INTEGER NOT NULL, row_json TEXT NOT NULL, "
                                   "PRIMARY KEY(parse_key,ordinal))")
        except BaseException:
            connection.close()
            raise
        return connection

    @staticmethod
    def key(text, analyzer, config):
        return fingerprint({"text_hash": fingerprint(text), "analyzer": analyzer, "config": config})

    def read(self, text, analyzer, config, *, readonly=False):
        key = self.key(text, analyzer, config)
        connection = (sqlite3.connect(self.database.resolve().as_uri() + '?mode=ro', uri=True)
                      if readonly else self._connect())
        with closing(connection):
            header = connection.execute("SELECT rows_hash,sentence_count,text_hash,analyzer_json,config_hash "
                                        "FROM segment_parses WHERE parse_key=?",
                                        (key,)).fetchone()
            if header is None:
                return None
            if header[2:] != (fingerprint(text), canonical(analyzer).decode(), fingerprint(config)):
                raise DerivedAnalysisError("派生解析行の入力・解析器・設定が一致しません。")
            rows = [
                [json.loads(row[0]) for row in connection.execute(
                    f"SELECT row_json FROM {table} WHERE parse_key=? ORDER BY ordinal", (key,))]
                for table in ("morphemes", "dependencies")
            ]
            result = (rows[0], rows[1], header[1])
            if fingerprint(result) != header[0]:
                raise DerivedAnalysisError("派生解析行のhashが一致しません。")
            return result

    def save(self, text, analyzer, config, result):
        key = self.key(text, analyzer, config)
        rows_hash = fingerprint(result)
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute("SELECT rows_hash FROM segment_parses WHERE parse_key=?", (key,)).fetchone()
            if existing is not None:
                if existing[0] != rows_hash:
                    raise DerivedAnalysisError("同じ派生解析キーに異なる結果は保存できません。")
                stored = tuple([
                    json.loads(row[0]) for row in connection.execute(
                        f"SELECT row_json FROM {table} WHERE parse_key=? ORDER BY ordinal", (key,))
                ] for table in ("morphemes", "dependencies")) + (result[2],)
                if fingerprint(stored) != rows_hash:
                    raise DerivedAnalysisError("既存の派生解析行のhashが一致しません。")
                return
            connection.execute("INSERT INTO segment_parses VALUES (?,?,?,?,?,?)",
                               (key, fingerprint(text), canonical(analyzer).decode(), fingerprint(config),
                                rows_hash, result[2]))
            for table, rows in zip(("morphemes", "dependencies"), result[:2]):
                connection.executemany(f"INSERT INTO {table} VALUES (?,?,?)",
                                       ((key, i, canonical(row).decode()) for i, row in enumerate(rows)))

    def restore(self, text, analyzer, config, result, expected_hash):
        """Restore only hash-verified deterministic rows; never replace another parser version."""
        if fingerprint(result) != expected_hash:
            raise DerivedAnalysisError('再計算した派生解析のhashが一致しません。')
        key = self.key(text, analyzer, config)
        with closing(self._connect()) as connection, connection:
            connection.execute('BEGIN IMMEDIATE')
            existing = connection.execute('SELECT text_hash,analyzer_json,config_hash,rows_hash,sentence_count FROM segment_parses WHERE parse_key=?', (key,)).fetchone()
            expected = (fingerprint(text), canonical(analyzer).decode(), fingerprint(config), expected_hash, result[2])
            if existing is not None and existing != expected:
                raise DerivedAnalysisError('既存の派生解析版と復旧条件が一致しません。')
            if existing is None:
                connection.execute('INSERT INTO segment_parses VALUES (?,?,?,?,?,?)', (key, *expected))
            for table, rows in zip(('morphemes', 'dependencies'), result[:2]):
                connection.execute(f'DELETE FROM {table} WHERE parse_key=?', (key,))
                connection.executemany(f'INSERT INTO {table} VALUES (?,?,?)',
                    ((key, i, canonical(row).decode()) for i, row in enumerate(rows)))
