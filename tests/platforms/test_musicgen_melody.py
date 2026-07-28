"""Tests for musicgen melody-conditioned wiring (mocked).

The model is replaced with a MagicMock and ``to_audio_ref`` is stubbed, so these
run with no audiocraft/transformers/torch.
"""

from unittest.mock import MagicMock

import arioso.platforms.musicgen.adapter as mg_adapter
from arioso.platforms.musicgen.adapter import Adapter
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
    adapter = Adapter(PLATFORM_CONFIG)
    loaded = {}
    fake_model = MagicMock()
    fake_model.sample_rate = 32000

    def fake_ensure(self, model_variant="facebook/musicgen-small"):
        loaded["model"] = model_variant
        self._model = fake_model
        self._model_name = model_variant
        self._use_transformers = False

    monkeypatch.setattr(Adapter, "_ensure_model", fake_ensure)
    _stub_ingress(monkeypatch)

    song = adapter.generate("happy rock", melody="tune.wav")

    # default (non-melody) model was auto-switched to the melody variant
    assert loaded["model"] == "facebook/musicgen-melody"
    # chroma path used, not plain generate
    assert fake_model.generate_with_chroma.called
    assert not fake_model.generate.called
    assert song.metadata.get("melody_conditioned") is True


def test_text_only_uses_plain_generate(monkeypatch):
    adapter = Adapter(PLATFORM_CONFIG)
    fake_model = MagicMock()
    fake_model.sample_rate = 32000
    fake_model.generate.return_value = [MagicMock()]

    def fake_ensure(self, model_variant="facebook/musicgen-small"):
        self._model = fake_model
        self._model_name = model_variant
        self._use_transformers = False

    monkeypatch.setattr(Adapter, "_ensure_model", fake_ensure)

    adapter.generate("happy rock")

    assert fake_model.generate.called
    assert not fake_model.generate_with_chroma.called
