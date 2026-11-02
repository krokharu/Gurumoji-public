"""Analysis save and Vault retry use cases, independent from Flask."""

from __future__ import annotations

from typing import Any, Callable

from ..analysis_store import StoreConflict


class AnalysisCommandNotFound(LookupError):
    """The requested conversation or saved run does not exist."""


class TranscriptConflictError(RuntimeError):
    def __init__(self, current_revision: int):
        super().__init__(
            "The transcript was changed by another editor. Reload before saving again."
        )
        self.current_revision = current_revision


class ComparisonRequestError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class AnalysisCommandRequestError(RuntimeError):
    def __init__(
        self, message: str, status: int, *, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.details = details or {}


class AnalysisCommands:
    """Coordinate fixed-result saves without changing store ownership rules."""

    def __init__(
        self,
        *,
        store: Any,
        find_item: Callable[[str], Any],
        build_analysis: Callable[[Any], dict[str, Any]],
        search_kwic: Callable[..., dict[str, Any]],
        archive_analysis: Callable[..., dict[str, Any]],
        source_fingerprint: Callable[[Any], str],
        mark_stale: Callable[[str], None],
        load_comparison_items: Callable[[dict[str, Any]], tuple[list[Any], bool]],
        build_comparison: Callable[..., dict[str, Any]],
        archive_comparison: Callable[..., dict[str, Any]],
        database_connection: Callable[[], Any],
        save_preparation_state: Callable[..., dict[str, Any]],
        segments_for_item: Callable[[Any], list[dict[str, Any]]],
        refresh_archive_index: Callable[[str], None],
        publish_input_vault: Callable[[Any], None],
        update_library_item_locked: Callable[[str, Any], dict[str, Any]],
        start_insights: Callable[..., tuple[dict[str, Any], int]],
        cancel_insights: Callable[[str, str], dict[str, Any]],
        start_transformer: Callable[..., tuple[dict[str, Any], int]],
        cancel_transformer: Callable[[str, str], dict[str, Any]],
        run_classification: Callable[..., dict[str, Any]],
        write_lock: Any,
        expose_local_paths: bool,
        pipeline_service: Any | None = None,
        freeze_comparison: Callable[..., dict[str, Any]] | None = None,
    ) -> None:
        self._store = store
        self._find_item = find_item
        self._build_analysis = build_analysis
        self._search_kwic = search_kwic
        self._archive_analysis = archive_analysis
        self._source_fingerprint = source_fingerprint
        self._mark_stale = mark_stale
        self._load_comparison_items = load_comparison_items
        self._build_comparison = build_comparison
        self._archive_comparison = archive_comparison
        self._database_connection = database_connection
        self._save_preparation_state = save_preparation_state
        self._segments_for_item = segments_for_item
        self._refresh_archive_index = refresh_archive_index
        self._publish_input_vault = publish_input_vault
        self._update_library_item_locked = update_library_item_locked
        self._start_insights = start_insights
        self._cancel_insights = cancel_insights
        self._start_transformer = start_transformer
        self._cancel_transformer = cancel_transformer
        self._run_classification = run_classification
        self._pipeline = pipeline_service
        self._write_lock = write_lock
        self._expose_local_paths = expose_local_paths
        self._freeze_comparison = freeze_comparison

    def save(
        self,
        item_id: str,
        *,
        request_id: str,
        source_revision: int,
        analysis_revision: int,
        kwic_request: dict[str, Any] | None,
        app_url: str,
    ) -> dict[str, Any]:
        with self._write_lock:
            item = self._find_item(item_id)
            if item is None:
                raise AnalysisCommandNotFound("対象の会話が見つかりません。")
            if (
                source_revision != item["revision_count"]
                or analysis_revision != item["analysis_revision"]
            ):
                raise StoreConflict(
                    "元データまたは分析条件が更新されています。再集計してください。"
                )

            analysis = self._build_analysis(item)
            kwic = None
            if kwic_request is not None:
                kwic = self._search_kwic(
                    analysis,
                    analysis["research"]["linguistics"]["morphemes"],
                    kwic_request.get("q", ""),
                    mode=kwic_request.get("mode", "literal"),
                    speaker=kwic_request.get("speaker", ""),
                    limit=None,
                )
            run = self._archive_analysis(
                item,
                analysis,
                request_id,
                kwic=kwic,
                kind="kwic" if kwic is not None else "text_analysis",
                app_url=app_url,
                store=self._store,
            )
        return self._store.public(run, local=self._expose_local_paths)

    def run_statistics(self, item_id: str, run_id: str, payload: dict, app_url: str) -> dict:
        import uuid
        from ..services.statistical_tests import run_statistics, VERSION
        from ..analysis_core import fingerprint
        source = self._store.get(run_id)
        item = self._find_item(item_id)
        if not item or not source or source['item_id'] != item_id or source['status'] != 'completed':
            raise AnalysisCommandNotFound('対象の固定分析が見つかりません。')
        if not isinstance(payload, dict):
            raise ValueError('統計計画を指定してください。')
        dataset = payload.get('dataset')
        table = self._store.read_table(run_id, dataset)
        result = run_statistics(table, payload.get('variables'), payload.get('plan'))
        result['parameters'] = {'source_run_id': run_id, 'source_dataset': dataset,
            'source_table_hash': fingerprint(table), 'plan': result['plan'], 'variables': result['variable_catalog']}
        result['algorithms'] = {'planned_statistics': VERSION}
        result['methods'] = [{'method_id': 'planned_statistics', 'title': '固定表の統計分析',
            'status': result['results'][0]['status'], 'limitations': result['results'][0]['warnings'],
            'datasets': ['statistical_results', 'variable_catalog', 'statistical_input', 'statistical_omissions']}]
        snapshot = self._store.readable_package(run_id)[0]
        datasets = {
            'statistical_results': (list(result['results'][0]), result['results']),
            'variable_catalog': (list(result['variable_catalog'][0]), result['variable_catalog']),
            'statistical_input': (list(result['analysis_rows'][0]) if result['analysis_rows'] else table['fields'], result['analysis_rows']),
            'statistical_omissions': (['row_id','reason'], result['omissions']),
        }
        with self._write_lock:
            saved = self._store.save(item_id=item_id, kind='planned_statistics', snapshot=snapshot,
                result=result, datasets=datasets, request_id=payload.get('request_id') or uuid.uuid4().hex,
                input_fingerprint=source['input_fingerprint'], source_revision=source['source_revision'],
                analysis_revision=source['analysis_revision'], app_url=app_url, publish=False)
        return {'run': self._store.public(saved, local=self._expose_local_paths), 'statistics': result}

    def retry_vault(self, run_id: str) -> dict[str, Any]:
        run = self._store.get(run_id)
        if not run:
            raise AnalysisCommandNotFound("保存結果が見つかりません。")
        if run.get("kind") != "interview_comparison" and self._find_item(run["item_id"]) is None:
            raise AnalysisCommandNotFound("保存結果が見つかりません。")
        with self._write_lock:
            if run.get("kind") != "interview_comparison":
                item = self._find_item(run["item_id"])
                if item is None:
                    raise AnalysisCommandNotFound("対象の会話が見つかりません。")
                if run["input_fingerprint"] != self._source_fingerprint(item):
                    self._mark_stale(run_id)
            result = self._store.retry(run_id)
        return self._store.public(result, local=self._expose_local_paths)

    def save_preparation(
        self, item_id: str, payload: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Save reviewed transcript state and publish only its derived Vault index."""
        with self._write_lock, self._database_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            item = connection.execute(
                "SELECT * FROM library_items WHERE id=?", (item_id,)
            ).fetchone()
            if item is None:
                raise AnalysisCommandNotFound("データが見つかりません。")
            result = self._save_preparation_state(
                connection, item, self._segments_for_item(item), payload
            )

        self._refresh_archive_index(item_id)
        self._publish_input_vault(self._find_item(item_id))
        return result

    def update_item(self, item_id: str, payload: Any) -> dict[str, Any]:
        """Commit a transcript edit and publish its derived indexes under one lock."""
        with self._write_lock:
            result = self._update_library_item_locked(item_id, payload)
            self._refresh_archive_index(item_id)
            self._publish_input_vault(self._find_item(item_id))
            return result

    def start_insight(
        self, item_id: str, payload: dict[str, Any], *, app_url: str
    ) -> tuple[dict[str, Any], int]:
        return self._start_insights(item_id, payload, app_url=app_url)

    def cancel_insight(self, item_id: str, request_id: str) -> dict[str, Any]:
        return self._cancel_insights(item_id, request_id)

    def start_transformer(
        self, item_id: str, payload: dict[str, Any], *, app_url: str
    ) -> tuple[dict[str, Any], int]:
        return self._start_transformer(item_id, payload, app_url=app_url)

    def cancel_transformer(self, item_id: str, request_id: str) -> dict[str, Any]:
        return self._cancel_transformer(item_id, request_id)

    def run_classification(
        self, item_id: str, payload: dict[str, Any], *, app_url: str
    ) -> dict[str, Any]:
        return self._run_classification(item_id, payload, app_url=app_url)

    def pipeline_capabilities(self) -> dict[str, Any]:
        if self._pipeline is None:
            return {"version": "unavailable", "capabilities": {}}
        return self._pipeline.capabilities()

    def get_definition(self, item_id: str, definition_id: str) -> dict[str, Any]:
        if self._pipeline is None:
            raise AnalysisCommandRequestError("分析pipelineを利用できません。", 503)
        if self._find_item(item_id) is None:
            raise AnalysisCommandNotFound("対象の会話が見つかりません。")
        return self._pipeline.get_definition(item_id, definition_id)

    def save_definition(
        self, item_id: str, definition_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if self._pipeline is None:
            raise AnalysisCommandRequestError("分析pipelineを利用できません。", 503)
        if self._find_item(item_id) is None:
            raise AnalysisCommandNotFound("対象の会話が見つかりません。")
        return self._pipeline.save_definition(item_id, definition_id, payload)

    def trial_definition(
        self, item_id: str, definition_id: str, *, limit: int
    ) -> dict[str, Any]:
        if self._pipeline is None:
            raise AnalysisCommandRequestError("分析pipelineを利用できません。", 503)
        return self._pipeline.trial_definition(item_id, definition_id, limit=limit)

    def preview_pipeline(self, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._pipeline is None:
            raise AnalysisCommandRequestError("分析pipelineを利用できません。", 503)
        return self._pipeline.preview(item_id, payload)

    def propose_pipeline(self, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._pipeline is None:
            raise AnalysisCommandRequestError("分析pipelineを利用できません。", 503)
        return self._pipeline.propose(item_id, payload)

    def start_pipeline(
        self, item_id: str, payload: dict[str, Any], *, app_url: str
    ) -> tuple[dict[str, Any], int]:
        if self._pipeline is None:
            raise AnalysisCommandRequestError("分析pipelineを利用できません。", 503)
        return self._pipeline.start(item_id, payload, app_url=app_url)

    def pipeline_status(self, item_id: str, pipeline_id: str) -> dict[str, Any]:
        if self._pipeline is None:
            raise AnalysisCommandRequestError("分析pipelineを利用できません。", 503)
        return self._pipeline.status(item_id, pipeline_id)

    def cancel_pipeline(self, item_id: str, pipeline_id: str) -> dict[str, Any]:
        if self._pipeline is None:
            raise AnalysisCommandRequestError("分析pipelineを利用できません。", 503)
        return self._pipeline.cancel(item_id, pipeline_id)

    def retry_pipeline(
        self, item_id: str, pipeline_id: str, payload: dict[str, Any], *, app_url: str
    ) -> dict[str, Any]:
        if self._pipeline is None:
            raise AnalysisCommandRequestError("分析pipelineを利用できません。", 503)
        return self._pipeline.retry(item_id, pipeline_id, payload, app_url=app_url)

    def resume_pipeline(
        self, item_id: str, pipeline_id: str, payload: dict[str, Any], *, app_url: str
    ) -> dict[str, Any]:
        if self._pipeline is None:
            raise AnalysisCommandRequestError("分析pipelineを利用できません。", 503)
        return self._pipeline.resume(item_id, pipeline_id, payload, app_url=app_url)

    def save_comparison(
        self,
        payload: dict[str, Any],
        *,
        request_id: str,
        input_fingerprints: dict[str, Any],
        app_url: str,
    ) -> dict[str, Any]:
        """Recompute and save a comparison only for the displayed input versions."""
        with self._write_lock:
            items, allow_different = self._load_comparison_items(payload)
            selection = self._freeze_comparison(items, payload) if self._freeze_comparison else None
            if payload.get('target_snapshot_hash') and (selection is None or payload['target_snapshot_hash'] != selection['hash']):
                raise StoreConflict("属性・タグ・グループが更新されています。比較を再集計してください。")
            current = {
                str(item["id"]): self._source_fingerprint(item) for item in items
            }
            if input_fingerprints != current:
                raise StoreConflict(
                    "比較対象が更新されています。比較を再集計してから保存してください。"
                )
            comparison = self._build_comparison(
                items, allow_different_content=allow_different
            )
            if selection is not None:
                comparison['target_snapshot'] = selection
            run = self._archive_comparison(
                items,
                comparison,
                request_id,
                app_url=app_url,
                store=self._store,
            )
        return self._store.public(run, local=self._expose_local_paths)
