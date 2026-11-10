"""MusicGen platform configuration."""

from arioso._isolated import GitSource

PLATFORM_CONFIG = {
    "name": "musicgen",
    "display_name": "MusicGen (Meta)",
    "website": "https://github.com/facebookresearch/audiocraft",
    "tier": "low_level",
    "access_type": "python_lib",
    "weights_license": "CC-BY-NC-4.0",
    "commercial_use": "no",
    "auth": {"type": "none"},
    "dependencies": [],
    # MLX needs no package here: it runs in its own runtime (see mlx_runtime below).
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
    # MusicGen on MLX (Apple Silicon): ml-explore/mlx-examples' port (MIT code) in its own
    # environment, run by a worker (arioso._isolated). Text mode only; the transformers or
    # audiocraft backend keeps melody and continuation. Measured on an M1 Max with
    # musicgen-small (10 s clips): 11-13 s on MLX against 186-350 s on transformers/MPS
    # (thorwhalen/arioso#54). Verified against mlx-examples/musicgen on 2026-11-10.
    "mlx_runtime": {
        "name": "mlx-examples",
        "env_var": "ARIOSO_MLX_EXAMPLES_DIR",
        "python": "musicgen/.venv/bin/python",
        "cwd": "musicgen",
        # the commit verified on 2026-11-10 (thorwhalen/arioso#63)
        "source": GitSource(
            "https://github.com/ml-explore/mlx-examples",
            "796f5b53cab69a3d48a44233ce21aae889e94a08",
        ),
        "setup": (
            "cd {root}/musicgen && uv venv .venv --python 3.12 "
            "&& uv pip install --python .venv/bin/python -r requirements.txt"
        ),
    },
    "mlx_worker": "musicgen_mlx",  # arioso/_workers/musicgen_mlx_worker.py
    "output": {
        "default_format": "wav",
        "sample_rate": 32000,
        "returns": "array",
    },
}
