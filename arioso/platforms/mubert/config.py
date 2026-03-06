"""Mubert platform configuration."""

PLATFORM_CONFIG = {
    "name": "mubert",
    "display_name": "Mubert",
    "website": "https://mubert.com",
    "tier": "prompt_and_duration",
    "access_type": "rest_api",
    "auth": {
        "type": "bearer_token",
        "env_var": "MUBERT_PAT",
    },
    "dependencies": ["requests"],
    "param_map": {
        "prompt": {"native_name": "prompt", "required": True},
        "duration": {
            "native_name": "duration",
            "unit": "seconds",
            "min": 15,
            "max": 1500,
        },
        "output_format": {
            "native_name": "format",
            "choices": ["wav", "mp3"],
            "native_default": "mp3",
        },
        "bitrate": {
            "native_name": "bitrate",
            "choices": [128, 320],
            "native_default": 320,
        },
        "energy": {
            "native_name": "intensity",
            "adapter_handled": True,
        },
    },
    "supported_affordances": [
        "prompt",
        "duration",
        "output_format",
        "bitrate",
        "energy",
    ],
    "on_unsupported_param": "warn",
    "output": {
        "default_format": "mp3",
        "sample_rate": 44100,
        "returns": "url",
    },
    "api": {
        "base_url": "https://api-b2b.mubert.com/v2",
        "generate_endpoint": {
            "method": "post",
            "path": "/RecordTrackTTM",
        },
    },
}
