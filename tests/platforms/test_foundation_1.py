"""Tests for the foundation_1 platform (Foundation-1 through stable-audio-tools, local).

The environment build and the worker are faked, and the worker file runs against fake
torch / stable-audio-tools modules, so these need no torch, no environment and no weights.
The last test renders for real only with ``ARIOSO_RUN_INTEGRATION=1``, the environment
built and the checkpoint in the Hugging Face cache.
"""

import os
import sys
import types
import wave
from pathlib import Path

import numpy as np
import pytest

import arioso
from arioso._isolated import worker_file
from arioso.platforms.foundation_1 import adapter as f1
from arioso.platforms.foundation_1.config import ENV_SPEC, PLATFORM_CONFIG
from arioso.registry import _registry, get_config
from tests._in_process import load_worker_module


def _write_wav(path, frames=441, rate=44100, channels=2):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * frames * channels)
    return str(path)


# --- the prompt grammar -------------------------------------------------------------


def test_bpm_and_key_become_tags_and_bars_follow_from_duration():
    text, seconds, timing = f1.build_prompt(
        "Synth Lead, Warm, Arp", bpm=140, key="Em", duration=12
    )
    assert text == "Synth Lead, Warm, Arp, 8 Bars, 140 BPM, E minor"
    assert seconds == pytest.approx(8 * 4 * 60 / 140)
    assert timing == {"bpm": 140, "bars": 8, "key": "E minor", "note": None}


def test_nearest_supported_bar_count_and_explicit_bars():
    assert f1.build_prompt("Pad", bpm=100, duration=10)[2]["bars"] == 4
    assert f1.build_prompt("Pad", bpm=120)[2]["bars"] == 4  # no duration: 4
    with pytest.warns(UserWarning, match="not the duration"):
        text, seconds, _ = f1.build_prompt("Pad", bpm=120, bars=8, duration=3)
    assert text == "Pad, 8 Bars, 120 BPM" and seconds == pytest.approx(16.0)


def test_tags_already_in_the_prompt_are_read_not_repeated():
    raw = "Bass, FM Bass, Acid, 8 Bars, 140 BPM, E minor"
    text, seconds, timing = f1.build_prompt(raw, bpm=140, key="E minor")
    assert text == raw
    assert timing == {"bpm": 140, "bars": 8, "key": "E minor", "note": None}
    assert seconds == pytest.approx(8 * 4 * 60 / 140)


def test_bars_go_before_a_tempo_already_in_the_prompt_and_tags_keep_card_order():
    text, _, timing = f1.build_prompt("Pad, Warm, 140 BPM, E minor", duration=14)
    assert text == "Pad, Warm, 8 Bars, 140 BPM, E minor" and timing["bars"] == 8
    text, _, _ = f1.build_prompt("Pad, D minor", bpm=120, bars=4)
    assert text == "Pad, 4 Bars, 120 BPM, D minor"


def test_short_key_tags_are_read_spelt_out_and_compared_by_pitch_class():
    text, _, timing = f1.build_prompt("Pad, Am", bpm=100, key="A minor")
    assert text == "Pad, 4 Bars, 100 BPM, A minor" and timing["key"] == "A minor"
    _, _, timing = f1.build_prompt("Pad, Cb major", key="B major")  # enharmonic
    assert timing["key"] == "Cb major"
    with pytest.raises(ValueError, match="contradicts"):
        f1.build_prompt("Pad, B minor", key="B major")  # same tonic, other mode
    with pytest.raises(ValueError, match="not a key"):
        f1.build_prompt("Pad", key="dorian thing")


def test_a_duration_far_from_the_loop_length_warns():
    with pytest.warns(UserWarning, match="not the duration"):
        _, seconds, _ = f1.build_prompt("Pad", bpm=128, duration=60)
    assert seconds == pytest.approx(15.0)  # 8 bars at 128 BPM
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        f1.build_prompt("Pad", bpm=100, duration=10)  # 9.6 s: within a bar


def test_a_tempo_goes_after_a_bars_tag_even_when_the_key_comes_first():
    text, _, _ = f1.build_prompt("Pad, E minor, 8 Bars", bpm=140)
    assert text == "Pad, E minor, 8 Bars, 140 BPM"


