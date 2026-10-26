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
        "melody": {
            "native_name": "melody",
            "adapter_handled": True,
        },
        # Audio continuation (thorwhalen/arioso#29): the audio itself, not a
        # clip id, since the model runs locally.
        "continue_from": {
            "native_name": "continue_from",
            "adapter_handled": True,
        },
        "continue_at": {
            "native_name": "continue_at",
            "adapter_handled": True,
        },
    },
    # batch_size and extend_stride are not listed: the adapter never read them,
    # so they were silently dropped on every path (thorwhalen/arioso#15). Add
    # them back with an adapter that passes them to audiocraft/transformers.
    "supported_affordances": [
        "prompt",
        "duration",
        "temperature",
        "top_k",
        "top_p",
        "guidance",
        "model",
        "melody",
        "continue_from",
        "continue_at",
    ],
    # Continuation knobs with no unified affordance: tail length fed as the
    # prompt, new audio per call, and how many calls to chain.
    "adapter_params": ["prompt_seconds", "extend_seconds", "rounds"],
    "on_unsupported_param": "warn",
    "output": {
        "default_format": "wav",
        "sample_rate": 32000,
        "returns": "array",
    },
}
