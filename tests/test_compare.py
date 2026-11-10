"""``arioso.compare``: records, measurement, checks, the hosted guard, the page and the command.

Runs against fake platforms (``tests/_compare_fake_platform.py``): no model, no network.
"""

import doctest
import json
import os
import sys
from pathlib import Path

import pytest

import arioso.compare as ac
from arioso.__main__ import main

FAKE = "tests._compare_fake_platform"
REPO = Path(__file__).resolve().parents[1]
PROMPTS = [
    {"id": "fast", "text": "click track at 120 BPM", "bpm": 120, "key": "C major"},
    {"id": "slow", "text": "click track at 90 BPM", "bpm": 90},
]


@pytest.fixture
def fakes():
    import importlib

    module = importlib.import_module(FAKE)
    module.register()
    module.CALLS.clear()
    yield module
    module.unregister()


def _run(contenders, tmp_path, **kwargs):
    kwargs = {
        "duration": 4.0,
        "warmup": 1.0,
        "out_dir": tmp_path,
        "runner": ac.in_this_process,
        "run_id": "r1",
        **kwargs,
    }
    return list(ac.compare(contenders, PROMPTS, **kwargs))


def test_doctests():
    assert doctest.testmod(ac).failed == 0


def test_one_record_per_take_with_timings_audio_and_settings_passed(fakes, tmp_path):
    records = _run("fake_clicks", tmp_path, seed=7)

    assert [r["prompt"] for r in records] == ["fast", "slow"]
    r = records[0]
    assert r["contender"] == r["platform"] == "fake_clicks"
    assert r["seconds_out"] == 4.0 and r["sample_rate"] == fakes.SAMPLE_RATE
    assert r["gen_s"] >= 0 and r["rtf"] == pytest.approx(r["gen_s"] / 4.0, abs=1e-3)
    assert r["load_s"] is not None  # a warm-up ran
    assert r["duration_used"] and r["seed_used"] and not r["melody_used"]
    assert r["weights_license"] == "MIT" and r["commercial_use"] == "yes"
    assert Path(r["path"]) == tmp_path / "r1" / "fake_clicks" / "fast.wav"
    assert Path(r["path"]).is_file() and r["run_id"] == "r1"
    if sys.platform == "darwin" or sys.platform.startswith("linux"):
        assert r["available_memory_gb"] > 0
    # warm-up first (1 s), then each prompt at the asked duration and seed
    assert [(c["duration"], c["seed"]) for c in fakes.CALLS] == [
        (1.0, 7),
        (4.0, 7),
        (4.0, 7),
    ]
    # records are appended to results.jsonl as they come
    assert ac.read_records(tmp_path) == records


def test_checks_find_the_tempo_that_was_rendered(fakes, tmp_path):
    pytest.importorskip("denote")
    pytest.importorskip("librosa")
    fast, slow = _run("fake_clicks", tmp_path)
    assert fast["tempo_detected"] == pytest.approx(120, rel=0.03)
    assert slow["tempo_detected"] == pytest.approx(90, rel=0.03)
    assert fast["tempo_err"] < 0.03 and slow["tempo_err"] < 0.03
    assert fast["clip_frac"] == 0 and -40 < fast["rms_dbfs"] < 0


def test_rtf_divides_by_the_audio_that_came_back(fakes, tmp_path):
    r = _run("fake_short", tmp_path, warmup=None)[0]
    assert r["seconds_out"] == 3.5
    # gen_s is rounded to 0.01 s and rtf to 0.001, so they agree up to that rounding
    rounding = 0.005 / 3.5 + 0.0005
    assert abs(r["rtf"] - r["gen_s"] / 3.5) <= rounding
    # the fake sleeps >= 0.3 s, so dividing by 4 s would be off by >= 0.0107
    assert abs(r["rtf"] - r["gen_s"] / 4.0) > 0.005


def test_a_leading_batch_axis_is_not_taken_for_channels(fakes, tmp_path):
    r = _run("fake_batched", tmp_path)[0]
    assert r["seconds_out"] == 4.0 and "error" not in r


def test_clipping_is_seen_even_above_full_scale(fakes, tmp_path):
    pytest.importorskip(
        "soundfile"
    )  # takes are float WAVs; 16-bit PCM would clamp at 1
    r = _run("fake_loud", tmp_path)[0]
    assert r["peak_abs"] == pytest.approx(1.5, abs=0.01)
    assert r["clip_frac"] > 0


