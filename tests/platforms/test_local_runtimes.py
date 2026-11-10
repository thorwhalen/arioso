"""Tests for the local-runtime platforms: stable_audio_3, magenta_rt, ace_step (runtime="local").

The process and worker seams are faked, and the worker files run against fake upstream modules,
so these need no MLX, torch or weights. The tests at the end render real audio only with
``ARIOSO_RUN_INTEGRATION=1`` and an installed runtime (``$ARIOSO_SA3_DIR`` /
``$ARIOSO_MAGENTA_RT_DIR`` / ``$ARIOSO_ACE_STEP_DIR``).
"""

import ast
import sys
import wave

import pytest

import arioso
from arioso._isolated import Runtime, worker_file
from arioso.platforms.ace_step import adapter as ace_mod
from arioso.platforms.ace_step.config import PLATFORM_CONFIG as ACE_CONFIG
from arioso.platforms.magenta_rt.adapter import Adapter as MrtAdapter
from arioso.platforms.magenta_rt.config import PLATFORM_CONFIG as MRT_CONFIG
from arioso.platforms.stable_audio_3.adapter import Adapter as Sa3Adapter
from arioso.platforms.stable_audio_3.config import PLATFORM_CONFIG as SA3_CONFIG
from tests._in_process import load_worker_module


def _write_wav(path, frames=441, rate=44100):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * frames)
    return str(path)


@pytest.fixture
def installed(monkeypatch, tmp_path):
    """Make every runtime look installed under tmp_path (an empty interpreter file)."""

    def make(config):
        rt = config["runtime"]
        root = tmp_path / rt["name"]
        py = root / rt.get("python", ".venv/bin/python")
        py.parent.mkdir(parents=True, exist_ok=True)
        py.touch()
        monkeypatch.setenv(rt["env_var"], str(root))
        return root

    return make


# --- stable_audio_3 -----------------------------------------------------------------


class _FakeRunner:
    def __init__(self, code=0, log=""):
        self.calls, self.code, self.log = [], code, log

    def __call__(self, cmd, *, cwd, env, timeout):
        self.calls.append(dict(cmd=[str(c) for c in cmd], cwd=cwd))
        if not self.code:
            _write_wav(cmd[cmd.index("--out") + 1])
        return self.code, self.log


def _flag(cmd, name):
    return cmd[cmd.index(name) + 1]


def test_sa3_maps_model_to_dit_and_decoder_and_records_a_drawn_seed(installed):
    root = installed(SA3_CONFIG)
    runner = _FakeRunner()
    song = Sa3Adapter(runner=runner, is_supported=lambda: True).generate(
        "lofi loop", duration=4, model="medium"
    )
    cmd = runner.calls[0]["cmd"]
    assert (_flag(cmd, "--dit"), _flag(cmd, "--decoder")) == ("medium", "same-l")
    assert _flag(cmd, "--seconds") == "4.0" and "--prompt=lofi loop" in cmd
    assert runner.calls[0]["cwd"] == root / "optimized/mlx"
    assert song.status == "complete" and song.sample_rate == 44100
    assert isinstance(song.metadata["seed"], int) and _flag(cmd, "--seed") == str(
        song.metadata["seed"]
    )


def test_sa3_passes_audio_to_audio_and_inpainting(installed, tmp_path):
    installed(SA3_CONFIG)
    runner = _FakeRunner()
    src = _write_wav(tmp_path / "src.wav")
    Sa3Adapter(runner=runner, is_supported=lambda: True).generate(
        "drums", audio_input=src, audio_input_strength=0.4, inpaint_range=(1, 2), seed=7
    )
    cmd = runner.calls[0]["cmd"]
    assert (
        _flag(cmd, "--init-noise-level") == "0.4"
        and _flag(cmd, "--inpaint-range") == "1,2"
    )
    assert _flag(cmd, "--seed") == "7"


def test_sa3_inpainting_defaults_to_full_noise(installed, tmp_path):
    installed(SA3_CONFIG)
    runner = _FakeRunner()
    src = _write_wav(tmp_path / "src.wav")
    a = Sa3Adapter(runner=runner, is_supported=lambda: True)
    a.generate("drums", audio_input=src, inpaint_range=(1, 2))
    a.generate("drums", audio_input=src)
    assert _flag(runner.calls[0]["cmd"], "--init-noise-level") == "1.0"
    assert _flag(runner.calls[1]["cmd"], "--init-noise-level") == "0.7"


