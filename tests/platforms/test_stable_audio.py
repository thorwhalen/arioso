"""Tests for the stable_audio adapter's audio-to-audio wiring (mocked).

The diffusers pipeline is replaced with a fake that records its call kwargs, and
``to_audio_ref`` is stubbed, so these run with no torch/diffusers/soundfont.
"""

from unittest.mock import MagicMock

import pytest

import arioso.platforms.stable_audio.adapter as sa_adapter
from arioso.platforms.stable_audio.adapter import Adapter
from arioso.platforms.stable_audio.config import PLATFORM_CONFIG


class _FakePipe:
    """Stand-in for diffusers StableAudioPipeline: records call kwargs."""

    def __init__(self, capture):
        self._capture = capture
        self.vae = MagicMock(sampling_rate=44100)

    def __call__(self, **kwargs):
        self._capture.update(kwargs)
        out = MagicMock()
        out.audios = [MagicMock()]
        return out


def _adapter_with_fake_pipe(monkeypatch, capture):
    adapter = Adapter(PLATFORM_CONFIG)
    monkeypatch.setattr(
        Adapter,
        "_ensure_model",
        lambda self: setattr(self, "_pipe", _FakePipe(capture)),
    )
    return adapter


def _stub_ingress(monkeypatch, sample_rate=44100):
    fake_ref = MagicMock()
    fake_ref.as_waveform.return_value = MagicMock(name="waveform")
    fake_ref.sample_rate = sample_rate
    monkeypatch.setattr(sa_adapter, "to_audio_ref", lambda v: fake_ref)
    return fake_ref


def test_config_declares_audio_affordances():
    sa = PLATFORM_CONFIG["supported_affordances"]
    assert "audio_input" in sa
    assert "audio_input_strength" in sa


def test_passes_init_audio_to_pipeline(monkeypatch):
    capture = {}
    adapter = _adapter_with_fake_pipe(monkeypatch, capture)
    _stub_ingress(monkeypatch, sample_rate=44100)

    song = adapter.generate("warm analog band", audio_input="in.wav")

    assert "initial_audio_waveforms" in capture
    assert capture["initial_audio_sampling_rate"] == 44100
    assert song.metadata["audio_to_audio"] is True


def test_text_only_has_no_init_audio(monkeypatch):
    capture = {}
    adapter = _adapter_with_fake_pipe(monkeypatch, capture)

    song = adapter.generate("warm analog band")

    assert "initial_audio_waveforms" not in capture
    assert song.metadata["audio_to_audio"] is False


def test_strength_is_ignored_with_warning(monkeypatch):
    capture = {}
    adapter = _adapter_with_fake_pipe(monkeypatch, capture)
    _stub_ingress(monkeypatch)

    with pytest.warns(UserWarning, match="strength"):
        adapter.generate("warm band", audio_input="in.wav", audio_input_strength=0.7)

    # strength must NOT be forwarded to the diffusers pipeline
    assert "strength" not in capture
    assert "audio_input_strength" not in capture
