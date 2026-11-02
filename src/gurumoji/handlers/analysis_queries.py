"""Read-only analysis use cases, independent from Flask."""

from __future__ import annotations

from dataclasses import dataclass
import io
import csv
import json
import math
import sys
from pathlib import Path
import zipfile
import hashlib
from ..services.analysis_package import MissingReference
from typing import Any, Callable

from ..analysis_method_registry import METHODS, REGISTRY_VERSION

# Saved artifact bytes are already loaded and hash-verified before parsing.
# CSV's default 128 KiB field ceiling rejects valid saved cells; previews are bounded separately.
# Set once at module initialization, never change/restore it across requests.
def _configure_csv_field_limit():
    limit = sys.maxsize
    while True:
        try:
            csv.field_size_limit(limit)
            return limit
        except OverflowError:
            # Windows' C long can be narrower than Python's sys.maxsize.
            limit //= 10


_configure_csv_field_limit()


def read_saved_json(data):
    def reject_constant(_value):
        raise ValueError("保存JSONに非有限値があります。")
    return json.loads(data, parse_constant=reject_constant)


class AnalysisQueryNotFound(LookupError):
    """The requested conversation, run, or artifact does not exist."""


@dataclass(frozen=True)
class AnalysisArtifact:
    data: bytes
    media_type: str
    download_name: str


