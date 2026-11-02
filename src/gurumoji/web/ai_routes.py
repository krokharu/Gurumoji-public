"""HTTP adapters for local-LLM settings."""

from __future__ import annotations

from typing import Any

from flask import Flask, jsonify


def register_ai_routes(
    app: Flask,
    *,
    lmstudio_reasoning_settings: Any,
    load_token_config: Any,
) -> None:
    def lmstudio_reasoning_route():
        config = load_token_config()
        return jsonify({'model': config.lmstudio_model, 'reasoning': lmstudio_reasoning_settings(
            config.lmstudio_base_url, config.lmstudio_api_key, config.lmstudio_model)})

    # Keep established endpoint names: the security hook and the
    # route-map snapshot depend on them.
    endpoints = (
        ('/api/ai/lmstudio-reasoning', 'lmstudio_reasoning_route', lmstudio_reasoning_route, 'GET'),
    )
    for rule, endpoint, view, method in endpoints:
        app.add_url_rule(rule, endpoint, view, methods=[method])