def test_a_target_note_in_the_prompt_is_read_and_compared():
    text, seconds, timing = f1.build_prompt("Cello, Target Note, c3")
    assert text == "Cello, Target Note, C3" and seconds == 3.0
    assert timing["note"] == "C3"
    assert f1.build_prompt("Cello, Target Note, C3", note="C3")[0] == (
        "Cello, Target Note, C3"
    )
    with pytest.raises(ValueError, match="contradicts"):
        f1.build_prompt("Cello, Target Note, C3", note="D3")


def test_a_key_goes_before_the_target_note():
    text, _, _ = f1.build_prompt("Cello", note="C3", key="Am")
    assert text == "Cello, A minor, Target Note, C3"


def test_a_note_makes_a_one_shot_at_that_pitch():
    text, seconds, timing = f1.build_prompt("Cello, Airy", note="d#3")
    assert text == "Cello, Airy, Target Note, D#3" and seconds == 3.0
    assert timing["note"] == "D#3"
    text, _, _ = f1.build_prompt("Cello", note="C4", keybed=True, duration=2)
    assert text == "Keybed, Timbre Profile, Cello, Target Note, C4"
    with pytest.raises(ValueError, match="one-shot"):
        f1.build_prompt("Cello", note="C4", bpm=120)
    with pytest.raises(ValueError, match="not a pitch"):
        f1.build_prompt("Cello", note="middle C")


def test_without_a_tempo_duration_is_the_clip_length():
    assert f1.build_prompt("Grand Piano, Hit", duration=3) == (
        "Grand Piano, Hit",
        3.0,
        {"bpm": None, "bars": None, "key": None, "note": None},
    )
    assert f1.build_prompt("Grand Piano")[1] == 10.0


def test_contradictions_and_bars_without_tempo_are_errors():
    with pytest.raises(ValueError, match="contradicts"):
        f1.build_prompt("Pad, 140 BPM", bpm=120)
    with pytest.raises(ValueError, match="needs a tempo"):
        f1.build_prompt("Pad", bars=4)


@pytest.mark.parametrize(
    "key, expected",
    [
        ("Am", "A minor"),
        ("a minor", "A minor"),
        ("F#", "F# major"),
        ("Bbmaj", "Bb major"),
        ("C# min", "C# minor"),
        ("eb", "Eb major"),
        ("dorian thing", "dorian thing"),
    ],
)
def test_keys_are_spelt_as_the_tags(key, expected):
    assert f1.normalize_key(key) == expected


# --- the adapter, with a fake worker and environment ---------------------------------


class _FakeWorker:
    """Records how it was built and what it was asked; writes a stereo wav where asked."""

    def __init__(self, python, adapter, *, init=None, env=None, cwd=None, stderr="log"):
        self.python, self.adapter, self.init, self.env = python, adapter, init, env
        self.stderr, self.requests, self.closed = stderr, [], False

    def call(self, op, /, **req):
        self.requests.append((op, req))
        frames = round(req["seconds"] * 44100)
        device = (self.init or {}).get("device") or "mps"  # None: the best, here MPS
        return {"out": _write_wav(req["out"], frames=frames), "device": device}

    def close(self):
        self.closed = True


@pytest.fixture
def adapter():
    built = []

    def ensure_env(spec):
        built.append(spec)
        return "/envs/foundation-1/bin/python"

    a = f1.Adapter(
        make_worker=_FakeWorker, ensure_env=ensure_env, is_supported=lambda: True
    )
    a.built = built
    return a


def test_renders_through_one_worker_in_the_built_environment(adapter):
    song = adapter.generate("Rhodes Piano, Warm", bpm=100, key="Am", seed=3)
    adapter.generate("Pluck, Bright", duration=2, model="1.2-samples")
    w = adapter._worker
    assert adapter.built == [ENV_SPEC]  # built (or checked) once, for the one worker
    assert w.python == "/envs/foundation-1/bin/python"
    assert w.adapter == worker_file("foundation_1")
    assert w.env["PYTORCH_ENABLE_MPS_FALLBACK"] == "1" and w.stderr is None
    (op, req), (_, req2) = w.requests
    assert op == "render"
    assert req["prompt"] == "Rhodes Piano, Warm, 4 Bars, 100 BPM, A minor"
    assert req["seconds"] == pytest.approx(9.6) and req["seed"] == 3
    assert req["checkpoint"] == "Foundation_1.safetensors"
    assert req["revision"] == PLATFORM_CONFIG["weights"]["revision"]
    assert (req["steps"], req["cfg_scale"], req["sampler"]) == (
        100,
        7.0,
        "dpmpp-3m-sde",
    )
    assert (req["sigma_min"], req["sigma_max"]) == (0.3, 500.0)  # SAO 1.0's schedule
    assert req["negative_prompt"] is None
    assert req["t5"] == PLATFORM_CONFIG["weights"]["t5"]
    assert req2["checkpoint"] == "Foundation-1.2-Samples.safetensors"
    assert song.sample_rate == 44100
    assert song.audio.duration_seconds == pytest.approx(9.6, abs=1e-3)
    assert song.metadata["prompt_sent"] == req["prompt"]
    assert song.metadata["bars"] == 4 and song.metadata["device"] == "mps"
    adapter.close()
    assert w.closed and adapter._worker is None


