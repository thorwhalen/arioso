"""Run a model inside its own Python environment, from arioso's.

Several local models ship as a checkout with its own virtualenv, pinning torch or MLX
versions that cannot share an environment with each other or with arioso. Three pieces
let arioso drive them anyway:

- :class:`Runtime` says where such an environment lives (``$<ENV_VAR>``, else
  ``$ARIOSO_RUNTIMES_DIR/<name>``, else ``~/.local/share/arioso/runtimes/<name>``) and how to
  install it; a missing one raises :class:`RuntimeNotInstalled` carrying the commands.
- :class:`Worker` keeps one process of that environment alive and talks to it in JSON
  lines, so a model loads once per session instead of once per call.
- :func:`serve` is the loop on the other side. arioso imports only the standard library,
  so the worker gets arioso on its ``PYTHONPATH`` and a driver can be a module of this
  package (``python -m arioso.platforms.<name>._driver``).

Platforms whose runtime is a one-shot command line tool use :func:`run_process` instead.
"""

from __future__ import annotations

import atexit
import json
import os
import subprocess
import sys
import threading
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

#: Where runtimes live when neither their own variable nor ``$ARIOSO_RUNTIMES_DIR`` is set.
DFLT_RUNTIMES_DIR = "~/.local/share/arioso/runtimes"

#: ``runner(cmd, *, cwd, env, timeout) -> (returncode, output_text)``.
Runner = Callable[..., "tuple[int, str]"]


class RuntimeNotInstalled(RuntimeError):
    """A platform's runtime environment is missing; the message says how to install it."""


class WorkerError(RuntimeError):
    """The worker process failed a request (its traceback is in the message) or died."""


@dataclass(frozen=True, kw_only=True)
class Runtime:
    """Where a model's own environment lives, and how to install it.

    Attributes:
        name: Directory name under the runtimes folder.
        env_var: Variable that overrides the location (the root of the checkout or venv).
        setup: Shell commands that install the runtime; ``{root}`` is replaced.
        python: The interpreter, relative to the root.
        cwd: Working directory for the process, relative to the root.
    """

    name: str
    env_var: str
    setup: str
    python: str = ".venv/bin/python"
    cwd: str = "."

    def root(self) -> Path:
        """The runtime's root directory (it may not exist yet)."""
        explicit = os.environ.get(self.env_var)
        if explicit:
            return Path(explicit).expanduser()
        base = os.environ.get("ARIOSO_RUNTIMES_DIR", DFLT_RUNTIMES_DIR)
        return Path(base).expanduser() / self.name

    def installed(self) -> bool:
        """Whether the runtime's interpreter exists."""
        return (self.root() / self.python).exists()

    def interpreter(self) -> Path:
        """The runtime's Python, or :class:`RuntimeNotInstalled` with the setup commands."""
        if not self.installed():
            raise RuntimeNotInstalled(self.hint())
        return self.root() / self.python

    def workdir(self) -> Path:
        """The directory the runtime's processes run in."""
        return self.root() / self.cwd

    def hint(self) -> str:
        """How to install this runtime, or point arioso at an existing one."""
        root = self.root()
        return (
            f"The {self.name!r} runtime is not installed at {root} "
            f"(no {self.python}). Install it with:\n\n"
            + self.setup.format(root=root)
            + f"\n\nor set ${self.env_var} to an existing installation."
        )


_ARIOSO_ONLY_DIR = None


def _arioso_only_dir() -> str:
    """A directory holding only this ``arioso`` package (a link to it), for a foreign ``PYTHONPATH``.

    Putting arioso's parent directory on the path would, for a regular install, expose the
    host's whole site-packages (its numpy, torch...) to an environment built to pin its own.
    """
    global _ARIOSO_ONLY_DIR
    if _ARIOSO_ONLY_DIR is None:
        import shutil
        import tempfile

        package = Path(__file__).resolve().parent
        base = Path(tempfile.mkdtemp(prefix="arioso_path_"))
        try:
            (base / "arioso").symlink_to(package, target_is_directory=True)
        except OSError:  # no symlink rights (e.g. Windows without developer mode)
            shutil.copytree(package, base / "arioso", ignore=shutil.ignore_patterns("__pycache__"))
        _ARIOSO_ONLY_DIR = str(base)
    return _ARIOSO_ONLY_DIR


