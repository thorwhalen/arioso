"""Compare platforms on the same prompts: time, memory and objective checks, as records.

Choosing a local model is a measurement. :func:`compare` renders every prompt with every
contender and yields one flat record per take: wall time (model load plus warm-up, then per
take), real-time factor, peak memory, and objective checks of the audio (detected tempo
against the BPM asked for, estimated key against the key asked for, clipping, level)::

    import arioso.compare as ac

    records = list(ac.compare(["stable_audio_3", "magenta_rt", "ace_step:runtime=local"]))
    ac.compare_page(records, "arioso_compare/index.html")

or, from the shell::

    arioso compare stable_audio_3,magenta_rt,ace_step:runtime=local --prompts prompts.json

The records are the single source of truth: they are appended to ``<out_dir>/results.jsonl``
as they come, the command prints a summary of them, and :func:`compare_page` renders them as a
page of players. Each contender runs in a fresh child process (see :func:`in_child_process`),
one after the other, so only one model is in memory at a time and each one's peak memory is
its own.

A **contender** is a platform plus the options it is called with, written
``platform[:key=value[:key=value...]]`` (values are read as JSON when they parse, so
``num_steps=8`` is an int): ``ace_step:runtime=local``, ``musicgen:model=facebook/musicgen-small``.

A **prompt** is a dict: ``text`` (required), ``id``, and optionally ``bpm``, ``key`` (``"C
major"``), ``melody`` (an audio file, passed to platforms that take a melody) and
``duration``. :data:`DFLT_PROMPTS` is a small set covering a groove, an accompaniment and a
loop.

Hosted platforms cost money per call, so :func:`compare` refuses them unless
``allow_hosted=True`` (:func:`is_hosted` says which those are).

Seams, all keyword arguments: ``runner`` (how one contender is run and measured:
:func:`in_child_process` or :func:`in_this_process`), ``scorer`` (audio to a dict of checks:
:func:`objective_checks`), and ``min_free_gb`` (refuse to start a contender when the machine
has less memory available than that).
"""

from __future__ import annotations

import html
import json
import os
import platform as _platform
import re
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

#: Prompts covering three common asks: a groove at a tempo, an accompaniment in a key, a loop.
DFLT_PROMPTS = (
    {
        "id": "groove100",
        "text": "funky drum and bass groove at 100 BPM, tight hi-hats, punchy kick, "
        "warm electric bass, steady pocket, instrumental",
        "bpm": 100,
    },
    {
        "id": "accomp",
        "text": "gentle acoustic guitar and soft piano accompaniment, 100 BPM, C major, "
        "warm and simple, instrumental",
        "bpm": 100,
        "key": "C major",
    },
    {
        "id": "loop85",
        "text": "4-bar lo-fi hip hop loop, 85 BPM, mellow Rhodes chords, dusty drums, "
        "vinyl crackle, seamless loop, instrumental",
        "bpm": 85,
    },
)
DFLT_OUT_DIR = "arioso_compare"
DFLT_DURATION = 10.0
#: Seconds of audio generated once before the timed takes, so load is not counted in them.
DFLT_WARMUP = 2.0
RESULTS_FILE = "results.jsonl"
#: The ``access_type`` values of platforms that run on this machine.
LOCAL_ACCESS_TYPES = frozenset({"python_lib", "local_runtime"})
_GB = 1e9  # GB, not GiB


# --------------------------------------------------------------------------------------------
# Contenders and prompts


@dataclass(frozen=True)
class Contender:
    """A platform and the options it is called with; ``label`` names it in records."""

    platform: str
    options: Mapping[str, Any] = field(default_factory=dict)
    label: str = ""

    def __post_init__(self):
        if not self.label:
            opts = ":".join(f"{k}={v}" for k, v in self.options.items())
            object.__setattr__(
                self, "label", f"{self.platform}:{opts}" if opts else self.platform
            )

    @classmethod
    def parse(cls, spec: "str | Contender") -> "Contender":
        """``"ace_step:runtime=local:num_steps=8"`` -> ``Contender("ace_step", {...})``.

        >>> Contender.parse("ace_step:runtime=local:num_steps=8").options
        {'runtime': 'local', 'num_steps': 8}
        """
        if isinstance(spec, Contender):
            return spec
        name, *pairs = spec.strip().split(":")
        options = {}
        for pair in pairs:
            key, sep, value = pair.partition("=")
            if not sep or not key:
                raise ValueError(
                    f"Contender {spec!r}: options are written key=value, got {pair!r}"
                )
            try:
                options[key] = json.loads(value)
            except json.JSONDecodeError:
                options[key] = value
        return cls(name, options, label=spec.strip())


