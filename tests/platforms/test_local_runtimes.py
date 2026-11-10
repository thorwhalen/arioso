"""Tests for the local-runtime platforms: stable_audio_3, magenta_rt, ace_step (runtime="local").

The process and worker seams are faked, so these run without MLX, torch or weights. The
``integration`` tests at the end render real audio and skip unless the runtime is installed
(point ``$ARIOSO_SA3_DIR`` / ``$ARIOSO_MAGENTA_RT_DIR`` / ``$ARIOSO_ACE_STEP_DIR`` at one).
"""

import wave

import pytest

import arioso
from arioso._isolated import Runtime
from arioso.platforms.ace_step import adapter as ace_mod
from arioso.platforms.ace_step.config import PLATFORM_CONFIG as ACE_CONFIG
from arioso.platforms.magenta_rt.adapter import Adapter as MrtAdapter
from arioso.platforms.magenta_rt.config import PLATFORM_CONFIG as MRT_CONFIG
from arioso.platforms.stable_audio_3.adapter import Adapter as Sa3Adapter
from arioso.platforms.stable_audio_3.config import PLATFORM_CONFIG as SA3_CONFIG


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
    song = Sa3Adapter(runner=runner, is_supported=lambda: True).generate("lofi loop", duration=4, model="medium")
    cmd = runner.calls[0]["cmd"]
    assert (_flag(cmd, "--dit"), _flag(cmd, "--decoder")) == ("medium", "same-l")
    assert _flag(cmd, "--seconds") == "4.0" and _flag(cmd, "--prompt") == "lofi loop"
    assert runner.calls[0]["cwd"] == root / "optimized/mlx"
    assert song.status == "complete" and song.sample_rate == 44100
    assert isinstance(song.metadata["seed"], int) and _flag(cmd, "--seed") == str(song.metadata["seed"])


def test_sa3_passes_audio_to_audio_and_inpainting(installed, tmp_path):
    installed(SA3_CONFIG)
    runner = _FakeRunner()
    src = _write_wav(tmp_path / "src.wav")
    Sa3Adapter(runner=runner, is_supported=lambda: True).generate(
        "drums", audio_input=src, audio_input_strength=0.4, inpaint_range=(1, 2), seed=7)
    cmd = runner.calls[0]["cmd"]
    assert _flag(cmd, "--init-noise-level") == "0.4" and _flag(cmd, "--inpaint-range") == "1,2"
    assert _flag(cmd, "--seed") == "7"


def test_sa3_rejects_inpainting_without_audio_and_unknown_models(installed):
    installed(SA3_CONFIG)
    a = Sa3Adapter(runner=_FakeRunner(), is_supported=lambda: True)
    with pytest.raises(ValueError, match="inpaint_range needs audio_input"):
        a.generate("x", inpaint_range=(0, 1))
    with pytest.raises(ValueError, match="unknown model"):
        a.generate("x", model="large")


def test_sa3_failure_carries_the_tool_log(installed):
    installed(SA3_CONFIG)
    a = Sa3Adapter(runner=_FakeRunner(code=2, log="\x1b[31mboom\x1b[0m"), is_supported=lambda: True)
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

    def __init__(self, python, module, *, env=None, cwd=None):
        self.python, self.module, self.env, self.cwd = python, module, env, cwd
        self.requests, self.closed = [], False
        _FakeWorker.instances.append(self)

    def call(self, req):
        self.requests.append(req)
        if "out_dir" in req:  # ace_step
            return {"out": _write_wav(f"{req['out_dir']}/a.wav", rate=48000), "params": {"bpm": req["bpm"]}}
        return {"out": _write_wav(req["out"], rate=48000), "frames": round(req["seconds"] * 25)}

    def close(self):
        self.closed = True


