"""Tests for musicgen audio continuation (``continue_from``), thorwhalen/arioso#29.

Both backends are faked, and so is ``torch`` (a stub in ``sys.modules``), so
these run with numpy alone. A fake model echoes its audio prompt and appends a
constant per round, the way MusicGen returns the re-decoded prompt followed by
its continuation.
"""

import contextlib
import sys
import types
import warnings

import pytest

np = pytest.importorskip("numpy")

from arioso.platforms.musicgen.adapter import Adapter  # noqa: E402
from arioso.platforms.musicgen.config import PLATFORM_CONFIG  # noqa: E402
from arioso.translation import check_supported_params  # noqa: E402

SR = 32000
HOP = SR // 50


class _Tensor:
    """The slice of the torch.Tensor API the adapter touches."""

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


@pytest.fixture
def fake_torch(monkeypatch):
    torch = types.SimpleNamespace(from_numpy=_Tensor, no_grad=contextlib.nullcontext)
    monkeypatch.setitem(sys.modules, "torch", torch)
    return torch


class _AudiocraftModel:
    """audiocraft MusicGen: ``duration`` covers prompt + continuation."""

    sample_rate = SR
    frame_rate = 50

    def __init__(self):
        self.params = []
        self.prompts = []

    def set_generation_params(self, **params):
        self.params.append(params)

    def generate_continuation(self, prompt, prompt_sample_rate, descriptions):
        assert prompt_sample_rate == SR
        tail = prompt.array[0, 0]
        self.prompts.append(tail.copy())
        total = int(round(self.params[-1]["duration"] * SR))
        new = np.full(total - len(tail), float(len(self.prompts)), np.float32)
        return _Tensor(np.concatenate([tail, new])[None, None])


class _TransformersModel:
    """transformers MusicGen: the delay pattern eats ``codebooks - 1`` frames."""

    device = "cpu"

    def __init__(self, *, codebooks=4):
        self.config = types.SimpleNamespace(
            audio_encoder=types.SimpleNamespace(sampling_rate=SR, frame_rate=50)
        )
        self.decoder = types.SimpleNamespace(
            config=types.SimpleNamespace(num_codebooks=codebooks, audio_channels=1)
        )
        self.calls = []

    def generate(self, *, audio, max_new_tokens, **kwargs):
        self.calls.append(dict(kwargs, max_new_tokens=max_new_tokens))
        frames = max_new_tokens - (self.decoder.config.num_codebooks - 1)
        new = np.full(frames * HOP, float(len(self.calls)), np.float32)
        return _Tensor(np.concatenate([audio, new])[None, None])


class _Inputs(dict):
    def to(self, device):
        return self


def _processor(*, audio, sampling_rate, text, **kwargs):
    assert sampling_rate == SR
    return _Inputs(audio=np.asarray(audio), text=text)


def _adapter(monkeypatch, model, *, transformers=False):
    loaded = []

    def fake_ensure(self, model_variant="facebook/musicgen-small"):
        loaded.append(model_variant)
        self._model = model
        self._model_name = model_variant
        self._use_transformers = transformers
        self._processor = _processor

    monkeypatch.setattr(Adapter, "_ensure_model", fake_ensure)
    adapter = Adapter(PLATFORM_CONFIG)
    adapter.loaded = loaded
    return adapter


def _source(seconds, *, value=0.25):
    return np.full(int(seconds * SR), value, np.float32), SR


def test_config_declares_continuation():
    assert {"continue_from", "continue_at"} <= set(
        PLATFORM_CONFIG["supported_affordances"]
    )
    assert PLATFORM_CONFIG["param_map"]["continue_from"]["adapter_handled"] is True
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        check_supported_params(
            {
                "continue_from": b"",
                "continue_at": 1.0,
                "prompt_seconds": 5,
                "extend_seconds": 5,
                "rounds": 2,
            },
            PLATFORM_CONFIG,
        )