def test_a_seed_is_drawn_and_recorded(adapter):
    song = adapter.generate("Pad", duration=1)
    assert isinstance(song.metadata["seed"], int)
    assert adapter._worker.requests[0][1]["seed"] == song.metadata["seed"]


def test_another_device_starts_a_fresh_worker(adapter):
    adapter.generate("Pad", duration=1, device="cpu")
    first = adapter._worker
    adapter.generate("Pad", duration=1)  # None: keep the running one
    assert adapter._worker is first
    adapter.generate("Pad", duration=1, device="mps")
    assert first.closed and adapter._worker.init == {"device": "mps"}


def test_naming_the_device_the_worker_chose_keeps_it(adapter):
    adapter.generate("Pad", duration=1)  # None: the worker picks MPS
    first = adapter._worker
    adapter.generate("Pad", duration=1, device="mps")
    assert adapter._worker is first and not first.closed  # no 5 GB reload


def test_negative_prompt_and_note_reach_the_worker(adapter):
    adapter.generate("Pad, Warm", negative_prompt="Distortion", duration=2)
    adapter.generate("Rhodes Piano", note="C3", model="1.2-keybeds")
    (_, req), (_, req2) = adapter._worker.requests
    assert req["negative_prompt"] == "Distortion"
    assert req2["prompt"] == "Keybed, Timbre Profile, Rhodes Piano, Target Note, C3"
    assert req2["seconds"] == 3.0


def test_refuses_intel_macs_before_building_anything():
    built = []
    a = f1.Adapter(
        make_worker=_FakeWorker, ensure_env=built.append, is_supported=lambda: False
    )
    with pytest.raises(RuntimeError, match="Apple Silicon"):
        a.generate("Pad", duration=1)
    assert built == []


def test_an_existing_environment_can_be_named(adapter, tmp_path, monkeypatch):
    python = tmp_path / "env" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.touch()
    monkeypatch.setenv("ARIOSO_FOUNDATION_1_ENV", str(tmp_path / "env"))
    adapter.generate("Pad", duration=1)
    assert adapter.built == [] and adapter._worker.python == python
    monkeypatch.setenv("ARIOSO_FOUNDATION_1_ENV", str(tmp_path / "nothing"))
    adapter.close()
    with pytest.raises(FileNotFoundError, match="no Python"):
        adapter.generate("Pad", duration=1)


def test_rejects_unknown_models_and_clips_past_the_window(adapter):
    with pytest.raises(ValueError, match="unknown model"):
        adapter.generate("Pad", model="foundation-2")
    with pytest.raises(ValueError, match="window"):
        adapter.generate("Pad", duration=25)
    assert adapter._worker is None  # nothing started for a bad request


def test_warns_on_a_tempo_it_was_not_trained_on(adapter):
    with pytest.warns(UserWarning, match="96 BPM"):
        adapter.generate("Pad", bpm=96, bars=4)


def test_generate_routes_affordances_and_adapter_params(adapter, monkeypatch):
    get_config("foundation_1")  # discovered
    monkeypatch.setitem(_registry["foundation_1"], "adapter", adapter)
    song = arioso.generate(
        "Cello, Airy",
        platform="foundation_1",
        bpm=120,
        key="D minor",
        bars=8,
        num_steps=50,
        guidance=6,
        model="1.2-keybeds",
        seed=1,
    )
    req = adapter._worker.requests[0][1]
    assert req["prompt"] == "Cello, Airy, 8 Bars, 120 BPM, D minor"
    assert (req["steps"], req["cfg_scale"]) == (50, 6.0)
    assert req["checkpoint"] == "Foundation-1.2-Keybeds.safetensors"
    assert song.platform == "foundation_1" and song.status == "complete"