def parse_contenders(specs: "str | Iterable[str | Contender]") -> list[Contender]:
    """Contenders from a comma-separated string or an iterable of specs."""
    if isinstance(specs, str):
        specs = [s for s in specs.split(",") if s.strip()]
    contenders = [Contender.parse(s) for s in specs]
    labels = [c.label for c in contenders]
    if len(set(labels)) != len(labels):
        raise ValueError(f"Contender labels must be unique, got {labels}")
    _check_unique_slugs(labels, "Contender labels")
    return contenders


def _check_unique_slugs(names, what):
    """Names become folder and file names: two that map to one would overwrite each other."""
    slugs = [_slug(n) for n in names]
    if len(set(slugs)) != len(slugs):
        raise ValueError(f"{what} {list(names)} collide as file names {slugs}")


def load_prompts(source=None) -> list[dict]:
    """Prompts from a JSON file (a list of dicts), a list, or :data:`DFLT_PROMPTS`.

    A ``melody`` path in a file is read relative to that file. Prompts without an ``id``
    get ``p0``, ``p1``...
    """
    if source is None:
        prompts, base = [dict(p) for p in DFLT_PROMPTS], None
    elif isinstance(source, (str, os.PathLike)):
        path = Path(source)
        prompts, base = json.loads(path.read_text()), path.parent
    else:
        prompts, base = [dict(p) for p in source], None
    out = []
    for i, p in enumerate(prompts):
        if not p.get("text"):
            raise ValueError(f"Prompt {i} has no 'text': {p}")
        p = dict(p, id=str(p.get("id") or f"p{i}"))
        if p.get("melody") and base is not None:
            p["melody"] = str((base / p["melody"]).resolve())
        out.append(p)
    ids = [p["id"] for p in out]
    if len(set(ids)) != len(ids):
        raise ValueError(f"Prompt ids must be unique, got {ids}")
    _check_unique_slugs(ids, "Prompt ids")
    return out


def is_hosted(contender: "str | Contender") -> bool:
    """Whether a contender may call a hosted (paid, per call) service rather than a local model.

    Errs on the side of caution. Local means: ``access_type`` is ``python_lib`` or
    ``local_runtime`` (a missing one is the translation layer's ``rest_api``), the terms are
    not the provider's, no credential is taken (even an optional one: ``yue`` calls fal.ai
    whenever ``FAL_KEY`` is set), and no fal model is declared. Anything else is hosted,
    unless the contender asks for ``runtime="local"`` *and* the platform declares a local
    runtime (``ace_step``); on any other platform that option is ignored, so it changes
    nothing here either.

    >>> is_hosted("elevenlabs"), is_hosted("stable_audio_3"), is_hosted("ace_step:runtime=local")
    (True, False, False)
    >>> is_hosted("elevenlabs:runtime=local")
    True
    """
    from arioso.registry import get_config

    c = Contender.parse(contender)
    config = get_config(c.platform)
    if c.options.get("runtime") == "local" and config.get("runtime"):
        return False
    return not (
        config.get("access_type") in LOCAL_ACCESS_TYPES
        and config.get("commercial_use") != "provider terms"
        and (config.get("auth") or {}).get("type", "none") == "none"
        and not config.get("fal")
    )


# --------------------------------------------------------------------------------------------
# Running one contender


def _supported(platform: str) -> set:
    from arioso.registry import get_config

    return set(get_config(platform).get("supported_affordances") or ())


