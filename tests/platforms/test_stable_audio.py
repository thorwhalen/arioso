"""Tests for the stable_audio adapter (mocked).

The diffusers pipeline is replaced with a fake that records its call kwargs (through the
adapter's ``load_pipeline`` seam), generators with tuples (``make_generator``), and
``to_audio_ref`` is stubbed, so these run with no torch/diffusers/soundfont and never
touch the gated weights.
"""

import sys
import types
import warnings
from unittest.mock import MagicMock

import pytest

import arioso.platforms.stable_audio.adapter as sa_adapter
from arioso.platforms.stable_audio.adapter import Adapter
from arioso.platforms.stable_audio.config import PLATFORM_CONFIG


class _FakePipe:
    """Stand-in for diffusers StableAudioPipeline: records call kwargs."""

    device = "fake-device"

    def __init__(self, capture):
        self._capture = capture
        self.vae = MagicMock(sampling_rate=44100)

    def __call__(self, **kwargs):
        self._capture.update(kwargs)
        out = MagicMock()
        out.audios = [MagicMock()]
        return out


def _fake_generator(device, seed):
    return ("generator", device, seed)


def _adapter_with_fake_pipe(monkeypatch, capture, *, loaded=None):
    """An Adapter whose pipelines are fakes; *loaded* collects the model ids it loads."""

    def load(model):
        if loaded is not None:
            loaded.append(model)
        return _FakePipe(capture)

    return Adapter(PLATFORM_CONFIG, load_pipeline=load, make_generator=_fake_generator)


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


# -- guidance, seed, model (thorwhalen/arioso#48, #51) ------------------------


def test_guidance_reaches_the_pipeline_as_guidance_scale(monkeypatch):
    capture = {}
    adapter = _adapter_with_fake_pipe(monkeypatch, capture)

    adapter.generate("warm band", guidance=3.5)

    assert capture["guidance_scale"] == 3.5


def test_config_maps_guidance_to_the_pipeline_argument():
    assert PLATFORM_CONFIG["param_map"]["guidance"]["native_name"] == "guidance_scale"


def test_seedless_call_draws_records_and_uses_a_seed(monkeypatch):
    capture = {}
    adapter = _adapter_with_fake_pipe(monkeypatch, capture)
    monkeypatch.setattr(sa_adapter.secrets, "randbelow", lambda bound: 1234)

    song = adapter.generate("warm band")

    assert song.metadata["seed"] == 1234
    assert capture["generator"] == ("generator", "fake-device", 1234)


def test_drawn_seeds_are_ints_below_the_bound(monkeypatch):
    adapter = _adapter_with_fake_pipe(monkeypatch, {})

    seeds = {adapter.generate("warm band").metadata["seed"] for _ in range(5)}

    assert all(isinstance(s, int) and 0 <= s < sa_adapter.SEED_BOUND for s in seeds)
    assert len(seeds) > 1  # drawn, not a constant


def test_given_seed_is_used_and_recorded(monkeypatch):
    capture = {}
    adapter = _adapter_with_fake_pipe(monkeypatch, capture)

    song = adapter.generate("warm band", seed=7)

    assert song.metadata["seed"] == 7
    assert capture["generator"] == ("generator", "fake-device", 7)


def test_model_defaults_to_stable_audio_open_and_is_recorded(monkeypatch):
    loaded = []
    adapter = _adapter_with_fake_pipe(monkeypatch, {}, loaded=loaded)

    song = adapter.generate("warm band")

    assert loaded == ["stabilityai/stable-audio-open-1.0"]
    assert song.metadata["model"] == "stabilityai/stable-audio-open-1.0"


def test_model_is_loaded_once_per_id(monkeypatch):
    loaded = []
    adapter = _adapter_with_fake_pipe(monkeypatch, {}, loaded=loaded)

    adapter.generate("a", model="org/one")
    adapter.generate("b", model="org/one")
    adapter.generate("c", model="org/two")

    assert loaded == ["org/one", "org/two"]


def test_model_is_a_supported_affordance(monkeypatch):
    import arioso
    from arioso.registry import _registry, get_platform

    capture = {}
    get_platform("stable_audio")  # discover it
    monkeypatch.setitem(
        _registry,
        "stable_audio",
        {"config": PLATFORM_CONFIG, "adapter": _adapter_with_fake_pipe(monkeypatch, capture)},
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # an unsupported kwarg would warn
        song = arioso.generate("warm band", platform="stable_audio", model="org/m")

    assert song.metadata["model"] == "org/m"


def test_pipeline_loads_in_float16_only_on_cuda(monkeypatch):
    calls = []

    class FakePipeline:
        @staticmethod
        def from_pretrained(model, torch_dtype):
            calls.append((model, torch_dtype))
            return types.SimpleNamespace(to=lambda device: ("on", device))

    monkeypatch.setitem(
        sys.modules, "diffusers", types.SimpleNamespace(StableAudioPipeline=FakePipeline)
    )
    monkeypatch.setitem(
        sys.modules, "torch", types.SimpleNamespace(float16="f16", float32="f32")
    )
    for device, dtype in [("cuda", "f16"), ("mps", "f32"), ("cpu", "f32")]:
        calls.clear()
        monkeypatch.setattr(sa_adapter, "torch_device", lambda d=device: d)
        assert sa_adapter.load_pipeline("org/m") == ("on", device)
        assert calls == [("org/m", dtype)]