def test_a_check_that_cannot_run_says_why(fakes, tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "denote", None)  # import denote -> ImportError
    r = _run("fake_clicks", tmp_path)[0]
    assert r["checks_skipped"] == {
        "tempo": "denote is not installed",
        "key": "denote is not installed",
    }


def test_a_failing_platform_is_recorded_not_raised(fakes, tmp_path):
    records = _run("fake_clicks,fake_broken", tmp_path)
    broken = [r for r in records if r["contender"] == "fake_broken"]
    assert len(broken) == 2 and all("model exploded" in r["error"] for r in broken)
    assert all("error" not in r for r in records if r["contender"] == "fake_clicks")
    lines = ac.summary_lines(records)
    assert lines[0].split()[:3] == ["contender", "takes", "failed"]
    assert any(
        line.startswith("fake_broken:") and "model exploded" in line for line in lines
    )


def test_hosted_contenders_are_refused_unless_allowed(fakes, tmp_path):
    assert ac.is_hosted("fake_hosted") and not ac.is_hosted("fake_clicks")
    with pytest.raises(ValueError, match="allow_hosted"):
        _run("fake_clicks,fake_hosted", tmp_path)
    assert fakes.CALLS == []  # refused before anything ran
    assert len(_run("fake_hosted", tmp_path, allow_hosted=True)) == 2


def test_hosted_errs_on_the_side_of_caution(fakes):
    # ace_step is a hosted (fal) platform unless asked to run its local runtime
    assert ac.is_hosted("ace_step")
    # runtime=local only counts on a platform that has a local runtime
    assert ac.is_hosted("elevenlabs:runtime=local")
    assert ac.is_hosted("yue:runtime=local")
    assert ac.is_hosted("stable_audio_25:runtime=local")
    # a config without access_type is a rest_api one to the translation layer
    assert ac.is_hosted("fake_no_access_type")
    assert ac.is_hosted("fake_provider_terms") and ac.is_hosted("fake_fal")
    assert ac.is_hosted("yue")  # local code, but takes a fal key: counted as hosted
    assert not any(
        ac.is_hosted(p) for p in ("musicgen", "stable_audio_3", "magenta_rt")
    )
    assert not ac.is_hosted("ace_step:runtime=local")


def test_unknown_platform_fails_before_anything_runs(fakes, tmp_path):
    with pytest.raises(ValueError, match="no_such_platform"):
        _run("fake_clicks,no_such_platform", tmp_path)
    assert fakes.CALLS == []


def test_min_free_gb_skips_a_contender(fakes, tmp_path):
    from arioso._measure import available_memory

    if available_memory() is None:
        pytest.skip("no memory probe on this platform")
    records = _run("fake_clicks", tmp_path, min_free_gb=10**6)
    assert all(r["error"].startswith("skipped:") for r in records)
    assert fakes.CALLS == []


def test_each_contender_in_its_own_process_measures_peak_memory(
    fakes, tmp_path, monkeypatch
):
    # the child imports the fake platforms itself (preload) and finds tests/ on its path
    monkeypatch.setenv(
        "PYTHONPATH", os.pathsep.join([str(REPO), os.environ.get("PYTHONPATH", "")])
    )

    def runner(*args, **kwargs):
        return ac.in_child_process(*args, preload=[f"{FAKE}:register"], **kwargs)

    records = _run("fake_clicks", tmp_path, runner=runner)

    assert [r["prompt"] for r in records] == ["fast", "slow"]
    assert fakes.CALLS == []  # it all happened in the child
    assert all(Path(r["path"]).is_file() for r in records)
    if sys.platform == "darwin" or sys.platform.startswith("linux"):
        assert records[0]["peak_memory_gb"] > 0


def test_the_peak_of_a_short_lived_process_per_take_is_caught(
    fakes, tmp_path, monkeypatch
):
    from arioso import _measure

    if _measure.peak_memory() is None:
        pytest.skip("no memory probe on this platform")
    # without the exit-time floor (blind to Metal memory), only the sampler can see it
    monkeypatch.setattr(_measure, "_children_maxrss", lambda: 0)
    records = _run("fake_oneshot", tmp_path, warmup=None)
    assert (
        records[0]["workers_peak_memory_gb"] >= 0.15
    )  # the ~200 MB children, long gone


