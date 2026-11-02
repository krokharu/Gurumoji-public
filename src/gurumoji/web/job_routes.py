"""HTTP adapters for transcription job operations."""

from __future__ import annotations

import sqlite3
import subprocess
from typing import Callable

from flask import Flask, g, jsonify, request, send_file

from ..handlers.analysis_commands import TranscriptConflictError
from ..handlers.jobs import JobHandler, JobRequestError


def register_job_routes(app: Flask, handler: Callable[[], JobHandler]) -> None:
    def create_job():
        try:
            body, status = handler().start(
                request.form,
                request.files.get("input_file"),
                admission_id=getattr(g, "job_admission_id", None),
            )
            return jsonify(body), status
        except JobRequestError as exc:
            return jsonify({"error": str(exc), **exc.details}), exc.status

    def get_job(job_id: str):
        try:
            body, status = handler().get(job_id)
            return jsonify(body), status
        except JobRequestError as exc:
            return jsonify({"error": str(exc), **exc.details}), exc.status

    def get_active_job():
        return jsonify(handler().active())

    def cancel_job(job_id: str):
        try:
            return jsonify(handler().cancel(job_id))
        except JobRequestError as exc:
            return jsonify({"error": str(exc), **exc.details}), exc.status

    def save_transcript(job_id: str):
        try:
            return jsonify(handler().save_transcript(
                job_id, request.get_json(silent=True)
            ))
        except JobRequestError as exc:
            return jsonify({"error": str(exc), **exc.details}), exc.status
        except TranscriptConflictError as exc:
            return jsonify({
                "error": str(exc),
                "conflict": True,
                "current_revision": exc.current_revision,
            }), 409
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (OSError, sqlite3.Error, subprocess.SubprocessError) as exc:
            return jsonify({"error": f"ファイルを保存できません: {exc}"}), 500

    def download_file(job_id: str, filename: str):
        try:
            artifact = handler().artifact(job_id, filename)
            return send_file(
                artifact.path,
                as_attachment=True,
                download_name=artifact.download_name,
            )
        except JobRequestError as exc:
            return jsonify({"error": str(exc), **exc.details}), exc.status

    # Keep the established endpoint names because the global admission/security
    # hooks and compatibility tests intentionally resolve them by endpoint.
    app.add_url_rule("/api/jobs", "create_job", create_job, methods=["POST"])
    app.add_url_rule("/api/jobs/<job_id>", "get_job", get_job, methods=["GET"])
    app.add_url_rule(
        "/api/jobs/active", "get_active_job", get_active_job, methods=["GET"]
    )
    app.add_url_rule(
        "/api/jobs/<job_id>/cancel", "cancel_job", cancel_job, methods=["POST"]
    )
    app.add_url_rule(
        "/api/jobs/<job_id>/transcript",
        "save_transcript",
        save_transcript,
        methods=["PUT"],
    )
    app.add_url_rule(
        "/api/jobs/<job_id>/files/<path:filename>",
        "download_file",
        download_file,
        methods=["GET"],
    )
