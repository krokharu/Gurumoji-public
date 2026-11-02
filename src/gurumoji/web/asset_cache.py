"""静的素材の内容が変わったときだけブラウザーに再取得させる。"""

from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from pathlib import Path

from flask import Flask, request


def register_asset_cache(app: Flask) -> None:
    root = Path(app.static_folder).resolve()

    @lru_cache(maxsize=512)
    def fingerprint(filename: str, modified: int, size: int) -> str:
        return sha256((root / filename).read_bytes()).hexdigest()[:16]

    def version(filename: str) -> str | None:
        path = (root / filename).resolve()
        if not path.is_relative_to(root):
            return None
        try:
            stat = path.stat()
            if not path.is_file():
                return None
            return fingerprint(filename, stat.st_mtime_ns, stat.st_size)
        except OSError:
            return None

    @app.url_defaults
    def static_version(endpoint: str, values: dict) -> None:
        if endpoint == "static" and isinstance(values.get("filename"), str):
            current = version(values["filename"])
            if current:
                values.setdefault("v", current)

    @app.after_request
    def cache_versioned_asset(response):
        # API・利用者データ・版指定のない素材には長期キャッシュを適用しない。
        if request.endpoint == "static" and response.status_code in (200, 206, 304):
            filename = (request.view_args or {}).get("filename", "")
            supplied = request.args.get("v")
            if supplied and supplied == version(filename):
                response.headers["Cache-Control"] = (
                    "public, max-age=31536000, immutable"
                )
        return response