def test_a_crashing_child_becomes_error_records(fakes, tmp_path):
    def runner(
        *args, **kwargs
    ):  # the child dies importing a module that does not exist
        return ac.in_child_process(
            *args, preload=["no_such_module_for_arioso_tests"], **kwargs
        )

    records = _run("fake_clicks", tmp_path, runner=runner)
    assert all("child process failed" in r["error"] for r in records)
    assert (
        "no_such_module_for_arioso_tests" in records[0]["error"]
    )  # the child's last words


def test_a_child_that_crashes_at_shutdown_keeps_its_records(
    fakes, tmp_path, monkeypatch
):
    monkeypatch.setenv(
        "PYTHONPATH", os.pathsep.join([str(REPO), os.environ.get("PYTHONPATH", "")])
    )
    preload = [f"{FAKE}:register", f"{FAKE}:exit_badly_at_shutdown"]

    def runner(*args, **kwargs):
        return ac.in_child_process(*args, preload=preload, **kwargs)

    records = _run("fake_clicks", tmp_path, runner=runner)
    assert all("error" not in r and r["child_exit"] == 139 for r in records)


def test_a_hung_child_is_killed_after_the_timeout(fakes, tmp_path, monkeypatch):
    monkeypatch.setenv(
        "PYTHONPATH", os.pathsep.join([str(REPO), os.environ.get("PYTHONPATH", "")])
    )

    def runner(*args, **kwargs):
        return ac.in_child_process(
            *args, preload=[f"{FAKE}:register"], timeout=3, **kwargs
        )

    records = _run("fake_slow", tmp_path, runner=runner)
    assert all("killed after 3 s" in r["error"] for r in records)


def _with_repo_on_path(monkeypatch):
    monkeypatch.setenv(
        "PYTHONPATH", os.pathsep.join([str(REPO), os.environ.get("PYTHONPATH", "")])
    )


def _alive(pid):
    """Whether ``pid`` is still running (a zombie counts as gone)."""
    if os.name == "nt":  # os.kill(pid, 0) would terminate it there
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        # SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION
        handle = kernel32.OpenProcess(0x00100000 | 0x1000, False, pid)
        if not handle:
            return False
        try:
            return kernel32.WaitForSingleObject(handle, 0) == 0x102  # WAIT_TIMEOUT
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    import subprocess

    out = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True)
    return bool(out.stdout.strip()) and not out.stdout.strip().startswith("Z")


def _gone_soon(pid, timeout=5.0):
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _alive(pid):
            return True
        time.sleep(0.05)
    return False


def _kill(pid):
    import signal

    try:
        os.kill(pid, getattr(signal, "SIGKILL", signal.SIGTERM))
    except OSError:
        pass


def test_the_liveness_check_sees_a_live_process_and_its_end():
    """So the 'gone' checks below cannot pass vacuously (on Windows above all)."""
    import subprocess

    sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert _alive(sleeper.pid)
    finally:
        sleeper.kill()
        sleeper.wait()
    assert _gone_soon(sleeper.pid)


def test_a_bad_timeout_raises_and_leaves_no_child(fakes, tmp_path, monkeypatch):
    import subprocess

    started = []
    real_popen = subprocess.Popen

    def popen(*args, **kwargs):
        started.append(real_popen(*args, **kwargs))
        return started[-1]

    monkeypatch.setattr(subprocess, "Popen", popen)
    with pytest.raises(ValueError):
        ac._run_child(
            [sys.executable, "-c", "import time; time.sleep(30)"], None, timeout=-1
        )
    assert len(started) == 1 and started[0].returncode is not None


def test_a_timeout_kills_the_child_and_its_workers_and_keeps_finished_takes(
    fakes, tmp_path, monkeypatch
):
    _with_repo_on_path(monkeypatch)
    pidfile = tmp_path / "worker.pid"
    monkeypatch.setenv("ARIOSO_TEST_PIDFILE", str(pidfile))
    records = _run(
        "fake_slow_second",
        tmp_path,
        runner=None,  # the default: in_child_process
        preload=[f"{FAKE}:register"],
        timeout=12,
    )
    fast, slow = records
    assert "error" not in fast and fast["child_exit"] == "killed after 12 s"
    assert Path(fast["path"]).is_file()
    assert "killed after 12 s" in slow["error"]
    worker = int(pidfile.read_text())
    gone = _gone_soon(worker)  # the worker the child started is gone too
    if not gone:
        _kill(worker)  # only a live one: a dead pid may be someone else's by now
    assert gone


