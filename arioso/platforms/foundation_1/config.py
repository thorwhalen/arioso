"""Foundation-1 platform configuration (local, stable-audio-tools in its own environment).

Foundation-1 (``RoyalCities/Foundation-1`` on the Hugging Face Hub, ungated) is a fine-tune
of Stable Audio Open 1.0 for structured, tempo- and bar-aware instrument loops and
one-shots: one ``model_config.json`` (a stable-audio-tools ``diffusion_cond`` model: oobleck
VAE, T5-base prompt encoder, ``seconds_start``/``seconds_total``, DiT; 44.1 kHz stereo, a
20 s window) shared by three checkpoints. Weights: Stability AI Community License (free
for research and non-commercial use, commercial use below US$1M annual revenue). Verified
against the model card, ``Master_Tag_Reference.md`` and ``model_config.json`` at the
revision below on 2026-11-10.

stable-audio-tools pins its own torch and Python (``<3.11``), so it runs in an environment
arioso builds once with ``uv`` (:class:`~arioso._isolated.EnvSpec`, under
``~/.local/share/arioso/envs/foundation-1``); weights go to the Hugging Face cache.
"""

import platform as _platform

from arioso._isolated import EnvSpec

#: The model card's prompt grammar: bar counts and tempos the loops were trained on.
SUPPORTED_BARS = (4, 8)
SUPPORTED_BPMS = (100, 110, 120, 128, 130, 140, 150)

#: stable-audio-tools and the packages whose versions decide its behaviour, pinned (the
#: set resolved and measured on 2026-11-10); the rest follow from these.
REQUIREMENTS = (
    "stable-audio-tools==0.0.20",
    "torch==2.7.1",
    "torchaudio==2.7.1",
    "transformers==4.57.1",
    "tokenizers==0.22.1",
    "huggingface-hub==0.36.0",
    "safetensors==0.6.2",
    "numpy==2.2.6",
    "scipy==1.15.3",
    "sentencepiece==0.1.99",
    "torchsde==0.2.6",
    "soundfile==0.13.1",
)

ENV_SPEC = EnvSpec(
    name="foundation-1",
    requirements=REQUIREMENTS,
    python="3.10",
    # On Linux let uv pick the wheel matching the machine's accelerator (CUDA or CPU)
    # instead of PyPI's default CUDA build; macOS wheels carry MPS, there is no index to pick.
    torch_backend=None if _platform.system() == "Darwin" else "auto",
)

PLATFORM_CONFIG = {
    "name": "foundation_1",
    "display_name": "Foundation-1 (local, stable-audio-tools)",
    "website": "https://huggingface.co/RoyalCities/Foundation-1",
    "tier": "low_level",
    "access_type": "local_runtime",
    "auth": {"type": "none"},
    "dependencies": [],
    "optional_dependencies": ["soundfile"],
    "weights_license": "Stability AI Community License",
    "commercial_use": "conditional",
    "env": ENV_SPEC,
    "worker": "foundation_1",  # arioso/_workers/foundation_1_worker.py
    "weights": {
        "repo_id": "RoyalCities/Foundation-1",
        "revision": "7b10fbbbc1be2f54cbc5540aab89ee383bc94e4a",
        "config_file": "model_config.json",
    },
    # model -> checkpoint file in the weights repository (all share model_config.json).
    "models": {
        "foundation-1": "Foundation_1.safetensors",  # loops
        "1.2-samples": "Foundation-1.2-Samples.safetensors",  # loops and one-shots
        "1.2-keybeds": "Foundation-1.2-Keybeds.safetensors",  # pitch-consistent one-shots
    },
    "supported_bars": SUPPORTED_BARS,
    "supported_bpms": SUPPORTED_BPMS,
    "param_map": {
        "prompt": {"native_name": "conditioning.prompt", "adapter_handled": True},
        "negative_prompt": {
            "native_name": "negative_conditioning.prompt",
            "adapter_handled": True,
        },
        "duration": {
            "native_name": "conditioning.seconds_total",
            "native_default": 10.0,
            "adapter_handled": True,
        },
        "bpm": {"native_name": "'<bpm> BPM' tag", "adapter_handled": True},
        "key": {"native_name": "'<key>' tag", "adapter_handled": True},
        "num_steps": {
            "native_name": "steps",
            "native_default": 100,
            "adapter_handled": True,
        },
        "guidance": {
            "native_name": "cfg_scale",
            "native_default": 7.0,
            "adapter_handled": True,
        },
        "seed": {"native_name": "seed", "adapter_handled": True},
        "model": {
            "native_name": "checkpoint",
            "native_default": "foundation-1",
            "adapter_handled": True,
        },
    },
    "supported_affordances": [
        "prompt",
        "negative_prompt",
        "duration",
        "bpm",
        "key",
        "num_steps",
        "guidance",
        "seed",
        "model",
    ],
    # bars: 4 or 8, the loop length when bpm is given (default: the nearest to duration).
    # sampler: stable-audio-tools sampler_type; device: "mps", "cuda" or "cpu" (default: best).
    "adapter_params": ["bars", "sampler", "device"],
    "on_unsupported_param": "warn",
    "output": {"default_format": "wav", "sample_rate": 44100, "returns": "array"},
}
