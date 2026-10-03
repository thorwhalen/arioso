"""ElevenLabs Music adapter.

Uses ``ho.route_to_func`` to auto-generate the raw callable from the
ElevenLabs OpenAPI spec, then handles parameter translation for
complex fields like ``composition_plan``.
"""

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
            lyrics: Custom lyrics text.
            title: Song title.
            structure: Song section structure (list of dicts).
            watermark: Apply C2PA content watermark.
            seed: Random seed (streaming endpoint only).

        Returns:
            A Song with audio_bytes populated.
        """
        self._ensure_func()

        native_kwargs = {
            "prompt": prompt,
            "music_length_ms": int(duration * 1000),
            "force_instrumental": instrumental,
            "model_id": model,
            "output_format": output_format,
            "sign_with_c2pa": watermark,
        }

        if seed is not None:
            native_kwargs["seed"] = seed

        # Build composition_plan for lyrics/title/structure
        if lyrics or title or structure:
            composition_plan = {}
            if title:
                composition_plan["title"] = title
            if structure:
                composition_plan["sections"] = structure
            elif lyrics:
                composition_plan["sections"] = [{"lyrics": lyrics}]
            native_kwargs["composition_plan"] = composition_plan

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
