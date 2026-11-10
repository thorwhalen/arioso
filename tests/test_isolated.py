"""Tests for arioso._isolated: runtime location, the JSON-lines worker, and wav reading."""

import sys
import wave

import pytest

from arioso._isolated import Runtime, RuntimeNotInstalled, Worker, WorkerError, read_wav, song_from_wav


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
    with pytest.raises(RuntimeNotInstalled, match=f"install into {tmp_path}") as err:
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
    with Worker(sys.executable, "tests._echo_driver") as w:
        assert w.call({"a": 1}) == {"echo": {"a": 1}}
        with pytest.raises(WorkerError, match="asked to fail"):
            w.call({"fail": True})
        assert w.alive, "a failed request must not kill the worker"
        assert w.call({"b": 2}) == {"echo": {"b": 2}}
    assert not w.alive


def test_worker_reports_a_driver_that_dies():
    w = Worker(sys.executable, "arioso_no_such_driver_module")
    with pytest.raises(WorkerError, match="exited"):
        w.call({})


def _write_wav(path, frames=800, rate=8000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * frames)
    return path


def test_song_from_wav_holds_bytes_rate_and_duration(tmp_path):
    path = _write_wav(tmp_path / "x.wav")
    song = song_from_wav(path, platform="toy", metadata={"seed": 3})
    assert song.status == "complete" and song.platform == "toy"
    assert song.audio_bytes == path.read_bytes()
    assert song.sample_rate == 8000
    assert song.metadata == {"seed": 3}
    array, sr = read_wav(path)
    if array is not None:  # soundfile installed
        assert len(array) == 800 and song.audio.duration_seconds == pytest.approx(0.1)