def _slug(label: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", label).strip("_") or "contender"


def _generate(contender: Contender, prompt: dict, *, duration, seed):
    """One take as ``(array, sample_rate, used)``; ``used`` says which asks were passed on."""
    import arioso

    supported = _supported(contender.platform)
    kwargs = dict(contender.options)
    used = {}
    asks = {
        "duration": prompt.get("duration", duration),
        "seed": seed,
        "melody": prompt.get("melody"),
    }
    for name, value in asks.items():
        if value is not None and name in supported and name not in kwargs:
            kwargs[name] = value
        used[f"{name}_used"] = name in kwargs
    song = arioso.generate(prompt["text"], platform=contender.platform, **kwargs)
    if song.is_error:
        raise RuntimeError(
            song.error_message or f"{contender.platform} returned an error"
        )
    if song.audio_array is None:
        raise RuntimeError(
            f"{contender.platform} returned no waveform (status {song.status!r})"
        )
    return song.audio_array, song.sample_rate, used


def in_this_process(
    contender: Contender,
    prompts: list[dict],
    *,
    duration: float,
    seed: Optional[int],
    out_dir: Path,
    warmup: Optional[float],
    on_record: Optional[Callable[[dict], None]] = None,
) -> list[dict]:
    """Run ``contender`` on ``prompts`` here; one record per prompt, audio under ``out_dir``.

    A take that fails becomes a record with an ``error`` (the others still run); a contender
    that fails its warm-up makes every record an error. ``peak_memory_gb`` is this process's
    lifetime peak, so run each contender in a fresh process (:func:`in_child_process`) to
    attribute it; ``workers_peak_memory_gb`` is the peak of the processes it started (a local
    runtime's worker, or one process per take), sampled while it ran (see
    :class:`~arioso._measure.PeakSampler`; here its exit-time floor also covers children of
    earlier contenders run in this process). ``on_record`` is called with each take's record
    as soon as it is made, before the memory figures are added at the end.
    """
    from arioso._measure import PeakSampler

    out_dir = Path(out_dir) / _slug(contender.label)
    out_dir.mkdir(parents=True, exist_ok=True)
    load_s, load_error = None, None
    with PeakSampler() as sampler:
        if warmup:
            t = time.perf_counter()
            try:
                _generate(
                    contender,
                    dict(prompts[0], duration=warmup),
                    duration=warmup,
                    seed=seed,
                )
            except Exception as error:  # noqa: BLE001 - recorded, not raised
                load_error = f"{type(error).__name__}: {error}"
            load_s = round(time.perf_counter() - t, 2)
        records = []
        for p in prompts:
            rec = _take(
                contender,
                p,
                duration=duration,
                seed=seed,
                out_dir=out_dir,
                load_error=load_error,
            )
            records.append(rec)
            if on_record is not None:
                on_record(rec)
    for rec in records:
        rec.update(
            load_s=load_s,
            peak_memory_gb=_gb(sampler.peak_self),
            workers_peak_memory_gb=_gb(sampler.peak_descendants),
        )
    return records


def _gb(n: Optional[int]) -> Optional[float]:
    return round(n / _GB, 2) if n else None


def _take(contender, prompt, *, duration, seed, out_dir: Path, load_error) -> dict:
    """One prompt's record: the take written to ``out_dir`` and timed, or an ``error``."""
    from arioso._audio import _channels_first

    rec = {
        "prompt": prompt["id"],
        "seconds_requested": prompt.get("duration", duration),
    }
    if load_error:
        return dict(rec, error=f"warm-up failed: {load_error}")
    t = time.perf_counter()
    try:
        audio, sr, used = _generate(contender, prompt, duration=duration, seed=seed)
    except Exception as error:  # noqa: BLE001 - recorded, not raised
        return dict(
            rec,
            error=f"{type(error).__name__}: {error}",
            gen_s=round(time.perf_counter() - t, 2),
        )
    gen_s = time.perf_counter() - t
    try:
        audio = _channels_first(_drop_batch_axes(audio))
        path = _write_take(audio, sr, out_dir / f"{_slug(prompt['id'])}.wav")
    except Exception as error:  # noqa: BLE001
        return dict(rec, error=f"writing the take: {type(error).__name__}: {error}")
    seconds_out = audio.shape[1] / sr if sr else None
    return dict(
        rec,
        **used,
        seconds_out=round(seconds_out, 2) if seconds_out else None,
        sample_rate=sr,
        gen_s=round(gen_s, 2),
        rtf=round(gen_s / seconds_out, 3) if seconds_out else None,
        path=str(path),
    )


def _drop_batch_axes(audio):
    """``audio`` without leading axes of size 1 (``(1, channels, frames)`` from some models)."""
    import numpy as np

    audio = np.asarray(audio)
    while audio.ndim > 2 and audio.shape[0] == 1:
        audio = audio[0]
    return audio


def _write_take(audio, sr: int, path: Path) -> Path:
    """Write a take as float WAV, so the checks see peaks above full scale (soundfile).

    Without soundfile, :func:`arioso._audio.write_wav` writes 16-bit PCM, which clamps them.
    """
    from arioso._audio import _channels_first, write_wav

    try:
        import soundfile
    except ImportError:
        return Path(write_wav(audio, sr, path))
    soundfile.write(str(path), _channels_first(audio).T, int(sr), subtype="FLOAT")
    return path


def in_child_process(
    contender: Contender,
    prompts: list[dict],
    *,
    duration: float,
    seed: Optional[int],
    out_dir: Path,
    warmup: Optional[float],
    python: Optional[str] = None,
    preload: Iterable[str] = (),
    timeout: Optional[float] = None,
) -> list[dict]:
    """Run ``contender`` in a fresh ``python -m arioso.compare`` process (the default runner).

    A fresh process per contender frees the previous model's memory before the next loads,
    and makes the process's lifetime peak memory that contender's own. ``python`` is the
    interpreter (default: this one); ``preload`` names what the child runs first, to make
    third-party platforms known: ``"module"`` is imported, ``"module:function"`` is imported
    and ``function()`` called. The child's output goes to ``<out_dir>/<contender>/child.log``.
    The child writes each take's record as soon as it is made, so a child killed after
    ``timeout`` seconds (with every process it started) or exiting non-zero still returns
    the takes it finished, each marked with ``child_exit``; prompts it never reached get an
    ``error``. Processes the child started are killed when it ends, however it ends; on
    Windows only when it is killed (thorwhalen/ps#25).
    """
    log_path = Path(out_dir) / _slug(contender.label) / "child.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    job = {
        "contender": {
            "platform": contender.platform,
            "options": dict(contender.options),
            "label": contender.label,
        },
        "prompts": prompts,
        "duration": duration,
        "seed": seed,
        "out_dir": str(out_dir),
        "warmup": warmup,
        "preload": list(preload),
    }
    with tempfile.TemporaryDirectory(prefix="arioso_compare_") as tmp:
        job_path, out_path = Path(tmp) / "job.json", Path(tmp) / "records.jsonl"
        job_path.write_text(json.dumps(job))
        cmd = [
            python or sys.executable,
            "-m",
            "arioso.compare",
            str(job_path),
            str(out_path),
        ]
        with open(log_path, "w") as log:
            code = _run_child(cmd, log, timeout=timeout)
        lines = out_path.read_text().splitlines() if out_path.exists() else []
    records = {}  # the last line per prompt wins: the final one carries the memory figures
    for line in lines:
        if line.strip():
            rec = json.loads(line)
            records[rec["prompt"]] = rec
    tail = " | ".join(log_path.read_text().strip().splitlines()[-15:])
    error = f"child process failed (exit {code}; log {log_path}): {tail}"
    return [
        (dict(records[p["id"]], child_exit=code) if code else records[p["id"]])
        if p["id"] in records
        else {"prompt": p["id"], "error": error}
        for p in prompts
    ]


