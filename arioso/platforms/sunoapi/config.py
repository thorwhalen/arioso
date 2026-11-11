"""Suno (via sunoapi.org) platform configuration."""

PLATFORM_CONFIG = {
    "name": "sunoapi",
    "display_name": "Suno (via sunoapi.org)",
    "website": "https://sunoapi.org",
    "tier": "structured",
    "access_type": "rest_api",
    "weights_license": "proprietary",
    "commercial_use": "provider terms",
    "auth": {
        "type": "bearer_token",
        "env_var": "SUNO_API_KEY",
    },
    "dependencies": ["requests"],
    # title/description/minimum/maximum/choices/default: what param_schema reports
    # (arioso.schema); Suno's own UI names ("Styles", "Audio Influence") as titles.
    "param_map": {
        "prompt": {
            "native_name": "prompt",
            "required": True,
            "title": "Song description",
            "description": "What the song is about and how it should feel. With "
            "Styles or Lyrics given, it is used as the style when Styles is empty.",
            "multiline": True,
        },
        "genre": {
            "native_name": "style",
            "adapter_handled": True,
            "title": "Styles",
            "description": "Genres, instruments, moods and production (e.g. "
            "'dreamy synth-pop, female vocals, 90 bpm'). Up to 1,000 characters.",
        },
        "lyrics": {
            "native_name": "prompt",
            "adapter_handled": True,
            "title": "Lyrics",
            "description": "Your lyrics, with [Verse]/[Chorus] tags if you like. "
            "Up to 5,000 characters on V6.",
            "multiline": True,
        },
        "title": {"native_name": "title", "title": "Title"},
        "instrumental": {
            "native_name": "instrumental",
            "title": "Instrumental",
            "description": "No vocals; lyrics are ignored.",
            "default": False,
        },
        "negative_prompt": {
            "native_name": "negativeTags",
            "title": "Exclude styles",
            "description": "Styles, instruments or traits to keep out.",
        },
        "model": {
            "native_name": "model",
            "native_default": "V6",
            "title": "Model",
            "default": "V6",
            "choices": [
                "V6",
                "V6_WILD",
                "V6_MINI",
                "V5_5",
                "V5",
                "V4_5PLUS",
                "V4_5ALL",
                "V4_5",
                "V4",
            ],
            "default_env_var": "SUNO_DEFAULT_MODEL",
        },
        "duration": {
            "native_name": "duration",
            "adapter_handled": True,
            "title": "Duration",
            "description": "Target length in seconds (V5_5 and the V6 family only); "
            "empty lets Suno decide.",
            "minimum": 10,
            "maximum": 360,
            "advanced": True,
        },
        "continue_from": {
            "native_name": "continue_clip_id",
            "type": str,
            "title": "Extend clip",
            "description": "The id of a Suno clip to continue.",
        },
        "continue_at": {
            "native_name": "continue_at",
            "title": "Extend from (s)",
            "description": "Where in the clip the continuation starts, in seconds.",
            "minimum": 0,
        },
        "audio_input": {
            "native_name": "uploadUrl",
            "adapter_handled": True,
            "title": "Audio",
            "description": "A clip to cover (upload-cover): the result keeps its "
            "melody and structure in the new style. Up to 8 minutes.",
        },
        "audio_input_strength": {
            "native_name": "audioWeight",
            "adapter_handled": True,
            "title": "Audio Influence",
            "description": "How closely the result follows the uploaded audio. "
            "Not used for instrumentals.",
            "default": 0.5,
            "scale_labels": ["Loose", "Faithful"],
            "requires": "audio_input",
        },
    },
    "supported_affordances": [
        "prompt",
        "genre",
        "lyrics",
        "title",
        "instrumental",
        "negative_prompt",
        "model",
        "duration",
        "continue_from",
        "continue_at",
        "audio_input",
        "audio_input_strength",
    ],
    # Suno-only generate controls, passed to the adapter under these names
    # (custom mode only; ranges are validated again in adapter._custom_controls).
    "adapter_params": {
        "weirdness": {
            "type": float,
            "title": "Weirdness",
            "description": "How far Suno strays from the expected; 0.5 is its "
            "normal result (weirdnessConstraint).",
            "minimum": 0,
            "maximum": 1,
            "default": 0.5,
            "scale_labels": ["Safe", "Chaos"],
        },
        "style_weight": {
            "type": float,
            "title": "Style Influence",
            "description": "How strictly the Styles text is followed (styleWeight).",
            "minimum": 0,
            "maximum": 1,
            "default": 0.5,
            "scale_labels": ["Loose", "Strong"],
        },
        "vocal_gender": {
            "type": str,
            "title": "Vocal Gender",
            "description": "Preferred singing voice: m or f (vocalGender).",
            "choices": ["m", "f"],
        },
        "variety": {
            "type": int,
            "title": "Variety",
            "description": "How much the takes of one generation differ, 0-4 "
            "(Suno's default is 1).",
            "minimum": 0,
            "maximum": 4,
            "advanced": True,
        },
    },
    "on_unsupported_param": "warn",
    "output": {
        "default_format": "mp3",
        "sample_rate": 44100,
        "returns": "url",
    },
    "api": {
        "base_url": "https://api.sunoapi.org",
        "generate_endpoint": {
            "method": "post",
            "path": "/api/v1/generate",
        },
    },
}
