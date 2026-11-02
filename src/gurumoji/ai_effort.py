"""Per-operation reasoning settings, kept explicit and isolated between jobs."""
STAGES = ("outline", "cleanup", "name_extract", "name_verify", "notation")
# ``auto`` remains valid for records created before the explicit thinking-mode UI.
# New jobs use either ``off`` or a concrete effort level.
LEVELS = ("auto", "off", "low", "medium", "high", "ultra")
SCHEMA_STAGES = {"meeting_outline": "outline", "transcript_outline_context": "outline",
                 # Insights are a long-form, evidence-grounded synthesis.  Reuse
                 # the outline control so local reasoning models can reserve
                 # generation tokens for the JSON findings.
                 "conversation_insights": "outline",
                 "transcript_cleanup": "cleanup", "transcript_recommended_cleanup": "cleanup",
                 "transcript_notation": "notation",
                 "speaker_identity_extraction": "name_extract",
                 "speaker_identity_link_verification": "name_verify"}


def normalize_efforts(value=None):
    if value is None:
        return {stage: "off" if stage == "notation" else "auto" for stage in STAGES}
    if not isinstance(value, dict) or set(value) - set(STAGES):
        raise ValueError("AIエフォートの設定形式が不正です。")
    result = {stage: value.get(stage, "off" if stage == "notation" else "auto") for stage in STAGES}
    if any(level not in LEVELS for level in result.values()):
        raise ValueError("AIエフォートは auto / off / low / medium / high / ultra を指定してください。")
    return result


def effort_payload(provider, model, schema_name, efforts=None):
    level = normalize_efforts(efforts).get(SCHEMA_STAGES.get(schema_name), "auto")
    if level == "auto":
        return {}
    if provider == "openai":
        return {"reasoning": {"effort": {"off": "none", "ultra": "xhigh"}.get(level, level)}}
    if provider == "lmstudio":
        return {"reasoning_effort": {"off": "none", "ultra": "xhigh"}.get(level, level)}
    if provider == "google":
        if model.startswith("gemini-2.5-"):
            budget = {
                "off": 0, "low": 1024, "medium": 8192, "high": 16384, "ultra": 24576,
            }[level]
            # Gemini 2.5 Pro does not support a zero thinking budget; its
            # lowest supported budget is the closest safe OFF equivalent.
            if level == "off" and model.startswith("gemini-2.5-pro"):
                budget = 1024
            return {"thinkingConfig": {"thinkingBudget": budget}}
        # Gemini 3 cannot fully disable thinking. MINIMAL is its closest supported
        # setting, and ultra maps to the provider's maximum HIGH setting.
        if level == "off":
            level = "minimal"
        elif level == "ultra":
            level = "high"
        if model.startswith("gemini-3-pro") and level == "medium":
            level = "high"
        return {"thinkingConfig": {"thinkingLevel": level.upper()}}
    return {}


class UnsupportedLocalEffort(ValueError):
    """The advertised capability cannot express the requested reasoning setting."""


def cleanup_enabled(efforts=None):
    """Cleanup OFF disables polishing, independently of model reasoning support."""
    return normalize_efforts(efforts)["cleanup"] != "off"


def local_cleanup_effort_payload(level, capability):
    """Keep content strength intact; omit only unsupported non-OFF reasoning.

    Cleanup strength controls edits/context, not a promise of extra thinking.
    Keep existing supported overrides for compatibility. Otherwise use the
    model default without enabling reasoning or changing the stored strength.
    OFF remains strict here; finishing entry points skip the entire operation.
    """
    try:
        return local_effort_payload(level, capability)
    except UnsupportedLocalEffort:
        if level not in ("low", "medium", "high", "ultra"):
            raise
        return {}


def local_effort_payload(level, capability):
    """Map UI presets to values the local model actually supports."""
    if level == 'auto':
        return {}
    allowed = capability.get('allowed_options', [])
    # Gemma and Llama variants commonly expose no reasoning capability.  Do
    # not send an OpenAI-compatible parameter they cannot accept; generation
    # continues with the model's normal instruction mode.
    if not allowed:
        return {}
    if level == 'off' and 'off' in allowed:
        return {'reasoning_effort': 'none'}
    if level in allowed:
        return {'reasoning_effort': level}
    if level == 'ultra' and 'xhigh' in allowed:
        return {'reasoning_effort': 'xhigh'}
    # LM Studio model families do not all expose the same vocabulary.  These
    # fallbacks keep the UI's common scale usable for Qwen, Gemma, and Llama
    # derivatives that advertise minimal or xhigh instead of a direct level.
    aliases = {
        'low': ('minimal',),
        'medium': ('low', 'minimal'),
        'high': ('xhigh', 'medium', 'low', 'minimal'),
        'ultra': ('high', 'medium', 'low', 'minimal'),
    }
    for value in aliases.get(level, ()):
        if value in allowed:
            return {'reasoning_effort': value}
    if level in ('low', 'medium', 'high', 'ultra') and 'on' in allowed and capability.get('default') == 'on':
        return {}  # Binary thinking models have no effort distinction.
    raise UnsupportedLocalEffort(
        'このローカルモデルでは指定の推論設定を適用できません。'
        '対応する設定を選んでください。ON/OFFのみのモデルでは、'
        'この連携ではON指定の対応を確認できていないため、既定値がONの場合のみ追加推論を利用できます。')
