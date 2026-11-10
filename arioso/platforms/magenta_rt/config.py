"""Magenta RealTime 2 platform configuration (local MLX runtime, Apple Silicon).

``magenta-rt[mlx]`` (Apache-2.0 code) with the exported ``.mlxfn`` models; weights
CC-BY-4.0 (Google claims no rights in generated outputs). ``mlx<0.32`` is pinned because
MLX 0.32 cannot load the exported functions (magenta/magenta-realtime#103). Verified
against ``magenta_rt/mlx/generate.py`` of magenta-rt on 2026-11-10. Offline renders only:
the streaming state is not exposed yet.
"""

PLATFORM_CONFIG = {
    "name": "magenta_rt",
    "display_name": "Magenta RealTime 2 (local, MLX)",
    "website": "https://github.com/magenta/magenta-realtime",
    "tier": "low_level",
    "access_type": "local_runtime",
    "auth": {"type": "none"},
    "dependencies": [],
    "optional_dependencies": ["soundfile"],
    "weights_license": "CC-BY-4.0",
    "commercial_use": "yes",
    "runtime": {
        "name": "magenta-rt",
        "env_var": "ARIOSO_MAGENTA_RT_DIR",
        "setup": (
            "uv venv {root}/.venv --python 3.12\n"
            'uv pip install --python {root}/.venv/bin/python "magenta-rt[mlx]" "mlx<0.32" "mlx-metal<0.32"\n'
            "MAGENTA_HOME={root}/home {root}/.venv/bin/mrt models init\n"
            "MAGENTA_HOME={root}/home {root}/.venv/bin/mrt models download mrt2_small"
        ),
    },
    "driver": "arioso.platforms.magenta_rt._driver",
    "frame_rate": 25,
    "param_map": {
        "prompt": {"native_name": "embed_style(text)", "adapter_handled": True},
        "duration": {"native_name": "frames", "native_default": 10.0, "adapter_handled": True},
        "model": {"native_name": "size", "native_default": "mrt2_small", "adapter_handled": True},
        "temperature": {"native_name": "temperature", "native_default": 1.3, "adapter_handled": True},
        "top_k": {"native_name": "top_k", "native_default": 40, "adapter_handled": True},
        "guidance": {"native_name": "cfg_scales.musiccoca", "native_default": 3.0, "adapter_handled": True},
        "reference_audio": {"native_name": "embed_style(audio)", "adapter_handled": True},
    },
    "supported_affordances": [
        "prompt",
        "duration",
        "model",
        "temperature",
        "top_k",
        "guidance",
        "reference_audio",
    ],
    "on_unsupported_param": "warn",
    "output": {"default_format": "wav", "sample_rate": 48000, "returns": "array"},
}
