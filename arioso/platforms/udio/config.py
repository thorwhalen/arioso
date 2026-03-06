"""Udio platform configuration (via udio-wrapper)."""

PLATFORM_CONFIG = {
    "name": "udio",
    "display_name": "Udio (via UdioWrapper)",
    "website": "https://udio.com",
    "tier": "structured",
    "access_type": "python_lib",
    "auth": {
        "type": "cookie",
        "env_var": "UDIO_AUTH_COOKIE",
        "note": "Requires browser auth cookie. See udio-wrapper docs.",
    },
    "dependencies": ["udio-wrapper"],
    "param_map": {
        "prompt": {"native_name": "prompt", "required": True},
        "lyrics": {"native_name": "custom_lyrics"},
        "seed": {"native_name": "seed"},
        "audio_input": {
            "native_name": "audio_conditioning_path",
            "adapter_handled": True,
        },
    },
    "supported_affordances": [
        "prompt",
        "lyrics",
        "seed",
        "audio_input",
    ],
    "on_unsupported_param": "warn",
    "output": {
        "default_format": "mp3",
        "sample_rate": 48000,
        "returns": "url",
    },
}
