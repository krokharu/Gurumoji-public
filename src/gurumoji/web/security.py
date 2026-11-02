"""Request security for the local web UI.

Every request passes the before_request guard: trusted Host header, remote
authentication when remote access is enabled, cross-site and CSRF checks,
and per-endpoint body limits. Responses get cache and security headers, and
remote JSON responses have local filesystem paths removed (see
gurumoji.diagnostics)."""

from __future__ import annotations

import ipaddress
import json
import os
import secrets
import urllib.parse
from typing import Any, Callable

from flask import Flask, has_request_context, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from ..diagnostics import sanitize_remote_json_payload

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
UNSAFE_HTTP_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def request_hostname() -> str:
    try:
        return (urllib.parse.urlsplit(f"//{request.host}").hostname or "").casefold()
    except ValueError:
        return ""


def remote_addr_is_loopback() -> bool:
    raw = str(request.remote_addr or "").strip()
    try:
        return ipaddress.ip_address(raw).is_loopback
    except ValueError:
        return raw.casefold() == "localhost"


def bind_host_is_loopback(host: str) -> bool:
    normalized = host.strip().strip("[]").casefold()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def make_request_guards(
    *,
    remote_access_enabled: Callable[[], Any],
    remote_access_token: Callable[[], Any],
    remote_local_paths_enabled: Callable[[], Any],
) -> tuple[Callable[..., Any], ...]:
    def trusted_request_hosts() -> set[str]:
        hosts = set(LOOPBACK_HOSTS)
        if not remote_access_enabled():
            return hosts
        configured = os.environ.get("MOJIOKOSI_TRUSTED_HOSTS", "")
        hosts.update(value.strip().casefold() for value in configured.split(",") if value.strip())
        bind_host = os.environ.get("MOJIOKOSI_HOST", "127.0.0.1").strip().casefold()
        if bind_host and bind_host not in {"0.0.0.0", "::", "[::]", "*"}:
            hosts.add(bind_host.strip("[]"))
        return hosts

    def local_path_access_allowed() -> bool:
        if not has_request_context():
            return True
        if remote_access_enabled():
            # Authentication is enforced by before_request.  Remote filesystem
            # access remains unavailable unless the separate high-risk opt-in is set.
            return remote_local_paths_enabled()
        return remote_addr_is_loopback()

    def remote_auth_valid() -> bool:
        if not remote_access_enabled() or len(remote_access_token()) < 20:
            return not remote_access_enabled()
        supplied = ""
        header = request.headers.get("Authorization", "")
        if header.casefold().startswith("bearer "):
            supplied = header[7:].strip()
        elif request.authorization and request.authorization.type.casefold() == "basic":
            supplied = request.authorization.password or ""
        return bool(supplied) and secrets.compare_digest(supplied, remote_access_token())

    def request_origin_allowed(value: str) -> bool:
        try:
            parsed = urllib.parse.urlsplit(value)
        except ValueError:
            return False
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        configured = {
            item.strip().rstrip("/").casefold()
            for item in os.environ.get("MOJIOKOSI_ALLOWED_ORIGINS", "").split(",")
            if item.strip()
        }
        normalized = f"{parsed.scheme}://{parsed.netloc}".rstrip("/").casefold()
        if normalized in configured:
            return True
        try:
            expected = urllib.parse.urlsplit(request.host_url)
        except ValueError:
            return False
        try:
            return (
                parsed.scheme == expected.scheme
                and parsed.hostname.casefold() == (expected.hostname or "").casefold()
                and parsed.port == expected.port
            )
        except ValueError:
            return False

    return (
        trusted_request_hosts,
        local_path_access_allowed,
        remote_auth_valid,
        request_origin_allowed,
    )


