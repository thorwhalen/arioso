"""Google Lyria 2 platform configuration."""

PLATFORM_CONFIG = {
    "name": "lyria2",
    "display_name": "Google Lyria 2",
    "website": "https://deepmind.google/technologies/lyria/",
    "tier": "structured",
    "access_type": "rest_api",
    "auth": {
        "type": "bearer_token",
        "env_var": "GOOGLE_CLOUD_API_KEY",
    },
    "dependencies": ["requests"],
    "optional_dependencies": ["google-cloud-aiplatform"],
    "param_map": {
        "prompt": {
            "native_name": "instances[].prompt",
            "required": True,
            "adapter_handled": True,
        },
        "negative_prompt": {
            "native_name": "negative_prompt",
        },
        "seed": {
            "native_name": "seed",
        },
        "model": {
            "native_name": "model",
            "native_default": "lyria-002",
        },
        "batch_size": {
            "native_name": "sample_count",
            "native_default": 1,
        },
    },
    "supported_affordances": [
        "prompt",
        "negative_prompt",
        "seed",
        "model",
        "batch_size",
    ],
    "on_unsupported_param": "warn",
    "output": {
        "default_format": "wav",
        "sample_rate": 48000,
        "returns": "bytes",
    },
    "api": {
        "base_url": "https://us-central1-aiplatform.googleapis.com",
        "generate_endpoint": {
            "method": "post",
        },
    },
}
