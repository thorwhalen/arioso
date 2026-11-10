"""The MLX MusicGen backend (thorwhalen/arioso#54): selection, the worker protocol, the worker.

No MLX and no model: the worker is a stand-in that runs the real worker file's functions
in this process against a fake ``musicgen`` module, so the request shapes, the step
arithmetic and the trimming are all exercised.
"""

import sys
import types

import pytest

np = pytest.importorskip("numpy")

from arioso._isolated import worker_file  # noqa: E402
from arioso.platforms.musicgen import backends as mg  # noqa: E402
from arioso.platforms.musicgen.adapter import Adapter  # noqa: E402
from arioso.platforms.musicgen.backends import (  # noqa: E402
    MlxBackend,
    Sampling,
    TransformersBackend,
    select_backend_class,
)
from arioso.platforms.musicgen.config import PLATFORM_CONFIG  # noqa: E402
from tests._in_process import InProcessWorker as _InProcessWorker  # noqa: E402

SR = 32000
HOP = SR // 50
SAMPLING = Sampling(temperature=0.7, top_k=123, top_p=0.0, guidance=4.5)


class _FakeMlxModel:
    """What the worker touches of mlx-examples' ``MusicGen``: 4 codebooks, 32 kHz."""

    sampling_rate = SR
    num_codebooks = 4

    def __init__(self):
        self.calls = []

    def generate(self, text, *, max_steps, top_k, temp, guidance_coef):
        self.calls.append(
            dict(
                text=text,
                max_steps=max_steps,
                top_k=top_k,
                temp=temp,
                guidance=guidance_coef,
            )
        )
        # the port returns max_steps - (num_codebooks - 1) frames after undoing the delay,
        # the last one misaligned: marked 9 here, so a test can see it is dropped
        frames = max_steps - (self.num_codebooks - 1)
        audio = np.ones(frames * HOP, np.float32)
        audio[-HOP:] = 9
        return audio


@pytest.fixture
def fake_port(monkeypatch):
    """A fake ``musicgen`` module and ``mlx.core`` for the real worker file to import."""
    model = _FakeMlxModel()
    loaded = []

    def from_pretrained(name):
        loaded.append(name)
        return model

    musicgen = types.ModuleType("musicgen")
    musicgen.MusicGen = types.SimpleNamespace(from_pretrained=from_pretrained)
    core = types.ModuleType("mlx.core")
    core.eval = lambda *a: None
    mlx = types.ModuleType("mlx")
    mlx.core = core
    monkeypatch.setitem(sys.modules, "musicgen", musicgen)
    monkeypatch.setitem(sys.modules, "mlx", mlx)
    monkeypatch.setitem(sys.modules, "mlx.core", core)
    monkeypatch.setattr(sys, "path", list(sys.path))  # load() puts its cwd on the path
    model.loaded = loaded
    return model


@pytest.fixture
def runtime_dir(tmp_path, monkeypatch):
    """An 'installed' mlx-examples runtime (its interpreter path exists; the pinned-commit
    check is skipped, as the folder is not a checkout: tests/test_isolated.py has it)."""
    monkeypatch.setattr("ps.isolated.check_git_source", lambda source, path, **kw: path)
    rt = PLATFORM_CONFIG["mlx_runtime"]
    python = tmp_path / rt["python"]
    python.parent.mkdir(parents=True)
    python.write_text("")
    monkeypatch.setenv(rt["env_var"], str(tmp_path))
    return tmp_path


def test_load_starts_the_worker_in_the_runtime_and_reads_the_rate(
    fake_port, runtime_dir
):
    backend = MlxBackend.load("facebook/musicgen-small", make_worker=_InProcessWorker)
    rt = PLATFORM_CONFIG["mlx_runtime"]
    w = backend.worker
    assert w.python == str(runtime_dir / rt["python"])
    assert w.adapter == worker_file("musicgen_mlx")
    assert str(w.cwd) == str(runtime_dir / rt["cwd"])
    assert w.init == {"model": "facebook/musicgen-small"} and w.stderr is None
    assert (backend.sample_rate, backend.frame_rate) == (SR, 50)
    assert fake_port.loaded == ["facebook/musicgen-small"]
    # the port's modules live in the working directory: load() puts it on the path
    assert sys.path[0] == str(runtime_dir / rt["cwd"])


