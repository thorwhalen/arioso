"""YuE platform configuration."""

PLATFORM_CONFIG = {
    "name": "yue",
    "display_name": "YuE",
    "website": "https://github.com/multimodal-art-projection/YuE",
    "tier": "structured",
    "access_type": "python_lib",
    "auth": {
        "type": "bearer_token",
        "env_var": "FAL_KEY",
        "optional": True,
    },
    "dependencies": [],
    "optional_dependencies": ["fal_client"],
    "param_map": {
        "prompt": {"native_name": "genre_txt"},
        "lyrics": {"native_name": "lyrics_txt"},
        "duration": {
            "native_name": "run_n_segments",
            "adapter_handled": True,
        },
        "model": {
            "native_name": "stage1_model",
            "native_default": "m-a-p/YuE-s1-7B-anneal-en-cot",
        },
        "batch_size": {
            "native_name": "stage2_batch_size",
            "native_default": 4,
        },
        "max_tokens": {
            "native_name": "max_new_tokens",
            "native_default": 3000,
        },
        "repetition_penalty": {
            "native_name": "repetition_penalty",
            "native_default": 1.1,
        },
        "audio_input": {
            "native_name": "vocal_track_prompt_path",
            "adapter_handled": True,
        },
    },
    "supported_affordances": [
        "prompt",
        "lyrics",
        "duration",
        "model",
        "batch_size",
        "max_tokens",
        "repetition_penalty",
        "audio_input",
    ],
    "on_unsupported_param": "warn",
    "output": {
        "default_format": "wav",
        "sample_rate": 0,  # codec-dependent
        "returns": "bytes",
    },
}
