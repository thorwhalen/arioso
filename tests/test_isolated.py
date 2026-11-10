"""Tests for arioso._isolated: arioso's runtime location, its worker files, and wav reading.

The worker mechanism itself (protocol, noise isolation, kills, environment) is ps.isolated's
and tested there; the worker files are exercised in tests/platforms/test_local_runtimes.py.
"""

import re
import wave
from pathlib import Path

import pytest

from arioso._isolated import (
    DFLT_RUNTIMES_DIR,
    Runtime,
    RuntimeNotInstalled,
    read_wav,
    song_from_wav,
    worker_file,
)


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


def test_worker_file_names_the_file_or_lists_the_known_ones():
    assert worker_file("ace_step").name == "ace_step_worker.py"
    with pytest.raises(ValueError, match="magenta_rt"):
        worker_file("no_such")


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


# The runtimes that are git checkouts, each pinned to one commit (thorwhalen/arioso#63).
def _checkout_runtimes():
    from arioso.platforms.ace_step.config import PLATFORM_CONFIG as ace_step
    from arioso.platforms.musicgen.config import PLATFORM_CONFIG as musicgen
    from arioso.platforms.stable_audio_3.config import PLATFORM_CONFIG as sa3

    return {
        "stable_audio_3": sa3["runtime"],
        "ace_step": ace_step["runtime"],
        "musicgen_mlx": musicgen["mlx_runtime"],
    }


@pytest.mark.parametrize("name", sorted(_checkout_runtimes()))
def test_checkout_runtimes_are_pinned_to_a_commit(name, monkeypatch, tmp_path):
    from arioso._isolated import GitSource

    config = _checkout_runtimes()[name]
    assert isinstance(config["source"], GitSource)  # a full SHA, checked on creation
    rt = Runtime(**config)
    monkeypatch.setenv(rt.env_var, str(tmp_path / "none"))
    hint = rt.hint()
    assert "git clone" not in hint  # an unpinned clone would follow upstream's tip
    assert f"{config['source'].url} {config['source'].commit}" in hint
    assert hint.index("checkout") < hint.index("uv ")  # checked out before installing


def test_a_checkout_at_another_commit_is_refused(monkeypatch, tmp_path):
    import subprocess

    from arioso._isolated import GitSource, SourceMismatch

    repo = tmp_path / "rt"  # under default_dir: the root arioso would choose
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "init", "--quiet", str(repo)], check=True)
    (repo / "bin").mkdir()
    (repo / "bin" / "python").write_text("")
    subprocess.run([*git, "-C", str(repo), "commit", "--quiet", "--allow-empty", "-m", "x"], check=True)
    monkeypatch.delenv("ARIOSO_TOY_DIR", raising=False)
    monkeypatch.delenv("ARIOSO_RUNTIMES_DIR", raising=False)
    pinned = GitSource("https://example.org/toy", "0" * 40)
    rt = Runtime(name="rt", env_var="ARIOSO_TOY_DIR", setup="", python="bin/python",
                 default_dir=str(tmp_path), source=pinned)
    with pytest.raises(SourceMismatch, match="not the pinned 000000000000"):
        rt.interpreter()  # a root arioso chose: refused
    monkeypatch.setenv("ARIOSO_TOY_DIR", str(repo))
    with pytest.warns(UserWarning, match="ARIOSO_TOY_DIR names a runtime that is not the pinned one"):
        assert rt.interpreter() == repo / "bin" / "python"  # the user's own: used, with a warning
