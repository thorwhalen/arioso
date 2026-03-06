"""CassetteAI platform configuration."""

PLATFORM_CONFIG = {
    "name": "cassetteai",
    "display_name": "CassetteAI",
    "website": "https://cassetteai.com",
    "tier": "no_api",
    "access_type": "none",
    "auth": {"type": "none"},
    "dependencies": [],
    "param_map": {
        "prompt": {"native_name": "prompt"},
        "duration": {"native_name": "duration"},
    },
    "supported_affordances": ["prompt", "duration"],
    "on_unsupported_param": "ignore",
    "output": {
        "default_format": "mp3",
        "sample_rate": 44100,
        "returns": "url",
    },
    "notes": (
        "CassetteAI is a prompt-and-duration tool with no known public API. "
        "Use via their web interface."
    ),
}
