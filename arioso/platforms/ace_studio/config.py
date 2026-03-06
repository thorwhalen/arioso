"""ACE Studio platform configuration (DAW plugin only, no API)."""

PLATFORM_CONFIG = {
    "name": "ace_studio",
    "display_name": "ACE Studio",
    "website": "https://acestudio.ai",
    "tier": "no_api",
    "access_type": "none",
    "auth": {"type": "none"},
    "dependencies": [],
    "param_map": {
        "voice_id": {"native_name": "voice_model"},
        "lyrics": {"native_name": "lyrics"},
        "instruments": {"native_name": "instruments"},
    },
    "supported_affordances": ["voice_id", "lyrics", "instruments"],
    "on_unsupported_param": "ignore",
    "output": {
        "default_format": "wav",
        "sample_rate": 48000,
        "returns": "bytes",
    },
    "notes": (
        "ACE Studio is a DAW plugin for AI vocal synthesis with 140+ voice "
        "models. No public API. Use via the desktop application or DAW plugin."
    ),
}
