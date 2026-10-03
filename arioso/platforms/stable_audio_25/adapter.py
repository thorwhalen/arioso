"""Stable Audio 2.5 adapter (fal.ai): text-to-audio and audio-to-audio.

Unlike the local ``stable_audio`` platform (Stable Audio Open via diffusers,
which has no strength knob), the hosted 2.5 audio-to-audio endpoint takes a
``strength`` in [0, 1]: low values keep the input nearly intact, high values
let the prompt take over. That makes it the arioso backend for "the same piece,
subtly changed".
"""

from __future__ import annotations

from arioso.base import Song
from arioso._fal import fal_audio_song, fal_run, fal_upload_audio
from arioso.platforms.stable_audio_25.config import PLATFORM_CONFIG

_API = PLATFORM_CONFIG["api"]


class Adapter:
    """fal.ai Stable Audio 2.5 adapter."""

    def __init__(self, config: dict):
        self.config = config

    def generate(
        self,
        prompt: str,
        *,
        duration: float = None,
        num_steps: int = 8,
        guidance: float = 1.0,
        seed: int = None,
        audio_input=None,
        audio_input_strength: float = 0.8,
        fetch: bool = True,
        **kwargs,
    ) -> Song:
        """Generate audio from a prompt, or transform ``audio_input`` toward it.

        Args:
            prompt: Text description of the desired audio (required).
            duration: Output length in seconds (1-190). Text-to-audio
                defaults to 30 s (fal's own default is its 190 s maximum, the
                most expensive clip); audio-to-audio defaults to the input's
                length.
            num_steps: Denoising steps (``num_inference_steps``, default 8).
            guidance: Prompt adherence (``guidance_scale``, default 1).
            seed: Random seed for reproducibility.
            audio_input: Audio to transform (path, bytes, Song, URL, ...).
                When given, the audio-to-audio endpoint is used.
            audio_input_strength: Denoising strength for audio-to-audio
                (0-1, default 0.8); lower keeps more of the input.
            fetch: Download the result so ``audio_bytes`` is populated.

        Returns:
            A completed Song (``audio_bytes`` and ``audio_url``).
        """
        if not prompt:
            raise ValueError("stable_audio_25 requires a non-empty prompt")
        arguments = {
            "prompt": prompt,
            "num_inference_steps": num_steps,
            "guidance_scale": guidance,
        }
        if seed is not None:
            arguments["seed"] = int(seed)
        seconds = None
        if duration is not None:
            seconds = max(1, min(int(round(duration)), _API["max_seconds"]))
        if audio_input is not None:
            if not 0 <= audio_input_strength <= 1:
                raise ValueError("audio_input_strength must be in [0, 1]")
            arguments["audio_url"] = fal_upload_audio(audio_input)
            arguments["strength"] = audio_input_strength
            if seconds is not None:  # this endpoint names it total_seconds
                arguments["total_seconds"] = seconds
            endpoint = _API["audio_to_audio_endpoint"]
        else:
            arguments["seconds_total"] = seconds or _API["default_seconds"]
            endpoint = _API["text_to_audio_endpoint"]
        result = fal_run(endpoint, arguments)
        meta = {k: v for k, v in arguments.items() if k != "audio_url"}
        meta.update(endpoint=endpoint, audio_to_audio=audio_input is not None)
        return fal_audio_song(
            result, platform="stable_audio_25", metadata=meta, fetch=fetch
        )
