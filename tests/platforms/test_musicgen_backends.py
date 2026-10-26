"""Tests for the musicgen backends themselves (thorwhalen/arioso#31).

The adapter-level tests fake whole backends' worth of model, so they cannot see
what a backend hands its library. These drive each backend with a recording fake
model and processor, and a stub ``torch`` in ``sys.modules``, so they run with
numpy alone and check the calls: sampling settings, frame counts, the device
move, and the melody audio.
"""

import contextlib
import sys
import types

import pytest

np = pytest.importorskip("numpy")

from arioso.platforms.musicgen.adapter import Adapter  # noqa: E402
from arioso.platforms.musicgen.backends import (  # noqa: E402
    AudiocraftBackend,
    Sampling,
    TransformersBackend,
)
from arioso.platforms.musicgen.config import PLATFORM_CONFIG  # noqa: E402

SR = 32000
HOP = SR // 50
#: The melody feature extractor's rate, distinct from ``SR`` so a test can tell them apart.
CHROMA_SR = 16000
DEVICE = "fake-device"
SECONDS = 2.3
#: round(2.3 * 50) frames, which float error must not turn into 114.
FRAMES = 115
SAMPLING = Sampling(temperature=0.7, top_k=123, top_p=0.9, guidance=4.5)


class _Tensor:
    """The slice of the torch.Tensor API the backends touch."""

    def __init__(self, array):
        self.array = np.asarray(array)

    def float(self):
        return _Tensor(self.array.astype(np.float32))

    def __getitem__(self, idx):
        return _Tensor(self.array[idx])

    def cpu(self):
        return self

    def numpy(self):
        return self.array


@pytest.fixture(autouse=True)
def fake_torch(monkeypatch):
    torch = types.SimpleNamespace(from_numpy=_Tensor, no_grad=contextlib.nullcontext)
    monkeypatch.setitem(sys.modules, "torch", torch)
    return torch


class _Inputs(dict):
    """Processor output; ``to`` returns a copy that says where it was moved."""

    def to(self, device):
        return _Inputs(self, moved_to=device)


class _Processor:
    """A recording transformers processor."""

    def __init__(self):
        self.calls = []
        self.feature_extractor = types.SimpleNamespace(sampling_rate=CHROMA_SR)

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return _Inputs(text=kwargs["text"])


class _TransformersModel:
    """A recording transformers MusicGen returning ``(1, channels, frames)``."""

    device = DEVICE

    def __init__(self, *, codebooks=4, channels=1):
        self.config = types.SimpleNamespace(
            audio_encoder=types.SimpleNamespace(sampling_rate=SR, frame_rate=50)
        )
        self.decoder = types.SimpleNamespace(
            config=types.SimpleNamespace(
                num_codebooks=codebooks * channels, audio_channels=channels
            )
        )
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        channels = self.decoder.config.audio_channels
        out = np.arange(channels * 10, dtype=np.float32).reshape(1, channels, 10)
        return _Tensor(out)


class _Ref:
    """An ``AudioRef`` that records the rate it was asked to resample to."""

    sample_rate = 44100

    def __init__(self):
        self.audio = np.linspace(-1, 1, 64, dtype=np.float32)
        self.target_rates = []

    def as_mono(self, *, target_rate):
        self.target_rates.append(target_rate)
        return self.audio, target_rate

    def as_waveform(self):
        return np.stack([self.audio, self.audio])


def _transformers(**model_kwargs):
    model = _TransformersModel(**model_kwargs)
    processor = _Processor()
    return TransformersBackend(model, processor), model, processor


def _run(backend, mode, *, sampling=SAMPLING):
    """Call *mode* of *backend* with the shared prompt, seconds and sampling."""
    if mode == "text":
        return backend.text("calm piano", seconds=SECONDS, sampling=sampling)
    if mode == "melody":
        return backend.melody("calm piano", _Ref(), seconds=SECONDS, sampling=sampling)
    tail = np.zeros(10 * HOP, np.float32)
    return backend.continuation("calm piano", tail, seconds=SECONDS, sampling=sampling)


MODES = ["text", "melody", "continuation"]


# -- transformers ------------------------------------------------------------


@pytest.mark.parametrize("mode", MODES)
def test_transformers_passes_sampling_to_generate(mode):
    backend, model, _ = _transformers()
    _run(backend, mode)
    (call,) = model.calls
    assert call["do_sample"] is True
    assert call["temperature"] == 0.7
    assert call["top_k"] == 123
    assert call["top_p"] == 0.9
    assert call["guidance_scale"] == 4.5


@pytest.mark.parametrize("mode", MODES)
def test_transformers_moves_inputs_to_model_device(mode):
    backend, model, processor = _transformers()
    _run(backend, mode)
    (call,) = model.calls
    assert call["moved_to"] == DEVICE
    assert call["text"] == ["calm piano"]
    assert processor.calls[0]["text"] == ["calm piano"]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("channels", [1, 2])
def test_transformers_max_new_tokens_adds_delay_frames(mode, channels):
    backend, model, _ = _transformers(codebooks=4, channels=channels)
    assert backend.delay_frames == 3
    _run(backend, mode)
    assert model.calls[0]["max_new_tokens"] == FRAMES + 3


def test_transformers_top_p_zero_becomes_none():
    backend, model, _ = _transformers()
    sampling = Sampling(temperature=1.0, top_k=250, top_p=0.0, guidance=3.0)
    _run(backend, "text", sampling=sampling)
    assert model.calls[0]["top_p"] is None