def _run_child(cmd, log, *, timeout) -> "int | str":
    """Run ``cmd`` with its output to ``log``; kill everything it started once it ends.

    Runtime workers start in sessions of their own (ps.isolated) and hold gigabytes, so
    they must not outlive the child, however it ends: on timeout, by a crash that skips
    its cleanup, or between the timeout and the kill. :func:`ps.util.wait_and_reap`
    watches the tree while waiting and kills what is left (``taskkill /T`` on Windows,
    on timeout only).
    """
    from ps.util import NEW_PROCESS_GROUP, kill_process_tree, wait_and_reap

    proc = subprocess.Popen(
        cmd, stdout=log, stderr=subprocess.STDOUT, **NEW_PROCESS_GROUP
    )
    try:
        return wait_and_reap(proc, timeout=timeout)
    except subprocess.TimeoutExpired:
        return f"killed after {timeout} s"
    except BaseException:  # a bad timeout, say: refused before any wait, child running
        kill_process_tree(proc)
        proc.wait()
        raise


def _run_preload(specs: Iterable[str]) -> None:
    """Import each ``"module"``; for ``"module:function"`` also call ``function()``."""
    import importlib

    for spec in specs:
        module, _, function = spec.partition(":")
        loaded = importlib.import_module(module)
        if function:
            getattr(loaded, function)()


def _child_main(job_path: str, out_path: str) -> None:
    job = json.loads(Path(job_path).read_text())
    _run_preload(job.get("preload", ()))
    out = Path(out_path)

    def append(record):
        with open(out, "a") as f:
            f.write(json.dumps(record) + "\n")

    c = job["contender"]
    records = in_this_process(
        Contender(c["platform"], c["options"], label=c["label"]),
        job["prompts"],
        duration=job["duration"],
        seed=job["seed"],
        out_dir=Path(job["out_dir"]),
        warmup=job["warmup"],
        on_record=append,
    )
    for record in records:  # again, now with the memory figures
        append(record)


