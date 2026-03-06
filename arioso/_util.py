"""Internal utilities for config loading and common helpers."""

import os
from typing import Optional


def load_env_file(path: str = ".env") -> dict[str, str]:
    """Load key=value pairs from a .env file into a dict.

    Does NOT modify os.environ. Returns empty dict if file doesn't exist.
    """
    env = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("\"'")
                env[key] = value
    except FileNotFoundError:
        pass
    return env


def get_config(
    key: str,
    default: Optional[str] = None,
    *,
    env_file: str = ".env",
) -> Optional[str]:
    """Get a config value from environment or .env file.

    Priority: os.environ > .env file > default.
    """
    value = os.environ.get(key)
    if value is not None:
        return value
    file_env = load_env_file(env_file)
    return file_env.get(key, default)


def get_suno_cookie_from_browser(browser: str = "safari") -> str:
    """Extract Suno cookies from a browser's cookie store.

    Requires the ``browser_cookie3`` package (``pip install browser-cookie3``).

    Args:
        browser: Browser name — "safari", "chrome", "firefox", "brave", "edge".

    Returns:
        A cookie header string for suno.com / clerk.suno.com domains.
    """
    try:
        import browser_cookie3
    except ImportError:
        raise ImportError(
            "browser_cookie3 is required to extract cookies from browsers.\n"
            "Install it with: pip install browser-cookie3"
        )

    loader = getattr(browser_cookie3, browser, None)
    if loader is None:
        raise ValueError(
            f"Unknown browser: {browser!r}. "
            f"Supported: safari, chrome, firefox, brave, edge"
        )

    # Extract cookies for both suno.com and clerk.suno.com
    domains = [".suno.com", "suno.com", "clerk.suno.com"]
    cookie_jar = loader(domain_name=".suno.com")

    # Format as a Cookie header string
    parts = []
    for cookie in cookie_jar:
        parts.append(f"{cookie.name}={cookie.value}")

    if not parts:
        raise RuntimeError(
            f"No suno.com cookies found in {browser}. "
            "Make sure you're logged into suno.com in that browser."
        )

    return "; ".join(parts)
