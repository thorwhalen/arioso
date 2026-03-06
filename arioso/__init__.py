"""Arioso - Unified facade for AI music generation platforms.

Usage::

    import arioso

    # Generate with the default platform (musicgen)
    song = arioso.generate("upbeat jazz piano", duration=10)

    # Generate with a specific platform
    song = arioso.generate("epic orchestral", platform="elevenlabs", duration=30)

    # List available platforms
    arioso.list_platforms()  # ['musicgen', 'sunoapi', 'elevenlabs']

    # Get platform config
    arioso.get_platform_info("musicgen")
"""

from arioso.base import Song, AudioResult, AFFORDANCES


def generate(prompt: str, *, platform: str = "musicgen", **kwargs) -> Song:
    """Generate music using the specified platform.

    Args:
        prompt: Text description of desired music.
        platform: Name of the generation platform (default: 'musicgen').
        **kwargs: Parameters using unified affordance names.
            See ``arioso.base.AFFORDANCES`` for the full list.

    Returns:
        A Song object containing the generated audio and metadata.

    Example::

        >>> song = generate("upbeat jazz piano", platform="musicgen", duration=10)
    """
    from arioso.registry import get_platform

    entry = get_platform(platform)
    adapter = entry["adapter"]

    if hasattr(adapter, "generate"):
        result = adapter.generate(prompt, **kwargs)
    elif callable(adapter):
        result = adapter(prompt, **kwargs)
    else:
        raise TypeError(f"Adapter for {platform!r} is not callable")

    # Normalize: if adapter returns a list, return first item
    if isinstance(result, list):
        return result[0] if result else Song(platform=platform, status="error")
    return result


def generate_many(prompt: str, *, platform: str = "musicgen", **kwargs) -> list[Song]:
    """Generate music, returning all results (some platforms return multiple).

    Same interface as :func:`generate` but always returns a list.
    """
    from arioso.registry import get_platform

    entry = get_platform(platform)
    adapter = entry["adapter"]

    if hasattr(adapter, "generate"):
        result = adapter.generate(prompt, **kwargs)
    elif callable(adapter):
        result = adapter(prompt, **kwargs)
    else:
        raise TypeError(f"Adapter for {platform!r} is not callable")

    if isinstance(result, list):
        return result
    return [result]


def list_platforms() -> list[str]:
    """Return names of all available platforms."""
    from arioso.registry import list_platforms as _list

    return _list()


def get_platform_info(name: str) -> dict:
    """Get configuration info for a platform.

    Args:
        name: Platform identifier.

    Returns:
        The platform's PLATFORM_CONFIG dict.
    """
    from arioso.registry import get_platform

    return get_platform(name)["config"]
