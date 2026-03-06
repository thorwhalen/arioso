"""ElevenLabs Music platform configuration."""

PLATFORM_CONFIG = {
    "name": "elevenlabs",
    "display_name": "ElevenLabs Music",
    "website": "https://elevenlabs.io",
    "tier": "structured",
    "access_type": "rest_api",
    "auth": {
        "type": "api_key",
        "env_var": "ELEVENLABS_API_KEY",
        "header_name": "xi-api-key",
    },
    "dependencies": ["requests"],
    "optional_dependencies": ["elevenlabs"],
    "param_map": {
        "prompt": {
            "native_name": "prompt",
            "required": True,
        },
        "duration": {
            "native_name": "music_length_ms",
            "coerce": lambda x: int(x * 1000),
            "coerce_back": lambda x: x / 1000,
            "native_default": 30000,
        },
        "lyrics": {
            "native_name": None,
            "adapter_handled": True,
        },
        "instrumental": {
            "native_name": "force_instrumental",
        },
        "model": {
            "native_name": "model_id",
            "native_default": "music_v1",
        },
        "seed": {
            "native_name": "seed",
        },
        "output_format": {
            "native_name": "output_format",
            "native_default": "mp3_44100_128",
        },
        "watermark": {
            "native_name": "sign_with_c2pa",
        },
        "title": {
            "native_name": None,
            "adapter_handled": True,
        },
        "structure": {
            "native_name": None,
            "adapter_handled": True,
        },
    },
    "supported_affordances": [
        "prompt",
        "duration",
        "lyrics",
        "instrumental",
        "model",
        "seed",
        "output_format",
        "watermark",
        "title",
        "structure",
    ],
    "on_unsupported_param": "warn",
    "output": {
        "default_format": "mp3",
        "sample_rate": 44100,
        "returns": "bytes",
    },
    "api": {
        "base_url": "https://api.elevenlabs.io",
        "openapi_spec_url": "https://api.elevenlabs.io/openapi.json",
        "generate_endpoint": {
            "method": "post",
            "path": "/v1/music",
        },
    },
}
