"""Harmonai (Dance Diffusion) platform configuration."""

PLATFORM_CONFIG = {
    "name": "harmonai",
    "display_name": "Harmonai (Dance Diffusion)",
    "website": "https://github.com/Harmonai-org/sample-generator",
    "tier": "low_level",
    "access_type": "python_lib",
    "auth": {"type": "none"},
    "dependencies": [],
    "optional_dependencies": ["diffusers", "torch"],
    "param_map": {
        "num_steps": {
            "native_name": "num_inference_steps",
            "native_default": 100,
        },
        "seed": {
            "native_name": "generator",
            "adapter_handled": True,
        },
        "batch_size": {
            "native_name": "batch_size",
            "native_default": 1,
        },
    },
    "supported_affordances": [
        "num_steps",
        "seed",
        "batch_size",
    ],
    "on_unsupported_param": "warn",
    "output": {
        "default_format": "wav",
        "sample_rate": 48000,
        "returns": "array",
    },
}
