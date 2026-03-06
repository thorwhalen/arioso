"""Soundraw platform configuration (enterprise B2B API only)."""

PLATFORM_CONFIG = {
    "name": "soundraw",
    "display_name": "Soundraw",
    "website": "https://soundraw.io",
    "tier": "no_api",
    "access_type": "none",
    "auth": {
        "type": "api_key",
        "env_var": "SOUNDRAW_API_KEY",
        "note": "Enterprise API access requires B2B agreement.",
    },
    "dependencies": [],
    "param_map": {
        "genre": {"native_name": "genre"},
        "duration": {"native_name": "duration"},
        "energy": {"native_name": "energy"},
    },
    "supported_affordances": ["genre", "duration", "energy"],
    "on_unsupported_param": "ignore",
    "output": {
        "default_format": "mp3",
        "sample_rate": 44100,
        "returns": "url",
    },
    "notes": (
        "Soundraw REST API is enterprise/B2B only. Consumer access is via "
        "soundraw.io web app ($11/mo). API docs at discover.soundraw.io/api."
    ),
}