def test_sa3_a_prompt_starting_with_a_dash_stays_a_prompt(installed):
    installed(SA3_CONFIG)
    runner = _FakeRunner()
    Sa3Adapter(runner=runner, is_supported=lambda: True).generate("-100 BPM techno")
    assert "--prompt=-100 BPM techno" in runner.calls[0]["cmd"]


def test_sa3_rejects_inpainting_without_audio_and_unknown_models(installed):
    installed(SA3_CONFIG)
    a = Sa3Adapter(runner=_FakeRunner(), is_supported=lambda: True)
    with pytest.raises(ValueError, match="inpaint_range needs audio_input"):
        a.generate("x", inpaint_range=(0, 1))
    with pytest.raises(ValueError, match="unknown model"):
        a.generate("x", model="large")


def test_sa3_failure_carries_the_tool_log(installed):
    installed(SA3_CONFIG)
    a = Sa3Adapter(
        runner=_FakeRunner(code=2, log="\x1b[31mboom\x1b[0m"), is_supported=lambda: True
    )
    with pytest.raises(RuntimeError, match="(?s)exit 2.*boom"):
        a.generate("x")


def test_sa3_refuses_off_apple_silicon(installed):
    installed(SA3_CONFIG)
    with pytest.raises(RuntimeError, match="Apple Silicon"):
        Sa3Adapter(runner=_FakeRunner(), is_supported=lambda: False).generate("x")


# --- worker-backed platforms ----------------------------------------------------------


class _FakeWorker:
    """Records how it was built and what it was asked; writes a wav where asked."""

    instances = []

    def __init__(self, python, adapter, *, init=None, env=None, cwd=None, stderr="log"):
        self.python, self.adapter, self.env, self.cwd = python, adapter, env, cwd
        self.init, self.stderr = init, stderr
        self.ops, self.requests, self.closed = [], [], False
        _FakeWorker.instances.append(self)

    def call(self, op, /, **req):
        self.ops.append(op)
        self.requests.append(req)
        if "out_dir" in req:  # ace_step
            return {
                "out": _write_wav(f"{req['out_dir']}/a.wav", rate=48000),
                "params": {"bpm": req["bpm"]},
            }
        return {
            "out": _write_wav(req["out"], rate=48000),
            "frames": round(req["seconds"] * 25),
        }

    def close(self):
        self.closed = True


def test_magenta_rt_renders_through_one_worker_with_its_home(installed, monkeypatch):
    root = installed(MRT_CONFIG)
    (root / "home").mkdir()
    monkeypatch.delenv("MAGENTA_HOME", raising=False)
    a = MrtAdapter(make_worker=_FakeWorker)
    song = a.generate("funk groove", duration=2, model="mrt2_base", guidance=4)
    a.generate("second take", duration=1)
    w = a._worker
    assert w.adapter == worker_file("magenta_rt") and w.ops == ["render", "render"]
    assert w.stderr is None  # model output stays on the terminal
    assert w.env["MAGENTA_HOME"] == str(root / "home")
    assert w.requests[0]["size"] == "mrt2_base" and w.requests[0]["guidance"] == 4.0
    assert song.metadata["frames"] == 50 and song.metadata["seed"] is None
    a.close()
    assert w.closed and a._worker is None


def test_ace_step_defaults_to_fal_and_env_can_make_local_the_default(
    installed, monkeypatch
):
    installed(ACE_CONFIG)
    seen = []
    monkeypatch.setattr(
        ace_mod,
        "fal_run",
        lambda endpoint, arguments: seen.append(endpoint) or {"audio": {"url": "u"}},
    )
    monkeypatch.delenv("ARIOSO_ACE_STEP_RUNTIME", raising=False)
    a = ace_mod.Adapter()
    with pytest.warns(UserWarning, match="no bpm"):
        a.generate("jazz", bpm=120, fetch=False)
    assert seen == ["fal-ai/ace-step"]
    monkeypatch.setenv("ARIOSO_ACE_STEP_RUNTIME", "local")
    local = ace_mod.LocalAceStep(ACE_CONFIG, make_worker=_FakeWorker)
    song = ace_mod.Adapter(local=local).generate(
        "jazz", bpm=120, key="C Major", duration=10
    )
    assert local._worker.adapter == worker_file("ace_step")
    assert local._worker.ops == ["render"] and local._worker.stderr is None
    req = local._worker.requests[0]
    assert (req["caption"], req["bpm"], req["key"], req["lyrics"]) == (
        "jazz",
        120,
        "C Major",
        "[Instrumental]",
    )
    assert song.metadata["runtime"] == "local" and isinstance(
        song.metadata["seed"], int
    )


