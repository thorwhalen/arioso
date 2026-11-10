"""Run a model inside its own Python environment, from arioso's: a thin layer over :mod:`ps.isolated`.

Several local models ship as a checkout with its own virtualenv, pinning torch or MLX
versions that cannot share an environment with each other or with arioso. The mechanism
lives in :mod:`ps.isolated`; this module adds arioso's conventions:

- :class:`Runtime` says where such an environment lives (``$<env_var>``, else
  ``$ARIOSO_RUNTIMES_DIR/<name>``, else ``~/.local/share/arioso/runtimes/<name>``) and how to
  install it; a missing one raises :class:`RuntimeNotInstalled` carrying the commands.
- :class:`Worker` keeps one process of that environment alive, running a **worker file**
  from ``arioso/_workers/`` (:func:`worker_file`): ``load(**init)`` keeps the model, one
  operation per render. Worker files import nothing from arioso (the environment need not
  have it). arioso's workers leave their output on the terminal (``stderr=None``), as
  model downloads and progress bars are worth seeing.
- :func:`run_process` is the one-shot alternative, for runtimes that are command line tools.

The rest are arioso's own helpers for what the runtimes return: :func:`song_from_wav`,
:func:`read_wav`, :func:`draw_seed`, :func:`is_apple_silicon`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ps.isolated import Runner, RuntimeNotInstalled, Worker, WorkerError, run_process
from ps.isolated import Runtime as _Runtime

__all__ = [
    "DFLT_RUNTIMES_DIR",
    "RUNTIMES_DIR_VAR",
    "WORKERS_DIR",
    "Runner",
    "Runtime",
    "RuntimeNotInstalled",
    "Worker",
    "WorkerError",
    "draw_seed",
    "is_apple_silicon",
    "read_wav",
    "run_process",
    "song_from_wav",
    "worker_file",
]

#: Where runtimes live when neither their own variable nor ``$ARIOSO_RUNTIMES_DIR`` is set.
DFLT_RUNTIMES_DIR = "~/.local/share/arioso/runtimes"
#: The variable naming the folder that holds every runtime.
RUNTIMES_DIR_VAR = "ARIOSO_RUNTIMES_DIR"
#: The worker files, run inside the runtimes' environments.
WORKERS_DIR = Path(__file__).resolve().parent / "_workers"


@dataclass(frozen=True)
class Runtime(_Runtime):
    """A :class:`ps.isolated.Runtime` located under arioso's runtimes folder by default.

    Built from a platform config's ``runtime`` dict: ``name``, ``env_var``, ``setup`` and
    optionally ``python`` (the interpreter, relative to the root) and ``cwd``.
    """

    default_dir: str = DFLT_RUNTIMES_DIR
    base_dir_var: Optional[str] = RUNTIMES_DIR_VAR


def worker_file(name: str) -> Path:
    """The worker file ``arioso/_workers/<name>_worker.py``, checked to exist.

    >>> worker_file("magenta_rt").name
    'magenta_rt_worker.py'
    """
    path = WORKERS_DIR / f"{name}_worker.py"
    if not path.is_file():
        known = sorted(
            p.stem[: -len("_worker")] for p in WORKERS_DIR.glob("*_worker.py")
        )
        raise ValueError(f"No worker file {path.name}; known workers: {known}")
    return path


def draw_seed() -> int:
    """A fresh seed to pass and record when the caller gave none (so takes reproduce)."""
    import secrets

    return secrets.randbelow(2**31)


def read_wav(path):
    """``(array, sample_rate)`` from a wav a runtime wrote: soundfile if installed, else bytes.

    Returns ``(None, sample_rate)`` when soundfile is missing (callers keep the bytes).
    """
    try:
        import soundfile as sf
    except ImportError:
        return None, _wav_header(path)[0]
    data, sr = sf.read(str(path), dtype="float32")
    return data, sr


def _wav_header(path) -> "tuple[int, float]":
    """``(sample_rate, seconds)`` from a wav header (stdlib only)."""
    import wave

    with wave.open(str(path)) as w:
        return w.getframerate(), w.getnframes() / w.getframerate()


def is_apple_silicon() -> bool:
    """Whether this is an Apple Silicon Mac (where the MLX runtimes run)."""
    import platform

    return platform.system() == "Darwin" and platform.machine() == "arm64"


def song_from_wav(path, *, platform: str, metadata: dict, remove: bool = False):
    """A complete :class:`~arioso.base.Song` holding the wav at ``path`` (bytes and array).

    The Song holds the audio in memory; with ``remove=True`` (for a temporary file a
    runtime wrote) the file, and its directory when that is left empty, are deleted.
    """
    from arioso.base import AudioResult, Song

    path = Path(path)
    array, sr = read_wav(path)
    duration = len(array) / sr if array is not None and sr else _wav_header(path)[1]
    data = path.read_bytes()
    if remove:
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass
    return Song(
        audio=AudioResult(
            audio_bytes=data,
            audio_array=array,
            sample_rate=sr,
            format="wav",
            duration_seconds=duration,
        ),
        platform=platform,
        status="complete",
        metadata=metadata,
    )
