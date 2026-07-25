"""Tests for the enhance stage: facade routing + audio-input ingress.

These are GPU/torch-free -- they exercise the facade's affordance routing and
the ``arioso._audio.to_audio_ref`` ingress, mocking anything model-heavy.
"""

import os

import pytest

import arioso
from arioso._audio import AudioRef, to_audio_ref
from arioso.base import AudioResult, Song


# --------------------------------------------------------------------------
# supports_audio_input / affordance selection
# --------------------------------------------------------------------------


def test_supports_audio_input():
    assert arioso.supports_audio_input("stable_audio") is True
    assert arioso.supports_audio_input("musicgen") is True
    assert arioso.supports_audio_input("mubert") is False
    assert arioso.supports_audio_input("does_not_exist") is False


def test_audio_affordance_for():
    from arioso import _audio_affordance_for

    assert _audio_affordance_for("stable_audio") == "audio_input"
    assert _audio_affordance_for("musicgen") == "melody"
    # musicgen supports 'melody' but not 'audio_input'
    with pytest.raises(ValueError):
        _audio_affordance_for("musicgen", "audio_input")
    # unknown affordance name
    with pytest.raises(ValueError):
        _audio_affordance_for("stable_audio", "not_an_affordance")


# --------------------------------------------------------------------------
# enhance() routing
# --------------------------------------------------------------------------


def test_enhance_routes_to_audio_input(monkeypatch):
    captured = {}

    def fake_generate(prompt, *, platform="musicgen", **kwargs):
        captured["prompt"] = prompt
        captured["platform"] = platform
        captured["kwargs"] = kwargs
        return Song(platform=platform, status="complete")

    monkeypatch.setattr(arioso, "generate", fake_generate)

    arioso.enhance(
        "in.wav", "warm band", platform="stable_audio", strength=0.5, duration=12
    )
    assert captured["prompt"] == "warm band"
    assert captured["platform"] == "stable_audio"
    assert captured["kwargs"]["audio_input"] == "in.wav"
    assert captured["kwargs"]["audio_input_strength"] == 0.5
    assert captured["kwargs"]["duration"] == 12


def test_enhance_routes_to_melody_for_musicgen(monkeypatch):
    captured = {}

    def fake_generate(prompt, *, platform="musicgen", **kwargs):
        captured["platform"] = platform
        captured["kwargs"] = kwargs
        return Song(platform=platform)

    monkeypatch.setattr(arioso, "generate", fake_generate)

    arioso.enhance("tune.wav", platform="musicgen")
    assert captured["platform"] == "musicgen"
    assert captured["kwargs"]["melody"] == "tune.wav"
    assert "audio_input" not in captured["kwargs"]


def test_enhance_no_strength_omits_key(monkeypatch):
    captured = {}

    def fake_generate(prompt, *, platform="musicgen", **kwargs):
        captured["kwargs"] = kwargs
        return Song()

    monkeypatch.setattr(arioso, "generate", fake_generate)
    arioso.enhance("x.wav", platform="stable_audio")
    assert "audio_input_strength" not in captured["kwargs"]


def test_enhance_explicit_as_override(monkeypatch):
    captured = {}

    def fake_generate(prompt, *, platform="musicgen", **kwargs):
        captured["kwargs"] = kwargs
        return Song()

    monkeypatch.setattr(arioso, "generate", fake_generate)
    arioso.enhance("t.wav", platform="musicgen", as_="melody")
    assert captured["kwargs"]["melody"] == "t.wav"


def test_enhance_rejects_text_only_platform():
    with pytest.raises(ValueError):
        arioso.enhance("x.wav", platform="mubert")


# --------------------------------------------------------------------------
# to_audio_ref ingress
# --------------------------------------------------------------------------


def test_to_audio_ref_passthrough():
    ref = AudioRef(path="a.wav")
    assert to_audio_ref(ref) is ref


def test_to_audio_ref_from_path():
    ref = to_audio_ref("/tmp/song.wav")
    assert ref.as_path() == "/tmp/song.wav"


def test_to_audio_ref_from_bytes():
    ref = to_audio_ref(b"RIFFfakewav")
    p = ref.as_path()
    try:
        assert os.path.exists(p)
        with open(p, "rb") as f:
            assert f.read() == b"RIFFfakewav"
    finally:
        ref.cleanup()
    assert not os.path.exists(p)


def test_to_audio_ref_from_song():
    np = pytest.importorskip("numpy")
    arr = np.zeros(100, dtype="float32")
    song = Song(audio=AudioResult(audio_array=arr, sample_rate=16000))
    ref = to_audio_ref(song)
    assert ref.sample_rate == 16000
    assert ref.as_array() is arr


def test_to_audio_ref_from_array_tuple():
    np = pytest.importorskip("numpy")
    arr = np.zeros((100, 2), dtype="float32")
    ref = to_audio_ref((arr, 22050))
    assert ref.sample_rate == 22050
    assert ref.as_array().shape == (100, 2)


def test_to_audio_ref_url_only_raises():
    song = Song(audio=AudioResult(audio_url="https://x/y.mp3"))
    with pytest.raises(ValueError):
        to_audio_ref(song)


def test_to_audio_ref_bad_type_raises():
    with pytest.raises(TypeError):
        to_audio_ref(12345)


def test_audio_ref_sample_rate_unknown_raises():
    np = pytest.importorskip("numpy")
    ref = AudioRef(array=np.zeros(10))
    with pytest.raises(ValueError):
        _ = ref.sample_rate
