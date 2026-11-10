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
    assert Path(r["path"]).is_file()
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
    assert fast["tempo_err"] < 0.05 and slow["tempo_err"] < 0.05
    assert fast["clip_frac"] == 0 and -40 < fast["rms_dbfs"] < 0


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


def test_runtime_local_is_not_hosted():
    # ace_step is a hosted (fal) platform unless asked to run its local runtime
    assert ac.is_hosted("ace_step")
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
        return ac.in_child_process(*args, preload=[FAKE], **kwargs)

    records = _run("fake_clicks", tmp_path, runner=runner)

    assert [r["prompt"] for r in records] == ["fast", "slow"]
    assert fakes.CALLS == []  # it all happened in the child
    assert all(Path(r["path"]).is_file() for r in records)
    if sys.platform == "darwin" or sys.platform.startswith("linux"):
        assert records[0]["peak_memory_gb"] > 0


def test_the_peak_of_a_short_lived_process_per_take_is_caught(fakes, tmp_path):
    from arioso._measure import peak_memory

    if peak_memory() is None:
        pytest.skip("no memory probe on this platform")
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


def test_page_links_audio_relative_to_itself(fakes, tmp_path):
    records = _run("fake_clicks,fake_broken", tmp_path)
    page = ac.compare_page(records, tmp_path / "index.html", prompts=PROMPTS)
    text = page.read_text()
    assert "src='fake_clicks/fast.wav'" in text
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

    out = capsys.readouterr().out
    assert code == 0
    assert out.splitlines()[0].startswith("contender")
    assert (tmp_path / "out" / "results.jsonl").is_file()
    assert (tmp_path / "out" / "index.html").is_file()


def test_the_command_refuses_hosted_platforms_in_one_line(fakes, capsys):
    code = main(["compare", "fake_hosted"])
    err = capsys.readouterr().err
    assert code == 1 and "--allow-hosted" in err and "Traceback" not in err


def test_the_sampler_reads_a_live_child_peak_not_only_the_exit_floor():
    # the floor (RUSAGE_CHILDREN) misses Metal memory on macOS, so the live reading must work
    import subprocess
    import time

    from arioso._measure import PeakSampler, peak_memory

    if peak_memory() is None:
        pytest.skip("no memory probe on this platform")
    code = "b = bytearray(200 * 2**20); b[::4096] = b'x' * len(b[::4096]); print('ready', flush=True); import time; time.sleep(5)"
    child = subprocess.Popen(
        [sys.executable, "-c", code], stdout=subprocess.PIPE, text=True
    )
    try:
        assert child.stdout.readline().strip() == "ready"
        sampler = PeakSampler()
        sampler.sample()  # while the child is alive, before anyone waits for it
        assert sampler.peak_descendants >= 0.15 * 2**30
    finally:
        child.kill()
        child.wait()
