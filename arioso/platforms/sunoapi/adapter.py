"""Suno adapter via sunoapi.org REST API."""

import os
import time

from arioso.base import AudioResult, Song
from arioso.platforms._base_adapter import BaseRestAdapter

# Valid model versions accepted by sunoapi.org
SUNO_MODELS = ("V4", "V4_5", "V4_5ALL", "V4_5PLUS", "V5")

# Default model, configurable via env var
SUNO_DEFAULT_MODEL = os.environ.get("SUNO_DEFAULT_MODEL", "V4")

# Default callback URL, configurable via env var.
# Required by the API -- set SUNO_CALLBACK_URL to a reachable webhook URL.
SUNO_DEFAULT_CALLBACK_URL = os.environ.get("SUNO_CALLBACK_URL", "")

# Status values returned by the record-info endpoint
_COMPLETE_STATUSES = {"SUCCESS"}
_ERROR_STATUSES = {
    "CREATE_TASK_FAILED",
    "GENERATE_AUDIO_FAILED",
    "SENSITIVE_WORD_ERROR",
    "CALLBACK_EXCEPTION",
}
_PARTIAL_STATUSES = {"TEXT_SUCCESS", "FIRST_SUCCESS"}


def _check_api_error(data: dict):
    """Raise RuntimeError if the API response indicates an error."""
    if isinstance(data, dict) and data.get("code") and data["code"] != 200:
        msg = data.get("msg", "Unknown API error")
        raise RuntimeError(
            f"sunoapi error (code {data['code']}): {msg}"
        )