def test_text_asks_for_the_frames_the_delay_pattern_costs_and_trims(
    fake_port, runtime_dir
):
    backend = MlxBackend.load("facebook/musicgen-small", make_worker=_InProcessWorker)
    audio = backend.text("warm piano", seconds=2.3, sampling=SAMPLING)

    frames = 115  # round(2.3 * 50)
    # num_codebooks - 1 steps for the delay pattern, one more for the port's bad last frame
    assert fake_port.calls[-1] == dict(
        text="warm piano", max_steps=frames + 4, top_k=123, temp=0.7, guidance=4.5
    )
    assert audio.shape == (frames * HOP,)  # exactly the seconds asked, mono
    assert (audio == 1).all()  # the misaligned last frame was trimmed


def test_top_p_has_no_mlx_counterpart_and_says_so(fake_port, runtime_dir):
    backend = MlxBackend.load("facebook/musicgen-small", make_worker=_InProcessWorker)
    with pytest.warns(UserWarning, match="top_p"):
        backend.text(
            "x",
            seconds=1,
            sampling=Sampling(temperature=1, top_k=250, top_p=0.9, guidance=3),
        )


def test_takes_past_the_context_are_warned_about(fake_port, runtime_dir):
    backend = MlxBackend.load("facebook/musicgen-small", make_worker=_InProcessWorker)
    with pytest.warns(UserWarning, match="30 s"):
        backend.text("x", seconds=31, sampling=SAMPLING)


def test_only_mono_text_checkpoints_run_on_mlx(runtime_dir):
    with pytest.raises(ValueError, match="musicgen-melody"):
        MlxBackend.load("facebook/musicgen-melody", make_worker=_InProcessWorker)
    assert not MlxBackend.supports("facebook/musicgen-stereo-small")
    assert MlxBackend.supports("facebook/musicgen-medium")
    assert not MlxBackend.supports(
        "facebook/musicgen-style"
    )  # no state_dict.bin to load
    assert not MlxBackend.supports("someone/musicgen-small-finetune")
    assert not MlxBackend.can_continue("facebook/musicgen-small")


def test_a_missing_runtime_says_how_to_install_it(tmp_path, monkeypatch):
    from arioso._isolated import RuntimeNotInstalled

    monkeypatch.setenv(
        PLATFORM_CONFIG["mlx_runtime"]["env_var"], str(tmp_path / "none")
    )
    with pytest.raises(
        RuntimeNotInstalled,
        match="fetch --quiet --depth 1 https://github.com/ml-explore/mlx-examples [0-9a-f]{40}",
    ):
        MlxBackend.load("facebook/musicgen-small", make_worker=_InProcessWorker)


@pytest.fixture
def apple_silicon(monkeypatch):
    import arioso._isolated

    monkeypatch.setattr(arioso._isolated, "is_apple_silicon", lambda: True)
    monkeypatch.delenv(mg.BACKEND_ENV_VAR, raising=False)
    monkeypatch.setitem(
        sys.modules, "audiocraft.models", None
    )  # audiocraft does not import


def test_selection_prefers_mlx_for_text_only(apple_silicon, runtime_dir):
    assert select_backend_class("facebook/musicgen-small") is MlxBackend
    assert (
        select_backend_class("facebook/musicgen-small", task="continuation")
        is TransformersBackend
    )
    assert (
        select_backend_class("facebook/musicgen-melody", task="melody")
        is TransformersBackend
    )
    assert select_backend_class("facebook/musicgen-stereo-small") is TransformersBackend


def test_selection_skips_mlx_without_its_runtime_or_off_apple_silicon(
    apple_silicon, tmp_path, monkeypatch
):
    import arioso._isolated

    monkeypatch.setenv(
        PLATFORM_CONFIG["mlx_runtime"]["env_var"], str(tmp_path / "none")
    )
    assert select_backend_class("facebook/musicgen-small") is TransformersBackend
    monkeypatch.setattr(arioso._isolated, "is_apple_silicon", lambda: False)
    monkeypatch.setenv(PLATFORM_CONFIG["mlx_runtime"]["env_var"], str(tmp_path))
    assert select_backend_class("facebook/musicgen-small") is TransformersBackend


