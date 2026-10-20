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


_SUBTYPE_FORMAT = {
    "mpeg": "mp3",
    "mp3": "mp3",
    "x-wav": "wav",
    "wav": "wav",
    "wave": "wav",
    "vnd.wave": "wav",
    "ogg": "ogg",
    "flac": "flac",
    "x-flac": "flac",
    "aac": "aac",
    "mp4": "m4a",
    "webm": "webm",
}


def _format_of(content_type: str, url: str) -> str:
    """``audio/wav;rate=44100`` -> ``wav``; unknown types fall back to the URL."""
    subtype = content_type.split(";")[0].strip().lower().rpartition("/")[2]
    if subtype in _SUBTYPE_FORMAT:
        return _SUBTYPE_FORMAT[subtype]
    ext = url.split("?")[0].rpartition(".")[2].lower()
    return _SUBTYPE_FORMAT.get(ext, ext if 2 <= len(ext) <= 4 else "wav")


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
    fmt = _format_of(file.get("content_type") or "", url)
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


# ---------------------------------------------------------------------------
# Config-driven adapter: a fal-hosted model is a config entry, not an adapter
# ---------------------------------------------------------------------------

#: Values that count as "not given" for a unified parameter.
_ABSENT = (None, "")

_COERCE = {"int": lambda v: int(round(float(v))), "float": float, "str": str}


class FalAdapter:
    """Build and run a fal.ai call from a platform config's ``"fal"`` section.

    The section declares, per endpoint (``text_to_audio``, ``audio_to_audio``), the
    *native* argument each unified affordance becomes. ``shared`` arguments apply to
    every endpoint; the ``audio_to_audio`` endpoint is used when ``audio_input`` is
    given. Each native argument is a spec::

        "native_name": {
            "from": ["unified", "names"],      # first one given (not None/"") wins
            "default": 8,                      # used when none is given (omitted if absent)
            "default_from": "other_native",    # ...or copy another native argument's value
            "required": True | "message",      # ValueError when nothing is given
            "type": "int" | "float" | "str",   # coerce (int rounds)
            "clamp": [lo, hi],                 # clamp into range
            "range": [lo, hi],                 # ValueError outside the range
            "choices": [...],                  # ValueError outside the set
            "force": {"when": "unified", "value": X},  # value X when that param is truthy
            "upload": True,                    # audio: upload and pass the URL
        }

    ``native_extras`` are fal-native argument names passed through from the caller's
    keywords as given; any other unknown keyword is ignored. ``fetch`` (download the
    result) is the one adapter keyword.

    ``run`` and ``upload`` are injected (default: :func:`fal_run`,
    :func:`fal_upload_audio`), so tests and callers can swap the transport.
    """

    def __init__(
        self,
        config: dict,
        *,
        run=None,
        upload=None,
    ):
        self.config = config
        self.spec = config["fal"]
        self.platform = self.spec.get("platform") or config.get("name", "fal")
        self._run = run or fal_run
        self._upload = upload or fal_upload_audio

    # -- building the call ---------------------------------------------------

    def _endpoint(self, params: dict) -> tuple:
        kind = "audio_to_audio" if params.get("audio_input") is not None else "text_to_audio"
        endpoint = self.spec["endpoints"].get(kind)
        if endpoint is None:
            raise ValueError(f"{self.platform} has no {kind} endpoint")
        return kind, endpoint

    def _value(self, native: str, rule: dict, params: dict, built: dict):
        given = next(
            (params[name] for name in rule.get("from", ()) if params.get(name) not in _ABSENT),
            None,
        )
        force = rule.get("force")
        if force and params.get(force["when"]):
            given = force["value"]
        if given is None:
            if rule.get("required"):
                message = rule["required"]
                raise ValueError(
                    message
                    if isinstance(message, str)
                    else f"{self.platform} requires a non-empty {rule['from'][0]}"
                )
            if "default_from" in rule:
                given = built.get(rule["default_from"])
            else:
                given = rule.get("default")
        if given is None:
            return None
        name = (rule.get("from") or [native])[0]
        if rule.get("upload"):
            return self._upload(given)
        if rule.get("type"):
            given = _COERCE[rule["type"]](given)
        if "range" in rule:
            low, high = rule["range"]
            if not low <= given <= high:
                raise ValueError(f"{name} must be in [{low}, {high}]")
        if "clamp" in rule:
            low, high = rule["clamp"]
            given = max(low, min(given, high))
        if "choices" in rule and given not in rule["choices"]:
            choices = " or ".join(repr(c) for c in rule["choices"])
            raise ValueError(f"{name} must be {choices}")
        return given

    def build(self, params: dict) -> tuple:
        """``(endpoint, arguments, uploaded)`` for ``params`` (unified names); no network call
        except uploads of ``audio_input``."""
        kind, endpoint = self._endpoint(params)
        rules = {**self.spec.get("shared", {}), **endpoint.get("arguments", {})}
        arguments: dict = {}
        uploaded: set = set()
        # `default_from` needs its source built first, so build in declaration order
        # with the sources (those without default_from) first.
        ordered = sorted(rules.items(), key=lambda item: "default_from" in item[1])
        for native, rule in ordered:
            value = self._value(native, rule, params, arguments)
            if value is not None:
                arguments[native] = value
                if rule.get("upload"):
                    uploaded.add(native)
        for key in self.spec.get("native_extras", ()):
            if key in params and params[key] is not None:
                arguments[key] = params[key]
        return endpoint["endpoint"], arguments, uploaded

    def accepted_params(self) -> frozenset:
        """Every keyword this adapter reads: unified names, native extras and ``fetch``."""
        rules = [
            *self.spec.get("shared", {}).values(),
            *(
                rule
                for endpoint in self.spec["endpoints"].values()
                for rule in endpoint.get("arguments", {}).values()
            ),
        ]
        names = {name for rule in rules for name in rule.get("from", ())}
        names |= {rule["force"]["when"] for rule in rules if "force" in rule}
        return frozenset(names | set(self.spec.get("native_extras", ())) | {"prompt", "fetch"})

    # -- the adapter contract --------------------------------------------------

    def generate(self, prompt: str = "", *, fetch: bool = True, **params) -> Song:
        """Run the platform's fal endpoint for the unified ``params`` and return a Song."""
        params["prompt"] = prompt
        endpoint, arguments, uploaded = self.build(params)
        result = self._run(endpoint, arguments)
        meta = {k: v for k, v in arguments.items() if k not in uploaded}
        meta.update(endpoint=endpoint, audio_to_audio=params.get("audio_input") is not None)
        return fal_audio_song(result, platform=self.platform, metadata=meta, fetch=fetch)
