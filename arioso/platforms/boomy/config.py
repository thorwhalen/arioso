"""Boomy platform configuration (enterprise API only)."""

PLATFORM_CONFIG = {
    "name": "boomy",
    "display_name": "Boomy",
    "website": "https://boomy.com",
    "tier": "no_api",
    "access_type": "none",
    "auth": {"type": "none"},
    "dependencies": [],
    "param_map": {
        "prompt": {"native_name": "prompt"},
        "voice_id": {"native_name": "voice"},
        "instrumental": {"native_name": "instrumental"},
    },
    "supported_affordances": ["prompt", "voice_id", "instrumental"],
    "on_unsupported_param": "ignore",
    "output": {
        "default_format": "mp3",
        "sample_rate": 44100,
        "returns": "url",
    },
    "notes": (
        "Boomy has an enterprise-only API. Consumer access is via the web "
        "app at boomy.com. Features Auto Vocal and distribution to streaming "
        "platforms."
    ),
}
