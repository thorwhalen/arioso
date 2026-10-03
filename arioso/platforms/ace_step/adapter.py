"""ACE-Step adapter (fal.ai): text-to-music and audio-to-audio remix.

ACE-Step is steered by comma-separated style *tags*, not a sentence, so the
unified ``prompt`` (or ``genre``) becomes ``tags``. Its audio-to-audio endpoint
"remixes" an input toward new tags; it also needs ``original_tags`` describing
the input, which default to the new tags when not given.
"""

from __future__ import annotations

from arioso.base import Song
from arioso._fal import fal_audio_song, fal_run, fal_upload_audio
from arioso.platforms.ace_step.config import PLATFORM_CONFIG

_API = PLATFORM_CONFIG["api"]
_INSTRUMENTAL = "[inst]"


class Adapter:
    """fal.ai ACE-Step adapter."""

    def __init__(self, config: dict):
        self.config = config

    def generate(
        self,
        prompt: str = "",
        *,
        genre: str = "",
        lyrics: str = "",
        instrumental: bool = False,
        duration: float = 60.0,
        num_steps: int = 27,
        guidance: float = 15.0,
        seed: int = None,
        audio_input=None,
        original_tags: str = "",
        original_lyrics: str = "",
        edit_mode: str = "remix",
        fetch: bool = True,
        **kwargs,
    ) -> Song:
        """Generate music from tags, or remix ``audio_input`` toward them.

        Args:
            prompt: Style tags (comma-separated works best). ``genre`` wins
                when both are given.
            genre: Style tags; an alias of ``prompt`` for this platform.
            lyrics: Lyrics to sing. Empty or ``instrumental=True`` sends
                ``[inst]``.
            instrumental: Force an instrumental (discards ``lyrics``).
            duration: Seconds (text-to-music only; a remix keeps the input's
                length).
            num_steps: ``number_of_steps`` (default 27).
            guidance: ``guidance_scale`` (default 15).
            seed: Random seed.
            audio_input: Audio to remix (path, bytes, Song, URL, ...). When
                given, the audio-to-audio endpoint is used.
            original_tags: Tags describing ``audio_input`` (defaults to the
                new tags).
            original_lyrics: Lyrics of ``audio_input``, if any.
            edit_mode: ``"remix"`` (default) or ``"lyrics"``.
            fetch: Download the result so ``audio_bytes`` is populated.
            **kwargs: Further native fal arguments (``scheduler``,
                ``guidance_type``, ``granularity_scale``, ...), passed through.

        Returns:
            A completed Song.
        """
        tags = genre or prompt
        if not tags:
            raise ValueError("ace_step requires style tags (prompt or genre)")
        lyric_text = _INSTRUMENTAL if instrumental or not lyrics else lyrics
        arguments = {
            "tags": tags,
            "lyrics": lyric_text,
            "number_of_steps": num_steps,
            "guidance_scale": guidance,
        }
        native = {"scheduler", "guidance_type", "granularity_scale", "guidance_interval"}
        arguments.update({k: v for k, v in kwargs.items() if k in native})
        if seed is not None:
            arguments["seed"] = int(seed)
        if audio_input is not None:
            if edit_mode not in ("remix", "lyrics"):
                raise ValueError("edit_mode must be 'remix' or 'lyrics'")
            arguments.update(
                audio_url=fal_upload_audio(audio_input),
                original_tags=original_tags or tags,
                original_lyrics=original_lyrics,
                edit_mode=edit_mode,
            )
            endpoint = _API["audio_to_audio_endpoint"]
        else:
            arguments["duration"] = float(duration)
            endpoint = _API["text_to_audio_endpoint"]
        result = fal_run(endpoint, arguments)
        meta = {k: v for k, v in arguments.items() if k != "audio_url"}
        meta.update(endpoint=endpoint, audio_to_audio=audio_input is not None)
        return fal_audio_song(result, platform="ace_step", metadata=meta, fetch=fetch)
