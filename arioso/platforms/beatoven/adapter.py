"""Beatoven.ai adapter via REST API."""

import time

from arioso.base import AudioResult, Song
from arioso.platforms._base_adapter import BaseRestAdapter


class Adapter(BaseRestAdapter):
    """Adapter for Beatoven.ai music generation.

    Beatoven uses a three-step flow:
    1. POST /tracks to create a track and get a track_id.
    2. Poll GET /tracks/{track_id} until status is 'composed'.
    3. GET /tracks/{track_id}/audio to retrieve the download URL.
    """

    def generate(
        self,
        prompt: str,
        *,
        duration: float = 30,
        negative_prompt: str = "",
        seed: int | None = None,
        guidance: float = 16,
        num_steps: int = 100,
        looping: bool = False,
        wait_for_completion: bool = True,
        poll_interval: float = 5.0,
        timeout: float = 300.0,
        **kwargs,
    ) -> list[Song]:
        """Generate music via Beatoven.ai.

        Args:
            prompt: Text description of desired music.
            duration: Track duration in seconds (5-150).
            negative_prompt: Elements to avoid in generation.
            seed: Random seed for reproducibility.
            guidance: Creativity/guidance scale (default 16).
            num_steps: Refinement steps (default 100).
            looping: Whether to generate loopable audio.
            wait_for_completion: If True, poll until audio is ready.
            poll_interval: Seconds between status checks.
            timeout: Max seconds to wait for completion.

        Returns:
            List containing a single Song object.
        """
        payload = {
            "prompt": prompt,
            "duration": duration,
            "creativity": guidance,
            "refinement": num_steps,
            "ENABLE_LOOPING": looping,
        }

        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if seed is not None:
            payload["seed"] = seed

        response = self.session.post(f"{self.base_url}/tracks", json=payload)
        response.raise_for_status()
        data = response.json()

        track_id = data.get("track_id", data.get("id", ""))
        if not track_id:
            raise RuntimeError(f"Beatoven API did not return a track_id: {data}")

        if not wait_for_completion:
            return [
                Song(
                    id=track_id,
                    audio=AudioResult(format="mp3"),
                    platform="beatoven",
                    status="pending",
                    metadata=data,
                )
            ]

        return self._poll_and_fetch(
            track_id,
            poll_interval=poll_interval,
            timeout=timeout,
        )

    def get_status(self, track_id: str) -> str:
        """Check the generation status of a track.

        Args:
            track_id: The track ID returned from generate().

        Returns:
            Status string from the API (e.g. 'composing', 'composed').
        """
        response = self.session.get(f"{self.base_url}/tracks/{track_id}")
        response.raise_for_status()
        data = response.json()
        return data.get("status", "unknown")

    def get_audio_url(self, track_id: str) -> str:
        """Retrieve the audio download URL for a completed track.

        Args:
            track_id: The track ID of a composed track.

        Returns:
            The audio download URL.
        """
        response = self.session.get(f"{self.base_url}/tracks/{track_id}/audio")
        response.raise_for_status()
        data = response.json()
        return data.get("audio_url", data.get("url", ""))

    def _poll_and_fetch(
        self,
        track_id: str,
        *,
        poll_interval: float = 5.0,
        timeout: float = 300.0,
    ) -> list[Song]:
        """Poll until composed, then fetch the audio URL."""
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_status(track_id)
            if status == "composed":
                audio_url = self.get_audio_url(track_id)
                return [
                    Song(
                        id=track_id,
                        audio=AudioResult(
                            audio_url=audio_url,
                            format="mp3",
                            sample_rate=44100,
                        ),
                        platform="beatoven",
                        status="complete",
                    )
                ]
            if status in ("failed", "error"):
                raise RuntimeError(
                    f"Beatoven generation failed (status={status}): track_id={track_id}"
                )
            time.sleep(poll_interval)

        raise TimeoutError(
            f"Beatoven generation did not complete within {timeout}s "
            f"(track_id={track_id})"
        )
