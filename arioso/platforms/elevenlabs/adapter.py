"""ElevenLabs Music adapter.

Uses ``ho.route_to_func`` to auto-generate the raw callable from the
ElevenLabs OpenAPI spec, then handles parameter translation for
complex fields like ``composition_plan``.
"""

import warnings
import os

from arioso.base import AudioResult, Song
from arioso.platforms._base_adapter import BaseRestAdapter


class Adapter(BaseRestAdapter):
    """ElevenLabs Music adapter with OpenAPI-based function generation."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._raw_func = None

    def _ensure_func(self):
        """Lazy-build the raw function from the OpenAPI spec."""
        if self._raw_func is not None:
            return

        try:
            from ho import route_to_func
            from ju.oas import Routes, ensure_openapi_dict

            spec = ensure_openapi_dict(self.config["api"]["openapi_spec_url"])
            routes = Routes(spec)
            endpoint = self.config["api"]["generate_endpoint"]
            target_route = routes[endpoint["method"], endpoint["path"]]

            api_key = os.environ.get(self.config["auth"]["env_var"], "")
            header = self.config["auth"]["header_name"]
            raw = route_to_func(
                target_route,
                self.config["api"]["base_url"],
                custom_headers={header: api_key},
            )
            self._raw_func = _bind_header_param(raw, header, api_key)
        except (ImportError, Exception):
            # Fallback to plain requests if ho/ju not available
            self._raw_func = self._fallback_func

    def _fallback_func(self, **kwargs):
        """Plain-requests call: used when ho/ju are missing or their binding fails."""
        endpoint = self.config["api"]["generate_endpoint"]
        url = f"{self.base_url}{endpoint['path']}"
        params = {}
        if "output_format" in kwargs:  # a query parameter in the spec, not body
            params["output_format"] = kwargs.pop("output_format")
        response = self.session.post(url, json=kwargs, params=params)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "json" in content_type:
            return response.json()
        return response.content

    def generate(
        self,
        prompt: str,
        *,
        duration: float = 30.0,
        instrumental: bool = False,
        model: str = "music_v1",
        output_format: str = "mp3_44100_128",
        lyrics: str = "",
        title: str = "",
        structure: list = None,
        watermark: bool = False,
        seed: int = None,
        **kwargs,
    ) -> Song:
        """Generate music using the ElevenLabs Music API.

        Args:
            prompt: Text description of desired music.
            duration: Length in seconds (3-600).
            instrumental: If True, generate without vocals.
            model: Model ID.
            output_format: Output format string (e.g. 'mp3_44100_128').
            lyrics: Lyrics to sing. ``[Section]`` lines (or blank lines) split them into
                sections; they turn the request into a composition plan.
            title: Song title. Kept on the returned Song only: the API has no title.
            structure: Your own composition-plan sections (``music_v1``) or chunks
                (``music_v2*``), sent as given.
            watermark: Apply C2PA content watermark.
            seed: Random seed; only with a composition plan (the API refuses it with
                a plain prompt, so it is dropped there, with a warning).

        Returns:
            A Song with audio_bytes populated.
        """
        self._ensure_func()

        native_kwargs = _music_request(
            prompt,
            duration=duration,
            instrumental=instrumental,
            model=model,
            lyrics=lyrics,
            structure=structure,
            seed=seed,
        )
        native_kwargs["output_format"] = output_format
        native_kwargs["sign_with_c2pa"] = watermark

        try:
            result = self._raw_func(**native_kwargs)
        except TypeError as exc:
            # ho can turn optional, nullable spec fields into required
            # arguments (e.g. ``generation_mode``); the plain request needs
            # none of them.
            if "missing a required argument" not in str(exc):
                raise
            self._raw_func = self._fallback_func
            result = self._raw_func(**native_kwargs)

        # Determine actual audio bytes
        if isinstance(result, bytes):
            audio_bytes = result
        elif hasattr(result, "content"):
            audio_bytes = result.content
        elif isinstance(result, dict):
            audio_bytes = None
        else:
            audio_bytes = bytes(result)

        fmt = output_format.split("_")[0] if "_" in output_format else output_format

        return Song(
            audio=AudioResult(
                audio_bytes=audio_bytes,
                format=fmt,
                sample_rate=44100,
                duration_seconds=duration,
            ),
            platform="elevenlabs",
            status="complete",
            title=title,
            metadata={"model": model, "output_format": output_format},
        )


#: ElevenLabs' limits on a composition plan (POST /v1/music, docs 2026-11).
SECTION_MS = (3000, 120000)
MAX_LINES = 30
MAX_LINE_CHARS = 200


def _lyric_sections(lyrics: str) -> list[tuple[str, list[str]]]:
    """``[(name, lines)]`` from lyrics: ``[Verse]``-style lines and blank lines split them.

    >>> _lyric_sections("[Verse]\\na\\nb\\n\\n[Chorus]\\nc")
    [('Verse', ['a', 'b']), ('Chorus', ['c'])]
    """
    sections, name, lines = [], "", []

    def close():
        if lines:
            for i in range(0, len(lines), MAX_LINES):
                sections.append(
                    (name or f"Part {len(sections) + 1}", lines[i : i + MAX_LINES])
                )

    for raw in lyrics.replace("\r", "\n").split("\n"):
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            close()
            name, lines = line[1:-1].strip()[:100], []
        elif not line:
            close()
            name, lines = "", []
        else:
            lines.append(line[:MAX_LINE_CHARS])
    close()
    return sections


def _music_request(
    prompt: str,
    *,
    duration: float,
    instrumental: bool,
    model: str,
    lyrics: str = "",
    structure=None,
    seed=None,
) -> dict:
    """The POST /v1/music body: a plain ``prompt``, or a ``composition_plan`` when there
    are lyrics or a structure (the two are mutually exclusive, and ``seed``,
    ``music_length_ms`` and ``force_instrumental`` belong to one side each).
    """
    sing = bool(lyrics) and not instrumental
    if not (sing or structure):
        if seed is not None:
            warnings.warn(
                "elevenlabs: seed only works with a composition plan; dropped",
                stacklevel=3,
            )
        return {
            "prompt": prompt,
            "music_length_ms": int(duration * 1000),
            "force_instrumental": instrumental,
            "model_id": model,
        }
    styles = [s.strip() for s in prompt.split(",") if s.strip()] or (
        [prompt] if prompt else []
    )
    if structure:
        plan = (
            {"chunks": list(structure)}
            if model.startswith("music_v2")
            else {
                "positive_global_styles": styles,
                "negative_global_styles": [],
                "sections": list(structure),
            }
        )
    else:
        parts = _lyric_sections(lyrics)
        lo, hi = SECTION_MS
        each = max(lo, min(hi, int(duration * 1000 / max(1, len(parts)))))
        if model.startswith("music_v2"):
            plan = {
                "chunks": [
                    {
                        "text": "\n".join(lines),
                        "duration_ms": each,
                        "positive_styles": styles,
                    }
                    for _, lines in parts
                ]
            }
        else:
            plan = {
                "positive_global_styles": styles,
                "negative_global_styles": [],
                "sections": [
                    {
                        "section_name": name,
                        "positive_local_styles": [],
                        "negative_local_styles": [],
                        "duration_ms": each,
                        "lines": lines,
                    }
                    for name, lines in parts
                ],
            }
    body = {"composition_plan": plan, "model_id": model}
    if seed is not None:
        body["seed"] = seed
    return body


def _bind_header_param(func, header: str, value: str):
    """Pre-fill the auth header when the spec also declares it as a parameter.

    The live ElevenLabs OpenAPI spec lists ``xi-api-key`` as a header
    parameter, so ``ho`` turns it into a required ``xi_api_key`` argument and
    ``custom_headers`` alone no longer satisfies the signature
    (``TypeError: missing a required argument: 'xi_api_key'``).
    """
    import functools
    import inspect

    name = header.replace("-", "_").lower()
    try:
        params = inspect.signature(func).parameters
    except (TypeError, ValueError):  # pragma: no cover - uninspectable callable
        return func
    if name in params:
        return functools.partial(func, **{name: value})
    return func