def register_request_security(
    app: Flask,
    *,
    remote_access_enabled: Callable[[], bool],
    remote_access_token: Callable[[], str],
    remote_local_paths_enabled: Callable[[], bool],
    max_media_upload_bytes: Callable[[], int],
    max_csv_upload_bytes: Callable[[], int],
    max_json_request_bytes: Callable[[], int],
    multipart_overhead_bytes: int,
    is_colab_runtime: Callable[[], bool],
    trusted_request_hosts: Callable[[], set[str]],
    remote_auth_valid: Callable[[], bool],
    request_origin_allowed: Callable[[str], bool],
    admit_transcription_job: Callable[[], Any],
    release_job_admission: Callable[[], None],
) -> None:
    """Install the before/after-request hooks shared by every route.

    Upload limits are keyed on the endpoint names ``create_job`` and
    ``import_speaker_registry``; the route-map snapshot test keeps them
    stable. Transcription admission stays with the job runtime, which
    passes it in as ``admit_transcription_job``/``release_job_admission``.
    """

    def enforce_request_security():
        hostname = request_hostname()
        colab_loopback_proxy = is_colab_runtime() and remote_addr_is_loopback()
        if not hostname or (
            hostname not in trusted_request_hosts() and not colab_loopback_proxy
        ):
            return jsonify({"error": "Untrusted Host header."}), 400

        if remote_access_enabled() and not remote_auth_valid():
            response = jsonify({"error": "Authentication is required."})
            response.status_code = 401 if len(remote_access_token()) >= 20 else 503
            if response.status_code == 401:
                response.headers["WWW-Authenticate"] = 'Basic realm="Gurumoji", charset="UTF-8"'
            return response

        fetch_site = request.headers.get("Sec-Fetch-Site", "").casefold()
        if request.path.startswith("/api/") and fetch_site in {"cross-site", "same-site"}:
            return jsonify({"error": "Cross-origin request rejected."}), 403

        if request.method in UNSAFE_HTTP_METHODS:
            origin = request.headers.get("Origin", "")
            referer = request.headers.get("Referer", "")
            # Fetch Metadata is authoritative for browser requests and remains correct
            # when Colab/tunnel reverse proxies rewrite Host before Flask sees it.
            if fetch_site != "same-origin" and origin and not request_origin_allowed(origin):
                return jsonify({"error": "Invalid request origin."}), 403
            if fetch_site != "same-origin" and not origin and referer and not request_origin_allowed(referer):
                return jsonify({"error": "Invalid request referrer."}), 403
            browser_markers = bool(origin or referer or fetch_site)
            if request.headers.get("X-Gurumoji-Request") != "1" and (
                remote_access_enabled() or browser_markers or not remote_addr_is_loopback()
            ):
                return jsonify({"error": "Missing CSRF request header."}), 403

        csv_limit = max_csv_upload_bytes() + multipart_overhead_bytes
        media_limit = max_media_upload_bytes() + multipart_overhead_bytes
        json_limit = max_json_request_bytes()
        if request.endpoint == "import_speaker_registry":
            request.max_content_length = csv_limit
        elif request.endpoint == "create_job":
            request.max_content_length = media_limit
        elif request.is_json:
            request.max_content_length = json_limit

        length = request.content_length
        if length is not None:
            if request.endpoint == "import_speaker_registry" and length > csv_limit:
                raise RequestEntityTooLarge()
            if request.endpoint == "create_job" and length > media_limit:
                raise RequestEntityTooLarge()
            if request.is_json and length > json_limit:
                raise RequestEntityTooLarge()

        if request.endpoint == "create_job" and request.method == "POST":
            return admit_transcription_job()
        return None

    def request_too_large(_error):
        return jsonify({"error": "Request body exceeds the configured size limit."}), 413

    def disable_development_cache(response):
        release_job_admission()
        if request.path == "/" or request.path.startswith(("/static/", "/api/")):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        if remote_access_enabled() and not remote_local_paths_enabled() and response.is_json:
            # send_file uses direct passthrough. Consume its JSON before applying
            # the same privacy boundary as ordinary API JSON, including downloads.
            if response.status_code == 206:
                response.close()
                response.status_code = 416
                response.headers.pop("Content-Range", None)
                response.set_data(json.dumps({"error": "JSONの部分取得には対応していません。"}))
            response.direct_passthrough = False
            payload = response.get_json(silent=True)
            if payload is not None:
                sanitized = sanitize_remote_json_payload(payload)
                if sanitized != payload:
                    response.set_data(json.dumps(sanitized, ensure_ascii=False, separators=(",", ":")))
                    response.headers["Content-Type"] = "application/json"
                    response.headers.pop("ETag", None)
                    response.headers.pop("Last-Modified", None)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        frame_ancestors = "'none'"
        if is_colab_runtime():
            frame_ancestors = "https://colab.research.google.com https://*.research.google.com"
        else:
            response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; "
            f"object-src 'none'; base-uri 'self'; frame-ancestors {frame_ancestors}",
        )
        return response

    app.before_request(enforce_request_security)
    app.register_error_handler(RequestEntityTooLarge, request_too_large)
    app.after_request(disable_development_cache)
