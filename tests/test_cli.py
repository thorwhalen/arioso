"""The ``arioso`` command line, run in-process against a fake platform (no model, no network)."""

import subprocess
import sys
import wave

import numpy as np
import pytest

from arioso.__main__ import main
from arioso._audio import save_song, write_wav
from arioso.base import AudioResult, Song
from arioso.registry import _registry, register_platform

SAMPLE_RATE = 8000


class _FakeAdapter:
    """Records its calls; returns *audio* as a complete Song."""

    def __init__(self, audio):
        self.audio = audio
        self.calls = []

    def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return Song(audio=self.audio, platform="fake", status="complete")


def _stereo_wave(seconds=0.5):
    t = np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE
    tone = 0.5 * np.sin(2 * np.pi * 440 * t)
    return np.stack([tone, -tone]).astype(np.float32)  # (channels, frames)


@pytest.fixture
def fake_platform():
    """Register a platform named 'fake' that takes duration, model and seed."""
    config = {
        "name": "fake",
        "access_type": "python_lib",
        "weights_license": "MIT",
        "commercial_use": "yes",
        "supported_affordances": ["prompt", "duration", "model", "seed"],
    }
    adapter = _FakeAdapter(AudioResult(audio_array=_stereo_wave(), sample_rate=SAMPLE_RATE))
    register_platform("fake", config, adapter)
    yield adapter
    _registry.pop("fake", None)


def test_generate_writes_a_wav_and_prints_its_path(fake_platform, tmp_path, capsys):
    out = tmp_path / "take.wav"

    code = main(["generate", "warm piano", "--platform", "fake", "--duration", "3",
                 "-o", str(out), "--model", "m1", "--seed", "42"])

    assert code == 0
    assert capsys.readouterr().out.strip() == str(out)
    assert fake_platform.calls == [("warm piano", {"duration": 3.0, "model": "m1", "seed": 42})]
    with wave.open(str(out)) as w:
        assert (w.getnchannels(), w.getframerate()) == (2, SAMPLE_RATE)
        assert w.getnframes() == SAMPLE_RATE // 2


def test_generate_passes_only_the_options_given(fake_platform, tmp_path):
    # platforms without a duration knob (or, like sunoapi, refusing one) get none
    main(["generate", "x", "-p", "fake", "-o", str(tmp_path / "a.wav")])
    assert fake_platform.calls == [("x", {})]


def test_unknown_platform_is_one_line_and_exit_1(capsys):
    code = main(["generate", "x", "--platform", "no_such_platform"])
    err = capsys.readouterr().err
    assert code == 1
    assert "Unknown platform 'no_such_platform'" in err
    assert "Traceback" not in err


def test_a_missing_optional_dependency_is_one_line(fake_platform, monkeypatch, capsys):
    def needs_torch(prompt, **kwargs):
        import torch_that_is_not_installed  # noqa: F401

    monkeypatch.setattr(fake_platform, "generate", needs_torch)
    assert main(["generate", "x", "-p", "fake"]) == 1
    assert "torch_that_is_not_installed" in capsys.readouterr().err


def test_an_internal_bug_keeps_its_traceback(fake_platform, monkeypatch):
    def buggy(prompt, **kwargs):
        return {}["sample_rate"]

    monkeypatch.setattr(fake_platform, "generate", buggy)
    with pytest.raises(KeyError, match="sample_rate"):
        main(["generate", "x", "-p", "fake"])


def test_platforms_lists_name_access_licence_and_commercial_use(capsys):
    assert main(["platforms"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ["name", "access_type", "weights_license", "commercial_use"]
    musicgen = next(line for line in lines if line.startswith("musicgen "))
    assert musicgen.split() == ["musicgen", "python_lib", "CC-BY-NC-4.0", "no"]


def test_import_arioso_does_not_import_the_cli_library():
    probe = "import sys, arioso; arioso.platform_table(); print('cw' in sys.modules)"
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "False"


def test_python_dash_m_arioso_runs():
    result = subprocess.run(
        [sys.executable, "-m", "arioso", "platforms"], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert "stable_audio" in result.stdout


# -- writing audio -------------------------------------------------------------


@pytest.mark.parametrize(
    "array",
    [
        _stereo_wave(),  # (channels, frames)
        _stereo_wave().T,  # (frames, channels)
        _stereo_wave()[None],  # a batch of one
    ],
    ids=["channels-first", "frames-first", "batched"],
)
def test_write_wav_layouts(tmp_path, array):
    path = write_wav(array, SAMPLE_RATE, tmp_path / "x.wav")
    with wave.open(path) as w:
        assert (w.getnchannels(), w.getnframes()) == (2, SAMPLE_RATE // 2)


def test_write_wav_falls_back_to_the_stdlib(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "soundfile", None)  # import soundfile -> ImportError
    mono = np.linspace(-1, 1, SAMPLE_RATE, dtype=np.float32)

    path = write_wav(mono, SAMPLE_RATE, tmp_path / "x.wav")

    with wave.open(path) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getnframes()) == (1, 2, SAMPLE_RATE)
        frames = np.frombuffer(w.readframes(SAMPLE_RATE), dtype="<i2")
    assert frames[0] == -32767 and frames[-1] == 32767


def test_save_song_names_a_waveform_wav(tmp_path):
    song = Song(audio=AudioResult(audio_array=_stereo_wave(), sample_rate=SAMPLE_RATE))

    path = save_song(song, tmp_path / "out.mp3")

    assert path == tmp_path / "out.wav"
    with wave.open(str(path)) as w:
        assert w.getnchannels() == 2


def test_save_song_keeps_encoded_bytes_and_their_format(tmp_path):
    song = Song(audio=AudioResult(audio_bytes=b"ID3fake", format="mp3"), status="complete")

    path = save_song(song, tmp_path / "out.wav")

    assert path == tmp_path / "out.mp3"
    assert path.read_bytes() == b"ID3fake"


def test_save_song_refuses_a_pending_song(tmp_path):
    song = Song(platform="sunoapi", status="pending")
    with pytest.raises(ValueError, match="check_status"):
        save_song(song, tmp_path / "out.wav")
