"""Arioso - Unified facade for AI music generation platforms.

Usage::

    import arioso

    # Generate with the default platform (musicgen)
    song = arioso.generate("upbeat jazz piano", duration=10)

    # Generate with a specific platform
    song = arioso.generate("epic orchestral", platform="elevenlabs", duration=30)

    # List available platforms
    arioso.list_platforms()  # ['musicgen', 'sunoapi', 'elevenlabs', ...]

    # Get platform config
    arioso.get_platform_info("musicgen")

    # Rich platform access via services
    s = arioso.services.sunoapi
    s.generate("jazz piano", duration=30)       # unified names
    s.native_generate("jazz", genre="jazz")     # native names
    s.upload_file("/path/to/audio.mp3")         # platform-specific

    # Cross-platform slices
    arioso.generators["sunoapi"]("jazz")
    arioso.generators.sunoapi("jazz")
"""

from arioso.base import Song, AudioResult, AFFORDANCES
from arioso.services import ServiceCollection, SliceMapping

services = ServiceCollection()
generators = SliceMapping(services, "generate")
native_generators = SliceMapping(services, "native_generate")
infos = SliceMapping(services, "info")
configs = SliceMapping(services, "config")
adapters = SliceMapping(services, "adapter")


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

        song = generate("upbeat jazz piano", platform="musicgen", duration=10)
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


#: Affordances that carry caller-supplied *input* audio (used by :func:`enhance`).
#: Distinct from clip-extension affordances like ``continue_from`` (which
#: reference a prior generation by id/URL rather than uploaded audio).
AUDIO_INPUT_AFFORDANCES = ("audio_input", "melody", "reference_audio")


def supports_audio_input(platform: str) -> bool:
    """Whether *platform* can condition on caller-supplied input audio.

    Returns True if the platform declares any of
    :data:`AUDIO_INPUT_AFFORDANCES` (``audio_input`` / ``melody`` /
    ``reference_audio``) in its config's ``supported_affordances``.

    Example::

        arioso.supports_audio_input("stable_audio")  # True
        arioso.supports_audio_input("mubert")        # False
    """
    try:
        config = get_platform_info(platform)
    except Exception:
        return False
    supported = set(config.get("supported_affordances", []))
    return any(a in supported for a in AUDIO_INPUT_AFFORDANCES)


def _audio_affordance_for(platform: str, prefer: str = "auto") -> str:
    """Pick which audio-carrying affordance to route input audio into.

    ``prefer='auto'`` selects the first supported of
    :data:`AUDIO_INPUT_AFFORDANCES`; otherwise validates the explicit choice.
    """
    config = get_platform_info(platform)
    supported = set(config.get("supported_affordances", []))
    if prefer != "auto":
        if prefer not in AUDIO_INPUT_AFFORDANCES:
            raise ValueError(
                f"as_={prefer!r} must be one of {AUDIO_INPUT_AFFORDANCES} or 'auto'"
            )
        if prefer not in supported:
            raise ValueError(
                f"Platform {platform!r} does not support the {prefer!r} affordance"
            )
        return prefer
    for aff in AUDIO_INPUT_AFFORDANCES:
        if aff in supported:
            return aff
    raise ValueError(
        f"Platform {platform!r} does not accept input audio. Check with "
        f"arioso.supports_audio_input(platform); audio-capable platforms "
        f"include 'stable_audio' and 'musicgen'."
    )


