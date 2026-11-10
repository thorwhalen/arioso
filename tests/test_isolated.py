"""Tests for arioso._isolated: runtime location, the JSON-lines worker, and wav reading."""

import os
import re
import sys
import wave
from pathlib import Path

import pytest

from arioso._isolated import Runtime, RuntimeNotInstalled, Worker, WorkerError, read_wav, song_from_wav

#: The repo root, passed explicitly so the worker can import the tests package's driver.
REPO = str(Path(__file__).resolve().parent.parent)


def _echo_worker(**kw):
    return Worker(sys.executable, "tests._echo_driver", env={"PYTHONPATH": REPO}, **kw)


def _runtime(**kw):
    return Runtime(name="toy", env_var="ARIOSO_TOY_DIR", setup="install into {root}", **kw)


def test_runtime_root_prefers_its_own_variable(monkeypatch, tmp_path):
    monkeypatch.setenv("ARIOSO_RUNTIMES_DIR", str(tmp_path / "all"))
    monkeypatch.delenv("ARIOSO_TOY_DIR", raising=False)
    assert _runtime().root() == tmp_path / "all" / "toy"
    monkeypatch.setenv("ARIOSO_TOY_DIR", str(tmp_path / "mine"))
    assert _runtime().root() == tmp_path / "mine"


def test_missing_runtime_raises_with_the_setup_commands(monkeypatch, tmp_path):
    monkeypatch.setenv("ARIOSO_TOY_DIR", str(tmp_path))
    rt = _runtime()
    assert not rt.installed()
    with pytest.raises(RuntimeNotInstalled, match=re.escape(f"install into {tmp_path}")) as err:
        rt.interpreter()
    assert "ARIOSO_TOY_DIR" in str(err.value)


def test_installed_runtime_gives_its_interpreter_and_workdir(monkeypatch, tmp_path):
    monkeypatch.setenv("ARIOSO_TOY_DIR", str(tmp_path))
    (tmp_path / "sub" / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / "sub" / ".venv" / "bin" / "python").touch()
    rt = _runtime(python="sub/.venv/bin/python", cwd="sub")
    assert rt.interpreter() == tmp_path / "sub/.venv/bin/python"
    assert rt.workdir() == tmp_path / "sub"


def test_worker_round_trip_survives_stdout_noise_and_errors():
    with _echo_worker() as w:
        assert w.call({"a": 1})["echo"] == {"a": 1}
        with pytest.raises(WorkerError, match="asked to fail"):
            w.call({"fail": True})
        assert w.alive, "a failed request must not kill the worker"
        assert w.call({"b": 2})["echo"] == {"b": 2}
    assert not w.alive


def test_worker_path_holds_only_arioso_and_what_was_passed(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/host/site-packages-that-must-not-leak")
    with _echo_worker() as w:
        path = w.call({})["pythonpath"].split(os.pathsep)
    assert "/host/site-packages-that-must-not-leak" not in path
    assert path[-1] == REPO
    assert sorted(os.listdir(path[0])) == ["arioso"]


class _FakeProc:
    """A worker process whose reply is scripted (a line, or an exception from readline)."""

    def __init__(self, reply):
        import io

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


@pytest.mark.parametrize("reply, error", [(KeyboardInterrupt(), KeyboardInterrupt), ("garbage\n", WorkerError)])
def test_an_interrupted_or_garbled_exchange_kills_the_worker(reply, error):
    procs = []
    w = Worker("python", "m", spawn=lambda *a, **k: procs.append(_FakeProc(reply)) or procs[-1])
    with pytest.raises(error):
        w.call({"x": 1})
    assert procs[0].killed and not w.alive, "a stale reply must never be read by the next call"


def test_worker_reports_a_driver_that_dies():
    w = Worker(sys.executable, "arioso_no_such_driver_module")
    with pytest.raises(WorkerError, match="exited"):
        w.call({})


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
    song = song_from_wav(path, platform="toy", metadata={"seed": 3})
    assert song.status == "complete" and song.platform == "toy"
    assert song.audio_bytes == data and song.sample_rate == 8000
    assert song.metadata == {"seed": 3}
    assert song.audio.duration_seconds == pytest.approx(0.1)
    if song.audio_array is not None:  # soundfile installed
        assert len(song.audio_array) == 800
    assert not path.parent.exists(), "the Song holds the audio, so the temp file and its folder go"


def test_read_wav_gives_the_rate_without_soundfile(tmp_path, monkeypatch):
    import builtins

    real_import = builtins.__import__
    monkeypatch.setattr(builtins, "__import__",
                        lambda name, *a, **k: (_ for _ in ()).throw(ImportError()) if name == "soundfile" else real_import(name, *a, **k))
    assert read_wav(_write_wav(tmp_path / "y.wav")) == (None, 8000)
