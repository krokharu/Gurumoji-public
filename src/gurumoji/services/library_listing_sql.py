"""通常の一覧ページをSQLiteで絞り、表示分だけPythonへ渡す。"""

from __future__ import annotations

import json
from .library_rows import emotion_values
from .transcription.segments import default_speaker_name
from ..text_utils import json_load

# 不正なJSONや配列以外の旧データは、従来と同じ空の発話一覧として扱う。
SEGMENTS = """CASE WHEN json_valid(i.segments_json)
    THEN CASE WHEN json_type(i.segments_json)='array' THEN i.segments_json ELSE '[]' END
    ELSE '[]' END"""
SEGMENT = "CASE WHEN j.type='object' THEN j.value ELSE '{}' END"
FOLDERS = """SELECT g.id, g.name, g.created_at, g.updated_at, COUNT(items.id) AS item_count
    FROM library_groups AS g LEFT JOIN library_items AS items ON items.group_id=g.id
    GROUP BY g.id, g.name, g.created_at, g.updated_at
    ORDER BY g.name COLLATE NOCASE, g.created_at"""
ITEMS = """SELECT i.*, m.duration_seconds AS media_duration_seconds,
    m.media_created_at AS media_created_at FROM library_items i
    LEFT JOIN media_assets m ON m.item_id=i.id AND m.role='stored'"""


def facets(connection):
    # 必要な話者・感情だけを一度で射影し、重複はDB側で除く。
    # 複数パスのjson_extractは型を保持するため、旧形式の真偽値等も失わない。
    speakers, emotions = set(), set()
    for row in connection.execute(f"""SELECT DISTINCT i.speaker_names_json,
        json_extract({SEGMENT}, '$.speaker', '$.emotions') AS display_values
        FROM library_items i, json_each({SEGMENTS}) j"""):
        label, source = json.loads(row["display_values"])
        if label:
            names = json_load(row["speaker_names_json"], {})
            if not isinstance(names, dict):
                names = {}
            speakers.add(str(names.get(str(label)) or default_speaker_name(label)))
        emotions.update(emotion_values({"emotions": source}))
    return sorted(speakers), sorted(emotions)


def folders(connection):
    return [
        {
            "id": str(row["id"]),
            "name": str(row["name"]),
            "item_count": int(row["item_count"] or 0),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in connection.execute(FOLDERS)
    ]


def native_page(connection, *, order, limit, offset, catalog, library_public):
    groups = folders(connection)
    names = {group["id"]: group["name"] for group in groups}
    speakers, emotions = facets(connection)
    total = connection.execute("SELECT COUNT(*) FROM library_items").fetchone()[0]
    rows = connection.execute(
        ITEMS + " ORDER BY " + order + " LIMIT ? OFFSET ?", (limit, offset)
    ).fetchall()
    items = []
    for row in rows:
        source = json_load(row["segments_json"], [])
        segments = (
            [item for item in source if isinstance(item, dict)]
            if isinstance(source, list)
            else []
        )
        items.append(
            library_public(
                row,
                full=False,
                match_count=0,
                group_name=names.get(str(row["group_id"] or ""), ""),
                segments=segments,
            )
        )
    return {
        "items": items,
        "total": total,
        "pagination": {
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(rows) < total,
        },
        "groups": groups,
        "data_groups": catalog["groups"],
        "tags": catalog["tags"],
        "facets": {"speakers": speakers, "emotions": emotions, "groups": groups},
    }
