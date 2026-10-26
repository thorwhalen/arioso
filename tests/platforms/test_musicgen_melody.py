"""Tests for musicgen melody-conditioned wiring (mocked).

The model is replaced with a MagicMock and ``to_audio_ref`` is stubbed, so these
run with no audiocraft/transformers/torch.
"""

from unittest.mock import MagicMock

import arioso.platforms.musicgen.adapter as mg_adapter
from arioso.platforms.musicgen.adapter import Adapter
from arioso.platforms.musicgen.backends import AudiocraftBackend
from arioso.platforms.musicgen.config import PLATFORM_CONFIG


def _stub_ingress(monkeypatch, sample_rate=44100):
    fake_ref = MagicMock()
    fake_ref.as_waveform.return_value = MagicMock(name="waveform")
    fake_ref.sample_rate = sample_rate
    monkeypatch.setattr(mg_adapter, "to_audio_ref", lambda v: fake_ref)
    return fake_ref


def test_config_declares_melody():
    assert "melody" in PLATFORM_CONFIG["supported_affordances"]
    assert PLATFORM_CONFIG["param_map"]["melody"]["adapter_handled"] is True


def test_melody_switches_model_and_calls_chroma(monkeypatch):
    loaded = {}
    fake_model = MagicMock()
    fake_model.sample_rate = 32000

    def fake_load(model_variant):
        loaded["model"] = model_variant
        return AudiocraftBackend(fake_model)

    adapter = Adapter(PLATFORM_CONFIG, load_backend=fake_load)
    _stub_ingress(monkeypatch)

    song = adapter.generate("happy rock", melody="tune.wav")

    # default (non-melody) model was auto-switched to the melody variant
    assert loaded["model"] == "facebook/musicgen-melody"
    # chroma path used, not plain generate
    assert fake_model.generate_with_chroma.called
    assert not fake_model.generate.called
    assert song.metadata.get("melody_conditioned") is True
    # the song reports the variant that ran, not the one asked for
    assert song.metadata["model"] == "facebook/musicgen-melody"


def test_text_only_uses_plain_generate():
    fake_model = MagicMock()
    fake_model.sample_rate = 32000
    fake_model.generate.return_value = [MagicMock()]

    adapter = Adapter(
        PLATFORM_CONFIG, load_backend=lambda variant: AudiocraftBackend(fake_model)
    )

    adapter.generate("happy rock")

    assert fake_model.generate.called
    assert not fake_model.generate_with_chroma.called
