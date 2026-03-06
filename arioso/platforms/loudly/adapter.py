"""Loudly adapter via REST API."""

import time

from arioso.base import AudioResult, Song
from arioso.platforms._base_adapter import BaseRestAdapter


class Adapter(BaseRestAdapter):
    """Adapter for Loudly music generation.

    Loudly may return the audio URL directly or require polling,
    depending on the generation complexity.
    """

    def generate(
        self,
        prompt: str,
        *,
        duration: float = 30,
        genre: str = "",
        bpm: int | None = None,
        key: str = "",
        energy: float | None = None,
        instruments: list[str] | None = None,
        structure: list | None = None,
        wait_for_completion: bool = True,
        poll_interval: float = 5.0,
        timeout: float = 300.0,
        **kwargs,
    ) -> list[Song]:
        """Generate music via Loudly.

        Args:
            prompt: Text description of desired music.
            duration: Track duration in seconds.
            genre: Genre tag (50+ options available).
            bpm: Tempo in beats per minute.
            key: Musical key (e.g. 'C major').
            energy: Energy level (0-1).
            instruments: List of instruments (up to 7).
            structure: Song section structure.
            wait_for_completion: If True, poll until audio is ready.
            poll_interval: Seconds between status checks.
            timeout: Max seconds to wait for completion.

        Returns:
            List containing a single Song object.
        """
        payload = {"prompt": prompt, "duration": duration}

        if genre:
            payload["genre"] = genre
        if bpm is not None:
            payload["tempo"] = bpm
        if key:
            payload["key"] = key
        if energy is not None:
            payload["energy"] = energy
        if instruments is not None:
            payload["instruments"] = instruments[:7]
        if structure is not None:
            payload["structure"] = structure

        response = self.session.post(
            f"{self.base_url}/music/generate", json=payload
        )
        response.raise_for_status()
        data = response.json()

        # If audio_url is directly available, return immediately
        audio_url = data.get("audio_url", data.get("url", ""))
        if audio_url:
            return [
                Song(
                    id=data.get("id", ""),
                    audio=AudioResult(
                        audio_url=audio_url,
                        format="mp3",
                        sample_rate=44100,
                    ),
                    platform="loudly",
                    status="complete",
                    metadata=data,
                )
            ]

        # Otherwise, poll for completion
        track_id = data.get("id", data.get("track_id", ""))
        if not track_id:
            raise RuntimeError(
                f"Loudly API did not return audio_url or track id: {data}"
            )

        if not wait_for_completion:
            return [
                Song(
                    id=track_id,
                    audio=AudioResult(format="mp3"),
                    platform="loudly",
                    status="pending",
                    metadata=data,
                )
            ]

        return self._poll_for_audio(
            track_id,
            poll_interval=poll_interval,
            timeout=timeout,
        )

    def _poll_for_audio(
        self,
        track_id: str,
        *,
        poll_interval: float = 5.0,
        timeout: float = 300.0,
    ) -> list[Song]:
        """Poll the Loudly API until audio is available."""
        start = time.time()
        while time.time() - start < timeout:
            response = self.session.get(
                f"{self.base_url}/music/{track_id}"
            )
            response.raise_for_status()
            data = response.json()

            status = data.get("status", "")
            audio_url = data.get("audio_url", data.get("url", ""))

            if audio_url:
                return [
                    Song(
                        id=track_id,
                        audio=AudioResult(
                            audio_url=audio_url,
                            format="mp3",
                            sample_rate=44100,
                        ),
                        platform="loudly",
                        status="complete",
                        metadata=data,
                    )
                ]

            if status in ("failed", "error"):
                raise RuntimeError(
                    f"Loudly generation failed (status={status}): "
                    f"track_id={track_id}"
                )

            time.sleep(poll_interval)

        raise TimeoutError(
            f"Loudly generation did not complete within {timeout}s "
            f"(track_id={track_id})"
        )
