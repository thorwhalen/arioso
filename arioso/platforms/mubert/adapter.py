"""Mubert adapter via REST API."""

import os
import time

from arioso.base import AudioResult, Song
from arioso.platforms._base_adapter import BaseRestAdapter

# Map normalized energy float (0-1) to Mubert intensity strings
_ENERGY_THRESHOLDS = ((0.33, "low"), (0.66, "medium"), (1.0, "high"))


def _energy_to_intensity(value: float) -> str:
    """Coerce a 0-1 float energy value to a Mubert intensity string."""
    for threshold, label in _ENERGY_THRESHOLDS:
        if value <= threshold:
            return label
    return "high"


class Adapter(BaseRestAdapter):
    """Adapter for Mubert music generation.

    Mubert uses a two-step flow: POST to /RecordTrackTTM to start a task,
    then poll until the download_link becomes available.
    """

    def generate(
        self,
        prompt: str,
        *,
        duration: float = 30,
        output_format: str = "mp3",
        bitrate: int = 320,
        energy: float | None = None,
        wait_for_completion: bool = True,
        poll_interval: float = 5.0,
        timeout: float = 300.0,
        **kwargs,
    ) -> list[Song]:
        """Generate music via Mubert.

        Args:
            prompt: Text description of desired music.
            duration: Track duration in seconds (15-1500).
            output_format: Output format ('mp3' or 'wav').
            bitrate: Audio bitrate (128 or 320).
            energy: Energy level 0-1 (coerced to low/medium/high).
            wait_for_completion: If True, poll until audio is ready.
            poll_interval: Seconds between status checks.
            timeout: Max seconds to wait for completion.

        Returns:
            List containing a single Song object.
        """
        pat = os.environ.get("MUBERT_PAT", "")
        if not pat:
            raise ValueError(
                "Mubert requires a personal access token. "
                "Set the MUBERT_PAT environment variable."
            )

        params = {
            "pat": pat,
            "prompt": prompt,
            "duration": duration,
            "mode": "track",
            "bitrate": bitrate,
            "format": output_format,
        }

        if energy is not None:
            params["intensity"] = _energy_to_intensity(energy)

        payload = {
            "method": "RecordTrackTTM",
            "params": params,
        }

        endpoint = "/RecordTrackTTM"
        response = self.session.post(
            f"{self.base_url}{endpoint}", json=payload
        )
        response.raise_for_status()
        data = response.json()

        # Extract download link or task info for polling
        tasks = (data.get("data", {}) or {}).get("tasks", [])

        if tasks and tasks[0].get("download_link"):
            return [self._task_to_song(tasks[0])]

        if not wait_for_completion:
            task_id = tasks[0].get("task_id", "") if tasks else ""
            return [
                Song(
                    id=task_id,
                    audio=AudioResult(format=output_format),
                    platform="mubert",
                    status="pending",
                    metadata=data,
                )
            ]

        # Poll until download_link is available
        return self._poll_for_track(
            data,
            output_format=output_format,
            poll_interval=poll_interval,
            timeout=timeout,
        )

    def _poll_for_track(
        self,
        initial_data: dict,
        *,
        output_format: str = "mp3",
        poll_interval: float = 5.0,
        timeout: float = 300.0,
    ) -> list[Song]:
        """Poll Mubert until the download link is available."""
        start = time.time()
        data = initial_data

        while time.time() - start < timeout:
            tasks = (data.get("data", {}) or {}).get("tasks", [])
            if tasks and tasks[0].get("download_link"):
                return [self._task_to_song(tasks[0])]

            time.sleep(poll_interval)

            # Re-request the same endpoint to check status
            response = self.session.post(
                f"{self.base_url}/RecordTrackTTM",
                json={"method": "RecordTrackTTM", "params": {}},
            )
            response.raise_for_status()
            data = response.json()

        raise TimeoutError(
            f"Mubert generation did not complete within {timeout}s"
        )

    def _task_to_song(self, task: dict) -> Song:
        """Convert a Mubert task dict to a Song."""
        download_link = task.get("download_link", "")
        return Song(
            id=task.get("task_id", ""),
            audio=AudioResult(
                audio_url=download_link,
                format="mp3",
                sample_rate=44100,
            ),
            platform="mubert",
            status="complete" if download_link else "pending",
            metadata=task,
        )
