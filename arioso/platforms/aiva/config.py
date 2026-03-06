"""AIVA platform configuration (no public API)."""

PLATFORM_CONFIG = {
    "name": "aiva",
    "display_name": "AIVA",
    "website": "https://aiva.ai",
    "tier": "no_api",
    "access_type": "none",
    "auth": {"type": "none"},
    "dependencies": [],
    "param_map": {
        "genre": {"native_name": "style_preset"},
        "bpm": {"native_name": "bpm"},
        "key": {"native_name": "key"},
        "instruments": {"native_name": "instruments"},
        "duration": {"native_name": "duration"},
    },
    "supported_affordances": ["genre", "bpm", "key", "instruments", "duration"],
    "on_unsupported_param": "ignore",
    "output": {
        "default_format": "wav",
        "sample_rate": 48000,
        "returns": "bytes",
    },
    "notes": (
        "AIVA has no public API. It is a desktop/web DAW application with "
        "250+ style presets, direct BPM/key/instrument control, and orchestral "
        "focus. Use via aiva.ai web interface."
    ),
}
