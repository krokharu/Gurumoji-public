"""公開版のWebアプリケーションを組み立てる。"""

from __future__ import annotations

from types import ModuleType
from flask import Flask
from .assets import application_scripts, application_styles
from .asset_cache import register_asset_cache


def build_application(core: ModuleType) -> Flask:
    """公開版の設定・セキュリティ・HTTPルートを一か所で組み立てる。"""
    flask_app = core.Flask(
        core.__name__, template_folder="templates", static_folder="static"
    )
    register_asset_cache(flask_app)
    flask_app.config["JSON_AS_ASCII"] = False
    flask_app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    flask_app.config["MAX_CONTENT_LENGTH"] = (
        core.MAX_MEDIA_UPLOAD_BYTES + core.MULTIPART_OVERHEAD_BYTES
    )
    from .notation_routes import register_notation_routes

    register_notation_routes(flask_app, service=core.notation_workflows)
    from .transcript_routes import register_transcript_routes

    register_transcript_routes(
        flask_app,
        update_item=core.update_library_from_payload,
        connect=core.database_connection,
        write_lock=core.library_write_lock,
        row_segments=core.row_segments,
    )
    core.register_request_security(
        flask_app,
        remote_access_enabled=lambda: core.REMOTE_ACCESS_ENABLED,
        remote_access_token=lambda: core.REMOTE_ACCESS_TOKEN,
        remote_local_paths_enabled=lambda: core.REMOTE_LOCAL_PATHS_ENABLED,
        max_media_upload_bytes=lambda: core.MAX_MEDIA_UPLOAD_BYTES,
        max_csv_upload_bytes=lambda: core.MAX_CSV_UPLOAD_BYTES,
        max_json_request_bytes=lambda: core.MAX_JSON_REQUEST_BYTES,
        multipart_overhead_bytes=core.MULTIPART_OVERHEAD_BYTES,
        is_colab_runtime=core.is_colab_runtime,
        trusted_request_hosts=core.trusted_request_hosts,
        remote_auth_valid=lambda: core.remote_auth_valid(),
        request_origin_allowed=core.request_origin_allowed,
        admit_transcription_job=core.admit_transcription_job,
        release_job_admission=core.release_job_admission,
    )
    core.register_system_routes(
        flask_app,
        app_name=core.APP_NAME,
        product_name=core.PRODUCT_NAME,
        app_version=core.APP_VERSION,
        app_creator=core.APP_CREATOR,
        token_file=lambda: core.TOKEN_FILE,
        default_output_directory=lambda: core.DEFAULT_OUTPUT_DIRECTORY,
        runtime_info=core.runtime_info,
        local_llm_label=core.local_llm_label,
        local_llm_short_label=core.local_llm_short_label,
        get_machine_profile=lambda: core.get_machine_profile(),
        load_token_config=lambda path: core.load_token_config(path),
        lmstudio_connection_status=core.lmstudio_connection_status,
        local_path_access_allowed=core.local_path_access_allowed,
        load_custom_vocabulary=core.load_custom_vocabulary,
        save_custom_vocabulary=core.save_custom_vocabulary,
        available_ai_models=lambda provider, config: core.available_ai_models(
            provider, config
        ),
        update_token_model=lambda provider, model, path: core.update_token_model(
            provider, model, path
        ),
        system_activity_snapshot=lambda: core.system_activity_snapshot(),
        library_diagnostics=core.library_storage_diagnostics,
        media_metadata_status=lambda: core.media_metadata_backfill.snapshot(),
        create_backup=lambda include_media: core.create_data_backup(include_media),
    )
    core.register_speaker_routes(
        flask_app,
        core.speaker_registry_handler,
        core.speaker_identification_handler,
        core.AI_MODEL_PROVIDERS,
        core.import_speaker_registry_csv,
        core.read_upload_limited,
        lambda: core.MAX_CSV_UPLOAD_BYTES,
    )
    core.register_outline_routes(
        flask_app, core.outline_rerun_handler, core.AI_MODEL_PROVIDERS
    )
    core.register_job_routes(flask_app, core.job_handler)
    core.register_library_group_routes(
        flask_app,
        database_connection=lambda *args, **kwargs: core.database_connection(
            *args, **kwargs
        ),
        library_write_lock=core.library_write_lock,
    )
    core.register_training_routes(
        flask_app,
        remote_access_enabled=lambda: core.REMOTE_ACCESS_ENABLED,
        database_connection=lambda *args, **kwargs: core.database_connection(
            *args, **kwargs
        ),
        refresh_training_exports=core.refresh_training_exports,
        training_events_from_connection=lambda *args,
        **kwargs: core.training_events_from_connection(*args, **kwargs),
    )
    core.register_export_routes(
        flask_app,
        database_connection=lambda *args, **kwargs: core.database_connection(
            *args, **kwargs
        ),
        library_row=lambda *args, **kwargs: core.library_row(*args, **kwargs),
        list_speaker_registry=core.list_speaker_registry,
        meeting_minutes_export_row=core.meeting_minutes_export_row,
        row_segments=lambda *args, **kwargs: core.row_segments(*args, **kwargs),
        row_session_profile=lambda *args, **kwargs: core.row_session_profile(
            *args, **kwargs
        ),
        row_speaker_profiles=lambda *args, **kwargs: core.row_speaker_profiles(
            *args, **kwargs
        ),
    )
    core.register_ai_routes(
        flask_app,
        lmstudio_reasoning_settings=lambda *args,
        **kwargs: core.lmstudio_reasoning_settings(*args, **kwargs),
        load_token_config=lambda *args, **kwargs: core.load_token_config(
            *args, **kwargs
        ),
    )
    core.register_library_routes(
        flask_app,
        media_directory=lambda: core.MEDIA_DIRECTORY,
        _delete_library_item_locked=core._delete_library_item_locked,
        database_connection=lambda *args, **kwargs: core.database_connection(
            *args, **kwargs
        ),
        file_dialog_lock=core.file_dialog_lock,
        generate_video_thumbnail=lambda *args, **kwargs: core.generate_video_thumbnail(
            *args, **kwargs
        ),
        library_public=core.library_public,
        library_row=lambda *args, **kwargs: core.library_row(*args, **kwargs),
        library_write_lock=core.library_write_lock,
        local_path_access_allowed=core.local_path_access_allowed,
        manual_output_directory=core.manual_output_directory,
        resolve_local_media_path=lambda *args, **kwargs: core.resolve_local_media_path(
            *args, **kwargs
        ),
        row_segments=lambda *args, **kwargs: core.row_segments(*args, **kwargs),
        runtime_info=core.runtime_info,
        upsert_library_item=lambda *args, **kwargs: core.upsert_library_item(
            *args, **kwargs
        ),
        list_library_trash=lambda: core.list_library_trash(),
        restore_library_trash=lambda entry_id: core.restore_library_trash(entry_id),
        purge_library_trash=lambda entry_id: core.purge_library_trash(entry_id),
    )

    flask_app.jinja_env.globals.update(
        application_scripts=application_scripts(),
        application_styles=application_styles(),
    )
    return flask_app
