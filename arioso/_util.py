"""Internal utilities for arioso: auth helpers, HTTP session factory."""

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
