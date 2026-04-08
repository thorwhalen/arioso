"""Suno adapter via sunoapi.org REST API."""

import os
import time
from pathlib import Path

from arioso.base import AudioResult, Song
from arioso.platforms._base_adapter import BaseRestAdapter

# Valid model versions accepted by sunoapi.org
SUNO_MODELS = ("V4", "V4_5", "V4_5ALL", "V4_5PLUS", "V5")

# File upload base URL (separate from the generation API)
SUNO_FILE_UPLOAD_BASE_URL = "https://sunoapiorg.redpandaai.co"

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
        raise RuntimeError(f"sunoapi error (code {data['code']}): {msg}")


class Adapter(BaseRestAdapter):
    """Adapter for Suno music generation via sunoapi.org.

    Handles the distinction between simple generation (prompt only)
    and custom generation (with lyrics/style via customMode).

    The sunoapi.org API is callback-based: it returns a taskId immediately
    and POSTs results to your callBackUrl when generation completes.
    Set the SUNO_CALLBACK_URL env var or pass callback_url to generate().

    After calling generate(), use get_status() to poll for results, or
    use generate() with wait_for_completion=True to block until audio is ready.

    All generation requests and status polls are automatically recorded in a
    local task store (``SunoTasks``).  Access it via the ``tasks`` property::

        adapter = Adapter(config)
        adapter.tasks                # SunoTasks Mapping
        adapter.tasks.last(10)       # last 10 tasks
        adapter.tasks.failed()       # all failed tasks
    """

    def __init__(self, config: dict, *, task_store=None):
        super().__init__(config)
        self._task_store = task_store  # lazy-init if None

    @property
    def tasks(self):
        """Local task store (``SunoTasks`` Mapping) for recorded requests."""
        if self._task_store is None:
            from arioso.platforms.sunoapi.task_store import SunoTasks

            self._task_store = SunoTasks()
        return self._task_store

    def _record_task(
        self, task_id, *, operation, request_params, status="PENDING", response=None
    ):
        """Save a new task record to the local store."""
        from arioso.platforms.sunoapi.task_store import _make_record

        record = _make_record(
            task_id,
            operation=operation,
            request_params=request_params,
            status=status,
            response=response,
        )
        self.tasks.save(record)

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

        self._record_task(
            task_id,
            operation="generate",
            request_params=payload,
            response=data if isinstance(data, dict) else {"raw": data},
        )

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

    def upload_file(self, file_path: str) -> str:
        """Upload a local audio file and return a public URL.

        Uses the sunoapi.org file upload API. Uploaded files are temporary
        and automatically deleted after 3 days.

        Args:
            file_path: Path to the local audio file.

        Returns:
            Public URL of the uploaded file.
        """
        file_path = str(file_path)
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        url = f"{SUNO_FILE_UPLOAD_BASE_URL}/api/file-stream-upload"
        filename = os.path.basename(file_path)

        # Use a fresh session without the default Content-Type: application/json
        import requests

        headers = dict(self.session.headers)
        headers.pop("Content-Type", None)

        with open(file_path, "rb") as f:
            resp = requests.post(
                url,
                headers=headers,
                files={"file": (filename, f)},
                data={"fileName": filename, "uploadPath": "arioso-uploads"},
            )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success") and data.get("code") != 200:
            msg = data.get("msg", "Unknown upload error")
            raise RuntimeError(f"File upload failed: {msg}")

        file_url = data.get("data", {}).get("fileUrl", "")
        if not file_url:
            file_url = data.get("data", {}).get("downloadUrl", "")
        if not file_url:
            raise RuntimeError(f"Upload succeeded but no URL returned: {data}")
        return file_url

    def upload_extend(
        self,
        audio_source: str,
        *,
        style: str = "",
        title: str = "",
        prompt: str = "",
        instrumental: bool = False,
        model: str = "",
        continue_at: float = 0,
        callback_url: str = "",
        negative_prompt: str = "",
        audio_weight: float = 0,
        style_weight: float = 0,
        wait_for_completion: bool = False,
        poll_interval: float = 5.0,
        timeout: float = 300.0,
        **kwargs,
    ) -> list[Song]:
        """Generate music from an uploaded audio file via upload-extend.

        Uploads a local file (if a path is given) or uses a URL directly,
        then calls the sunoapi.org upload-extend endpoint.

        Args:
            audio_source: Local file path or public URL to the source audio.
                Max 8 minutes (1 minute for V4_5ALL model).
            style: Genre/style tags for the generation.
            title: Song title.
            prompt: Lyrics or text prompt (used when instrumental=False).
            instrumental: If True, generate without vocals.
            model: Suno model version ({models}).
            continue_at: Start point in seconds within the uploaded audio.
            callback_url: Webhook URL. Defaults to SUNO_CALLBACK_URL env var.
            negative_prompt: Styles to exclude.
            audio_weight: How much the source audio influences output (0.0-1.0).
            style_weight: How much the style prompt influences output (0.0-1.0).
            wait_for_completion: If True, poll until audio is ready.
            poll_interval: Seconds between status checks (default 5).
            timeout: Max seconds to wait (default 300).

        Returns:
            List of Song objects.
        """.format(models=", ".join(SUNO_MODELS))
        model = model or SUNO_DEFAULT_MODEL
        callback_url = callback_url or SUNO_DEFAULT_CALLBACK_URL

        if not callback_url:
            raise ValueError(
                "sunoapi.org requires a callback URL. "
                "Set the SUNO_CALLBACK_URL environment variable or pass "
                "callback_url to upload_extend()."
            )

        # Determine upload URL: if it looks like a local path, upload it first
        if os.path.isfile(audio_source):
            upload_url = self.upload_file(audio_source)
        elif audio_source.startswith(("http://", "https://")):
            upload_url = audio_source
        else:
            raise ValueError(
                f"audio_source must be a local file path or a URL, "
                f"got: {audio_source!r}"
            )

        custom_mode = bool(style or title or prompt)

        payload = {
            "uploadUrl": upload_url,
            "model": model,
            "instrumental": instrumental,
            "callBackUrl": callback_url,
            "defaultParamFlag": custom_mode,
        }

        # continueAt is required by the API; default to 0 (start of audio)
        payload["continueAt"] = continue_at or 0

        if custom_mode:
            if style:
                payload["style"] = style
            if title:
                payload["title"] = title
            if not instrumental and prompt:
                payload["prompt"] = prompt

        if negative_prompt:
            payload["negativeTags"] = negative_prompt
        if audio_weight:
            payload["audioWeight"] = audio_weight
        if style_weight:
            payload["styleWeight"] = style_weight

        endpoint = "/api/v1/generate/upload-extend"
        response = self.session.post(f"{self.base_url}{endpoint}", json=payload)
        response.raise_for_status()
        data = response.json()

        _check_api_error(data)

        task_id = ""
        if isinstance(data, dict):
            inner = data.get("data")
            if isinstance(inner, dict):
                task_id = inner.get("taskId", "")
            if not task_id:
                task_id = data.get("taskId", "")

        if not task_id:
            return self._parse_songs(data, title=title)

        self._record_task(
            task_id,
            operation="upload_extend",
            request_params=payload,
            response=data if isinstance(data, dict) else {"raw": data},
        )

        if wait_for_completion:
            return self._poll_for_songs(
                task_id,
                title=title,
                poll_interval=poll_interval,
                timeout=timeout,
            )

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

    def upload_cover(
        self,
        audio_source: str,
        *,
        style: str = "",
        title: str = "",
        prompt: str = "",
        instrumental: bool = False,
        model: str = "",
        callback_url: str = "",
        negative_prompt: str = "",
        audio_weight: float = 0,
        style_weight: float = 0,
        weirdness: float = 0,
        wait_for_completion: bool = False,
        poll_interval: float = 5.0,
        timeout: float = 300.0,
        **kwargs,
    ) -> list[Song]:
        """Cover/transform an uploaded audio file via upload-cover.

        Uploads a local file (if a path is given) or uses a URL directly,
        then calls the sunoapi.org upload-cover endpoint to re-generate
        the track in the specified style.

        Args:
            audio_source: Local file path or public URL to the source audio.
                Max 8 minutes.
            style: Genre/style tags for the cover.
            title: Song title.
            prompt: Lyrics or text prompt. In non-custom mode (no style/title),
                this is the main prompt (max 500 chars).
            instrumental: If True, generate without vocals.
            model: Suno model version ({models}).
            callback_url: Webhook URL. Defaults to SUNO_CALLBACK_URL env var.
            negative_prompt: Styles to exclude.
            audio_weight: How much the source audio influences output (0.0-1.0).
            style_weight: How much the style prompt influences output (0.0-1.0).
            weirdness: Creative deviation limit (0.0-1.0).
            wait_for_completion: If True, poll until audio is ready.
            poll_interval: Seconds between status checks (default 5).
            timeout: Max seconds to wait (default 300).

        Returns:
            List of Song objects (typically 2 per call).
        """.format(models=", ".join(SUNO_MODELS))
        model = model or SUNO_DEFAULT_MODEL
        callback_url = callback_url or SUNO_DEFAULT_CALLBACK_URL

        if not callback_url:
            raise ValueError(
                "sunoapi.org requires a callback URL. "
                "Set the SUNO_CALLBACK_URL environment variable or pass "
                "callback_url to upload_cover()."
            )

        # Resolve audio source to a URL
        if os.path.isfile(audio_source):
            upload_url = self.upload_file(audio_source)
        elif audio_source.startswith(("http://", "https://")):
            upload_url = audio_source
        else:
            raise ValueError(
                f"audio_source must be a local file path or a URL, "
                f"got: {audio_source!r}"
            )

        custom_mode = bool(style or title)

        payload = {
            "uploadUrl": upload_url,
            "model": model,
            "instrumental": instrumental,
            "callBackUrl": callback_url,
            "customMode": custom_mode,
        }

        if custom_mode:
            if style:
                payload["style"] = style
            if title:
                payload["title"] = title
            if not instrumental and prompt:
                payload["prompt"] = prompt
        else:
            if prompt:
                payload["prompt"] = prompt

        if negative_prompt:
            payload["negativeTags"] = negative_prompt
        if audio_weight:
            payload["audioWeight"] = audio_weight
        if style_weight:
            payload["styleWeight"] = style_weight
        if weirdness:
            payload["weirdnessConstraint"] = weirdness

        endpoint = "/api/v1/generate/upload-cover"
        response = self.session.post(f"{self.base_url}{endpoint}", json=payload)
        response.raise_for_status()
        data = response.json()

        _check_api_error(data)

        task_id = ""
        if isinstance(data, dict):
            inner = data.get("data")
            if isinstance(inner, dict):
                task_id = inner.get("taskId", "")
            if not task_id:
                task_id = data.get("taskId", "")

        if not task_id:
            return self._parse_songs(data, title=title)

        self._record_task(
            task_id,
            operation="upload_cover",
            request_params=payload,
            response=data if isinstance(data, dict) else {"raw": data},
        )

        if wait_for_completion:
            return self._poll_for_songs(
                task_id,
                title=title,
                poll_interval=poll_interval,
                timeout=timeout,
            )

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
            task_id: The taskId returned from generate(), upload_extend(),
                or upload_cover().

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

        # Update local task store if this task is tracked
        if task_id in self.tasks:
            self.tasks.update(task_id, status=status_raw, response=record)

        if status_raw in _ERROR_STATUSES:
            raise RuntimeError(
                f"sunoapi generation failed (status={status_raw}): taskId={task_id}"
            )

        suno_data = (record.get("response") or {}).get("sunoData", [])
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
            f"sunoapi generation did not complete within {timeout}s (taskId={task_id})"
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
