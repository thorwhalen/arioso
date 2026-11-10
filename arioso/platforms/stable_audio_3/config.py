"""Stable Audio 3 platform configuration (local MLX runtime, Apple Silicon).

Stability ships the MLX build as ``optimized/mlx`` in ``Stability-AI/stable-audio-3`` (MIT
code), a script with its own small virtualenv; weights come on first use from Stability's
ungated ``stabilityai/stable-audio-3-optimized`` (Stability AI Community License, plus the
Gemma terms for the T5Gemma text encoder). Verified against the checkout's
``scripts/sa3_mlx.py`` and the model card on 2026-11-10.
"""

PLATFORM_CONFIG = {
    "name": "stable_audio_3",
    "display_name": "Stable Audio 3 (local, MLX)",
    "website": "https://github.com/Stability-AI/stable-audio-3/tree/main/optimized/mlx",
    "tier": "low_level",
    "access_type": "local_runtime",
    "auth": {"type": "none"},
    "dependencies": [],
    "optional_dependencies": ["soundfile"],
    "weights_license": "Stability AI Community License (+ Gemma terms for T5Gemma)",
    "commercial_use": "conditional",
    "runtime": {
        "name": "stable-audio-3",
        "env_var": "ARIOSO_SA3_DIR",
        "python": "optimized/mlx/.venv/bin/python",
        "cwd": "optimized/mlx",
        "setup": (
            "git clone --depth 1 https://github.com/Stability-AI/stable-audio-3 {root}\n"
            "cd {root}/optimized/mlx && uv venv .venv --python 3.11 "
            "&& uv pip install --python .venv/bin/python -r requirements.txt"
        ),
    },
    # model -> (DiT, decoder) of the MLX script.
    "models": {
        "sm-music": ("sm-music", "same-s"),
        "sm-sfx": ("sm-sfx", "same-s"),
        "medium": ("medium", "same-l"),
    },
    "param_map": {
        "prompt": {"native_name": "--prompt", "adapter_handled": True},
        "negative_prompt": {"native_name": "--negative-prompt", "adapter_handled": True},
        "duration": {"native_name": "--seconds", "native_default": 10.0, "adapter_handled": True},
        "num_steps": {"native_name": "--steps", "native_default": 8, "adapter_handled": True},
        "guidance": {"native_name": "--cfg", "native_default": 1.0, "adapter_handled": True},
        "seed": {"native_name": "--seed", "adapter_handled": True},
        "model": {"native_name": "--dit", "native_default": "sm-music", "adapter_handled": True},
        "audio_input": {"native_name": "--init-audio", "adapter_handled": True},
        "audio_input_strength": {
            "native_name": "--init-noise-level",
            "native_default": 0.7,
            "adapter_handled": True,
        },
    },
    "supported_affordances": [
        "prompt",
        "negative_prompt",
        "duration",
        "num_steps",
        "guidance",
        "seed",
        "model",
        "audio_input",
        "audio_input_strength",
    ],
    # (start, end) seconds of audio_input to regenerate; the rest is kept.
    "adapter_params": ["inpaint_range"],
    "on_unsupported_param": "warn",
    "output": {"default_format": "wav", "sample_rate": 44100, "returns": "array"},
}