def test_ace_step_local_cover_from_audio_input(installed, tmp_path):
    installed(ACE_CONFIG)
    local = ace_mod.LocalAceStep(ACE_CONFIG, make_worker=_FakeWorker)
    src = _write_wav(tmp_path / "melody.wav")
    ace_mod.Adapter(local=local).generate(
        "piano", runtime="local", audio_input=src, audio_input_strength=0.3
    )
    req = local._worker.requests[0]
    assert (
        req["task_type"] == "cover"
        and req["cover_strength"] == 0.3
        and req["src_audio"].endswith(".wav")
    )


def test_ace_step_rejects_an_unknown_runtime(monkeypatch):
    with pytest.raises(ValueError, match="runtime must be"):
        ace_mod.Adapter().generate("x", runtime="cloud")
    monkeypatch.setenv("ARIOSO_ACE_STEP_RUNTIME", "cloud")
    with pytest.raises(ValueError, match="ARIOSO_ACE_STEP_RUNTIME must be"):
        ace_mod.Adapter().generate("x")


def test_ace_step_local_warns_on_fal_only_options(installed):
    installed(ACE_CONFIG)
    local = ace_mod.LocalAceStep(ACE_CONFIG, make_worker=_FakeWorker)
    with pytest.warns(UserWarning, match="no edit_mode"):
        local.generate("jazz", edit_mode="remix")


def test_local_only_keywords_are_read_by_the_local_runtime():
    import inspect

    local_params = inspect.signature(ace_mod.LocalAceStep.generate).parameters
    assert set(ace_mod.LOCAL_ONLY) <= set(local_params)
    assert {"bpm", "key", "reference_audio"} <= set(ace_mod.LOCAL_ONLY)
    assert "seed" not in ace_mod.LOCAL_ONLY  # fal maps it too


# --- the worker files, against fake upstream modules --------------------------------


def _install_fake_modules(monkeypatch, modules):
    import sys
    import types

    for name, attrs in modules.items():
        mod = types.ModuleType(name)
        mod.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, mod)


def test_ace_step_worker_passes_our_seed_and_controls(monkeypatch, tmp_path):
    seen = {}

    class Params:
        def __init__(self, **kw):
            seen["params"] = kw
            self.__dict__.update(kw)

    class Config:
        def __init__(self, **kw):
            seen["config"] = kw

    class Handler:
        def initialize_service(self, **kw):
            seen["dit"] = kw
            return "ok", True

    def generate_music(dit_h, llm_h, *, params, config, save_dir):
        out = _write_wav(tmp_path / "ace.wav", rate=48000)
        return type(
            "R",
            (),
            {
                "success": True,
                "audios": [{"path": out, "key": "C", "params": {"bpm": 100}}],
                "status_message": "",
                "error": None,
            },
        )()

    _install_fake_modules(
        monkeypatch,
        {
            "acestep": {},
            "acestep.handler": {"AceStepHandler": Handler},
            "acestep.inference": {
                "GenerationParams": Params,
                "GenerationConfig": Config,
                "generate_music": generate_music,
            },
        },
    )
    monkeypatch.setattr(sys, "path", list(sys.path))  # load() puts the checkout on it
    monkeypatch.setenv("TOKENIZERS_PARALLELISM", "false")
    monkeypatch.chdir(tmp_path)  # the worker runs in the checkout
    worker = load_worker_module(worker_file("ace_step"))
    state = worker.load()
    assert state["root"] == str(tmp_path) and sys.path[0] == str(tmp_path)
    request = {
        "caption": "funk",
        "seconds": 10.0,
        "steps": 8,
        "guidance": 7.0,
        "seed": 123,
        "dit": "acestep-v15-turbo",
        "lm": None,
        "bpm": 100,
        "key": "C Major",
        "out_dir": str(tmp_path),
    }
    out = worker.render(state, **request)
    worker.render(state, **request)
    assert seen["dit"]["project_root"] == str(tmp_path)
    assert len(state["handlers"]) == 1, "the DiT loads once and is kept"
    assert seen["config"]["use_random_seed"] is False and seen["config"]["seeds"] == [
        123
    ]
    assert (
        seen["params"]["seed"] == 123
        and seen["params"]["bpm"] == 100
        and seen["params"]["thinking"] is False
    )
    assert out["out"].endswith("ace.wav")