# --------------------------------------------------------------------------------------------
# Objective checks


def _key_parts(name: str) -> Optional[tuple[int, str]]:
    """``"C# minor"`` -> ``(1, "minor")``; ``None`` when it does not parse."""
    from arioso.analysis import pitch_class

    m = re.match(
        r"\s*([A-Ga-gH][#b]?)\s*(major|minor|maj|min|m)?\s*$", name or "", re.I
    )
    if not m:
        return None
    mode = (m.group(2) or "major").lower()
    mode = "minor" if mode in ("minor", "min", "m") else "major"
    try:
        return pitch_class(m.group(1).capitalize()), mode
    except (KeyError, ValueError):
        return None


def key_agreement(detected: str, asked: str) -> Optional[str]:
    """``"exact"``, ``"relative"`` (C major vs A minor), ``"other"``, or ``None`` if unparsable.

    >>> key_agreement("A minor", "C major"), key_agreement("c major", "C Major")
    ('relative', 'exact')
    """
    d, a = _key_parts(detected), _key_parts(asked)
    if d is None or a is None:
        return None
    if d == a:
        return "exact"
    major, minor = (a, d) if a[1] == "major" else (d, a)
    if major[1] == "major" and minor[1] == "minor" and (major[0] - 3) % 12 == minor[0]:
        return "relative"
    return "other"


def tempo_error(detected: Optional[float], asked: Optional[float]) -> Optional[float]:
    """Relative tempo error, forgiving the half/double-time slips beat trackers make.

    >>> tempo_error(50, 100), tempo_error(110, 100)
    (0.0, 0.1)
    """
    if not detected or not asked:
        return None
    return round(min(abs(detected * f - asked) / asked for f in (0.5, 1, 2)), 3)


def objective_checks(y, sr: int, prompt: Mapping) -> dict:
    """Checks a listener would otherwise make by ear: level, clipping, tempo, key.

    Level and clipping need numpy only. Tempo comes from ``denote.get_beats`` and key from
    ``denote.get_key`` when ``denote`` provides them; a check that cannot run goes into
    ``checks_skipped`` (check name to reason) instead of failing the take.
    """
    import numpy as np

    from arioso._audio import _channels_first

    y = _channels_first(y).mean(axis=0)  # mono, whichever way round the channels come
    rms = float(np.sqrt(np.mean(y**2))) if y.size else 0.0
    out = {
        "peak_abs": round(float(np.max(np.abs(y))), 3) if y.size else 0.0,
        "clip_frac": round(float(np.mean(np.abs(y) >= 0.999)), 4) if y.size else 0.0,
        "rms_dbfs": round(float(20 * np.log10(rms + 1e-12)), 1),
    }
    skipped = {}
    try:
        import denote
    except ImportError:
        reason = "denote is not installed"
        return dict(out, checks_skipped={"tempo": reason, "key": reason})
    try:
        beats = denote.get_beats(y, sr=sr)
        tempo = (
            float(np.atleast_1d(beats.tempo)[0]) if beats.tempo is not None else None
        )
        ibi = np.diff(np.asarray(beats.beats, dtype=float))
        out.update(
            tempo_detected=round(tempo, 1) if tempo else None,
            tempo_err=tempo_error(tempo, prompt.get("bpm")),
            beat_cv=round(float(ibi.std() / ibi.mean()), 3) if len(ibi) > 2 else None,
        )
    except Exception as error:  # noqa: BLE001 - recorded with its reason
        skipped["tempo"] = f"{type(error).__name__}: {error}"
    get_key = getattr(denote, "get_key", None)
    if get_key is None:
        skipped["key"] = "this denote has no get_key (denote>=0.0.10 has)"
    else:
        try:
            result = get_key(y, sr=sr)
            out.update(
                key=result.key,
                key_confidence=_round(getattr(result, "confidence", None)),
            )
            if prompt.get("key"):
                out["key_agreement"] = key_agreement(result.key, prompt["key"])
        except Exception as error:  # noqa: BLE001 - e.g. a take too quiet for a key
            skipped["key"] = f"{type(error).__name__}: {error}"
    if skipped:
        out["checks_skipped"] = skipped
    return out


def _round(x, n=3):
    return round(float(x), n) if x is not None else None


