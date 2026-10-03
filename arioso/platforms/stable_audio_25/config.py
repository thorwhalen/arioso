"""Stable Audio 2.5 platform configuration (fal.ai hosted).

Live docs (verified 2026-10-03):
https://fal.ai/models/fal-ai/stable-audio-25/text-to-audio/api and
https://fal.ai/models/fal-ai/stable-audio-25/audio-to-audio/api
"""

PLATFORM_CONFIG = {
    "name": "stable_audio_25",
    "display_name": "Stable Audio 2.5 (Stability AI, via fal.ai)",
    "website": "https://fal.ai/models/fal-ai/stable-audio-25/audio-to-audio",
    "tier": "low_level",
    "access_type": "rest_api",
    "auth": {"type": "api_key", "env_var": "FAL_KEY"},
    "dependencies": [],
    "optional_dependencies": ["fal_client", "requests"],
    "param_map": {
        "prompt": {"native_name": "prompt", "required": True, "adapter_handled": True},
        "duration": {
            "native_name": "seconds_total | total_seconds (audio-to-audio)",
            "adapter_handled": True,
        },
        "num_steps": {
            "native_name": "num_inference_steps",
            "native_default": 8,
            "adapter_handled": True,
        },
        "guidance": {
            "native_name": "guidance_scale",
            "native_default": 1.0,
            "adapter_handled": True,
        },
        "seed": {"native_name": "seed", "adapter_handled": True},
        "audio_input": {"native_name": "audio_url", "adapter_handled": True},
        "audio_input_strength": {
            "native_name": "strength",
            "native_default": 0.8,
            "adapter_handled": True,
        },
    },
    "supported_affordances": [
        "prompt",
        "duration",
        "num_steps",
        "guidance",
        "seed",
        "audio_input",
        "audio_input_strength",
    ],
    # The adapter takes the unified names itself (native_name documents the
    # mapping), and these adapter-only keywords pass validation untouched.
    "adapter_params": ["fetch"],
    "on_unsupported_param": "warn",
    "output": {"default_format": "wav", "sample_rate": 44100, "returns": "bytes"},
    "api": {
        "text_to_audio_endpoint": "fal-ai/stable-audio-25/text-to-audio",
        "audio_to_audio_endpoint": "fal-ai/stable-audio-25/audio-to-audio",
        "max_seconds": 190,
        "default_seconds": 30,
    },
}
