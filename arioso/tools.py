"""High-level tools for common arioso workflows (submit, poll, download)."""

import os
import re
import subprocess
import tempfile
import time

from arioso.base import Song

# ---------------------------------------------------------------------------
# Defaults — override via keyword arguments or environment variables
# ---------------------------------------------------------------------------

DFLT_MAX_DURATION = 480  # 8 minutes (sunoapi limit)
DFLT_POLL_INTERVAL = 15
DFLT_TIMEOUT = 600
DFLT_MODEL = "V5"
DFLT_AUDIO_WEIGHT = 0.5
DFLT_STYLE_WEIGHT = 0.5
DFLT_PLATFORM = os.getenv("ACCOMPY_DFLT_PLATFORM", "sunoapi") 


# ---------------------------------------------------------------------------
# Adapter resolution
# ---------------------------------------------------------------------------


def ensure_adapter(adapter=DFLT_PLATFORM):
    """Return a ready-to-use platform adapter.

    ``adapter`` can be:

    - An existing adapter instance — returned as-is.
    - A platform config dict — instantiated via its ``Adapter`` class.
    - A string that is a valid platform name (e.g. ``"sunoapi"``) — loaded
      from the arioso registry.
    - ``None`` — falls back to :data:`DFLT_PLATFORM`.

    Raises ``ValueError`` for unrecognised inputs.
    """
    if adapter is None:
        adapter = DFLT_PLATFORM

    if isinstance(adapter, str):
        if adapter.isidentifier():
            return _adapter_from_platform_name(adapter)
        raise ValueError(
            f"adapter string must be a valid platform name, got: {adapter!r}"
        )

    if isinstance(adapter, dict):
        return _adapter_from_config(adapter)

    # Assume it's already an adapter instance
    return adapter


def _adapter_from_platform_name(name: str):
    """Load an adapter via the arioso registry."""
    from arioso.registry import get_platform

    entry = get_platform(name)
    return entry["adapter"]


def _adapter_from_config(config: dict):
    """Instantiate an adapter directly from a platform config dict."""
    _validate_platform_config(config)
    platform_name = config.get("name", "")
    if not platform_name:
        raise ValueError("Platform config must include a 'name' key")
    import importlib

    module = importlib.import_module(f"arioso.platforms.{platform_name}.adapter")
    adapter_class = getattr(module, "Adapter")
    return adapter_class(config)


def _validate_platform_config(config: dict):
    """Validate that a platform config dict has required keys."""
    required = {"name", "auth", "api"}
    missing = required - set(config)
    if missing:
        raise ValueError(
            f"Platform config missing required keys: {missing}. "
            f"Got keys: {set(config)}"
        )


# ---------------------------------------------------------------------------
# Audio conversion
# ---------------------------------------------------------------------------


def wav_to_mp3(wav_path, *, max_duration=DFLT_MAX_DURATION):
    """Convert wav to a trimmed mp3. Returns path to a temp mp3 file.

    The caller is responsible for deleting the temp file when done.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", wav_path,
            "-t", str(max_duration),
            "-q:a", "2",
            tmp.name,
        ],
        capture_output=True,
        check=True,
    )
    return tmp.name


# ---------------------------------------------------------------------------
# Submit / poll / download
# ---------------------------------------------------------------------------
from functools import partial

_wav_to_mp3 = partial(wav_to_mp3, max_duration=DFLT_MAX_DURATION)

def submit_cover(
    source_path,
    *,
    style="",
    prompt="",
    instrumental=True,
    model=DFLT_MODEL,
    audio_weight=DFLT_AUDIO_WEIGHT,
    style_weight=DFLT_STYLE_WEIGHT,
    source_prep=_wav_to_mp3,
    adapter=DFLT_PLATFORM,
):
    """Submit an upload-cover job. Returns ``(task_id, source_path)``.

    Args:
        source_path: Path to source audio file.
        source_prep: Callable ``(path) -> path`` to prepare the source file
            before upload (e.g. convert wav to mp3).  Defaults to
            :func:`wav_to_mp3` (trimmed to *max_duration*).
        adapter: Platform adapter, config dict, platform name, or ``None``.

    The caller is responsible for cleaning up *source_path* when done.
    """
    adapter = ensure_adapter(adapter)

    if source_prep is not None:
        assert callable(source_prep), "source_prep must be a callable function"
        source_path = source_prep(source_path)

    songs = adapter.upload_cover(
        source_path,
        style=style,
        prompt=prompt,
        instrumental=instrumental,
        model=model,
        audio_weight=audio_weight,
        style_weight=style_weight,
        wait_for_completion=False,
    )
    task_id = songs[0].id
    return task_id, source_path


def poll_status(
    task_id,
    *,
    poll_interval=DFLT_POLL_INTERVAL,
    timeout=DFLT_TIMEOUT,
    adapter=None,
):
    """Poll until a task completes. Returns list of completed Song objects."""
    adapter = ensure_adapter(adapter)
    start = time.time()
    while time.time() - start < timeout:
        songs = adapter.get_status(task_id)
        if all(s.status == "complete" for s in songs):
            return songs
        elapsed = int(time.time() - start)
        print(f"  [{elapsed}s] status: {songs[0].status}...")
        time.sleep(poll_interval)
    raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")


def download_songs(
    songs,
    target_folder,
    *,
    name_prefix="cover",
    adapter=None,
):
    """Download completed songs to *target_folder*. Returns list of saved paths."""
    adapter = ensure_adapter(adapter)
    os.makedirs(target_folder, exist_ok=True)
    saved = []
    for idx, song in enumerate(songs, 1):
        out_name = f"{name_prefix}_{idx:02d}.mp3"
        out_path = os.path.join(target_folder, out_name)
        song_with_audio = adapter.fetch_audio(song)
        with open(out_path, "wb") as f:
            f.write(song_with_audio.audio_bytes)
        size = os.path.getsize(out_path)
        print(f"  Saved: {out_name} ({size:,} bytes)")
        saved.append(out_path)
    return saved


# ---------------------------------------------------------------------------
# Filename helpers
# ---------------------------------------------------------------------------


def extract_style(filename):
    """Parse style from a filename like ``barry_{key}_{bpm}bpm_{Style}.wav``."""
    m = re.match(r".*?_\d+bpm_(.+)\.\w+$", filename)
    return m.group(1) if m else filename


def safe_name(text):
    """Convert arbitrary text to a filesystem-safe string."""
    return re.sub(r"[^\w]+", "_", text).strip("_")
