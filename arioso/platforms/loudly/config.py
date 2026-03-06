"""Loudly platform configuration."""

PLATFORM_CONFIG = {
    "name": "loudly",
    "display_name": "Loudly",
    "website": "https://loudly.com",
    "tier": "structured",
    "access_type": "rest_api",
    "auth": {
        "type": "bearer_token",
        "env_var": "LOUDLY_API_KEY",
    },
    "dependencies": ["requests"],
    "param_map": {
        "prompt": {"native_name": "prompt", "required": True},
        "duration": {"native_name": "duration"},
        "genre": {"native_name": "genre"},
        "bpm": {"native_name": "tempo"},
        "key": {"native_name": "key"},
        "energy": {"native_name": "energy"},
        "instruments": {
            "native_name": "instruments",
            "max_items": 7,
        },
        "structure": {"native_name": "structure"},
    },
    "supported_affordances": [
        "prompt",
        "duration",
        "genre",
        "bpm",
        "key",
        "energy",
        "instruments",
        "structure",
    ],
    "on_unsupported_param": "warn",
    "output": {
        "default_format": "mp3",
        "sample_rate": 44100,
        "returns": "url",
    },
    "api": {
        "base_url": "https://api.loudly.com/api",
        "generate_endpoint": {
            "method": "post",
            "path": "/music/generate",
        },
    },
}
