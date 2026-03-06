"""Unofficial Suno API client.

Supports two authentication modes:

1. **Cookie-based (direct)**: Authenticates via extracted browser cookies through
   Suno's Clerk.dev backend. Set ``SUNO_COOKIE`` env var.

2. **Commercial proxy**: Uses third-party API proxies (sunoapi.org, MusicAPI.ai, etc.).
   Set ``SUNO_API_KEY`` and ``SUNO_API_BASE`` env vars.

Example (cookie from browser — easiest)::

    from arioso.suno import SunoCookieClient
    client = SunoCookieClient(browser="chrome")  # auto-extracts from Chrome
    songs = client.generate("upbeat summer pop song about surfing")
    songs = client.wait_for_songs(songs)

Example (cookie string)::

    from arioso.suno import SunoCookieClient
    client = SunoCookieClient(cookie="__client=...; __session=...")
    songs = client.generate("upbeat summer pop song about surfing")
    songs = client.wait_for_songs(songs)

Example (proxy mode)::

    from arioso.suno import SunoProxyClient
    client = SunoProxyClient()  # reads SUNO_API_KEY, SUNO_API_BASE from env
    songs = client.generate("melancholic jazz ballad")
    songs = client.wait_for_songs(songs)
"""

import time
from typing import Any, Optional, Sequence

from arioso.base import Song

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLERK_BASE = "https://clerk.suno.com"
SUNO_API_BASE = "https://studio-api.prod.suno.com"
DEFAULT_CLERK_JS_VERSION = "4.73.2"
DEFAULT_MODEL = "chirp-crow"  # v5 as of March 2026
TOKEN_REFRESH_INTERVAL = 5  # seconds
DEFAULT_POLL_INTERVAL = 5  # seconds
DEFAULT_TIMEOUT = 300  # seconds
DEFAULT_REQUEST_TIMEOUT = 120  # seconds per HTTP request

HCAPTCHA_SITEKEY = "d65453de-3f1a-4aac-9366-a0f06e52b2ce"
HCAPTCHA_PAGEURL = "https://suno.com/create"

# Browser-like headers to reduce CAPTCHA triggers
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://suno.com/",
    "Origin": "https://suno.com",
}


def _clip_to_song(clip: dict) -> Song:
    """Convert a Suno API clip dict to a Song dataclass."""
    return Song(
        id=clip["id"],
        title=clip.get("title", ""),
        audio_url=clip.get("audio_url", ""),
        status=clip.get("status", "unknown"),
        metadata=clip,
    )


# ---------------------------------------------------------------------------
# Cookie-based client (direct access to Suno's internal API)
# ---------------------------------------------------------------------------