def _read_take(path) -> tuple[Any, int]:
    """A take written by :func:`_write_take`: ``(frames,)`` or ``(frames, channels)`` float32, rate."""
    try:
        import soundfile
    except ImportError:
        import wave

        import numpy as np

        with wave.open(str(path)) as w:
            sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
            pcm = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float32) / 32768
        return (pcm.reshape(-1, ch) if ch > 1 else pcm), sr
    y, sr = soundfile.read(str(path), dtype="float32")
    return y, sr


# --------------------------------------------------------------------------------------------
# The comparison


def compare(
    contenders: "str | Iterable[str | Contender]",
    prompts=None,
    *,
    duration: float = DFLT_DURATION,
    seed: Optional[int] = 0,
    out_dir: "str | os.PathLike" = DFLT_OUT_DIR,
    warmup: Optional[float] = DFLT_WARMUP,
    runner: Optional[Callable[..., list[dict]]] = None,
    scorer: Optional[Callable[[Any, int, Mapping], dict]] = objective_checks,
    allow_hosted: bool = False,
    min_free_gb: Optional[float] = None,
    preload: Iterable[str] = (),
    timeout: Optional[float] = None,
    run_id: Optional[str] = None,
) -> Iterator[dict]:
    """Render every prompt with every contender; yield one record per take.

    Args:
        contenders: Platform specs (``"ace_step:runtime=local"``, see :class:`Contender`),
            comma-separated or as an iterable.
        prompts: A JSON file, a list of prompt dicts, or ``None`` for :data:`DFLT_PROMPTS`.
        duration: Seconds asked of each take (a prompt's own ``duration`` wins).
        seed: Passed to platforms that take one (``None``: don't).
        out_dir: Takes go to ``<out_dir>/<run_id>/<contender>/<prompt id>.wav``; records
            are appended to ``<out_dir>/results.jsonl`` (one file for every run).
        warmup: Seconds generated once per contender before the timed takes (``0``/``None``:
            no warm-up, so the first take's time includes loading the model).
        runner: Runs one contender: :func:`in_child_process` (``None``, the default) or
            :func:`in_this_process`, or any callable with their signature.
        scorer: ``(audio, sample_rate, prompt) -> dict`` merged into each record; ``None``
            for no checks.
        allow_hosted: Allow contenders that call paid hosted services (:func:`is_hosted`).
        min_free_gb: When the machine has less memory available than this before a
            contender starts, record that contender as an error instead of running it.
        preload: Modules (``"module"`` or ``"module:function"``) that make third-party
            platforms known, run here before anything is checked and passed to a runner
            that takes ``preload`` (the child process runs them too).
        timeout: Seconds a contender may run before it is killed with every process it
            started, passed to a runner that takes ``timeout`` (the default one does).
        run_id: Names this run in its records and its folder (default: the start time).

    Yields:
        Flat dicts: ``contender``, ``platform``, ``options``, ``prompt``, timings
        (``load_s``, ``gen_s``, ``rtf``), memory (``peak_memory_gb``,
        ``workers_peak_memory_gb``, ``available_memory_gb``), ``path``, the scorer's
        checks, ``error`` when a take failed, and the machine.
    """
    import inspect

    from arioso._measure import available_memory
    from arioso.registry import get_config

    preload = list(preload)
    _run_preload(preload)
    contenders = parse_contenders(contenders)
    prompts = load_prompts(prompts)
    unknown = []
    for c in contenders:  # fail before anything runs
        try:
            get_config(c.platform)
        except KeyError:
            unknown.append(c.platform)
    if unknown:
        raise ValueError(
            f"Unknown platforms {unknown}. See `arioso platforms` for the list."
        )
    hosted = [c.label for c in contenders if is_hosted(c)]
    if hosted and not allow_hosted:
        raise ValueError(
            f"Hosted (paid, per call) contenders: {hosted}. Pass allow_hosted=True "
            "(--allow-hosted) to compare them anyway."
        )
    runner = runner or in_child_process
    try:
        accepted = inspect.signature(runner).parameters
    except (TypeError, ValueError):
        accepted = {}
    given = {"preload": preload or None, "timeout": timeout}
    runner_kwargs = {k: v for k, v in given.items() if v is not None and k in accepted}
    out_dir = Path(out_dir)
    run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
    run_dir = out_dir / _slug(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    machine = {"machine": _platform.machine(), "system": _platform.system()}
    for c in contenders:
        avail = available_memory()
        avail_gb = round(avail / _GB, 1) if avail else None
        process_s = None
        if min_free_gb is not None and avail_gb is not None and avail_gb < min_free_gb:
            error = f"skipped: {avail_gb} GB available, under min_free_gb={min_free_gb}"
            records = [{"prompt": p["id"], "error": error} for p in prompts]
        else:
            t = time.perf_counter()
            records = runner(
                c,
                prompts,
                duration=duration,
                seed=seed,
                out_dir=run_dir,
                warmup=warmup,
                **runner_kwargs,
            )
            process_s = round(time.perf_counter() - t, 1)
        config = get_config(c.platform)
        for rec in records:
            rec = {
                "run_id": run_id,
                "contender": c.label,
                "platform": c.platform,
                "options": dict(c.options),
                **rec,
                "available_memory_gb": avail_gb,
                "weights_license": config.get("weights_license"),
                "commercial_use": config.get("commercial_use"),
                **machine,
                "when": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            if process_s is not None:
                rec["process_s"] = process_s
            if scorer is not None and rec.get("path") and "error" not in rec:
                prompt = next(p for p in prompts if p["id"] == rec["prompt"])
                try:
                    y, sr = _read_take(rec["path"])
                    rec.update(scorer(y, sr, prompt))
                except Exception as error:  # noqa: BLE001
                    rec["score_error"] = f"{type(error).__name__}: {error}"
            with open(out_dir / RESULTS_FILE, "a") as f:
                f.write(json.dumps(rec) + "\n")
            yield rec


def read_records(out_dir: "str | os.PathLike" = DFLT_OUT_DIR) -> list[dict]:
    """The records in ``<out_dir>/results.jsonl``, keeping the latest per (contender, prompt)."""
    latest = {}
    path = Path(out_dir) / RESULTS_FILE
    for line in path.read_text().splitlines() if path.exists() else ():
        if line.strip():
            r = json.loads(line)
            latest[(r.get("contender"), r.get("prompt"))] = r
    return list(latest.values())


# --------------------------------------------------------------------------------------------
# Summaries


def summarize(records: Iterable[Mapping]) -> list[dict]:
    """One row per contender: takes, failures, median RTF, load, peak memory, check rates."""

    def median(xs):
        xs = [x for x in xs if x is not None]
        return round(statistics.median(xs), 3) if xs else None

    rows = {}
    for r in records:
        rows.setdefault(r["contender"], []).append(r)
    out = []
    for label, rs in rows.items():
        ok = [r for r in rs if "error" not in r]
        keyed = [r["key_agreement"] for r in ok if r.get("key_agreement")]
        out.append(
            {
                "contender": label,
                "takes": len(ok),
                "failed": len(rs) - len(ok),
                "rtf": median(r.get("rtf") for r in ok),
                "load_s": median(r.get("load_s") for r in ok),
                "peak_memory_gb": max(
                    (
                        (r.get("peak_memory_gb") or 0)
                        + (r.get("workers_peak_memory_gb") or 0)
                        for r in ok
                    ),
                    default=None,
                )
                or None,
                "tempo_err": median(r.get("tempo_err") for r in ok),
                "key_hits": f"{keyed.count('exact')}/{len(keyed)}" if keyed else None,
                "weights_license": rs[0].get("weights_license"),
                "first_error": next((r["error"] for r in rs if "error" in r), None),
            }
        )
    return out


def summary_lines(records: Iterable[Mapping]) -> list[str]:
    """:func:`summarize` as aligned text lines, a header first."""
    fields = (
        "contender",
        "takes",
        "failed",
        "rtf",
        "load_s",
        "peak_memory_gb",
        "tempo_err",
        "key_hits",
    )
    rows = summarize(records)
    table = [fields] + [
        tuple("-" if r[f] is None else str(r[f]) for f in fields) for r in rows
    ]
    widths = [max(len(row[i]) for row in table) for i in range(len(fields))]
    lines = [
        "  ".join(c.ljust(w) for c, w in zip(row, widths)).rstrip() for row in table
    ]
    lines += [f"{r['contender']}: {r['first_error']}" for r in rows if r["first_error"]]
    return lines


def compare_page(
    records: Iterable[Mapping],
    path: "str | os.PathLike" = Path(DFLT_OUT_DIR) / "index.html",
    *,
    title: str = "Music generation compared",
    prompts: Optional[Iterable[Mapping]] = None,
) -> Path:
    """Write a self-contained HTML page: a summary table, then each prompt's takes as players.

    Audio is linked relative to the page, so keep the page beside the takes (the default
    ``<out_dir>/index.html``) and publish the folder.
    """
    records = list(records)
    path = Path(path)
    esc = html.escape
    texts = {p["id"]: p.get("text", "") for p in (prompts or ())}

    def cell(v):
        return "-" if v is None else esc(str(v))

    summary = "".join(
        "<tr>" + "".join(f"<td>{cell(r[f])}</td>" for f in _PAGE_FIELDS) + "</tr>"
        for r in summarize(records)
    )
    by_prompt = {}
    for r in records:
        by_prompt.setdefault(r["prompt"], []).append(r)
    sections = []
    for pid, rs in by_prompt.items():
        takes = []
        for r in rs:
            if "error" in r:
                body = f"<div class=err>{esc(r['error'][:300])}</div>"
            else:
                src = os.path.relpath(r["path"], path.parent) if r.get("path") else ""
                chips = [
                    f"{r.get('gen_s')}s for {r.get('seconds_out')}s (RTF {r.get('rtf')})"
                ]
                if r.get("tempo_detected"):
                    chips.append(
                        f"tempo {r['tempo_detected']}"
                        + (
                            f", err {r['tempo_err']}"
                            if r.get("tempo_err") is not None
                            else ""
                        )
                    )
                if r.get("key"):
                    chips.append(
                        f"key {r['key']}"
                        + (f" ({r['key_agreement']})" if r.get("key_agreement") else "")
                    )
                if r.get("clip_frac"):
                    chips.append(f"clipped {100 * r['clip_frac']:.2f}%")
                body = (
                    f"<audio controls preload=none src='{esc(Path(src).as_posix())}'></audio>"
                    f"<div class=chips>{' · '.join(esc(c) for c in chips)}</div>"
                )
            takes.append(
                f"<div class=take><div class=who>{esc(r['contender'])}</div>{body}</div>"
            )
        text = texts.get(pid, "")
        sections.append(
            f"<section><h2>{esc(pid)}</h2>"
            + (f"<p class=prompt>{esc(text)}</p>" if text else "")
            + "".join(takes)
            + "</section>"
        )
    head = "".join(f"<th>{esc(f)}</th>" for f in _PAGE_FIELDS)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _PAGE.format(
            title=esc(title),
            head=head,
            summary=summary,
            sections="".join(sections),
            when=esc(time.strftime("%Y-%m-%d %H:%M")),
        )
    )
    return path


_PAGE_FIELDS = (
    "contender",
    "takes",
    "failed",
    "rtf",
    "load_s",
    "peak_memory_gb",
    "tempo_err",
    "key_hits",
    "weights_license",
)

_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{ --bg:#fbfaf7; --fg:#1d1c1a; --muted:#6b675f; --line:#e3dfd6; --card:#fff; --err:#a33; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#141413; --fg:#ecebe6; --muted:#a29e94; --line:#2c2b28; --card:#1c1b19; --err:#e88; }} }}
:root[data-theme="dark"] {{ --bg:#141413; --fg:#ecebe6; --muted:#a29e94; --line:#2c2b28; --card:#1c1b19; --err:#e88; }}
* {{ box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--fg); font:16px/1.5 system-ui, sans-serif; margin:0 auto; padding:16px; max-width:860px; }}
h1 {{ font-size:1.4rem; }} h2 {{ font-size:1.1rem; border-bottom:1px solid var(--line); margin-top:1.5em; }}
.wrap {{ overflow-x:auto; }} table {{ border-collapse:collapse; width:100%; font-size:.85rem; }}
th, td {{ text-align:left; padding:5px 7px; border-bottom:1px solid var(--line); white-space:nowrap; }}
.prompt, .chips, small {{ color:var(--muted); }} .prompt {{ font-style:italic; }}
.take {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:10px 12px; margin:10px 0; }}
.who {{ font-weight:600; }} audio {{ width:100%; }} .chips {{ font-size:.85rem; }} .err {{ color:var(--err); font-size:.85rem; }}
</style></head><body>
<h1>{title}</h1><p><small>{when} · rtf: generation time over audio length (under 1 is faster than real time) · tempo_err: relative error against the BPM asked, half/double time forgiven · key_hits: exact key matches over the prompts that asked for a key</small></p>
<div class=wrap><table><tr>{head}</tr>{summary}</table></div>
{sections}
</body></html>
"""


if __name__ == "__main__":
    _child_main(*sys.argv[1:3])
