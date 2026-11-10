"""Tests for arioso._isolated: arioso's runtime location, its workers (over ps.isolated),
and wav reading."""

import io
import re
import sys
import wave
from pathlib import Path

import pytest

from arioso._isolated import (
    DFLT_RUNTIMES_DIR,
    Runtime,
    RuntimeNotInstalled,
    Worker,
    WorkerError,
    read_wav,
    song_from_wav,
    worker_file,
)

ECHO_WORKER = """\
import os
print('import-time noise')

def load(**init):
    return init

def echo(state, **request):
    print('library noise on stdout')
    os.write(1, b'C-level noise\\n')
    return {'state': state, 'echo': request, 'pythonpath': os.environ.get('PYTHONPATH')}

def fail(state):
    raise ValueError('asked to fail')
"""


@pytest.fixture
def echo_worker(tmp_path):
    path = tmp_path / "echo_worker.py"
    path.write_text(ECHO_WORKER)
    return path


def _runtime(**kw):
    return Runtime(
        name="toy", env_var="ARIOSO_TOY_DIR", setup="install into {root}", **kw
    )


def test_runtime_root_prefers_its_own_variable_then_the_runtimes_dir(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("ARIOSO_TOY_DIR", raising=False)
    monkeypatch.delenv("ARIOSO_RUNTIMES_DIR", raising=False)
    assert _runtime().root() == Path(DFLT_RUNTIMES_DIR).expanduser() / "toy"
    monkeypatch.setenv("ARIOSO_RUNTIMES_DIR", str(tmp_path / "all"))
    assert _runtime().root() == tmp_path / "all" / "toy"
    monkeypatch.setenv("ARIOSO_TOY_DIR", str(tmp_path / "mine"))
    assert _runtime().root() == tmp_path / "mine"


def test_missing_runtime_raises_with_the_setup_commands(monkeypatch, tmp_path):
    monkeypatch.setenv("ARIOSO_TOY_DIR", str(tmp_path))
    rt = _runtime()
    assert not rt.installed()
    with pytest.raises(
        RuntimeNotInstalled, match=re.escape(f"install into {tmp_path}")
    ) as err:
        rt.interpreter()
    assert "ARIOSO_TOY_DIR" in str(err.value)


def test_installed_runtime_gives_its_interpreter_and_workdir(monkeypatch, tmp_path):
    monkeypatch.setenv("ARIOSO_TOY_DIR", str(tmp_path))
    (tmp_path / "sub" / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / "sub" / ".venv" / "bin" / "python").touch()
    rt = _runtime(python="sub/.venv/bin/python", cwd="sub")
    assert rt.interpreter() == tmp_path / "sub/.venv/bin/python"
    assert rt.workdir() == tmp_path / "sub"


def test_the_default_venv_is_found_in_either_layout(monkeypatch, tmp_path):
    monkeypatch.setenv("ARIOSO_TOY_DIR", str(tmp_path))
    (tmp_path / ".venv" / "Scripts").mkdir(parents=True)
    (tmp_path / ".venv" / "Scripts" / "python.exe").touch()
    assert _runtime().interpreter() == tmp_path / ".venv/Scripts/python.exe"


def test_worker_file_names_the_file_or_lists_the_known_ones():
    assert worker_file("ace_step").name == "ace_step_worker.py"
    with pytest.raises(ValueError, match="magenta_rt"):
        worker_file("no_such")


def test_worker_round_trip_survives_stdout_noise_and_errors(echo_worker, tmp_path):
    with Worker(
        sys.executable, echo_worker, init={"size": "s"}, stderr=tmp_path / "w.log"
    ) as w:
        reply = w.call("echo", a=1)
        assert reply["state"] == {"size": "s"} and reply["echo"] == {"a": 1}
        with pytest.raises(WorkerError, match="asked to fail"):
            w.call("fail")
        assert w.running, "a failed request must not kill the worker"
        assert w.call("echo", b=2)["echo"] == {"b": 2}
    assert not w.running
    log = (tmp_path / "w.log").read_text()
    assert "library noise" in log and "C-level noise" in log


def test_the_host_pythonpath_does_not_reach_the_worker(echo_worker, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/host/site-packages-that-must-not-leak")
    with Worker(sys.executable, echo_worker) as w:
        assert w.call("echo")["pythonpath"] is None


class _FakeProc:
    """A worker process whose reply is scripted (a line, or an exception from readline)."""

    def __init__(self, reply):
        self.stdin, self.killed = io.StringIO(), False
        self.stdout = self
        self._reply = reply

    def readline(self):
        if isinstance(self._reply, BaseException):
            raise self._reply
        return self._reply

    def poll(self):
        return 0 if self.killed else None

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return 0


@pytest.mark.parametrize(
    "reply, error",
    [(KeyboardInterrupt(), KeyboardInterrupt), ("garbage\n", WorkerError)],
)
def test_an_interrupted_or_garbled_exchange_kills_the_worker(reply, error, tmp_path):
    procs = []
    w = Worker(
        "python",
        "m_worker.py",
        stderr=tmp_path / "w.log",
        spawn=lambda *a, **k: procs.append(_FakeProc(reply)) or procs[-1],
    )
    with pytest.raises(error):
        w.call("x")
    assert procs[0].killed and not w.running, "a stale reply must never be read next"


def test_worker_reports_a_worker_that_dies(tmp_path):
    path = tmp_path / "bad_worker.py"
    path.write_text("import arioso_no_such_module\n")
    with pytest.raises(WorkerError, match="(?s)exited.*arioso_no_such_module"):
        Worker(sys.executable, path, stderr=tmp_path / "w.log").call("x")


def _write_wav(path, frames=800, rate=8000):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * frames)
    return path


def test_song_from_wav_holds_bytes_rate_and_duration(tmp_path):
    path = _write_wav(tmp_path / "out" / "x.wav")
    data = path.read_bytes()
    song = song_from_wav(path, platform="toy", metadata={"seed": 3}, remove=True)
    assert song.status == "complete" and song.platform == "toy"
    assert song.audio_bytes == data and song.sample_rate == 8000
    assert song.metadata == {"seed": 3}
    assert song.audio.duration_seconds == pytest.approx(0.1)
    if song.audio_array is not None:  # soundfile installed
        assert len(song.audio_array) == 800
    assert not path.parent.exists(), (
        "the Song holds the audio, so the temp file and its folder go"
    )


def test_read_wav_gives_the_rate_without_soundfile(tmp_path, monkeypatch):
    import builtins

    real_import = builtins.__import__
    monkeypatch.setattr(
        builtins,
        "__import__",
        lambda name, *a, **k: (
            (_ for _ in ()).throw(ImportError())
            if name == "soundfile"
            else real_import(name, *a, **k)
        ),
    )
    assert read_wav(_write_wav(tmp_path / "y.wav")) == (None, 8000)