def test_cached_weights_looks_in_the_hub_cache_at_the_pinned_revision(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    assert f1.cached_weights() is None
    snap = (
        tmp_path
        / "models--RoyalCities--Foundation-1"
        / "snapshots"
        / PLATFORM_CONFIG["weights"]["revision"]
    )
    snap.mkdir(parents=True)
    (snap / "Foundation_1.safetensors").touch()
    assert f1.cached_weights() == snap / "Foundation_1.safetensors"
    assert f1.cached_weights("1.2-keybeds") is None


def test_the_environment_spec_is_pinned_and_resolves_reproducibly():
    assert ENV_SPEC.python == "3.10"
    packages = [r for r in ENV_SPEC.requirements if not r.startswith("-")]
    assert all("==" in r for r in packages)
    assert "stable-audio-tools==0.0.20" in packages
    assert "--exclude-newer=2026-11-10T00:00:00Z" in ENV_SPEC.requirements


@pytest.mark.parametrize("system, backend", [("Linux", "auto"), ("Darwin", None)])
def test_torch_backend_follows_the_os(system, backend, monkeypatch):
    from arioso.platforms.foundation_1 import config

    monkeypatch.setattr("platform.system", lambda: system)
    assert config.env_spec().torch_backend == backend
    assert config.env_spec("Windows").torch_backend == "auto"


def test_registered_with_its_licence():
    info = arioso.get_platform_info("foundation_1")
    assert info["access_type"] == "local_runtime"
    assert (info["weights_license"], info["commercial_use"]) == (
        "Stability AI Community License",
        "conditional",
    )


# --- the worker file, against fake upstream modules ----------------------------------


class _Tensor:
    """Just what the worker does to the sampled audio: index, cast, move, to numpy."""

    def __init__(self, array):
        self.array = array

    def __getitem__(self, i):
        return _Tensor(self.array[i])

    def to(self, dtype):
        return _Tensor(self.array.astype(np.float32))

    def cpu(self):
        return self

    def numpy(self):
        return self.array


def _fake_upstream(monkeypatch, tmp_path, seen, *, cached=True):
    import contextlib
    import json

    config = {  # a 20 s window at 100 Hz, a T5 prompt conditioner and a number one
        "sample_rate": 100,
        "sample_size": 2000,
        "model": {
            "conditioning": {
                "configs": [
                    {
                        "id": "prompt",
                        "type": "t5",
                        "config": {"t5_model_name": "t5-base"},
                    },
                    {"id": "seconds_total", "type": "number", "config": {}},
                ]
            }
        },
    }
    (tmp_path / "model_config.json").write_text(json.dumps(config))

    class Model:
        def __init__(self, cfg):
            seen.setdefault("built", []).append(cfg)
            self.modes = []

        def to(self, device):
            seen["device"] = device
            return self

        def eval(self):
            self.modes.append("eval")
            return self

        def requires_grad_(self, flag):
            self.modes.append(f"grad={flag}")
            return self

    def generate_diffusion_cond(model, **kw):
        seen.setdefault("calls", []).append(kw)
        seen["modes"] = model.modes
        audio = np.zeros((1, 2, kw["sample_size"]))
        audio[0, 0, 5] = 0.5  # normalised to a peak of 1
        return _Tensor(audio)

    def hf_hub_download(repo_id, filename, revision=None, local_files_only=False):
        if local_files_only and not cached:
            raise FileNotFoundError(filename)  # what the hub raises varies
        seen.setdefault("downloads", []).append(
            (repo_id, filename, revision, local_files_only)
        )
        folder = tmp_path / repo_id.replace("/", "--") / str(revision)
        return (
            str(tmp_path / filename)
            if filename.endswith("model_config.json")
            and (repo_id == "RoyalCities/Foundation-1")
            else str(folder / filename)
        )

    def sf_write(path, data, sr, subtype=None):
        seen["written"] = (path, data.shape, sr, subtype, float(np.abs(data).max()))

    torch = types.SimpleNamespace(
        float32="float32",
        inference_mode=contextlib.nullcontext,
        cuda=types.SimpleNamespace(is_available=lambda: False),
        backends=types.SimpleNamespace(
            mps=types.SimpleNamespace(is_available=lambda: True)
        ),
        mps=types.SimpleNamespace(empty_cache=lambda: None),
    )
    modules = {
        "torch": torch,
        "soundfile": types.SimpleNamespace(write=sf_write),
        "huggingface_hub": types.SimpleNamespace(hf_hub_download=hf_hub_download),
        "stable_audio_tools": types.SimpleNamespace(),
        "stable_audio_tools.models": types.SimpleNamespace(),
        "stable_audio_tools.models.factory": types.SimpleNamespace(
            create_model_from_config=Model
        ),
        "stable_audio_tools.models.utils": types.SimpleNamespace(
            copy_state_dict=lambda model, sd: seen.setdefault("weights", []).append(sd),
            load_ckpt_state_dict=lambda path: f"state of {Path(path).name}",
        ),
        "stable_audio_tools.inference": types.SimpleNamespace(),
        "stable_audio_tools.inference.generation": types.SimpleNamespace(
            generate_diffusion_cond=generate_diffusion_cond
        ),
    }
    for name, mod in modules.items():
        monkeypatch.setitem(sys.modules, name, mod)


T5 = {
    "repo_id": "google-t5/t5-base",
    "revision": "t5rev",
    "files": ("config.json", "spiece.model"),
}


def _request(tmp_path, **overrides):
    base = dict(
        repo_id="RoyalCities/Foundation-1",
        revision="abc",
        config_file="model_config.json",
        t5=T5,
        prompt="Pad, 4 Bars, 120 BPM",
        seconds=8.0,
        steps=100,
        cfg_scale=7.0,
        seed=11,
        sampler="dpmpp-3m-sde",
        sigma_min=0.3,
        sigma_max=500.0,
        out=str(tmp_path / "o.wav"),
    )
    return {**base, **overrides}


def test_worker_samples_with_plain_cfg_our_settings_and_holds_one_model(
    monkeypatch, tmp_path
):
    seen = {}
    _fake_upstream(monkeypatch, tmp_path, seen)
    worker = load_worker_module(worker_file("foundation_1"))
    state = worker.load()
    assert state["device"] == "mps"
    req = _request(tmp_path)
    out = worker.render(state, checkpoint="Foundation_1.safetensors", **req)
    worker.render(state, checkpoint="Foundation_1.safetensors", **req)
    assert len(seen["built"]) == 1  # loaded once
    assert seen["modes"] == ["eval", "grad=False"]  # inference mode, no dropout
    call = seen["calls"][0]
    assert call["apg_scale"] == 0.0  # plain CFG: nothing in float64 on MPS
    assert (call["seed"], call["steps"], call["cfg_scale"]) == (11, 100, 7.0)
    # left out, stable-audio-tools falls back to euler and its own schedule
    assert call["sampler_type"] == "dpmpp-3m-sde"
    assert (call["sigma_min"], call["sigma_max"]) == (0.3, 500.0)
    assert call["sample_size"] == 2000 and call["device"] == "mps"
    assert call["conditioning"] == [
        {"prompt": "Pad, 4 Bars, 120 BPM", "seconds_start": 0, "seconds_total": 8}
    ]
    assert call["negative_conditioning"] is None
    assert seen["written"] == (req["out"], (800, 2), 100, "PCM_16", 1.0)
    assert out == {
        "out": req["out"],
        "sample_rate": 100,
        "seconds": 8.0,
        "device": "mps",
    }
    worker.render(state, checkpoint="Foundation-1.2-Keybeds.safetensors", **req)
    assert len(seen["built"]) == 2 and state["loaded"][-1].endswith(
        "Keybeds.safetensors"
    )
    assert seen["weights"][-1] == "state of Foundation-1.2-Keybeds.safetensors"


def test_worker_conditions_on_whole_seconds_and_trims_exactly(monkeypatch, tmp_path):
    seen = {}
    _fake_upstream(monkeypatch, tmp_path, seen)
    worker = load_worker_module(worker_file("foundation_1"))
    state = worker.load()
    out = worker.render(
        state,
        checkpoint="Foundation_1.safetensors",
        **_request(tmp_path, seconds=9.6, negative_prompt="Distortion"),
    )
    call = seen["calls"][0]
    assert call["conditioning"][0]["seconds_total"] == 10  # 9.6 rounded up
    assert call["negative_conditioning"] == [
        {"prompt": "Distortion", "seconds_start": 0, "seconds_total": 10}
    ]
    assert seen["written"][1] == (960, 2) and out["seconds"] == pytest.approx(9.6)


@pytest.mark.parametrize(
    "seconds, total", [(6.4, 7), (8.0, 8), (8.0000001, 8), (0.3, 1)]
)
def test_worker_rounds_the_conditioning_up_as_in_training(
    seconds, total, monkeypatch, tmp_path
):
    """A loop told less than its length fades before its end (150 BPM, 4 bars: 6.4 s)."""
    seen = {}
    _fake_upstream(monkeypatch, tmp_path, seen)
    worker = load_worker_module(worker_file("foundation_1"))
    worker.render(
        worker.load(),
        checkpoint="Foundation_1.safetensors",
        **_request(tmp_path, seconds=seconds),
    )
    assert seen["calls"][0]["conditioning"][0]["seconds_total"] == total


def test_worker_points_the_t5_conditioner_at_the_pinned_files(monkeypatch, tmp_path):
    seen = {}
    _fake_upstream(monkeypatch, tmp_path, seen, cached=False)
    worker = load_worker_module(worker_file("foundation_1"))
    worker.render(
        worker.load(), checkpoint="Foundation_1.safetensors", **_request(tmp_path)
    )
    t5_cond, number = seen["built"][0]["model"]["conditioning"]["configs"]
    assert t5_cond["config"]["model_path"] == str(
        tmp_path / "google-t5--t5-base" / "t5rev"
    )
    assert "model_path" not in number["config"]
    t5_fetches = [d for d in seen["downloads"] if d[0] == "google-t5/t5-base"]
    assert {(f, r) for _, f, r, _ in t5_fetches} == {
        ("config.json", "t5rev"),
        ("spiece.model", "t5rev"),
    }
    assert all(not local for *_, local in t5_fetches)  # not cached: downloaded


def test_worker_reads_cached_files_without_the_network(monkeypatch, tmp_path):
    seen = {}
    _fake_upstream(monkeypatch, tmp_path, seen, cached=True)
    worker = load_worker_module(worker_file("foundation_1"))
    worker.render(
        worker.load(), checkpoint="Foundation_1.safetensors", **_request(tmp_path)
    )
    assert seen["downloads"] and all(local for *_, local in seen["downloads"])


# --- integration: a real render, only where the environment and weights are ----------


def _skip_unless_ready():
    from ps.isolated import is_env_ready

    from arioso._isolated import env_dir

    if not os.environ.get("ARIOSO_RUN_INTEGRATION"):
        return pytest.mark.skip(
            reason="set ARIOSO_RUN_INTEGRATION=1 to render with Foundation-1 (a 5 GB model)"
        )
    if f1.cached_weights() is None:
        return pytest.mark.skip(
            reason="Foundation-1 weights not in the Hugging Face cache"
        )
    existing = os.environ.get(PLATFORM_CONFIG["env_var"])
    if existing:  # an environment named instead of the built one
        from ps.isolated import venv_python

        ready = venv_python(Path(existing).expanduser()).exists()
        return pytest.mark.skipif(not ready, reason=f"no Python in {existing}")
    ready = is_env_ready(ENV_SPEC, env_dir(ENV_SPEC.name))
    return pytest.mark.skipif(not ready, reason="foundation-1 environment not built")


@pytest.fixture
def heavy_model_lock():
    """Hold the lock directory ``$ARIOSO_HEAVY_MODEL_LOCK`` names, if any, while rendering.

    Machines that run one large model at a time share such a lock (``mkdir`` is atomic);
    a lock someone else holds skips the test rather than load a second model.
    """
    import shutil

    lock = os.environ.get("ARIOSO_HEAVY_MODEL_LOCK")
    if not lock:
        yield
        return
    try:
        os.mkdir(lock)
    except FileExistsError:
        pytest.skip(f"another heavy model holds {lock}")
    try:
        Path(lock, "owner").write_text("arioso foundation_1 integration test\n")
        yield
    finally:
        shutil.rmtree(lock, ignore_errors=True)


@_skip_unless_ready()
def test_foundation_1_renders_for_real(heavy_model_lock):
    a = f1.Adapter()
    try:
        song = a.generate(
            "Pluck, Bright, Melody", bpm=150, bars=4, num_steps=20, seed=1
        )
    finally:
        a.close()
    assert song.status == "complete" and song.sample_rate == 44100
    assert song.audio.duration_seconds == pytest.approx(6.4, abs=0.01)
    assert np.abs(song.audio_array).max() > 0.5  # peak-normalised, not silence