@pytest.mark.skipif(
    not (sys.platform == "darwin" or sys.platform.startswith("linux")),
    reason="the tree is watched through macOS libproc or Linux /proc",
)
def test_a_child_that_crashes_takes_its_workers_with_it(fakes, tmp_path, monkeypatch):
    _with_repo_on_path(monkeypatch)
    pidfile = tmp_path / "worker.pid"
    monkeypatch.setenv("ARIOSO_TEST_PIDFILE", str(pidfile))
    records = _run(
        "fake_crash_with_worker",
        tmp_path,
        runner=None,
        preload=[f"{FAKE}:register"],
        timeout=60,
    )
    assert all("child process failed (exit 139" in r["error"] for r in records)
    worker = int(pidfile.read_text())
    gone = _gone_soon(worker)  # a crash skips the child's cleanup; ours ran
    if not gone:
        _kill(worker)
    assert gone


def test_preload_reaches_the_default_child_runner(tmp_path, monkeypatch):
    import importlib

    _with_repo_on_path(monkeypatch)
    module = importlib.import_module(FAKE)
    module.unregister()
    try:
        records = _run(
            "fake_clicks", tmp_path, runner=None, preload=[f"{FAKE}:register"]
        )
        assert all("error" not in r for r in records)
        assert module.CALLS == []  # generated in the child, which had the platform too
    finally:
        module.unregister()


def test_preload_makes_a_third_party_platform_known_here_too(tmp_path):
    import importlib

    module = importlib.import_module(FAKE)
    module.unregister()
    try:
        records = _run("fake_clicks", tmp_path, preload=[f"{FAKE}:register"])
        assert [r["prompt"] for r in records] == ["fast", "slow"]
    finally:
        module.unregister()


def test_names_that_collide_as_files_are_refused():
    with pytest.raises(ValueError, match="collide"):
        ac.parse_contenders(["musicgen:model=a/b", "musicgen:model=a_b"])
    with pytest.raises(ValueError, match="collide"):
        ac.load_prompts([{"id": "a b", "text": "x"}, {"id": "a_b", "text": "y"}])


def test_page_links_audio_relative_to_itself(fakes, tmp_path):
    records = _run("fake_clicks,fake_broken", tmp_path)
    page = ac.compare_page(records, tmp_path / "index.html", prompts=PROMPTS)
    text = page.read_text()
    assert "src='r1/fake_clicks/fast.wav'" in text
    assert "click track at 120 BPM" in text and "model exploded" in text


def test_contender_options_are_parsed_as_json_when_they_parse():
    c = ac.Contender.parse(
        "musicgen:model=facebook/musicgen-small:num_steps=8:guidance=1.5"
    )
    assert c.platform == "musicgen"
    assert c.options == {
        "model": "facebook/musicgen-small",
        "num_steps": 8,
        "guidance": 1.5,
    }
    with pytest.raises(ValueError, match="key=value"):
        ac.Contender.parse("musicgen:oops")
    with pytest.raises(ValueError, match="unique"):
        ac.parse_contenders("musicgen,musicgen")


def test_prompts_from_a_file_resolve_melody_paths_and_get_ids(tmp_path):
    (tmp_path / "p.json").write_text(
        json.dumps([{"text": "a", "melody": "m.wav"}, {"text": "b"}])
    )
    prompts = ac.load_prompts(tmp_path / "p.json")
    assert [p["id"] for p in prompts] == ["p0", "p1"]
    assert prompts[0]["melody"] == str((tmp_path / "m.wav").resolve())
    with pytest.raises(ValueError, match="text"):
        ac.load_prompts([{"id": "x"}])


def test_key_agreement_knows_relative_keys():
    assert ac.key_agreement("A minor", "C major") == "relative"
    assert ac.key_agreement("C major", "A minor") == "relative"
    assert ac.key_agreement("Eb major", "D# major") == "exact"
    assert ac.key_agreement("G major", "C major") == "other"
    assert ac.key_agreement("weird", "C major") is None