def test_the_environment_variable_forces_a_backend(
    apple_silicon, runtime_dir, monkeypatch
):
    monkeypatch.setenv(mg.BACKEND_ENV_VAR, "transformers")
    assert select_backend_class("facebook/musicgen-small") is TransformersBackend
    monkeypatch.setenv(mg.BACKEND_ENV_VAR, "mlx")  # forced only where it can run
    assert select_backend_class("facebook/musicgen-small") is MlxBackend
    assert (
        select_backend_class("facebook/musicgen-small", task="continuation")
        is TransformersBackend
    )
    monkeypatch.setenv(mg.BACKEND_ENV_VAR, "nope")
    with pytest.raises(ValueError, match="ARIOSO_MUSICGEN_BACKEND"):
        select_backend_class("facebook/musicgen-small")


class _FakeTransformers(TransformersBackend):
    """Loads nothing; continues with a constant, so a test can see which backend ran."""

    loads = []

    @classmethod
    def load(cls, model_variant):
        cls.loads.append(model_variant)
        return cls(None, None)

    sample_rate = SR
    frame_rate = 50

    def continuation(self, prompt, tail, *, seconds, sampling):
        return np.concatenate([tail, np.full(int(seconds * SR), 0.5, np.float32)])


def test_the_adapter_uses_mlx_for_text_and_hands_continuation_over(
    apple_silicon, runtime_dir, fake_port, monkeypatch
):
    workers = []
    real_load = MlxBackend.load

    def load(model_variant):
        backend = real_load(model_variant, make_worker=_InProcessWorker)
        workers.append(backend.worker)
        return backend

    monkeypatch.setattr(MlxBackend, "load", staticmethod(load))
    monkeypatch.setitem(mg.BACKENDS, "transformers", _FakeTransformers)
    monkeypatch.setattr(mg, "TransformersBackend", _FakeTransformers)
    _FakeTransformers.loads = []
    adapter = Adapter(PLATFORM_CONFIG)

    song = adapter.generate("warm piano", duration=1.0)
    assert song.audio.audio_array.shape == (SR,) and len(workers) == 1

    source = (np.full(SR, 0.25, np.float32), SR)
    adapter.generate(
        "warm piano", continue_from=source, duration=1.0, prompt_seconds=1.0
    )
    assert _FakeTransformers.loads == ["facebook/musicgen-small"]
    assert workers[0].closed  # the MLX model is released before the other one loads


@pytest.mark.parametrize(
    "env, picked, variant, expected",
    [
        (None, "mps", "facebook/musicgen-small", "cpu"),
        (None, "mps", "facebook/musicgen-melody", "mps"),  # measured faster on MPS
        ("mps", "mps", "facebook/musicgen-small", "mps"),
        (None, "cuda", "facebook/musicgen-small", "cuda"),
        (None, "cpu", "facebook/musicgen-small", "cpu"),
    ],
)
def test_transformers_runs_text_on_cpu_rather_than_mps_unless_asked(
    monkeypatch, env, picked, variant, expected
):
    if env:
        monkeypatch.setenv("ARIOSO_TORCH_DEVICE", env)
    else:
        monkeypatch.delenv("ARIOSO_TORCH_DEVICE", raising=False)
    monkeypatch.setattr(mg, "torch_device", lambda: picked)
    assert mg._transformers_device(variant) == expected


def test_transformers_load_moves_the_model_to_that_device(monkeypatch):
    moved = []

    class _Model:
        @classmethod
        def from_pretrained(cls, name):
            return cls()

        def to(self, device):
            moved.append(device)
            return self

    fake = types.ModuleType("transformers")
    fake.MusicgenForConditionalGeneration = _Model
    fake.MusicgenMelodyForConditionalGeneration = _Model
    fake.AutoProcessor = types.SimpleNamespace(from_pretrained=lambda name: "processor")
    monkeypatch.setitem(sys.modules, "transformers", fake)
    monkeypatch.delenv("ARIOSO_TORCH_DEVICE", raising=False)
    monkeypatch.setattr(mg, "torch_device", lambda: "mps")
    TransformersBackend.load("facebook/musicgen-small")
    TransformersBackend.load("facebook/musicgen-melody")
    assert moved == ["cpu", "mps"]


def test_a_chooser_taking_keywords_is_told_the_task():
    seen = []

    def chooser(variant, **kwargs):
        seen.append(kwargs)
        return TransformersBackend

    adapter = Adapter(PLATFORM_CONFIG, backend_for=chooser)
    adapter._class_for("facebook/musicgen-small", "continuation")
    assert seen == [{"task": "continuation"}]