class SunoCookieClient:
    """Suno client that authenticates via browser cookies.

    This client reverse-engineers Suno's private API endpoints. It requires a
    ``SUNO_COOKIE`` extracted from a logged-in browser session.

    Warning:
        This violates Suno's Terms of Service. Use at your own risk.
        Cookies expire every ~7 days and need manual re-extraction.
        hCaptcha may block generation — especially from datacenter IPs, Docker,
        and Linux/Windows. macOS triggers fewer CAPTCHAs.
    """

    def __init__(
        self,
        cookie: Optional[str] = None,
        *,
        browser: Optional[str] = None,
        twocaptcha_key: Optional[str] = None,
        clerk_js_version: str = DEFAULT_CLERK_JS_VERSION,
        model: str = DEFAULT_MODEL,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    ):
        """Initialize the cookie-based Suno client.

        Args:
            cookie: The full cookie string from a suno.com browser session.
                If None, reads from ``SUNO_COOKIE`` env var.
            browser: Extract cookies automatically from this browser instead.
                Options: "safari", "chrome", "firefox", "brave", "edge".
                Requires ``pip install browser-cookie3``.
                Note: Safari on macOS requires Full Disk Access for the
                terminal app. Chrome works without extra permissions.
            twocaptcha_key: 2Captcha API key for solving hCaptcha challenges.
                If None, reads from ``TWOCAPTCHA_KEY`` env var.
                Required for generation — Suno blocks API calls without a
                solved hCaptcha token. Get a key at https://2captcha.com
                (~$2.99 per 1,000 solves).
            clerk_js_version: Clerk JS version string used in token refresh.
                May need updating when Suno upgrades their Clerk integration.
            model: Suno model version. Default is "chirp-crow" (v5).
                Other options: "chirp-bluejay" (v4.5), "chirp-v3-5".
            request_timeout: HTTP request timeout in seconds.
        """
        from arioso._util import get_config

        if browser:
            from arioso._util import get_suno_cookie_from_browser

            self._cookie = get_suno_cookie_from_browser(browser)
        else:
            self._cookie = cookie or get_config("SUNO_COOKIE")

        if not self._cookie:
            raise ValueError(
                "No Suno cookie provided. Either:\n"
                "  1. Pass browser='chrome' to auto-extract from Chrome\n"
                "  2. Pass cookie='...' with your cookie string\n"
                "  3. Set the SUNO_COOKIE environment variable\n\n"
                "To manually extract your cookie:\n"
                "  1. Log into suno.com/create in your browser\n"
                "  2. Open DevTools (F12) → Network tab\n"
                "  3. Refresh the page\n"
                "  4. Find a request containing '?__clerk_api_version'\n"
                "  5. Copy the full Cookie header value"
            )
        self._twocaptcha_key = twocaptcha_key or get_config("TWOCAPTCHA_KEY")
        self._clerk_js_version = clerk_js_version
        self._model = model
        self._request_timeout = request_timeout
        self._session_id: Optional[str] = None
        self._token: Optional[str] = None
        self._token_expiry: float = 0

    def _get_session(self) -> "requests.Session":
        """Lazily import requests and create a session."""
        import requests

        if not hasattr(self, "_http"):
            self._http = requests.Session()
            self._http.headers.update({"Cookie": self._cookie})
            self._http.headers.update(_BROWSER_HEADERS)
        return self._http

    def _extract_session_id(self) -> str:
        """Extract the Clerk session ID from the cookie."""
        if self._session_id:
            return self._session_id

        session = self._get_session()
        resp = session.get(
            f"{CLERK_BASE}/v1/client?_clerk_js_version={self._clerk_js_version}",
            timeout=self._request_timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        sessions = data.get("response", {}).get("sessions", [])
        if not sessions:
            raise RuntimeError(
                "No active Clerk sessions found. Your cookie may be expired.\n"
                "Re-extract your cookie from the browser."
            )

        active = [s for s in sessions if s.get("status") == "active"]
        if not active:
            raise RuntimeError(
                "No active sessions found. All sessions may be expired."
            )

        self._session_id = active[0]["id"]
        return self._session_id

    def _refresh_token(self) -> str:
        """Refresh the JWT token via Clerk's token endpoint."""
        now = time.time()
        if self._token and now < self._token_expiry:
            return self._token

        session_id = self._extract_session_id()
        session = self._get_session()

        resp = session.post(
            f"{CLERK_BASE}/v1/client/sessions/{session_id}/tokens"
            f"?_clerk_js_version={self._clerk_js_version}",
            timeout=self._request_timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        self._token = data.get("jwt")
        if not self._token:
            raise RuntimeError(f"Failed to obtain JWT token. Response: {data}")

        # Tokens are very short-lived; refresh proactively
        self._token_expiry = now + TOKEN_REFRESH_INTERVAL
        return self._token

    def _auth_headers(self) -> dict[str, str]:
        """Get authorization headers with a fresh token."""
        token = self._refresh_token()
        return {"Authorization": f"Bearer {token}"}

    def _solve_captcha(self) -> str:
        """Solve Suno's hCaptcha challenge via 2Captcha.

        Requires a ``TWOCAPTCHA_KEY`` (set via constructor or env var).

        Returns:
            The solved hCaptcha token string to pass as ``token`` in
            the generate payload.

        Raises:
            RuntimeError: If no 2Captcha key is configured or solving fails.
        """
        import requests as _requests

        if not self._twocaptcha_key:
            raise RuntimeError(
                "hCaptcha solving requires a 2Captcha API key.\n"
                "Get one at https://2captcha.com (~$2.99/1,000 solves).\n"
                "Pass twocaptcha_key= to the constructor or set TWOCAPTCHA_KEY."
            )

        # Step 1: Submit the captcha task
        resp = _requests.get(
            "https://2captcha.com/in.php",
            params={
                "key": self._twocaptcha_key,
                "method": "hcaptcha",
                "sitekey": HCAPTCHA_SITEKEY,
                "pageurl": HCAPTCHA_PAGEURL,
                "json": 1,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != 1:
            raise RuntimeError(f"2Captcha submission failed: {data}")

        captcha_id = data["request"]

        # Step 2: Poll for the solution (human workers solve it)
        for _ in range(60):  # max ~5 minutes
            time.sleep(5)
            resp = _requests.get(
                "https://2captcha.com/res.php",
                params={
                    "key": self._twocaptcha_key,
                    "action": "get",
                    "id": captcha_id,
                    "json": 1,
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") == 1:
                return data["request"]  # the solved token
            if data.get("request") != "CAPCHA_NOT_READY":
                raise RuntimeError(f"2Captcha solving failed: {data}")

        raise TimeoutError("2Captcha did not return a solution within 5 minutes")

    def _get_captcha_token(self) -> Optional[str]:
        """Get a solved hCaptcha token if captcha is required, else None."""
        if not self._twocaptcha_key:
            return None
        try:
            return self._solve_captcha()
        except Exception:
            return None

    def diagnose(self) -> dict[str, Any]:
        """Run diagnostics on the connection and return a status report.

        Checks cookie validity, session extraction, token refresh, and
        whether the feed endpoint is accessible. Useful for debugging.

        Returns:
            Dict with keys: cookie_ok, session_id, token_ok, feed_ok,
            credits_total, credits_left, song_count, and any errors.
        """
        import requests

        report: dict[str, Any] = {
            "cookie_ok": bool(self._cookie),
            "session_id": None,
            "token_ok": False,
            "feed_ok": False,
            "song_count": 0,
            "errors": [],
        }

        try:
            report["session_id"] = self._extract_session_id()
        except Exception as e:
            report["errors"].append(f"Session extraction failed: {e}")
            return report

        try:
            self._refresh_token()
            report["token_ok"] = True
        except Exception as e:
            report["errors"].append(f"Token refresh failed: {e}")
            return report

        try:
            session = self._get_session()
            headers = self._auth_headers()
            resp = session.get(
                f"{SUNO_API_BASE}/api/feed/?page=0",
                headers=headers,
                timeout=self._request_timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            report["feed_ok"] = True
            report["song_count"] = len(data)
        except Exception as e:
            report["errors"].append(f"Feed endpoint failed: {e}")

        return report

    def get_feed(self, page: int = 0) -> list[Song]:
        """Get the user's song feed (previously generated songs).

        Args:
            page: Page number (0-indexed).

        Returns:
            List of Song objects.
        """
        session = self._get_session()
        headers = self._auth_headers()

        resp = session.get(
            f"{SUNO_API_BASE}/api/feed/?page={page}",
            headers=headers,
            timeout=self._request_timeout,
        )
        resp.raise_for_status()
        return [_clip_to_song(clip) for clip in resp.json()]

    def generate(
        self,
        prompt: str = "",
        *,
        style: str = "",
        title: str = "",
        lyrics: str = "",
        instrumental: bool = False,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> list[Song]:
        """Generate songs via Suno's internal API.

        Two modes:

        - **Description mode** (default): Pass ``prompt`` as a natural language
          description. Suno generates lyrics, style, and title automatically.
        - **Custom mode**: Pass ``lyrics`` (and optionally ``style``/``title``).
          You control the exact lyrics and style tags.

        Args:
            prompt: Natural language description (description mode, max 500 chars).
            style: Genre/style tags (custom mode, max 1000 chars).
            title: Song title (custom mode).
            lyrics: Full lyrics with structural tags like [Verse], [Chorus].
            instrumental: If True, generate without vocals.
            model: Override the default model version.
            **kwargs: Additional Suno API params (e.g., ``negative_tags``,
                ``generation_type``, ``token`` for hCaptcha).

        Returns:
            List of Song objects with IDs (status will be 'submitted').

        Note:
            The generate endpoint may hang if Suno presents an hCaptcha
            challenge. If this happens, you may need a 2Captcha key or
            consider using a commercial proxy (SunoProxyClient) instead.
        """
        session = self._get_session()
        headers = self._auth_headers()
        mv = model or self._model

        # Determine description vs custom mode
        custom_mode = bool(lyrics or (style and title))

        payload: dict[str, Any] = {
            "make_instrumental": instrumental,
            "mv": mv,
        }

        if custom_mode:
            payload["prompt"] = lyrics or ""
            if style:
                payload["tags"] = style
            if title:
                payload["title"] = title
        else:
            payload["gpt_description_prompt"] = prompt[:500]
            payload["prompt"] = ""  # Must be empty string in description mode

        # Standard fields
        payload.setdefault("generation_type", "TEXT")

        # Pass through any extra kwargs as-is
        payload.update(kwargs)

        # Solve hCaptcha if we have a 2Captcha key and no token was provided
        if payload.get("token") is None and self._twocaptcha_key:
            payload["token"] = self._solve_captcha()

        resp = session.post(
            f"{SUNO_API_BASE}/api/generate/v2/",
            json=payload,
            headers=headers,
            timeout=self._request_timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        clips = data.get("clips", [])
        return [_clip_to_song(clip) for clip in clips]

    def get_song(self, song_id: str) -> Song:
        """Get the current status of a song by ID."""
        session = self._get_session()
        headers = self._auth_headers()

        resp = session.get(
            f"{SUNO_API_BASE}/api/feed/?ids={song_id}",
            headers=headers,
            timeout=self._request_timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        if not data:
            raise ValueError(f"Song not found: {song_id}")
        return _clip_to_song(data[0])

    def get_songs(self, song_ids: Sequence[str]) -> list[Song]:
        """Get the current status of multiple songs by ID."""
        session = self._get_session()
        headers = self._auth_headers()

        ids_param = ",".join(song_ids)
        resp = session.get(
            f"{SUNO_API_BASE}/api/feed/?ids={ids_param}",
            headers=headers,
            timeout=self._request_timeout,
        )
        resp.raise_for_status()
        return [_clip_to_song(clip) for clip in resp.json()]

    def wait_for_songs(
        self,
        songs: Sequence[Song],
        *,
        timeout: float = DEFAULT_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> list[Song]:
        """Poll until all songs are complete or timeout is reached.

        Args:
            songs: Songs to wait for (as returned by generate()).
            timeout: Max seconds to wait.
            poll_interval: Seconds between status checks.

        Returns:
            Updated Song objects.

        Raises:
            TimeoutError: If songs don't complete within timeout.
        """
        pending_ids = {s.id for s in songs}
        results: dict[str, Song] = {}
        deadline = time.time() + timeout

        while pending_ids and time.time() < deadline:
            updated = self.get_songs(list(pending_ids))
            for song in updated:
                results[song.id] = song
                if song.status == "complete":
                    pending_ids.discard(song.id)
            if pending_ids:
                time.sleep(poll_interval)

        if pending_ids:
            raise TimeoutError(
                f"Songs did not complete within {timeout}s: {pending_ids}"
            )

        return [results[s.id] for s in songs]

    def download_song(self, song: Song) -> Song:
        """Download the audio bytes for a completed song.

        Args:
            song: A Song with a non-empty audio_url.

        Returns:
            The same Song with audio_bytes populated.
        """
        import requests

        if not song.audio_url:
            raise ValueError(
                f"Song {song.id} has no audio_url. "
                "Is it complete? Call wait_for_songs() first."
            )

        resp = requests.get(song.audio_url, timeout=self._request_timeout)
        resp.raise_for_status()
        song.audio_bytes = resp.content
        return song

    # ------------------------------------------------------------------
    # Upload & Cover
    # ------------------------------------------------------------------

    def upload_audio(
        self,
        file_path: str,
        *,
        poll_interval: float = 2,
        timeout: float = 120,
    ) -> str:
        """Upload a local audio file to Suno and return its clip ID.

        This is a multi-step process:
        1. Request a presigned S3 upload URL from Suno.
        2. Upload the file bytes to S3.
        3. Tell Suno the upload is done.
        4. Poll until processing is complete.

        Args:
            file_path: Path to a local audio file (WAV, MP3, etc.).
            poll_interval: Seconds between processing status checks.
            timeout: Max seconds to wait for processing.

        Returns:
            The clip ID (UUID string) to use with ``cover()``.
        """
        import os
        import requests as _requests

        session = self._get_session()

        ext = os.path.splitext(file_path)[1].lstrip(".")
        if not ext:
            ext = "wav"

        # Step 1: Get presigned upload URL
        headers = self._auth_headers()
        resp = session.post(
            f"{SUNO_API_BASE}/api/uploads/audio/",
            json={"extension": ext},
            headers=headers,
            timeout=self._request_timeout,
        )
        resp.raise_for_status()
        upload_info = resp.json()

        upload_id = upload_info["id"]
        s3_url = upload_info["url"]
        s3_fields = upload_info["fields"]

        # Step 2: Upload file to S3 via presigned POST
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f)}
            s3_resp = _requests.post(s3_url, data=s3_fields, files=files, timeout=120)
            s3_resp.raise_for_status()

        # Step 3: Notify Suno the upload is done
        filename = os.path.basename(file_path)
        headers = self._auth_headers()
        resp = session.post(
            f"{SUNO_API_BASE}/api/uploads/audio/{upload_id}/upload-finish/",
            headers=headers,
            json={
                "upload_type": "file_upload",
                "upload_filename": filename,
            },
            timeout=self._request_timeout,
        )
        resp.raise_for_status()

        # Step 4: Poll until processing is complete
        deadline = time.time() + timeout
        while time.time() < deadline:
            headers = self._auth_headers()
            resp = session.get(
                f"{SUNO_API_BASE}/api/uploads/audio/{upload_id}/",
                headers=headers,
                timeout=self._request_timeout,
            )
            resp.raise_for_status()
            status_data = resp.json()
            status = status_data.get("status", "")
            if status == "complete":
                return upload_id
            if status == "error":
                raise RuntimeError(
                    f"Upload processing failed: {status_data}"
                )
            time.sleep(poll_interval)

        raise TimeoutError(
            f"Upload processing did not complete within {timeout}s"
        )

    def cover(
        self,
        clip_id: str,
        *,
        style: str = "",
        title: str = "",
        lyrics: str = "",
        instrumental: bool = False,
        model: Optional[str] = None,
        style_weight: Optional[float] = None,
        weirdness_constraint: Optional[float] = None,
        vocal_gender: Optional[str] = None,
        negative_tags: str = "",
        **kwargs: Any,
    ) -> list[Song]:
        """Generate a cover/remix from a previously uploaded audio clip.

        Args:
            clip_id: The UUID returned by ``upload_audio()``.
            style: Genre/style tags (e.g. "Jazz, Piano, Drums").
            title: Song title.
            lyrics: Lyrics with structural tags ([Verse], [Chorus], etc.).
            instrumental: If True, generate without vocals.
            model: Model version override.
            style_weight: 0.0-1.0, how strictly to follow style tags.
            weirdness_constraint: 0.0-1.0, creative variation level.
            vocal_gender: "m" or "f".
            negative_tags: Styles to avoid.
            **kwargs: Additional API parameters passed through.

        Returns:
            List of Song objects (status will be 'submitted').
        """
        session = self._get_session()
        headers = self._auth_headers()
        mv = model or self._model

        payload: dict[str, Any] = {
            "task": "cover",
            "cover_clip_id": clip_id,
            "mv": mv,
            "generation_type": "TEXT",
            "make_instrumental": instrumental,
            "token": None,
        }

        if style:
            payload["tags"] = style
        if title:
            payload["title"] = title
        if lyrics:
            payload["prompt"] = lyrics
        else:
            payload["prompt"] = ""
        if negative_tags:
            payload["negative_tags"] = negative_tags

        # Control sliders go in metadata
        control_sliders: dict[str, float] = {}
        can_control: list[str] = []
        if style_weight is not None:
            control_sliders["style_weight"] = style_weight
            can_control.append("style_weight")
        if weirdness_constraint is not None:
            control_sliders["weirdness_constraint"] = weirdness_constraint
            can_control.append("weirdness_constraint")

        metadata: dict[str, Any] = {"create_mode": "custom"}
        if control_sliders:
            metadata["control_sliders"] = control_sliders
            metadata["can_control_sliders"] = can_control
        if vocal_gender:
            metadata["vocal_gender"] = vocal_gender

        payload["metadata"] = metadata
        payload.update(kwargs)

        # Solve hCaptcha if we have a 2Captcha key and no token was provided
        if payload.get("token") is None and self._twocaptcha_key:
            payload["token"] = self._solve_captcha()

        resp = session.post(
            f"{SUNO_API_BASE}/api/generate/v2/",
            json=payload,
            headers=headers,
            timeout=self._request_timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        clips = data.get("clips", [])
        return [_clip_to_song(clip) for clip in clips]


# ---------------------------------------------------------------------------
# Commercial proxy client
# ---------------------------------------------------------------------------


class SunoProxyClient:
    """Suno client that uses a third-party commercial API proxy.

    Commercial proxies (sunoapi.org, MusicAPI.ai, CometAPI, etc.) maintain
    their own Suno account pools, handle CAPTCHA solving, and expose
    simpler REST APIs.

    Set ``SUNO_API_KEY`` and ``SUNO_API_BASE`` environment variables.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ):
        """Initialize the proxy-based Suno client.

        Args:
            api_key: API key for the commercial proxy.
                If None, reads from ``SUNO_API_KEY`` env var.
            api_base: Base URL of the commercial proxy API.
                If None, reads from ``SUNO_API_BASE`` env var.
        """
        from arioso._util import get_config

        self._api_key = api_key or get_config("SUNO_API_KEY")
        self._api_base = api_base or get_config("SUNO_API_BASE")

        if not self._api_key:
            raise ValueError(
                "No API key provided. Set the SUNO_API_KEY environment variable "
                "or pass api_key= to the constructor."
            )
        if not self._api_base:
            raise ValueError(
                "No API base URL provided. Set the SUNO_API_BASE environment variable "
                "or pass api_base= to the constructor.\n\n"
                "Example values:\n"
                "  https://api.sunoapi.org   (sunoapi.org)\n"
                "  https://api.musicapi.ai   (MusicAPI.ai)\n"
                "  https://api.cometapi.com  (CometAPI)"
            )

        self._api_base = self._api_base.rstrip("/")

    def _get_session(self) -> "requests.Session":
        """Lazily import requests and create a session."""
        import requests

        if not hasattr(self, "_http"):
            self._http = requests.Session()
            self._http.headers.update({
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            })
        return self._http

    def generate(
        self,
        prompt: str = "",
        *,
        style: str = "",
        title: str = "",
        lyrics: str = "",
        instrumental: bool = False,
        callback_url: str = "",
        **kwargs: Any,
    ) -> list[Song]:
        """Generate songs via the commercial proxy API.

        Args:
            prompt: Natural language description.
            style: Genre/style tags.
            title: Song title.
            lyrics: Full lyrics with structural tags.
            instrumental: If True, generate without vocals.
            callback_url: Optional webhook URL for completion notifications.
            **kwargs: Additional provider-specific parameters.

        Returns:
            List of Song objects (status will vary by provider).
        """
        session = self._get_session()

        custom_mode = bool(lyrics or (style and title))

        payload: dict[str, Any] = {
            "make_instrumental": instrumental,
        }

        if custom_mode:
            payload["prompt"] = lyrics or ""
            payload["tags"] = style
            payload["title"] = title
        else:
            payload["gpt_description_prompt"] = prompt

        if callback_url:
            payload["callBackUrl"] = callback_url

        payload.update(kwargs)

        resp = session.post(f"{self._api_base}/api/generate", json=payload)
        resp.raise_for_status()
        data = resp.json()

        # Normalize response — proxies return data in various shapes
        clips = (
            data
            if isinstance(data, list)
            else data.get("clips", data.get("data", []))
        )
        if isinstance(clips, dict):
            clips = [clips]

        return [
            Song(
                id=clip.get("id", clip.get("song_id", "")),
                title=clip.get("title", ""),
                audio_url=clip.get("audio_url", clip.get("song_url", "")),
                status=clip.get("status", "submitted"),
                metadata=clip,
            )
            for clip in clips
        ]

    def get_song(self, song_id: str) -> Song:
        """Get the current status of a song by ID."""
        session = self._get_session()
        resp = session.get(f"{self._api_base}/api/feed/?ids={song_id}")
        resp.raise_for_status()
        data = resp.json()

        clips = data if isinstance(data, list) else data.get("data", [data])
        clip = clips[0] if clips else {}

        return Song(
            id=clip.get("id", song_id),
            title=clip.get("title", ""),
            audio_url=clip.get("audio_url", clip.get("song_url", "")),
            status=clip.get("status", "unknown"),
            metadata=clip,
        )

    def get_songs(self, song_ids: Sequence[str]) -> list[Song]:
        """Get the current status of multiple songs."""
        session = self._get_session()
        ids_param = ",".join(song_ids)
        resp = session.get(f"{self._api_base}/api/feed/?ids={ids_param}")
        resp.raise_for_status()
        data = resp.json()

        clips = data if isinstance(data, list) else data.get("data", [])
        return [
            Song(
                id=clip.get("id", ""),
                title=clip.get("title", ""),
                audio_url=clip.get("audio_url", clip.get("song_url", "")),
                status=clip.get("status", "unknown"),
                metadata=clip,
            )
            for clip in clips
        ]

    def wait_for_songs(
        self,
        songs: Sequence[Song],
        *,
        timeout: float = DEFAULT_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> list[Song]:
        """Poll until all songs are complete or timeout is reached."""
        pending_ids = {s.id for s in songs}
        results: dict[str, Song] = {}
        deadline = time.time() + timeout

        while pending_ids and time.time() < deadline:
            updated = self.get_songs(list(pending_ids))
            for song in updated:
                results[song.id] = song
                if song.status == "complete":
                    pending_ids.discard(song.id)
            if pending_ids:
                time.sleep(poll_interval)

        if pending_ids:
            raise TimeoutError(
                f"Songs did not complete within {timeout}s: {pending_ids}"
            )

        return [results[s.id] for s in songs]

    def download_song(self, song: Song) -> Song:
        """Download the audio bytes for a completed song."""
        import requests

        if not song.audio_url:
            raise ValueError(
                f"Song {song.id} has no audio_url. "
                "Is it complete? Call wait_for_songs() first."
            )

        resp = requests.get(song.audio_url)
        resp.raise_for_status()
        song.audio_bytes = resp.content
        return song