def test_the_command_prints_a_summary_and_writes_records_and_page(
    fakes, tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(ac, "in_child_process", ac.in_this_process)
    (tmp_path / "prompts.json").write_text(json.dumps(PROMPTS))

    code = main(
        [
            "compare",
            "fake_clicks",
            "--prompts",
            str(tmp_path / "prompts.json"),
            "--duration",
            "3",
            "--out-dir",
            str(tmp_path / "out"),
        ]
    )

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.splitlines()[0].startswith("contender")
    assert "fake_clicks fast" in captured.err  # one progress line per take
    assert (tmp_path / "out" / "results.jsonl").is_file()
    assert len(list((tmp_path / "out").glob("*/index.html"))) == 1


def test_the_command_fails_when_every_take_failed(fakes, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ac, "in_child_process", ac.in_this_process)
    code = main(["compare", "fake_broken", "--out-dir", str(tmp_path)])
    assert code == 1 and "every take failed" in capsys.readouterr().err


def test_the_command_refuses_hosted_platforms_in_one_line(fakes, capsys):
    code = main(["compare", "fake_hosted"])
    err = capsys.readouterr().err
    assert code == 1 and "--allow-hosted" in err and "Traceback" not in err


def test_the_sampler_keeps_a_live_child_lifetime_peak():
    # the child allocated 200 MB and freed it before we look: only its lifetime peak shows it
    # the floor (RUSAGE_CHILDREN) misses Metal memory on macOS, so the live reading must work
    import subprocess
    import time

    from arioso._measure import PeakSampler, peak_memory

    if peak_memory() is None:
        pytest.skip("no memory probe on this platform")
    code = (
        "b = bytearray(200 * 2**20); b[::4096] = b'x' * len(b[::4096]); del b; "
        "print('ready', flush=True); import time; time.sleep(5)"
    )
    child = subprocess.Popen(
        [sys.executable, "-c", code], stdout=subprocess.PIPE, text=True
    )
    try:
        assert child.stdout.readline().strip() == "ready"
        sampler = PeakSampler()
        sampler.sample()  # while the child is alive, before anyone waits for it
        assert sampler.peak_descendants >= 0.15 * 2**30
        assert sampler.errors == []
    finally:
        child.kill()
        child.wait()


def _hold(mb, seconds, *, child=False):
    """Python code holding ``mb`` MB for ``seconds`` (in a child process of its own if asked)."""
    code = (
        f"b = bytearray({mb} * 2**20); b[::4096] = b'x' * len(b[::4096]); "
        f"import time; time.sleep({seconds})"
    )
    if child:
        code = (
            f"import subprocess, sys; subprocess.run([sys.executable, '-c', {code!r}])"
        )
    return [sys.executable, "-c", code]


def test_the_sampler_does_not_add_up_peaks_that_never_coincided(monkeypatch):
    # A peaks at 200 MB and frees it; B takes 200 MB while A is still alive. Never more
    # than ~200 MB at once, though their lifetime peaks add up to 400.
    import subprocess
    import time

    from arioso import _measure

    if _measure.peak_memory() is None:
        pytest.skip("no memory probe on this platform")
    monkeypatch.setattr(_measure, "_children_maxrss", lambda: 0)
    first = [
        sys.executable,
        "-c",
        "b = bytearray(200 * 2**20); b[::4096] = b'x' * len(b[::4096]); del b; "
        "import time; time.sleep(1.5)",
    ]
    with _measure.PeakSampler(interval=0.05) as sampler:
        a = subprocess.Popen(first)
        time.sleep(0.5)
        subprocess.run(_hold(200, 0.6), check=True)
        a.wait()
    assert 0.15 * 2**30 <= sampler.peak_descendants < 0.35 * 2**30


def test_the_sampler_sees_grandchildren(monkeypatch):
    import subprocess

    from arioso import _measure

    if _measure.peak_memory() is None:
        pytest.skip("no memory probe on this platform")
    monkeypatch.setattr(_measure, "_children_maxrss", lambda: 0)
    with _measure.PeakSampler(interval=0.05) as sampler:
        subprocess.run(_hold(200, 0.6, child=True), check=True)
    assert sampler.peak_descendants >= 0.15 * 2**30


def test_a_sampling_error_is_kept_not_raised(monkeypatch):
    from arioso import _measure

    def broken(pid=None):
        raise OSError("no /proc today")

    monkeypatch.setattr(_measure, "descendants", broken)
    with _measure.PeakSampler(interval=0.01) as sampler:
        pass
    assert sampler.errors and "no /proc today" in sampler.errors[0]
