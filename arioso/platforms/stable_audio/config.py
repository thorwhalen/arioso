"""Stable Audio Open platform configuration."""

DEFAULT_MODEL = "stabilityai/stable-audio-open-1.0"

PLATFORM_CONFIG = {
    "name": "stable_audio",
    "display_name": "Stable Audio Open (Stability AI)",
    "website": "https://huggingface.co/stabilityai/stable-audio-open-1.0",
    "tier": "low_level",
    "access_type": "python_lib",
    "weights_license": "Stability AI Community License",
    # Free for commercial use below US$1M annual revenue; an enterprise licence above.
    "commercial_use": "conditional",
    "auth": {"type": "none"},
    "dependencies": [],
    "optional_dependencies": ["diffusers", "torch", "transformers"],
    "param_map": {
        "prompt": {"native_name": "prompt"},
        "negative_prompt": {"native_name": "negative_prompt"},
        "duration": {"native_name": "audio_end_in_s", "native_default": 10.0},
        "num_steps": {
            "native_name": "num_inference_steps",
            "native_default": 200,
        },
        "guidance": {"native_name": "guidance_scale", "native_default": 7.0},
        "seed": {
            "native_name": "generator",
            "adapter_handled": True,
        },
        "batch_size": {"native_name": "num_waveforms_per_prompt"},
        "sampler": {
            "native_name": "sampler_type",
            "native_default": "dpmpp-3m-sde",
        },
        "audio_input": {
            "native_name": "init_audio",
            "adapter_handled": True,
        },
        "audio_input_strength": {"native_name": "strength"},
        "model": {
            "native_name": "pretrained_model_name_or_path",
            "native_default": DEFAULT_MODEL,
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
        "batch_size",
        "sampler",
        "audio_input",
        "audio_input_strength",
        "model",
    ],
    "on_unsupported_param": "warn",
    "output": {
        "default_format": "wav",
        "sample_rate": 44100,
        "returns": "array",
    },
}
