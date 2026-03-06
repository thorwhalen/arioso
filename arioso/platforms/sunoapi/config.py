"""Suno (via sunoapi.org) platform configuration."""

PLATFORM_CONFIG = {
    "name": "sunoapi",
    "display_name": "Suno (via sunoapi.org)",
    "website": "https://sunoapi.org",
    "tier": "structured",
    "access_type": "rest_api",
    "auth": {
        "type": "bearer_token",
        "env_var": "SUNO_API_KEY",
    },
    "dependencies": ["requests"],
    "param_map": {
        "prompt": {"native_name": "prompt", "required": True},
        "genre": {"native_name": "tags"},
        "lyrics": {"native_name": "prompt", "adapter_handled": True},
        "title": {"native_name": "title"},
        "instrumental": {"native_name": "make_instrumental"},
        "model": {
            "native_name": "model_version",
            "native_default": "v3.5",
        },
        "wait_for_completion": {
            "native_name": "wait_audio",
            "native_default": True,
        },
        "continue_from": {"native_name": "continue_clip_id"},
        "continue_at": {"native_name": "continue_at"},
    },
    "supported_affordances": [
        "prompt",
        "genre",
        "lyrics",
        "title",
        "instrumental",
        "model",
        "wait_for_completion",
        "continue_from",
        "continue_at",
    ],
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
