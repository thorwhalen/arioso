"""ACE-Step platform configuration (fal.ai hosted).

Live docs (verified 2026-10-03): https://fal.ai/models/fal-ai/ace-step/api and
https://fal.ai/models/fal-ai/ace-step/audio-to-audio/api
"""

PLATFORM_CONFIG = {
    "name": "ace_step",
    "display_name": "ACE-Step (via fal.ai)",
    "website": "https://fal.ai/models/fal-ai/ace-step",
    "tier": "structured",
    "access_type": "rest_api",
    "auth": {"type": "api_key", "env_var": "FAL_KEY"},
    "dependencies": [],
    "optional_dependencies": ["fal_client", "requests"],
    "param_map": {
        "prompt": {"native_name": "tags", "required": True},
        "genre": {"native_name": "tags", "adapter_handled": True},
        "lyrics": {"native_name": "lyrics", "native_default": "[inst]"},
        "instrumental": {"native_name": "lyrics", "adapter_handled": True},
        "duration": {"native_name": "duration", "native_default": 60.0},
        "num_steps": {"native_name": "number_of_steps", "native_default": 27},
        "guidance": {"native_name": "guidance_scale", "native_default": 15.0},
        "seed": {"native_name": "seed"},
        "audio_input": {"native_name": "audio_url", "adapter_handled": True},
    },
    "supported_affordances": [
        "prompt",
        "genre",
        "lyrics",
        "instrumental",
        "duration",
        "num_steps",
        "guidance",
        "seed",
        "audio_input",
    ],
    "on_unsupported_param": "warn",
    "output": {"default_format": "wav", "sample_rate": 44100, "returns": "bytes"},
    "api": {
        "text_to_audio_endpoint": "fal-ai/ace-step",
        "audio_to_audio_endpoint": "fal-ai/ace-step/audio-to-audio",
    },
}