def test_magenta_rt_worker_loads_once_per_size_and_samples_per_call(
    monkeypatch, tmp_path
):
    built, calls = [], []

    class Model:
        def __init__(self, size):
            built.append(size)

        def embed_style(self, style, use_mapper):
            return [0.0]

        def generate(self, *, conditioning, cfg_scales, temperature, top_k, frames):
            calls.append((cfg_scales["musiccoca"], temperature, top_k, frames))
            wav = type(
                "W",
                (),
                {
                    "sample_rate": 48000,
                    "write": lambda self, p: _write_wav(p, rate=48000),
                },
            )()
            return wav, None

    _install_fake_modules(
        monkeypatch,
        {
            "magenta_rt": {"MagentaRT2StdMlxfn": Model, "audio": None},
            "magenta_rt.config": {"MUSICCOCA": type("M", (), {"key": "musiccoca"})},
        },
    )
    worker = load_worker_module(worker_file("magenta_rt"))
    models = worker.load()
    base = {
        "prompt": "funk",
        "seconds": 2.0,
        "size": "mrt2_small",
        "top_k": 40,
        "out": str(tmp_path / "o.wav"),
    }
    out = worker.render(models, **base, temperature=1.3, guidance=3.0)
    worker.render(models, **base, temperature=0.9, guidance=5.0)
    assert out == {"out": base["out"], "sample_rate": 48000, "frames": 50}
    assert built == ["mrt2_small"]
    assert calls == [(3.0, 1.3, 40, 50), (5.0, 0.9, 40, 50)]


WORKERS = ("magenta_rt", "ace_step", "musicgen_mlx")


@pytest.mark.parametrize("name", WORKERS)
def test_worker_files_import_nothing_from_arioso(name):
    """They run in environments that need not have arioso."""
    tree = ast.parse(worker_file(name).read_text())
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert "arioso" not in imported and "ps" not in imported


def test_the_configs_name_existing_workers():
    from arioso.platforms.musicgen.config import PLATFORM_CONFIG as MG_CONFIG

    for name in (MRT_CONFIG["worker"], ACE_CONFIG["worker"], MG_CONFIG["mlx_worker"]):
        assert worker_file(name).is_file()


@pytest.mark.parametrize("name", ["magenta_rt", "ace_step"])
def test_worker_files_load_in_a_real_worker(name, tmp_path):
    """Through ps: the file loads standalone and answers (a bad render is reported)."""
    from arioso._isolated import Worker, WorkerError

    with Worker(sys.executable, worker_file(name), cwd=tmp_path) as w:
        with pytest.raises(WorkerError, match="TypeError"):
            w.call("render")  # no arguments: load() ran, render() refused them
        assert w.running


def test_local_platforms_are_registered_with_their_licences():
    for name in ("stable_audio_3", "magenta_rt"):
        info = arioso.get_platform_info(name)
        assert info["access_type"] == "local_runtime" and info["weights_license"]
    assert ACE_CONFIG["commercial_use"] == "yes"


# --- integration: real renders, only where the runtime is installed -------------------


def _skip_unless_installed(config):
    """Real renders are opt-in ($ARIOSO_RUN_INTEGRATION=1): ACE-Step's first one downloads 9.4 GB."""
    import os

    rt = Runtime(**config["runtime"])
    if not os.environ.get("ARIOSO_RUN_INTEGRATION"):
        return pytest.mark.skip(
            reason="set ARIOSO_RUN_INTEGRATION=1 to render with installed runtimes"
        )
    return pytest.mark.skipif(
        not rt.installed(), reason=f"{rt.name} runtime not installed ({rt.root()})"
    )


@_skip_unless_installed(SA3_CONFIG)
def test_sa3_renders_for_real():
    song = arioso.generate(
        "lo-fi hip hop loop, 85 BPM", platform="stable_audio_3", duration=2, seed=1
    )
    assert (
        song.status == "complete"
        and song.sample_rate == 44100
        and len(song.audio_bytes) > 1000
    )


@_skip_unless_installed(MRT_CONFIG)
def test_magenta_rt_renders_for_real():
    song = arioso.generate("funk drum groove", platform="magenta_rt", duration=2)
    assert song.status == "complete" and song.sample_rate == 48000


@_skip_unless_installed(ACE_CONFIG)
def test_ace_step_local_renders_for_real():
    song = arioso.generate(
        "funk groove",
        platform="ace_step",
        runtime="local",
        duration=10,
        bpm=100,
        seed=1,
    )
    assert song.status == "complete" and song.audio_bytes