def test_audiocraft_chains_rounds_and_stitches(monkeypatch, fake_torch):
    model = _AudiocraftModel()
    adapter = _adapter(monkeypatch, model)

    song = adapter.generate(
        "calm piano",
        continue_from=_source(3),
        prompt_seconds=2,
        extend_seconds=1.5,
        rounds=2,
    )

    audio = song.audio.audio_array
    assert song.audio.sample_rate == SR
    assert len(audio) == int(6 * SR)
    # original kept, then round 1, then round 2
    assert np.all(audio[: 3 * SR] == 0.25)
    assert np.all(audio[3 * SR : int(4.5 * SR)] == 1.0)
    assert np.all(audio[int(4.5 * SR) :] == 2.0)
    # audiocraft's duration is prompt + continuation
    assert [p["duration"] for p in model.params] == [3.5, 3.5]
    # round 2 is prompted by the tail of the audio so far, round 1's output in it
    assert len(model.prompts[1]) == 2 * SR
    assert np.all(model.prompts[1][-int(1.5 * SR) :] == 1.0)

    meta = song.metadata
    assert meta["continued"] is True
    assert meta["continue_from_seconds"] == 3
    assert meta["rounds"] == 2
    continuation = meta["continuation"]
    assert continuation.duration_seconds == 3
    assert np.array_equal(continuation.audio_array, audio[3 * SR :])


def test_extend_seconds_defaults_to_duration(monkeypatch, fake_torch):
    model = _AudiocraftModel()
    adapter = _adapter(monkeypatch, model)

    song = adapter.generate("x", continue_from=_source(3), duration=4)

    assert song.metadata["continuation"].duration_seconds == 4


def test_continue_at_cuts_the_source(monkeypatch, fake_torch):
    model = _AudiocraftModel()
    adapter = _adapter(monkeypatch, model)

    song = adapter.generate(
        "x", continue_from=_source(5), continue_at=2.0, extend_seconds=1
    )

    assert song.metadata["continue_from_seconds"] == 2
    assert len(song.audio.audio_array) == 3 * SR
    # the source is shorter than prompt_seconds (10): its whole length prompts
    assert len(model.prompts[0]) == 2 * SR


def test_prompt_is_whole_codec_frames(monkeypatch, fake_torch):
    model = _AudiocraftModel()
    adapter = _adapter(monkeypatch, model)

    adapter.generate(
        "x", continue_from=_source(3), prompt_seconds=1.01, extend_seconds=1
    )

    assert len(model.prompts[0]) % HOP == 0
    assert len(model.prompts[0]) == int(1.01 * SR) // HOP * HOP


def test_transformers_compensates_delay_frames(monkeypatch, fake_torch):
    model = _TransformersModel()
    adapter = _adapter(monkeypatch, model, transformers=True)

    song = adapter.generate(
        "calm piano", continue_from=_source(3), extend_seconds=2, rounds=2
    )

    assert [c["max_new_tokens"] for c in model.calls] == [103, 103]
    assert song.metadata["continuation"].duration_seconds == 4
    assert np.all(song.audio.audio_array[: 3 * SR] == 0.25)
    assert np.all(song.audio.audio_array[3 * SR : 5 * SR] == 1.0)


def test_transformers_refuses_melody_checkpoint(monkeypatch, fake_torch):
    adapter = _adapter(monkeypatch, _TransformersModel(), transformers=True)

    with pytest.raises(ValueError, match="non-melody checkpoint"):
        adapter.generate(
            "x", continue_from=_source(3), model="facebook/musicgen-melody"
        )


@pytest.mark.parametrize(
    "kwargs, match",
    [
        (dict(prompt_seconds=10, extend_seconds=25), "window"),
        (dict(extend_seconds=0), "positive"),
        (dict(rounds=0), "rounds"),
    ],
)
def test_bad_window_raises_before_loading(monkeypatch, kwargs, match):
    adapter = _adapter(monkeypatch, _AudiocraftModel())

    with pytest.raises(ValueError, match=match):
        adapter.generate("x", continue_from=_source(3), **kwargs)
    assert adapter.loaded == []


def test_melody_and_continue_from_are_exclusive(monkeypatch):
    adapter = _adapter(monkeypatch, _AudiocraftModel())

    with pytest.raises(ValueError, match="cannot be combined"):
        adapter.generate("x", continue_from=_source(3), melody=_source(3))