class Adapter(BaseRestAdapter):
    """Adapter for Suno music generation via sunoapi.org.

    Handles the distinction between simple generation (prompt only)
    and custom generation (with lyrics/style via customMode).

    The sunoapi.org API is callback-based: it returns a taskId immediately
    and POSTs results to your callBackUrl when generation completes.
    Set the SUNO_CALLBACK_URL env var or pass callback_url to generate().

    After calling generate(), use get_status() to poll for results, or
    use generate() with wait_for_completion=True to block until audio is ready.
    """

    def generate(
        self,
        prompt: str,
        *,
        genre: str = "",
        lyrics: str = "",
        title: str = "",
        instrumental: bool = False,
        model: str = "",
        continue_from: str = "",
        continue_at: float = 0,
        callback_url: str = "",
        negative_prompt: str = "",
        wait_for_completion: bool = False,
        poll_interval: float = 5.0,
        timeout: float = 300.0,
        **kwargs,
    ) -> list[Song]:
        """Generate music via sunoapi.org.

        Args:
            prompt: Text description of desired music. In simple mode, this
                is the generation prompt. In custom mode (when lyrics or
                genre are provided), this is used as style if genre is empty.
            genre: Genre/style tags (triggers customMode).
            lyrics: Custom lyrics (triggers customMode). Ignored when
                instrumental=True.
            title: Song title (used in customMode).
            instrumental: If True, generate without vocals.
            model: Suno model version. Valid: {models}.
                Defaults to SUNO_DEFAULT_MODEL env var, or 'V4'.
            continue_from: Clip ID to extend from.
            continue_at: Timestamp in seconds to continue from.
            callback_url: Webhook URL for completion notification (required
                by the API). Defaults to SUNO_CALLBACK_URL env var.
            negative_prompt: Styles to exclude (negativeTags).
            wait_for_completion: If True, poll until audio is ready (or
                timeout). If False (default), return pending Songs immediately.
            poll_interval: Seconds between status checks (default 5).
            timeout: Max seconds to wait for completion (default 300).

        Returns:
            List of Song objects (typically 2 per call).
        """.format(models=", ".join(SUNO_MODELS))
        model = model or SUNO_DEFAULT_MODEL
        callback_url = callback_url or SUNO_DEFAULT_CALLBACK_URL

        if not callback_url:
            raise ValueError(
                "sunoapi.org requires a callback URL. "
                "Set the SUNO_CALLBACK_URL environment variable or pass "
                "callback_url='https://your-server.com/webhook' to generate()."
            )

        # Determine if we need customMode (lyrics, genre, or title provided)
        custom_mode = bool(lyrics or genre or title)

        payload = {
            "model": model,
            "instrumental": instrumental,
            "callBackUrl": callback_url,
            "customMode": custom_mode,
        }

        if custom_mode:
            payload["style"] = genre or prompt
            if title:
                payload["title"] = title
            if not instrumental and lyrics:
                payload["prompt"] = lyrics
            elif not instrumental:
                payload["prompt"] = prompt
        else:
            payload["prompt"] = prompt

        if negative_prompt:
            payload["negativeTags"] = negative_prompt

        if continue_from:
            payload["continue_clip_id"] = continue_from
            if continue_at:
                payload["continue_at"] = continue_at

        endpoint = "/api/v1/generate"
        response = self.session.post(f"{self.base_url}{endpoint}", json=payload)
        response.raise_for_status()
        data = response.json()

        _check_api_error(data)

        # The API returns a taskId; songs arrive via callback or polling.
        task_id = ""
        if isinstance(data, dict):
            inner = data.get("data")
            if isinstance(inner, dict):
                task_id = inner.get("taskId", "")
            if not task_id:
                task_id = data.get("taskId", "")

        if not task_id:
            return self._parse_songs(data, title=title)

        if wait_for_completion:
            return self._poll_for_songs(
                task_id,
                title=title,
                poll_interval=poll_interval,
                timeout=timeout,
            )

        # Return pending songs immediately
        return [
            Song(
                id=task_id,
                title=title,
                audio=AudioResult(format="mp3"),
                platform="sunoapi",
                status="pending",
                metadata=data if isinstance(data, dict) else {"raw": data},
            )
        ]

    def get_status(self, task_id: str) -> list[Song]:
        """Check the status of a generation task and return updated Songs.

        Args:
            task_id: The taskId returned from generate().

        Returns:
            List of Song objects with current status and audio URLs
            (if generation is complete).
        """
        url = f"{self.base_url}/api/v1/generate/record-info"
        response = self.session.get(url, params={"taskId": task_id})
        response.raise_for_status()
        data = response.json()

        _check_api_error(data)

        record = data.get("data", {})
        status_raw = record.get("status", "PENDING")

        if status_raw in _ERROR_STATUSES:
            raise RuntimeError(
                f"sunoapi generation failed (status={status_raw}): "
                f"taskId={task_id}"
            )

        suno_data = record.get("response", {}).get("sunoData", [])
        if not suno_data:
            return [
                Song(
                    id=task_id,
                    platform="sunoapi",
                    status="pending" if status_raw == "PENDING" else "generating",
                    metadata=record,
                )
            ]

        songs = []
        for item in suno_data:
            audio_url = item.get("audioUrl", "")
            stream_url = item.get("streamAudioUrl", "")
            is_complete = bool(audio_url)
            songs.append(
                Song(
                    id=item.get("id", task_id),
                    title=item.get("title", ""),
                    audio=AudioResult(
                        audio_url=audio_url or stream_url,
                        format="mp3",
                        duration_seconds=item.get("duration", 0.0),
                    ),
                    platform="sunoapi",
                    status="complete" if is_complete else "generating",
                    metadata=item,
                )
            )
        return songs

    def fetch_audio(self, song: Song) -> Song:
        """Download the audio bytes for a Song that has an audio_url.

        Args:
            song: A Song object with a populated audio_url.

        Returns:
            A new Song with audio_bytes populated.
        """
        url = song.audio_url
        if not url:
            raise ValueError(
                f"Song {song.id!r} has no audio_url. "
                "Check status with get_status() first."
            )
        response = self.session.get(url)
        response.raise_for_status()
        return Song(
            id=song.id,
            title=song.title,
            audio=AudioResult(
                audio_bytes=response.content,
                audio_url=url,
                format=song.audio.format or "mp3",
                duration_seconds=song.audio.duration_seconds,
                sample_rate=song.audio.sample_rate,
            ),
            platform=song.platform,
            status=song.status,
            metadata=song.metadata,
        )

    def _poll_for_songs(
        self,
        task_id: str,
        *,
        title: str = "",
        poll_interval: float = 5.0,
        timeout: float = 300.0,
    ) -> list[Song]:
        """Poll get_status until completion or timeout."""
        start = time.time()
        while time.time() - start < timeout:
            songs = self.get_status(task_id)
            if all(s.status == "complete" for s in songs):
                return songs
            time.sleep(poll_interval)
        raise TimeoutError(
            f"sunoapi generation did not complete within {timeout}s "
            f"(taskId={task_id})"
        )

    def _parse_songs(self, data, *, title: str = "") -> list[Song]:
        """Parse Song objects from an API response."""
        songs = []
        items = data if isinstance(data, list) else data.get("data", [data])
        if isinstance(items, dict):
            items = [items]
        for item in items:
            if not isinstance(item, dict):
                continue
            audio_url = item.get("audio_url", item.get("audioUrl", ""))
            songs.append(
                Song(
                    id=item.get("id", ""),
                    title=item.get("title", title),
                    audio=AudioResult(
                        audio_url=audio_url,
                        format="mp3",
                    ),
                    platform="sunoapi",
                    status="complete" if audio_url else "pending",
                    metadata=item,
                )
            )
        return songs
