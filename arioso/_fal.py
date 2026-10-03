"""Shared plumbing for platforms hosted on fal.ai.

Several arioso platforms (``stable_audio_25``, ``ace_step``, and ``yue``'s fal
backend) call fal.ai the same way: upload any input audio to fal's file store,
``subscribe`` to an endpoint (a blocking queue call), and read an audio File
object back. This module is that one path, so each adapter only declares its
endpoint and its argument mapping.

``fal_client`` is imported lazily; ``FAL_KEY`` must be set in the environment.
"""

from __future__ import annotations

from typing import Any, Optional

from arioso.base import AudioResult, Song
from arioso._audio import to_audio_ref


def _fal_client():
    try:
        import fal_client
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise ImportError(
            "This platform runs on fal.ai and needs the fal_client package: "
            "pip install fal-client (and set FAL_KEY)."
        ) from exc
    return fal_client


def fal_upload_audio(audio) -> str:
    """Return a URL fal endpoints can read for *audio*.

    *audio* is anything :func:`arioso._audio.to_audio_ref` accepts (a path,
    bytes, a Song, an ``(array, sample_rate)`` pair, ...). A string that is
    already an ``http(s)`` URL is passed through untouched.
    """
    if isinstance(audio, str) and audio.startswith(("http://", "https://")):
        return audio
    path = to_audio_ref(audio).as_path()
    return _fal_client().upload_file(path)


def fal_run(endpoint: str, arguments: dict) -> dict:
    """Run a fal endpoint to completion and return its JSON result."""
    return _fal_client().subscribe(endpoint, arguments=arguments)


def _audio_file(result: Any) -> dict:
    """Find the audio File object (``{"url": ..., "content_type": ...}``)."""
    if not isinstance(result, dict):
        return {}
    for key in ("audio", "audio_file", "output"):
        value = result.get(key)
        if isinstance(value, dict) and value.get("url"):
            return value
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return value[0]
    if result.get("url"):
        return result
    return {}


def fal_audio_song(
    result: dict,
    *,
    platform: str,
    metadata: Optional[dict] = None,
    fetch: bool = True,
) -> Song:
    """Wrap a fal audio result as a completed :class:`~arioso.base.Song`.

    With ``fetch=True`` (default) the audio is downloaded so
    ``song.audio_bytes`` is ready to write; ``song.audio_url`` is always set.
    """
    file = _audio_file(result)
    url = file.get("url", "")
    if not url:
        raise RuntimeError(f"{platform}: no audio in fal result: {result!r}")
    content_type = file.get("content_type") or ""
    fmt = content_type.split("/")[-1] if "/" in content_type else ""
    fmt = {"mpeg": "mp3", "x-wav": "wav", "wave": "wav"}.get(fmt, fmt) or "wav"
    audio_bytes = None
    if fetch:
        import requests

        resp = requests.get(url, timeout=300)
        resp.raise_for_status()
        audio_bytes = resp.content
    meta = dict(metadata or {})
    meta.setdefault("seed", result.get("seed"))
    return Song(
        audio=AudioResult(audio_url=url, audio_bytes=audio_bytes, format=fmt),
        platform=platform,
        status="complete",
        metadata=meta,
    )
