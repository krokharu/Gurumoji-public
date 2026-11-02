"""会話一覧の読取・条件検査・表示用ページをHTTPから独立して組み立てる。"""

from __future__ import annotations

import datetime
import math
import sqlite3
from typing import Any
from . import data_catalog
from .library_listing_sql import native_page
from .library_rows import emotion_values
from .transcription.segments import default_speaker_name
from ..text_utils import json_load

# 値は固定したSQL断片だけを許可し、利用者の入力はSQLへ連結しない。
NATIVE_SORTS = {
    "updated_desc": "i.updated_at DESC, i.rowid",
    "created_desc": "i.created_at DESC, i.updated_at DESC, i.rowid",
    "recorded_desc": "m.media_created_at IS NOT NULL DESC, m.media_created_at DESC, i.updated_at DESC, i.rowid",
    "media_duration_desc": "m.duration_seconds IS NOT NULL DESC, m.duration_seconds DESC, i.updated_at DESC, i.rowid",
}


def list_library_items(query, *, database_connection, library_public):
    try:
        page_limit = int(query.get("limit", 0))
        page_offset = int(query.get("offset", 0))
        if not 0 <= page_limit <= 200 or not 0 <= page_offset <= 2**63 - 1:
            raise ValueError()
    except (ValueError, OverflowError):
        return ({"error": "一覧のページ指定が正しくありません。"}, 400)
    keyword = query.get("keyword", "").strip().casefold()
    speaker_filter = query.get("speaker", "").strip().casefold()
    emotion_filter = query.get("emotion", "").strip().casefold()
    group_filter = query.get("group", "").strip()
    sort_key = query.get("sort", "updated_desc").strip()
    date_from = query.get("recorded_from", "").strip()
    date_to = query.get("recorded_to", "").strip()
    try:
        duration_min = (
            float(query["media_duration_min"])
            if query.get("media_duration_min")
            else None
        )
        duration_max = (
            float(query["media_duration_max"])
            if query.get("media_duration_max")
            else None
        )
        for value in (duration_min, duration_max):
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError
        for value in (date_from, date_to):
            if value:
                datetime.date.fromisoformat(value)
        if date_from and date_to and (date_from > date_to):
            raise ValueError
        if (
            duration_min is not None
            and duration_max is not None
            and (duration_min > duration_max)
        ):
            raise ValueError
    except ValueError:
        return ({"error": "収録日・メディアの長さの条件を確認してください。"}, 400)
    selected_group = query.get("data_group", "")
    selected_tag = query.get("tag", "")
    use_native_page = (
        page_limit
        and sort_key in NATIVE_SORTS
        and not any(
            (
                keyword,
                speaker_filter,
                emotion_filter,
                group_filter,
                selected_group,
                selected_tag,
                date_from,
                date_to,
            )
        )
        and duration_min is None
        and duration_max is None
    )
    with database_connection() as connection:
        # 一覧が使わない会話ごとの属性・タグ照会を発行しない。
        catalog = data_catalog.catalog(connection, include_items=not use_native_page)
        try:
            selected_members = (
                set(data_catalog.members(connection, selected_group))
                if selected_group
                else None
            )
        except LookupError as exc:
            return ({"error": str(exc)}, 404)
        # 通常のページ表示では全会話の本文をPythonへ展開しない。
        if use_native_page:
            return native_page(
                connection,
                order=NATIVE_SORTS[sort_key],
                limit=page_limit,
                offset=page_offset,
                catalog=catalog,
                library_public=library_public,
            ), 200
        catalog_items = {item["id"]: item for item in catalog["items"]}
        order = NATIVE_SORTS.get(sort_key, NATIVE_SORTS["updated_desc"])
        rows = connection.execute(
            """SELECT i.*, m.duration_seconds AS media_duration_seconds,
            m.media_created_at AS media_created_at FROM library_items i
            LEFT JOIN media_assets m ON m.item_id=i.id AND m.role='stored'
            ORDER BY """
            + order
        ).fetchall()
        group_rows = connection.execute(
            "\n                SELECT g.id, g.name, g.created_at, g.updated_at,\n                       COUNT(items.id) AS item_count\n                FROM library_groups AS g\n                LEFT JOIN library_items AS items ON items.group_id = g.id\n                GROUP BY g.id, g.name, g.created_at, g.updated_at\n                ORDER BY g.name COLLATE NOCASE, g.created_at\n                "
        ).fetchall()
    groups = [
        {
            "id": str(row["id"]),
            "name": str(row["name"]),
            "item_count": int(row["item_count"] or 0),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in group_rows
    ]
    group_names = {group["id"]: group["name"] for group in groups}
    all_speakers: set[str] = set()
    all_emotions: set[str] = set()
    candidates: list[
        tuple[sqlite3.Row, int, list[dict[str, Any]], list[str], str, list[str]]
    ] = []
    for row in rows:
        recording_date = str(row["media_created_at"] or "")[:10]
        duration = row["media_duration_seconds"]
        if (date_from or date_to) and (
            not recording_date
            or (date_from and recording_date < date_from)
            or (date_to and recording_date > date_to)
        ):
            continue
        if (duration_min is not None or duration_max is not None) and (
            duration is None
            or (duration_min is not None and duration < duration_min)
            or (duration_max is not None and duration > duration_max)
        ):
            continue
        raw_segments = json_load(row["segments_json"], [])
        segments = (
            [item for item in raw_segments if isinstance(item, dict)]
            if isinstance(raw_segments, list)
            else []
        )
        names = json_load(row["speaker_names_json"], {})
        if not isinstance(names, dict):
            names = {}
        speakers = sorted(
            {
                str(
                    names.get(str(item.get("speaker") or ""))
                    or default_speaker_name(item.get("speaker"))
                )
                for item in segments
                if item.get("speaker")
            }
        )
        emotions = sorted(
            {value for item in segments for value in emotion_values(item)}
        )
        all_speakers.update(speakers)
        all_emotions.update(emotions)
        searchable_segments = [str(item.get("text") or "") for item in segments]
        match_count = sum(
            (
                1
                for text_value in searchable_segments
                if keyword and keyword in text_value.casefold()
            )
        )
        source_match = bool(keyword and keyword in str(row["source_name"]).casefold())
        if keyword and (not match_count) and (not source_match):
            continue
        if speaker_filter and (
            not any((speaker_filter == value.casefold() for value in speakers))
        ):
            continue
        if emotion_filter and (
            not any((emotion_filter == value.casefold() for value in emotions))
        ):
            continue
        row_group_id = str(row["group_id"] or "")
        if selected_members is not None and row["id"] not in selected_members:
            continue
        if selected_tag and selected_tag not in catalog_items[row["id"]]["tag_ids"]:
            continue
        if group_filter == "__ungrouped__" and row_group_id:
            continue
        if (
            group_filter
            and group_filter != "__ungrouped__"
            and (row_group_id != group_filter)
        ):
            continue
        candidates.append(
            (
                row,
                match_count,
                segments,
                emotions,
                group_names.get(row_group_id, ""),
                speakers,
            )
        )
    if sort_key in NATIVE_SORTS or sort_key not in (
        "speaker",
        "emotion",
        "keyword",
        "name",
        "group",
    ):
        pass
    elif sort_key == "speaker":
        candidates.sort(
            key=lambda item: (
                item[5][0] if item[5] else "\uffff",
                item[0]["updated_at"],
            )
        )
    elif sort_key == "emotion":
        candidates.sort(
            key=lambda item: (
                item[3][0] if item[3] else "\uffff",
                item[0]["updated_at"],
            )
        )
    elif sort_key == "keyword":
        candidates.sort(key=lambda item: (item[1], item[0]["updated_at"]), reverse=True)
    elif sort_key == "name":
        candidates.sort(key=lambda item: str(item[0]["source_name"]).casefold())
    elif sort_key == "group":
        candidates.sort(
            key=lambda item: (
                not bool(item[4]),
                item[4].casefold(),
                str(item[0]["source_name"]).casefold(),
            )
        )
    else:
        candidates.sort(key=lambda item: item[0]["updated_at"], reverse=True)
    total = len(candidates)
    page_candidates = (
        candidates[page_offset : page_offset + page_limit] if page_limit else candidates
    )
    return (
        {
            "items": [
                library_public(
                    row,
                    full=False,
                    match_count=count,
                    group_name=group_name,
                    segments=segments,
                )
                for row, count, segments, _, group_name, _ in page_candidates
            ],
            "total": total,
            "pagination": {
                "offset": page_offset,
                "limit": page_limit or total,
                "has_more": bool(
                    page_limit and page_offset + len(page_candidates) < total
                ),
            },
            "groups": groups,
            "data_groups": catalog["groups"],
            "tags": catalog["tags"],
            "facets": {
                "speakers": sorted(all_speakers),
                "emotions": sorted(all_emotions),
                "groups": groups,
            },
        },
        200,
    )