def test_transformers_text_returns_first_channel():
    backend, _, _ = _transformers(channels=2)
    out = _run(backend, "text")
    np.testing.assert_array_equal(out, np.arange(10, dtype=np.float32))


def test_transformers_melody_passes_audio_at_feature_extractor_rate():
    backend, _, processor = _transformers()
    ref = _Ref()
    backend.melody("calm piano", ref, seconds=SECONDS, sampling=SAMPLING)
    assert ref.target_rates == [CHROMA_SR]
    (call,) = processor.calls
    assert call["audio"] is ref.audio
    assert call["sampling_rate"] == CHROMA_SR


@pytest.mark.parametrize("channels", [1, 2])
def test_transformers_continuation_feeds_tail_and_returns_mono(channels):
    backend, _, processor = _transformers(channels=channels)
    tail = np.full(10 * HOP, 0.5, np.float32)
    out = backend.continuation("calm piano", tail, seconds=SECONDS, sampling=SAMPLING)
    (call,) = processor.calls
    (audio,) = call["audio"]
    expected = np.stack([tail, tail]) if channels == 2 else tail
    np.testing.assert_array_equal(audio, expected)
    assert call["sampling_rate"] == SR
    assert out.shape == (10,)


def test_transformers_audio_channels_without_decoder_config():
    backend, model, _ = _transformers()
    model.decoder = types.SimpleNamespace()
    assert backend.audio_channels == 1
    assert backend.delay_frames == 0


# -- audiocraft --------------------------------------------------------------


class _AudiocraftModel:
    """A recording audiocraft MusicGen returning ``(1, channels, frames)``."""

    sample_rate = SR
    frame_rate = 50

    def __init__(self):
        self.params = []
        self.calls = []

    def set_generation_params(self, **params):
        self.params.append(params)

    def _out(self):
        return _Tensor(np.ones((1, 1, 10), np.float32))

    def generate(self, descriptions):
        self.calls.append(("generate", descriptions))
        return self._out()

    def generate_with_chroma(self, descriptions, melody_wavs, melody_sample_rate):
        self.calls.append(("chroma", descriptions, melody_wavs, melody_sample_rate))
        return self._out()

    def generate_continuation(self, prompt, prompt_sample_rate, descriptions):
        self.calls.append(("continuation", prompt, prompt_sample_rate, descriptions))
        return self._out()


@pytest.mark.parametrize("mode", MODES)
def test_audiocraft_sets_generation_params(mode):
    model = _AudiocraftModel()
    _run(AudiocraftBackend(model), mode)
    (params,) = model.params
    prompt_frames = 10 if mode == "continuation" else 0
    assert params == {
        "use_sampling": True,
        "top_k": 123,
        "top_p": 0.9,
        "temperature": 0.7,
        "duration": (prompt_frames + FRAMES + 0.5) / 50,
        "cfg_coef": 4.5,
    }
    # audiocraft generates int(duration * frame_rate) frames
    assert int(params["duration"] * 50) == prompt_frames + FRAMES


def test_audiocraft_passes_top_p_zero_through():
    model = _AudiocraftModel()
    sampling = Sampling(temperature=1.0, top_k=250, top_p=0.0, guidance=3.0)
    _run(AudiocraftBackend(model), "text", sampling=sampling)
    assert model.params[0]["top_p"] == 0.0


def test_audiocraft_melody_passes_batched_waveform_and_rate():
    model = _AudiocraftModel()
    ref = _Ref()
    AudiocraftBackend(model).melody(
        "calm piano", ref, seconds=SECONDS, sampling=SAMPLING
    )
    ((kind, descriptions, wavs, rate),) = model.calls
    assert kind == "chroma" and descriptions == ["calm piano"]
    np.testing.assert_array_equal(wavs, ref.as_waveform()[None])
    assert rate == ref.sample_rate


# -- loading -----------------------------------------------------------------


def test_ensure_model_falls_back_to_transformers(monkeypatch):
    """Without audiocraft, the adapter loads with transformers once per variant."""
    loaded = []

    class _ModelClass:
        @classmethod
        def from_pretrained(cls, name):
            loaded.append(("model", name))
            return types.SimpleNamespace(to=lambda device: ("model", name, device))

    class _AutoProcessor:
        @classmethod
        def from_pretrained(cls, name):
            loaded.append(("processor", name))
            return ("processor", name)

    transformers = types.SimpleNamespace(
        AutoProcessor=_AutoProcessor, MusicgenForConditionalGeneration=_ModelClass
    )
    monkeypatch.setitem(sys.modules, "audiocraft", None)  # import raises ImportError
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    monkeypatch.setenv("ARIOSO_TORCH_DEVICE", DEVICE)

    adapter = Adapter(PLATFORM_CONFIG)
    adapter._ensure_model("facebook/musicgen-small")
    adapter._ensure_model("facebook/musicgen-small")

    assert loaded == [
        ("model", "facebook/musicgen-small"),
        ("processor", "facebook/musicgen-small"),
    ]
    assert adapter._use_transformers is True
    assert adapter._model == ("model", "facebook/musicgen-small", DEVICE)
    assert adapter._processor == ("processor", "facebook/musicgen-small")
    assert isinstance(adapter._backend("facebook/musicgen-small"), TransformersBackend)
