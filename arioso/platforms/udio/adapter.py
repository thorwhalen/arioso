"""Udio adapter via udio-wrapper (unofficial)."""

import os

from arioso.base import AudioResult, Song


class Adapter:
    """Adapter for Udio using the unofficial udio-wrapper package.

    Requires ``pip install udio-wrapper`` and a valid auth cookie
    set in the UDIO_AUTH_COOKIE environment variable.
    """

    def __init__(self, config: dict):
        self.config = config
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return
        try:
            from udio_wrapper import UdioApiWrapper
        except ImportError:
            raise ImportError(
                "udio-wrapper is required for the Udio platform. "
                "Install it with: pip install udio-wrapper"
            )
        cookie = os.environ.get("UDIO_AUTH_COOKIE", "")
        if not cookie:
            raise ValueError(
                "UDIO_AUTH_COOKIE environment variable is required. "
                "Extract it from your browser after logging into udio.com."
            )
        self._client = UdioApiWrapper(auth_token=cookie)

    def generate(
        self,
        prompt: str,
        *,
        lyrics: str = "",
        seed: int = -1,
        audio_input: str = "",
        **kwargs,
    ) -> Song:
        """Generate music via Udio.

        Args:
            prompt: Text description of desired music.
            lyrics: Custom lyrics text.
            seed: Random seed (-1 for random).
            audio_input: Path to conditioning audio file.

        Returns:
            A Song with audio_url populated.
        """
        self._ensure_client()

        gen_kwargs = {"prompt": prompt}
        if lyrics:
            gen_kwargs["custom_lyrics"] = lyrics
        if seed >= 0:
            gen_kwargs["seed"] = seed
        if audio_input:
            gen_kwargs["audio_conditioning_path"] = audio_input

        songs = self._client.make_request(**gen_kwargs)

        results = []
        items = songs if isinstance(songs, list) else [songs]
        for item in items:
            audio_url = ""
            song_id = ""
            if isinstance(item, dict):
                audio_url = item.get("song_path", item.get("audio_url", ""))
                song_id = item.get("id", "")
            elif hasattr(item, "song_path"):
                audio_url = item.song_path
                song_id = getattr(item, "id", "")

            results.append(
                Song(
                    id=song_id,
                    audio=AudioResult(audio_url=audio_url, format="mp3"),
                    platform="udio",
                    status="complete" if audio_url else "pending",
                    metadata=item if isinstance(item, dict) else {},
                )
            )

        return results[0] if len(results) == 1 else results
