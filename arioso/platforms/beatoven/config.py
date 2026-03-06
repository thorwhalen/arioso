"""Beatoven.ai platform configuration."""

PLATFORM_CONFIG = {
    "name": "beatoven",
    "display_name": "Beatoven.ai",
    "website": "https://beatoven.ai",
    "tier": "structured",
    "access_type": "rest_api",
    "auth": {
        "type": "bearer_token",
        "env_var": "BEATOVEN_API_KEY",
    },
    "dependencies": ["requests"],
    "param_map": {
        "prompt": {"native_name": "prompt", "required": True},
        "duration": {
            "native_name": "duration",
            "unit": "seconds",
            "min": 5,
            "max": 150,
        },
        "negative_prompt": {"native_name": "negative_prompt"},
        "seed": {"native_name": "seed"},
        "guidance": {
            "native_name": "creativity",
            "native_default": 16,
        },
        "num_steps": {
            "native_name": "refinement",
            "native_default": 100,
        },
        "looping": {"native_name": "ENABLE_LOOPING"},
    },
    "supported_affordances": [
        "prompt",
        "duration",
        "negative_prompt",
        "seed",
        "guidance",
        "num_steps",
        "looping",
    ],
    "on_unsupported_param": "warn",
    "output": {
        "default_format": "mp3",
        "sample_rate": 44100,
        "returns": "url",
    },
    "api": {
        "base_url": "https://api.beatoven.ai/api/v1",
        "generate_endpoint": {
            "method": "post",
            "path": "/tracks",
        },
    },
}
