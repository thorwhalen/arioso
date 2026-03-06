"""MusicGen platform configuration."""

PLATFORM_CONFIG = {
    "name": "musicgen",
    "display_name": "MusicGen (Meta)",
    "website": "https://github.com/facebookresearch/audiocraft",
    "tier": "low_level",
    "access_type": "python_lib",
    "auth": {"type": "none"},
    "dependencies": [],
    "optional_dependencies": ["audiocraft", "transformers", "torch"],
    "param_map": {
        "prompt": {"native_name": "descriptions", "coerce": lambda x: [x]},
        "duration": {"native_name": "duration", "native_default": 8.0},
        "temperature": {"native_name": "temperature", "native_default": 1.0},
        "top_k": {"native_name": "top_k", "native_default": 250},
        "top_p": {"native_name": "top_p", "native_default": 0.0},
        "guidance": {"native_name": "cfg_coef", "native_default": 3.0},
        "model": {
            "native_name": "model_variant",
            "native_default": "facebook/musicgen-small",
        },
        "extend_stride": {"native_name": "extend_stride", "native_default": 18},
        "batch_size": {
            "native_name": "batch_size",
            "adapter_handled": True,
        },
    },
    "supported_affordances": [
        "prompt",
        "duration",
        "temperature",
        "top_k",
        "top_p",
        "guidance",
        "model",
        "batch_size",
        "extend_stride",
    ],
    "on_unsupported_param": "warn",
    "output": {
        "default_format": "wav",
        "sample_rate": 32000,
        "returns": "array",
    },
}