def enhance(
    audio,
    prompt: str = "",
    *,
    platform: str = "stable_audio",
    strength: float = None,
    as_: str = "auto",
    **kwargs,
) -> Song:
    """Transform existing audio into AI-enhanced audio (pipeline stage 3->4).

    Progressive-disclosure sugar over :func:`generate`: routes *audio* into the
    platform's audio-conditioning affordance and generates. This is the entry
    point for the "rendered MIDI audio -> AI-enhanced audio" step.

    Args:
        audio: The input audio to transform -- a :class:`~arioso.base.Song`,
            :class:`~arioso.base.AudioResult`, ``bytes``, a file path, an
            ``(array, sample_rate)`` pair, or a NumPy waveform (normalized by
            ``arioso._audio.to_audio_ref``).
        prompt: Optional text guiding the transformation.
        platform: An audio-capable platform (default ``'stable_audio'``); verify
            with :func:`supports_audio_input`.
        strength: How much the input audio influences the output (0-1), where the
            platform supports it. (Note: ``stable_audio`` via diffusers has no
            strength knob and will warn if one is passed.)
        as_: Which affordance to route *audio* into -- ``'auto'`` (default; picks
            ``audio_input`` > ``melody`` > ``reference_audio``) or an explicit
            affordance name from :data:`AUDIO_INPUT_AFFORDANCES`.
        **kwargs: Further unified affordance parameters (duration, seed, ...).

    Returns:
        A :class:`~arioso.base.Song` with the enhanced audio.

    Example::

        rendered = ...  # a Song from a score2audio render
        better = arioso.enhance(rendered, "warm analog studio band")
    """
    affordance = _audio_affordance_for(platform, as_)
    call_kwargs = dict(kwargs)
    call_kwargs[affordance] = audio
    if strength is not None:
        call_kwargs["audio_input_strength"] = strength
    return generate(prompt, platform=platform, **call_kwargs)


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


def check_status(song: Song) -> list[Song]:
    """Check the current status of a pending Song and return updated Songs.

    For platforms that use async/callback-based generation (like sunoapi),
    this polls the platform's status endpoint to get the latest state,
    including audio URLs once generation is complete.

    Args:
        song: A Song object (typically with status='pending').

    Returns:
        List of updated Song objects with current status and audio URLs.

    Example::

        songs = arioso.generate_many("reggae", platform="sunoapi", ...)
        # ... wait a bit ...
        updated = arioso.check_status(songs[0])
        if updated[0].status == "complete":
            print(updated[0].audio_url)
    """
    from arioso.registry import get_platform

    platform = song.platform
    if not platform:
        raise ValueError("Song has no platform set, cannot check status")

    entry = get_platform(platform)
    adapter = entry["adapter"]

    if not hasattr(adapter, "get_status"):
        raise NotImplementedError(
            f"Platform {platform!r} does not support status checking"
        )

    task_id = song.id
    if not task_id:
        raise ValueError("Song has no id/taskId, cannot check status")

    return adapter.get_status(task_id)


def fetch_audio(song: Song) -> Song:
    """Download the audio bytes for a Song that has an audio_url.

    Args:
        song: A Song with a populated audio_url (status='complete').

    Returns:
        A new Song with audio_bytes populated.

    Example::

        updated = arioso.check_status(song)
        if updated[0].status == "complete":
            song_with_audio = arioso.fetch_audio(updated[0])
            # song_with_audio.audio_bytes is now the raw MP3 data
    """
    from arioso.registry import get_platform

    platform = song.platform
    if not platform:
        raise ValueError("Song has no platform set")

    entry = get_platform(platform)
    adapter = entry["adapter"]

    if hasattr(adapter, "fetch_audio"):
        return adapter.fetch_audio(song)

    # Generic fallback: download from audio_url
    url = song.audio_url
    if not url:
        raise ValueError(
            f"Song {song.id!r} has no audio_url. "
            "Is the generation complete? Try check_status() first."
        )
    import requests

    response = requests.get(url)
    response.raise_for_status()
    return Song(
        id=song.id,
        title=song.title,
        audio=AudioResult(
            audio_bytes=response.content,
            audio_url=url,
            format=song.audio.format,
            duration_seconds=song.audio.duration_seconds,
            sample_rate=song.audio.sample_rate,
        ),
        platform=song.platform,
        status=song.status,
        metadata=song.metadata,
    )
