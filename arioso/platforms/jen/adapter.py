"""Jen adapter via REST API."""

from arioso.base import AudioResult, Song
from arioso.platforms._base_adapter import BaseRestAdapter


class Adapter(BaseRestAdapter):
    """Adapter for Jen music generation."""

    def generate(
        self,
        prompt: str,
        *,
        duration: float = 30,
        output_format: str = "mp3",
        continue_from: str = "",
        **kwargs,
    ) -> list[Song]:
        """Generate music via Jen.

        Args:
            prompt: Text description of desired music.
            duration: Track duration in seconds.
            output_format: Output format ('mp3' or 'wav').
            continue_from: Track ID or URL to extend from.

        Returns:
            List containing a single Song object.
        """
        payload = {
            "prompt": prompt,
            "duration": duration,
            "format": output_format,
        }

        if continue_from:
            payload["continue_from"] = continue_from

        response = self.session.post(f"{self.base_url}/generate", json=payload)
        response.raise_for_status()
        data = response.json()

        audio_url = data.get("audio_url", data.get("url", ""))
        track_id = data.get("id", data.get("track_id", ""))

        return [
            Song(
                id=track_id,
                audio=AudioResult(
                    audio_url=audio_url,
                    format=output_format,
                    sample_rate=48000,
                ),
                platform="jen",
                status="complete" if audio_url else "pending",
                metadata=data,
            )
        ]