def saved_result_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Project saved human-readable fields only; no calculations or current joins."""
    budget = 16384
    truncated = False
    def text(value, limit=512):
        nonlocal budget, truncated
        if value is None:
            return None
        if not isinstance(value, (str, int, float, bool)):
            return None
        original = str(value)
        clipped = original[:limit].encode("utf-8")[:max(0, budget)].decode("utf-8", errors="ignore")
        budget -= len(clipped.encode("utf-8"))
        truncated = truncated or clipped != original
        return clipped
    def version(value):
        if value is None or isinstance(value, str) and not value.strip():
            return None, "missing"
        if not (isinstance(value, str) or type(value) is int or type(value) is float and math.isfinite(value)):
            return None, "unsupported"
        # A present value clipped by the shared budget remains recorded, not missing.
        return text(value, 256), "recorded"

    def entries(value, limit):
        nonlocal truncated
        if not isinstance(value, list):
            return []
        truncated = truncated or len(value) > limit
        return value[:limit]
    methods = result.get("methods")
    items = []
    for method in entries(methods, 12):
        if not isinstance(method, dict) or budget <= 0:
            truncated = True
            continue
        item = {key:text(method.get(key),256) for key in ("method_id","title","status","analysis_unit")}
        item["method_version"], item["method_version_status"] = version(method.get("method_version"))
        engine = method.get("engine")
        item["engine_version"], item["engine_version_status"] = (
            version(engine.get("version")) if isinstance(engine, dict)
            else (None, "missing" if engine is None else "unsupported")
        )
        for key in ("summaries","findings"):
            item[key] = [{"title":text(row.get("title"),256),"text":text(row.get("text"))}
                         for row in entries(method.get(key),5) if isinstance(row,dict)]
        item["limitations"] = [text(value) for value in entries(method.get("limitations"),5)]
        items.append(item)
    definitions = []
    parameters = result.get("parameters", {})
    for definition in entries(parameters.get("definitions"),20):
        if not isinstance(definition,dict) or budget <= 0:
            truncated = True
            continue
        definitions.append({key:text(definition.get(key),256) for key in
                            ("definition_id","version","name","output_column","measurement_rule","method")})
    saved_algorithms = result.get("algorithms")
    algorithms = []
    algorithms_status = "missing" if saved_algorithms is None else "recorded" if isinstance(saved_algorithms, dict) else "unsupported"
    if isinstance(saved_algorithms, dict):
        for index, (name, value) in enumerate(saved_algorithms.items()):
            if index >= 20:
                truncated = True
                break
            algorithm_name = text(name, 128)
            algorithm_version, status = version(value)
            algorithms.append({"name": algorithm_name, "version": algorithm_version, "status": status})
    return {"methods":items,"total_methods":len(methods) if isinstance(methods,list) else None,
            "definitions":definitions,"algorithms":algorithms,"algorithms_status":algorithms_status,
            "total_algorithms":len(saved_algorithms) if isinstance(saved_algorithms,dict) else None,
            "truncated":truncated,"text_byte_limit":16384}


class AnalysisQueries:
    """Coordinate analysis reads using the existing store and item lookup."""

    def __init__(
        self,
        *,
        store: Any,
        find_item: Callable[[str], Any],
        source_fingerprint: Callable[[Any], str],
        database_connection: Callable[[], Any],
        build_analysis: Callable[[Any], dict[str, Any]],
        public_insight_request: Callable[[Any], dict[str, Any] | None],
        public_transformer_request: Callable[[Any], dict[str, Any] | None],
        expose_local_paths: bool,
    ) -> None:
        self._store = store
        self._find_item = find_item
        self._source_fingerprint = source_fingerprint
        self._database_connection = database_connection
        self._build_analysis = build_analysis
        self._public_insight_request = public_insight_request
        self._public_transformer_request = public_transformer_request
        self._expose_local_paths = expose_local_paths

    def methods(self) -> dict[str, Any]:
        return {
            "version": REGISTRY_VERSION,
            "methods": [
                {"id": key, "title": title, "datasets": tables}
                for key, title, tables in METHODS
            ],
        }

    def runs(self, item_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        item = self._find_item(item_id)
        if item is None:
            raise AnalysisQueryNotFound("対象の会話が見つかりません。")
        fingerprint = self._source_fingerprint(item)
        runs = []
        for stored in self._store.list(item_id, limit=limit, offset=offset):
            run = dict(stored)
            run["stale"] = bool(
                run["stale"] or run["input_fingerprint"] != fingerprint
            )
            runs.append(
                self._store.public(run, local=self._expose_local_paths)
            )
        return {
            "runs": runs,
            "pagination": {"offset": offset, "limit": limit, "total": self._store.run_count(item_id),
                           "has_more": offset + len(runs) < self._store.run_count(item_id)},
            "storage": {
                "database": "SQLite",
                "artifacts": "CSV / JSON",
                "notes": "ResearchVault",
            },
        }

    def _fixed_package(self, item_id: str, run_id: str):
        run = self._store.get(run_id)
        item = self._find_item(item_id)
        if not run or run["item_id"] != item_id or item is None:
            raise AnalysisQueryNotFound("指定した会話の保存結果が見つかりません。")
        snapshot, result, manifest, content = self._store.readable_package(run_id)
        # All saved tables must be readable, even if only one preview is requested.
        # This validates stored rows; it does not calculate scientific results.
        for artifact in self._store.artifacts(run_id):
            if artifact["media_type"] == "text/csv":
                count = 0
                reader = csv.reader(io.StringIO(content[artifact["name"]].decode("utf-8-sig")), strict=True)
                header = next(reader, None)
                if header is None:
                    raise ValueError("保存表の列がありません。")
                for row in reader:
                    if len(row) != len(header):
                        raise ValueError("保存表の列数が一致しません。")
                    count += 1
                if artifact["rows"] is not None and count != artifact["rows"]:
                    raise ValueError("保存表の件数が一致しません。")
            elif artifact["media_type"] == "application/json":
                read_saved_json(content[artifact["name"]])
        return run, item, manifest, content, result

    def run(self, item_id: str, run_id: str) -> dict[str, Any]:
        """Direct fixed-run lookup, independent of the newest-100 history window."""
        try:
            run, item, manifest, content, saved_result = self._fixed_package(item_id, run_id)
        except MissingReference as exc:
            run = self._store.get(run_id)
            return {'run': self._store.public(run, local=False), 'integrity': 'missing_reference',
                'recovery_status': getattr(exc, 'recovery_status', 'missing_reference'),
                'error': str(exc), 'saved_summary': {}, 'provenance': {}, 'current_input': {'stale': None}}
        public = self._store.public(run, local=False)
        public["saved_publication_targets"] = saved_result.get("parameters", {}).get("publication_targets")
        return {
            "run": public,
            "integrity": "verified",
            "saved_summary": saved_result_summary(saved_result),
            "provenance": {key: manifest.get(key) for key in (
                "schema_version", "method_version", "input_snapshot_id", "input_fingerprint",
                "source_revision", "analysis_revision", "created_at", "fingerprint",
            )},
            "current_input": {"stale": (bool(run.get("stale") or
                run.get("input_fingerprint") != self._source_fingerprint(item))
                if run.get("input_fingerprint") else None)},
            "preview_limits": {"rows": 20, "columns": 24, "cell_characters": 256, "bytes": 16384},
        }

    def run_preview(self, item_id: str, run_id: str, artifact_id: str) -> dict[str, Any]:
        run, _item, _manifest, content, _result = self._fixed_package(item_id, run_id)
        artifact = next((a for a in self._store.export_artifacts(run_id) if a["id"] == artifact_id), None)
        if artifact is None:
            raise AnalysisQueryNotFound("指定した保存結果のファイルが見つかりません。")
        data = self._store.table_csv(run_id, artifact['name'][7:-4]) if artifact.get('generated') else content[artifact["name"]]
        preview = {"artifact_id": artifact_id, "run_id": run["id"], "bytes": len(data),
                   "format": "text", "truncated": False}
        if artifact["media_type"] == "text/csv":
            reader = csv.reader(io.StringIO(data.decode("utf-8-sig")), strict=True)
            fields = next(reader)
            rows = []
            clipped = len(fields) > 24
            budget = 16384
            def cells(values):
                nonlocal clipped, budget
                result = []
                for value in values[:24]:
                    encoded = value[:256].encode("utf-8")[:max(0, budget)]
                    text = encoded.decode("utf-8", errors="ignore")
                    budget -= len(text.encode("utf-8"))
                    clipped = clipped or text != value
                    result.append(text)
                return result
            columns = cells(fields)
            total = 0
            for row in reader:
                total += 1
                if len(rows) < 20 and budget > 0:
                    rows.append(cells(row))
            preview.update(format="table", columns=columns, rows=rows, total_rows=total,
                           total_columns=len(fields), shown_rows=len(rows),
                           truncated=clipped or len(rows) < total)
        else:
            # A bounded UTF-8 fragment preserves null/zero/empty strings literally.
            # Do not expose the manifest's private filesystem paths in a preview.
            if artifact["name"] == "manifest.json":
                value = read_saved_json(data)
                for entry in value.get("artifacts", []):
                    entry.pop("path", None)
                data = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
            elif artifact["media_type"] == "application/json":
                data = json.dumps(read_saved_json(data), ensure_ascii=False, indent=2).encode("utf-8")
            preview.update(text=data[:16384].decode("utf-8", errors="ignore"), truncated=len(data) > 16384)
        return {"preview": preview}

    def artifact(self, artifact_id: str) -> AnalysisArtifact:
        try:
            metadata, data = self._store.read_artifact(artifact_id)
        except LookupError as exc:
            raise AnalysisQueryNotFound("保存ファイルが見つかりません。") from exc
        run = self._store.get(metadata["run_id"])
        if not run or self._find_item(run["item_id"]) is None:
            raise AnalysisQueryNotFound("保存ファイルが見つかりません。")
        return AnalysisArtifact(
            data=data,
            media_type=metadata["media_type"],
            download_name=Path(metadata["name"]).name,
        )

    def table_schema(self, item_id: str, run_id: str, name: str) -> dict:
        self._fixed_package(item_id, run_id)
        table = self._store.read_table(run_id, name)
        return {'run_id': run_id, 'dataset': name, 'fields': table['fields'], 'columns':table.get('columns',[]), 'row_count': len(table['rows'])}

    def run_export(self, run_id: str, format: str, dataset: str | None = None) -> AnalysisArtifact:
        from ..services.fixed_exports import export_fixed
        run = self._store.get(run_id)
        if not run or run.get('status') != 'completed' or self._find_item(run['item_id']) is None:
            raise AnalysisQueryNotFound('保存結果が見つかりません。')
        self._fixed_package(run['item_id'], run_id)
        data, media_type, extension = export_fixed(self._store, run_id, format, dataset)
        return AnalysisArtifact(data=data, media_type=media_type, download_name=f'analysis-{run_id}.{extension}')

    def run_bundle(self, run_id: str) -> AnalysisArtifact:
        run = self._store.get(run_id)
        if not run or run.get("status") != "completed" or self._find_item(run["item_id"]) is None:
            raise AnalysisQueryNotFound("保存結果が見つかりません。")
        _run, _item, manifest, content, _result = self._fixed_package(run["item_id"], run_id)
        if manifest.get('schema_version') == 2:
            from ..analysis_store import canonical, csv_bytes
            content = dict(content)
            mapping = {}
            for name in manifest['typed_tables']:
                table = self._store.read_table(run_id, name)
                content[f'tables/{name}.json'] = canonical(table)
                content[f'tables/{name}.csv'] = csv_bytes(table['fields'], [r['values'] for r in table['rows']])
                mapping[name] = {**manifest['typed_tables'][name], 'data': f'tables/{name}.json'}
                mapping[name].pop('reference', None)
            compact = read_saved_json(content['result.json'])
            compact['tables'] = mapping
            content['result.json'] = canonical(compact)
            exported = {**manifest, 'typed_tables': mapping, 'references': {}, 'export': 'self_contained',
                'artifacts': [{'name': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                              for name, data in content.items() if name != 'manifest.json']}
            content['manifest.json'] = canonical(exported)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in content.items():
                archive.writestr(name, data)
        return AnalysisArtifact(
            data=stream.getvalue(), media_type="application/zip",
            download_name=f"analysis-{run_id}.zip",
        )

    def table_csv(self, run_id: str, name: str) -> AnalysisArtifact:
        run = self._store.get(run_id)
        if not run or self._find_item(run['item_id']) is None:
            raise AnalysisQueryNotFound('保存結果が見つかりません。')
        return AnalysisArtifact(data=self._store.table_csv(run_id, name), media_type='text/csv', download_name=name + '.csv')

    def insights(self, item_id: str) -> dict[str, Any]:
        """Read the latest request and saved insight from one SQLite snapshot."""
        with self._database_connection() as connection:
            connection.execute("BEGIN")
            item = connection.execute(
                "SELECT * FROM library_items WHERE id=?", (item_id,)
            ).fetchone()
            if item is None:
                raise AnalysisQueryNotFound("処理済みデータが見つかりません。")
            run = connection.execute(
                "SELECT * FROM analysis_insight_requests WHERE item_id=? "
                "ORDER BY created_at DESC LIMIT 1",
                (item_id,),
            ).fetchone()
        analysis = self._build_analysis(item)
        return {
            "insights": analysis["insights"],
            "run": self._public_insight_request(run),
        }

    def transformer(self, item_id: str) -> dict[str, Any]:
        with self._database_connection() as connection:
            connection.execute("BEGIN")
            item = connection.execute(
                "SELECT * FROM library_items WHERE id=?", (item_id,)
            ).fetchone()
            if item is None:
                raise AnalysisQueryNotFound("処理済みデータが見つかりません。")
            run = connection.execute(
                "SELECT * FROM transformer_analysis_requests WHERE item_id=? "
                "ORDER BY created_at DESC LIMIT 1",
                (item_id,),
            ).fetchone()
        analysis = self._build_analysis(item)
        return {
            "transformer": analysis["transformer"],
            "run": self._public_transformer_request(run),
        }

    def classifications(self, item_id: str) -> dict[str, Any]:
        with self._database_connection() as connection:
            connection.execute("BEGIN")
            item = connection.execute(
                "SELECT * FROM library_items WHERE id=?", (item_id,)
            ).fetchone()
            if item is None:
                raise AnalysisQueryNotFound("データが見つかりません。")
        analysis = self._build_analysis(item)
        return {"segment_classification": analysis["segment_classification"]}
