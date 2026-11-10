"""Internal utilities for arioso: auth helpers, HTTP session factory, torch device choice."""

import os


def build_auth_headers(auth_config: dict) -> dict:
    """Build HTTP headers for authentication from a platform auth config.

    Args:
        auth_config: Dict with keys 'type', 'env_var', and optionally
            'header_name'. Supported types: 'api_key', 'bearer_token', 'none'.

    Returns:
        Dict of HTTP headers to include in requests.
    """
    auth_type = auth_config.get("type", "none")
    if auth_type == "none":
        return {}
    env_var = auth_config.get("env_var", "")
    key = os.environ.get(env_var, "")
    if auth_type == "api_key":
        header_name = auth_config.get("header_name", "Authorization")
        return {header_name: key}
    elif auth_type == "bearer_token":
        return {"Authorization": f"Bearer {key}"}
    return {}


def make_session(auth_config: dict):
    """Create a requests.Session with auth headers pre-configured.

    Args:
        auth_config: Platform auth config dict.

    Returns:
        A requests.Session instance.
    """
    import requests

    session = requests.Session()
    headers = build_auth_headers(auth_config)
    session.headers.update(headers)
    session.headers.setdefault("Content-Type", "application/json")
    return session


#: Environment variable that forces the torch device of every local platform.
TORCH_DEVICE_ENV_VAR = "ARIOSO_TORCH_DEVICE"


def torch_device() -> str:
    """The torch device local platforms run on: ``$ARIOSO_TORCH_DEVICE``, else
    CUDA, else Apple MPS, else CPU.

    A CPU-only default made a 30-second melody-conditioned MusicGen generation
    take a quarter of an hour on a machine with an Apple GPU.
    """
    import torch

    env = os.environ.get(TORCH_DEVICE_ENV_VAR)
    if env:
        return env
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def torch_dtype(device: str):
    """The weights dtype for *device*: float16 on CUDA, float32 elsewhere.

    Half precision is only reliably supported by CUDA kernels; diffusers audio
    pipelines in float16 on MPS or CPU fail or produce silence.
    """
    import torch

    return torch.float16 if str(device).startswith("cuda") else torch.float32
