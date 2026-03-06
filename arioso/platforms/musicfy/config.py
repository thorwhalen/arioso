"""Musicfy platform configuration."""

PLATFORM_CONFIG = {
    "name": "musicfy",
    "display_name": "Musicfy",
    "website": "https://musicfy.lol",
    "tier": "no_api",
    "access_type": "none",
    "auth": {"type": "none"},
    "dependencies": [],
    "param_map": {
        "prompt": {"native_name": "prompt"},
        "voice_id": {"native_name": "voice_id"},
        "pitch_shift": {"native_name": "pitch_shift"},
    },
    "supported_affordances": ["prompt", "voice_id", "pitch_shift"],
    "on_unsupported_param": "ignore",
    "output": {
        "default_format": "mp3",
        "sample_rate": 44100,
        "returns": "url",
    },
    "notes": (
        "Musicfy is a web-based tool for AI music generation and voice "
        "conversion. No known public API. Features voice cloning and "
        "pitch shifting."
    ),
}
