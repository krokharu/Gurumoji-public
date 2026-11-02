"""Speaker registry use cases, independent from Flask."""

from __future__ import annotations

import re
from typing import Any, Callable


class SpeakerRegistryConflictError(RuntimeError):
    def __init__(self, current_revision: int):
        super().__init__(
            "The speaker registry was changed in another tab. Reload before saving again."
        )
        self.current_revision = current_revision


class SpeakerIdentificationRequestError(RuntimeError):
    def __init__(
        self,
        message: str,
        status: int,
        *,
        current_revision: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.current_revision = current_revision


class SpeakerIdentificationHandler:
    """Run one synchronous speaker-identification use case without Flask."""

    def __init__(self, run_identification: Callable[..., dict[str, Any]]) -> None:
        self._run_identification = run_identification

    def run(
        self, item_id: str, *, provider: str, expected_revision: int
    ) -> dict[str, Any]:
        return self._run_identification(
            item_id, provider=provider, expected_revision=expected_revision
        )


def parse_registry_revision(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("registry_revision must be a non-negative integer.")
    if isinstance(value, int):
        revision = value
    elif isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip()):
        revision = int(value.strip())
    else:
        raise ValueError("registry_revision must be a non-negative integer.")
    if revision < 0:
        raise ValueError("registry_revision must be a non-negative integer.")
    return revision


class SpeakerRegistryHandler:
    """Read and update the global speaker registry under its shared lock."""

    def __init__(
        self,
        *,
        snapshot: Callable[..., tuple[list[dict[str, Any]], int]],
        save_records_locked: Callable[..., tuple[list[dict[str, Any]], int]],
        database_connection: Callable[[], Any],
        refresh_archive_index: Callable[[str], None],
        write_lock: Any,
    ) -> None:
        self._snapshot = snapshot
        self._save_records_locked = save_records_locked
        self._database_connection = database_connection
        self._refresh_archive_index = refresh_archive_index
        self._write_lock = write_lock

    def list(self, *, include_inactive: bool = True) -> dict[str, Any]:
        records, revision = self._snapshot(include_inactive=include_inactive)
        return {
            "speakers": records,
            "total": len(records),
            "registry_revision": revision,
        }

    def save(
        self,
        records: Any,
        *,
        delete_ids: Any = None,
        expected_revision: int | None = None,
        merge_by_participant_code: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        with self._write_lock:
            result = self._save_records_locked(
                records,
                delete_ids=delete_ids,
                expected_revision=expected_revision,
                merge_by_participant_code=merge_by_participant_code,
            )
            with self._database_connection() as connection:
                items = connection.execute(
                    "SELECT DISTINCT item_id FROM analysis_runs "
                    "WHERE status='completed'"
                ).fetchall()
            for item in items:
                self._refresh_archive_index(str(item[0]))
            return result
