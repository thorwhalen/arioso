"""Riffusion platform configuration."""

PLATFORM_CONFIG = {
    "name": "riffusion",
    "display_name": "Riffusion",
    "website": "https://riffusion.com",
    "tier": "low_level",
    "access_type": "python_lib",
    "auth": {"type": "none"},
    "dependencies": [],
    "optional_dependencies": ["diffusers", "torch", "scipy", "numpy", "Pillow"],
    "param_map": {
        "prompt": {"native_name": "prompt"},
        "negative_prompt": {"native_name": "negative_prompt"},
        "seed": {"native_name": "start.seed", "adapter_handled": True},
        "guidance": {
            "native_name": "start.guidance",
            "native_default": 7.0,
        },
        "num_steps": {
            "native_name": "num_inference_steps",
            "native_default": 50,
        },
        "audio_input_strength": {
            "native_name": "start.denoising",
            "native_default": 0.75,
        },
    },
    "supported_affordances": [
        "prompt",
        "negative_prompt",
        "seed",
        "guidance",
        "num_steps",
        "audio_input_strength",
    ],
    "on_unsupported_param": "warn",
    "output": {
        "default_format": "wav",
        "sample_rate": 44100,
        "returns": "array",
    },
}