class Worker:
    """One long-lived process of a runtime, answering JSON requests one line at a time.

    Started on the first :meth:`call`, stopped by :meth:`close` (also at interpreter exit).
    Requests are serialised: one in flight at a time.

    Args:
        python: The interpreter to run.
        module: The driver module, run as ``python -m module``; it calls :func:`serve`.
        env: Extra environment variables for the process. The host's ``PYTHONPATH`` is not
            passed on; a ``PYTHONPATH`` given here is appended after arioso's.
        cwd: Its working directory.
        spawn: The process factory (seam; defaults to :class:`subprocess.Popen`).
    """

    def __init__(
        self,
        python,
        module: str,
        *,
        env: Optional[dict] = None,
        cwd=None,
        spawn: Callable[..., subprocess.Popen] = subprocess.Popen,
    ):
        self.python = str(python)
        self.module = module
        self.env = dict(env or {})
        self.cwd = str(cwd) if cwd else None
        self._spawn = spawn
        self._proc = None
        self._lock = threading.Lock()
        atexit.register(self.close)

    def _start(self):
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        env.update(self.env)
        extra = self.env.get("PYTHONPATH")
        env["PYTHONPATH"] = _arioso_only_dir() + (os.pathsep + extra if extra else "")
        self._proc = self._spawn(
            [self.python, "-u", "-m", self.module],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,  # the model's own logs go to our stderr
            cwd=self.cwd,
            env=env,
            text=True,
            bufsize=1,
        )

    @property
    def alive(self) -> bool:
        """Whether the process is running."""
        return self._proc is not None and self._proc.poll() is None

    def call(self, request: dict) -> dict:
        """Send ``request``, return the driver's result dict (start the process if needed)."""
        with self._lock:
            if not self.alive:
                self._start()
            try:
                reply = self._exchange(request)
            except BaseException:
                # An interrupted or garbled exchange would leave a reply in the pipe that the
                # next call would read as its own: stop the worker instead (it restarts lazily).
                self._kill()
                raise
            if not reply.get("ok"):
                raise WorkerError(f"{self.module} worker failed:\n{reply.get('error')}")
            return reply["result"]

    def _exchange(self, request: dict) -> dict:
        try:
            self._proc.stdin.write(json.dumps(request) + "\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise WorkerError(f"{self.module} worker is not accepting requests: {exc}")
        line = self._proc.stdout.readline()
        if not line:
            code = self._proc.wait()
            raise WorkerError(f"{self.module} worker exited (code {code}) before answering")
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            raise WorkerError(f"{self.module} worker sent a line that is not a reply: {line[:200]!r}")

    def _kill(self):
        proc, self._proc = self._proc, None
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait()

    def close(self):
        """Stop the process (closing its stdin ends :func:`serve`'s loop)."""
        proc, self._proc = self._proc, None
        if proc is None or proc.poll() is not None:
            return
        try:
            proc.stdin.close()
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def serve(handle: Callable[[dict], dict], *, stdin=None) -> None:
    """The driver side of :class:`Worker`: answer each JSON line on stdin with ``handle``.

    Model libraries print progress to stdout, which would corrupt the protocol, so the
    real stdout is kept for replies and everything else written to file descriptor 1 is
    sent to stderr. ``handle`` returns a JSON-serialisable dict; an exception is sent back
    as its traceback and the loop carries on.
    """
    replies = os.fdopen(os.dup(1), "w", buffering=1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    for line in stdin or sys.stdin:
        if not line.strip():
            continue
        try:
            reply = {"ok": True, "result": handle(json.loads(line))}
        except Exception:
            reply = {"ok": False, "error": traceback.format_exc()}
        replies.write(json.dumps(reply) + "\n")
        replies.flush()


def run_process(cmd, *, cwd, env, timeout=None) -> "tuple[int, str]":
    """The default one-shot runner: a subprocess, stdout and stderr captured together."""
    proc = subprocess.run(
        [str(c) for c in cmd],
        cwd=cwd,
        env={**os.environ, **(env or {})},
        timeout=timeout,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


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


def song_from_wav(path, *, platform: str, metadata: dict, remove: bool = True):
    """A complete :class:`~arioso.base.Song` holding the wav at ``path`` (bytes and array).

    The Song holds the audio in memory, so the file (and its directory, when that is left
    empty) is removed unless ``remove=False``.
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
