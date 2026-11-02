"""HTTP adapters for application settings and system status."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Callable

from flask import Flask, jsonify, render_template, request

from ..services.transcription_readiness import transcription_readiness


def register_system_routes(
    app: Flask,
    *,
    app_name: str,
    product_name: str,
    app_version: str,
    app_creator: str,
    token_file: Callable[[], Path],
    default_output_directory: Callable[[], Path],
    runtime_info: Callable[[], dict[str, Any]],
    local_llm_label: Callable[[], str],
    local_llm_short_label: Callable[[], str],
    get_machine_profile: Callable[[], dict[str, Any]],
    load_token_config: Callable[[Path], Any],
    lmstudio_connection_status: Callable[[Any], dict[str, Any]],
    local_path_access_allowed: Callable[[], bool],
    load_custom_vocabulary: Callable[[], tuple[str, ...]],
    save_custom_vocabulary: Callable[[Any], tuple[str, ...]],
    available_ai_models: Callable[[str, Any], list[dict[str, Any]]],
    update_token_model: Callable[[Any, Any, Path], Any],
    system_activity_snapshot: Callable[[], dict[str, Any]],
    obsidian_watcher_status: Callable[[], dict[str, Any]] = lambda: {},
    create_backup: Callable[[bool], dict[str, Any]] | None = None,
    library_diagnostics: Callable[[], dict[str, Any]] = lambda: {},
    media_metadata_status: Callable[[], dict[str, Any]] = lambda: {},
) -> None:
    def index() -> str:
        runtime = runtime_info()
        return render_template(
            "index.html",
            app_name=app_name,
            product_name=product_name,
            app_version=app_version,
            app_creator=app_creator,
            runtime=runtime,
            local_llm_label=local_llm_label(),
            local_llm_short_label=local_llm_short_label(),
        )

    def watcher_public() -> dict[str, Any]:
        status = dict(obsidian_watcher_status())
        if not local_path_access_allowed():
            # Exception text can name local paths; remote viewers get the summary only.
            status.pop("detail", None)
        return status

    def api_config():
        machine = get_machine_profile()
        try:
            config = load_token_config(token_file())
            lmstudio_status = lmstudio_connection_status(config)
            return jsonify({
                "ok": True,
                **config.availability(),
                "lmstudio": lmstudio_status["reachable"],
                "lmstudio_status": lmstudio_status,
                "default_output_dir": str(default_output_directory()) if local_path_access_allowed() else "",
                "machine": machine,
                "transcription_readiness": transcription_readiness(),
                "runtime": runtime_info(),
                "obsidian_watcher": watcher_public(),
            })
        except RuntimeError as exc:
            return jsonify({
                "ok": False,
                "error": str(exc),
                "token_file": token_file().name,
                "machine": machine,
                "runtime": runtime_info(),
                "obsidian_watcher": watcher_public(),
            }), 500

    def api_custom_vocabulary():
        return jsonify({"terms": list(load_custom_vocabulary())})

    def api_update_custom_vocabulary():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "単語登録の内容が JSON ではありません。"}), 400
        try:
            terms = save_custom_vocabulary(payload.get("terms"))
            return jsonify({
                "ok": True,
                "terms": list(terms),
                "message": f"{len(terms)}語を単語登録しました。",
            })
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except OSError as exc:
            return jsonify({"error": f"単語登録を保存できません: {exc}"}), 500

    def api_ai_models():
        provider = str(request.args.get("provider") or "").strip().casefold()
        try:
            config = load_token_config(token_file())
            models = available_ai_models(provider, config)
            selected = {
                "openai": config.openai_model,
                "google": config.google_model,
                "lmstudio": config.lmstudio_model,
            }.get(provider, "")
            return jsonify({
                "provider": provider,
                "selected_model": selected,
                "models": models,
                "source": token_file().name,
            })
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 502

    def api_update_ai_model():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "モデル設定が JSON ではありません。"}), 400
        try:
            config = update_token_model(
                payload.get("provider"),
                payload.get("model"),
                token_file(),
            )
            return jsonify({
                "ok": True,
                **config.availability(),
                "message": f"{token_file().name} のモデル設定を更新しました。",
            })
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (OSError, RuntimeError) as exc:
            return jsonify({"error": str(exc)}), 500

    def api_system_activity():
        result = {"ok": True, **system_activity_snapshot(), "media_metadata": media_metadata_status()}
        if request.args.get("library_check") == "1":
            result["library_projection"] = library_diagnostics()
        return jsonify(result)

    def api_create_backup():
        # The backup is written on this PC; only its own browser may start one.
        if create_backup is None or not local_path_access_allowed():
            return jsonify({"error": "バックアップは保存PCから作成してください。"}), 403
        payload = request.get_json(silent=True)
        payload = payload if isinstance(payload, dict) else {}
        try:
            result = create_backup(payload.get("include_media") is True)
        except (OSError, ValueError, sqlite3.Error) as exc:
            return jsonify({"error": f"バックアップを作成できませんでした: {exc}"}), 500
        return jsonify({
            "ok": True, "path": str(result["path"]), "file_count": result["file_count"],
            "total_bytes": result["total_bytes"], "include_media": result["include_media"],
            "excluded": result["excluded"],
        })

    # Keep established endpoint names for compatibility and security hooks.
    endpoints = (
        ("/", "index", index, "GET"),
        ("/api/config", "api_config", api_config, "GET"),
        ("/api/custom-vocabulary", "api_custom_vocabulary", api_custom_vocabulary, "GET"),
        ("/api/custom-vocabulary", "api_update_custom_vocabulary", api_update_custom_vocabulary, "PUT"),
        ("/api/ai/models", "api_ai_models", api_ai_models, "GET"),
        ("/api/ai/model", "api_update_ai_model", api_update_ai_model, "PUT"),
        ("/api/system/activity", "api_system_activity", api_system_activity, "GET"),
        ("/api/system/backup", "api_create_backup", api_create_backup, "POST"),
    )
    for rule, endpoint, view, method in endpoints:
        app.add_url_rule(rule, endpoint, view, methods=[method])
