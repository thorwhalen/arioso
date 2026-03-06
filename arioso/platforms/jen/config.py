"""Jen platform configuration."""

PLATFORM_CONFIG = {
    "name": "jen",
    "display_name": "Jen",
    "website": "https://jenmusic.ai",
    "tier": "structured",
    "access_type": "rest_api",
    "auth": {
        "type": "bearer_token",
        "env_var": "JEN_API_KEY",
    },
    "dependencies": ["requests"],
    "param_map": {
        "prompt": {"native_name": "prompt", "required": True},
        "duration": {"native_name": "duration"},
        "output_format": {
            "native_name": "format",
            "choices": ["mp3", "wav"],
            "native_default": "mp3",
        },
        "continue_from": {"native_name": "continue_from"},
    },
    "supported_affordances": [
        "prompt",
        "duration",
        "output_format",
        "continue_from",
    ],
    "on_unsupported_param": "warn",
    "output": {
        "default_format": "mp3",
        "sample_rate": 48000,
        "returns": "url",
    },
    "api": {
        "base_url": "https://api.jenmusic.ai/v1",
        "generate_endpoint": {
            "method": "post",
            "path": "/generate",
        },
    },
}
