"""ACE-Step platform configuration: fal.ai hosted, or ACE-Step 1.5 run locally.

Live docs (verified 2026-10-03): https://fal.ai/models/fal-ai/ace-step/api and
https://fal.ai/models/fal-ai/ace-step/audio-to-audio/api. Local runtime: the
``ACE-Step/ACE-Step-1.5`` checkout (MIT code and weights), verified against its
``docs/en/INFERENCE.md`` and ``acestep.inference.GenerationParams`` on 2026-11-10.
"""

from arioso._isolated import GitSource

PLATFORM_CONFIG = {
    "name": "ace_step",
    "display_name": "ACE-Step (fal.ai, or local ACE-Step 1.5)",
    "website": "https://fal.ai/models/fal-ai/ace-step",
    "tier": "structured",
    "access_type": "rest_api",
    "auth": {"type": "api_key", "env_var": "FAL_KEY"},
    "dependencies": [],
    "optional_dependencies": ["fal_client", "requests", "soundfile"],
    "weights_license": "MIT (ACE-Step 1.5; Apache-2.0 for v1 on fal)",
    "commercial_use": "yes",
    # runtime="local": ACE-Step 1.5 in its own checkout and environment (arioso._isolated).
    "runtime": {
        "name": "ace-step-1.5",
        "env_var": "ARIOSO_ACE_STEP_DIR",
        # the commit measured on 2026-11-10 (thorwhalen/arioso#63)
        "source": GitSource(
            "https://github.com/ACE-Step/ACE-Step-1.5",
            "ca1e85fe9430179831e6bc6be790c332190a3866",
        ),
        "setup": (
            "cd {root} && uv sync   # checkpoints (about 9.4 GB) download on first use"
        ),
    },
    "worker": "ace_step",  # arioso/_workers/ace_step_worker.py
    "param_map": {
        "prompt": {"native_name": "tags", "required": True, "adapter_handled": True},
        "genre": {"native_name": "tags", "adapter_handled": True},
        "lyrics": {
            "native_name": "lyrics",
            "native_default": "[inst]",
            "adapter_handled": True,
        },
        "instrumental": {"native_name": "lyrics", "adapter_handled": True},
        "duration": {
            "native_name": "duration",
            "native_default": 60.0,
            "adapter_handled": True,
        },
        "num_steps": {
            "native_name": "number_of_steps",
            "native_default": 27,
            "adapter_handled": True,
        },
        "guidance": {
            "native_name": "guidance_scale",
            "native_default": 15.0,
            "adapter_handled": True,
        },
        "seed": {"native_name": "seed", "adapter_handled": True},
        "audio_input": {"native_name": "audio_url", "adapter_handled": True},
    },
    "supported_affordances": [
        "prompt",
        "genre",
        "lyrics",
        "instrumental",
        "duration",
        "num_steps",
        "guidance",
        "seed",
        "audio_input",
        # local runtime only (the fal adapter warns and drops them)
        "bpm",
        "key",
        "model",
        "reference_audio",
        "audio_input_strength",
    ],
    # The adapter takes the unified names itself (native_name documents the
    # mapping), and these adapter-only keywords pass validation untouched.
    "adapter_params": [
        "runtime",
        "lm_model",
        "timesignature",
        "fetch",
        "original_tags",
        "original_lyrics",
        "edit_mode",
        "scheduler",
        "guidance_type",
        "granularity_scale",
        "guidance_interval",
        "guidance_interval_decay",
        "minimum_guidance_scale",
        "tag_guidance_scale",
        "lyric_guidance_scale",
        "original_seed",
    ],
    "on_unsupported_param": "warn",
    "output": {"default_format": "wav", "sample_rate": 44100, "returns": "bytes"},
    "api": {
        "text_to_audio_endpoint": "fal-ai/ace-step",
        "audio_to_audio_endpoint": "fal-ai/ace-step/audio-to-audio",
    },
    # How unified affordances become fal arguments (see arioso._fal.FalAdapter).
    # ACE-Step is steered by style tags, so `genre` (else `prompt`) is `tags`; empty
    # lyrics or instrumental=True send "[inst]".
    "fal": {
        "platform": "ace_step",
        "shared": {
            "tags": {
                "from": ["genre", "prompt"],
                "required": "ace_step requires style tags (prompt or genre)",
            },
            "lyrics": {
                "from": ["lyrics"],
                "default": "[inst]",
                "force": {"when": "instrumental", "value": "[inst]"},
            },
            "number_of_steps": {"from": ["num_steps"], "default": 27},
            "guidance_scale": {"from": ["guidance"], "default": 15.0},
            "seed": {"from": ["seed"], "type": "int"},
        },
        "native_extras": [
            "scheduler",
            "guidance_type",
            "granularity_scale",
            "guidance_interval",
            "guidance_interval_decay",
            "minimum_guidance_scale",
            "tag_guidance_scale",
            "lyric_guidance_scale",
            "original_seed",
        ],
        "endpoints": {
            "text_to_audio": {
                "endpoint": "fal-ai/ace-step",
                "arguments": {
                    "duration": {
                        "from": ["duration"],
                        "default": 60.0,
                        "type": "float",
                    },
                },
            },
            "audio_to_audio": {
                "endpoint": "fal-ai/ace-step/audio-to-audio",
                "arguments": {
                    "audio_url": {"from": ["audio_input"], "upload": True},
                    "original_tags": {
                        "from": ["original_tags"],
                        "default_from": "tags",
                    },
                    "original_lyrics": {"from": ["original_lyrics"], "default": ""},
                    "edit_mode": {
                        "from": ["edit_mode"],
                        "default": "remix",
                        "choices": ["remix", "lyrics"],
                    },
                },
            },
        },
    },
}