def test_magenta_rt_renders_through_one_worker_with_its_home(installed, monkeypatch):
    root = installed(MRT_CONFIG)
    monkeypatch.delenv("MAGENTA_HOME", raising=False)
    a = MrtAdapter(make_worker=_FakeWorker)
    song = a.generate("funk groove", duration=2, model="mrt2_base", guidance=4)
    a.generate("second take", duration=1)
    w = a._worker
    assert w.module == "arioso.platforms.magenta_rt._driver" and len(w.requests) == 2
    assert w.env["MAGENTA_HOME"] == str(root / "home")
    assert w.requests[0]["size"] == "mrt2_base" and w.requests[0]["guidance"] == 4.0
    assert song.metadata["frames"] == 50 and song.metadata["seed"] is None
    a.close()
    assert w.closed and a._worker is None


def test_ace_step_defaults_to_fal_and_env_can_make_local_the_default(installed, monkeypatch):
    installed(ACE_CONFIG)
    seen = []
    monkeypatch.setattr(ace_mod, "fal_run", lambda endpoint, arguments: seen.append(endpoint) or {"audio": {"url": "u"}})
    monkeypatch.delenv("ARIOSO_ACE_STEP_RUNTIME", raising=False)
    a = ace_mod.Adapter()
    with pytest.warns(UserWarning, match="no bpm"):
        a.generate("jazz", bpm=120, fetch=False)
    assert seen == ["fal-ai/ace-step"]
    monkeypatch.setenv("ARIOSO_ACE_STEP_RUNTIME", "local")
    local = ace_mod.LocalAceStep(ACE_CONFIG, make_worker=_FakeWorker)
    song = ace_mod.Adapter(local=local).generate("jazz", bpm=120, key="C Major", duration=10)
    req = local._worker.requests[0]
    assert (req["caption"], req["bpm"], req["key"], req["lyrics"]) == ("jazz", 120, "C Major", "[Instrumental]")
    assert song.metadata["runtime"] == "local" and isinstance(song.metadata["seed"], int)


def test_ace_step_local_cover_from_audio_input(installed, tmp_path):
    installed(ACE_CONFIG)
    local = ace_mod.LocalAceStep(ACE_CONFIG, make_worker=_FakeWorker)
    src = _write_wav(tmp_path / "melody.wav")
    ace_mod.Adapter(local=local).generate("piano", runtime="local", audio_input=src, audio_input_strength=0.3)
    req = local._worker.requests[0]
    assert req["task_type"] == "cover" and req["cover_strength"] == 0.3 and req["src_audio"].endswith(".wav")


def test_ace_step_rejects_an_unknown_runtime():
    with pytest.raises(ValueError, match="runtime must be"):
        ace_mod.Adapter().generate("x", runtime="cloud")


def test_local_platforms_are_registered_with_their_licences():
    for name in ("stable_audio_3", "magenta_rt"):
        info = arioso.get_platform_info(name)
        assert info["access_type"] == "local_runtime" and info["weights_license"]
    assert ACE_CONFIG["commercial_use"] == "yes"


# --- integration: real renders, only where the runtime is installed -------------------


def _skip_unless_installed(config):
    rt = Runtime(**config["runtime"])
    return pytest.mark.skipif(not rt.installed(), reason=f"{rt.name} runtime not installed ({rt.root()})")


@_skip_unless_installed(SA3_CONFIG)
def test_sa3_renders_for_real():
    song = arioso.generate("lo-fi hip hop loop, 85 BPM", platform="stable_audio_3", duration=2, seed=1)
    assert song.status == "complete" and song.sample_rate == 44100 and len(song.audio_bytes) > 1000


@_skip_unless_installed(MRT_CONFIG)
def test_magenta_rt_renders_for_real():
    song = arioso.generate("funk drum groove", platform="magenta_rt", duration=2)
    assert song.status == "complete" and song.sample_rate == 48000


@_skip_unless_installed(ACE_CONFIG)
def test_ace_step_local_renders_for_real():
    song = arioso.generate("funk groove", platform="ace_step", runtime="local", duration=10, bpm=100, seed=1)
    assert song.status == "complete" and song.audio_bytes
