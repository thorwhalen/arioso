"""Foundation-1 adapter: stable-audio-tools in its own environment, one worker per adapter.

The model loads once, in a :class:`~arioso._isolated.Worker` running
``arioso/_workers/foundation_1_worker.py`` with the Python of the ``foundation-1``
environment, which :func:`~arioso._isolated.ensure_env` builds on first use (pinned
stable-audio-tools, torch 2.7). ``make_worker=`` and ``ensure_env=`` are the seams.

Foundation-1 reads a tag prompt: instrument family and sub-family, timbre, notation and FX
tags, then ``"<N> Bars, <BPM> BPM, <key>"`` (see :func:`build_prompt`). arioso's ``bpm``
and ``key`` become those tags; a loop's length follows from its bars and tempo, so with a
tempo the clip is exactly ``bars`` bars of 4/4 (``bars=`` 4 or 8, else the count nearest
to ``duration``). Without one, ``duration`` is the clip length (a one-shot or free clip).
"""

from __future__ import annotations

import os
import re
import tempfile
import warnings
from pathlib import Path

from arioso._isolated import (
    Worker,
    draw_seed,
    ensure_env,
    is_apple_silicon,
    song_from_wav,
    worker_file,
)
from arioso.platforms.foundation_1.config import PLATFORM_CONFIG

#: Beats in a bar (the loops are 4/4).
BEATS_PER_BAR = 4
#: Seconds of audio the model renders at most (its 882000-sample window at 44.1 kHz).
WINDOW_SECONDS = 20.0
#: stable-audio-tools' sampler and noise schedule used for Stable Audio Open 1.0.
DFLT_SAMPLER = "dpmpp-3m-sde"
DFLT_SIGMA_MIN = 0.3
DFLT_SIGMA_MAX = 500.0
#: Variables for the worker: MPS falls back to the CPU for an operator it lacks.
WORKER_ENV = {"PYTORCH_ENABLE_MPS_FALLBACK": "1", "TOKENIZERS_PARALLELISM": "false"}

_BARS_TAG = re.compile(r"^(\d+)\s*Bars?$", re.IGNORECASE)
_BPM_TAG = re.compile(r"^(\d+(?:\.\d+)?)\s*BPM$", re.IGNORECASE)
_KEY = re.compile(
    r"^([A-Ga-g])([#b]?)\s*(m|min|minor|maj|major)?$",
)
_KEY_LONG = re.compile(r"^([A-Ga-g])([#b]?)\s+(minor|major)$", re.IGNORECASE)
_NOTE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d)$")
_PITCH_CLASS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
#: The tag before a one-shot's pitch, and the keybeds checkpoint's single-note prefix
#: (``keybed_training_strategy.md`` in the model repository).
TARGET_NOTE_TAG = "Target Note"
KEYBED_PREFIX = ("Keybed", "Timbre Profile")
#: A one-shot's length when no duration is given (the keybed notes were trained at 3 s).
DFLT_NOTE_SECONDS = 3.0
DFLT_SECONDS = 10.0


def parse_key(key: str):
    """``(spelling, pitch_class, mode)`` of a key, or None if ``key`` is not one.

    The spelling is the tags' (``"A minor"``); the pitch class compares enharmonics.

    >>> parse_key("Am"), parse_key("f# major"), parse_key("Bell")
    (('A minor', 9, 'minor'), ('F# major', 6, 'major'), None)
    """
    text = key.strip()
    m = _KEY_LONG.match(text) or _KEY.match(text)
    if not m:
        return None
    letter, accidental, quality = m.groups()
    if not _KEY_LONG.match(text) and letter.islower() and quality is None:
        return None  # a lone lower-case letter is not a key tag
    mode = "minor" if (quality or "").lower() in ("m", "min", "minor") else "major"
    pc = (_PITCH_CLASS[letter.upper()] + {"#": 1, "b": -1, "": 0}[accidental]) % 12
    return f"{letter.upper()}{accidental} {mode}", pc, mode


def normalize_key(key: str) -> str:
    """A key as Foundation-1's tags spell it: ``"Am"`` -> ``"A minor"``, ``"f#"`` -> ``"F# major"``.

    Anything that is not a key comes back stripped, unchanged.

    >>> normalize_key("Am"), normalize_key("C# minor"), normalize_key("eb")
    ('A minor', 'C# minor', 'Eb major')
    """
    text = key.strip()
    parsed = parse_key(text) or (
        parse_key(text[0].upper() + text[1:]) if text else None
    )
    return parsed[0] if parsed else text


def normalize_note(note: str) -> str:
    """A pitch as the tags spell it (``"c#3"`` -> ``"C#3"``); a ValueError if it is not one."""
    m = _NOTE.match(note.strip())
    if not m:
        raise ValueError(
            f"foundation_1: note={note!r} is not a pitch like 'C3' or 'F#4'"
        )
    letter, accidental, octave = m.groups()
    return f"{letter.upper()}{accidental}{octave}"


def hf_hub_cache() -> Path:
    """The Hugging Face hub cache: ``$HF_HUB_CACHE``, else ``$HF_HOME/hub``, else the default."""
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"]).expanduser()
    home = os.environ.get("HF_HOME") or "~/.cache/huggingface"
    return Path(home).expanduser() / "hub"


def cached_weights(model: str = "foundation-1", *, config: dict = None):
    """The local path of ``model``'s checkpoint in the Hugging Face cache, or None if absent.

    Looks at the pinned revision only (no network, no huggingface_hub import).
    """
    config = config or PLATFORM_CONFIG
    weights = config["weights"]
    repo = "models--" + weights["repo_id"].replace("/", "--")
    path = (
        hf_hub_cache()
        / repo
        / "snapshots"
        / weights["revision"]
        / config["models"][model]
    )
    return path if path.exists() else None


def _nearest(value: float, choices) -> int:
    return min(choices, key=lambda c: (abs(c - value), c))


def build_prompt(
    prompt: str,
    *,
    bpm: float = None,
    key: str = None,
    bars: int = None,
    duration: float = None,
    note: str = None,
    keybed: bool = False,
    supported_bars=PLATFORM_CONFIG["supported_bars"],
) -> "tuple[str, float, dict]":
    """The tag prompt, the clip's seconds and the timing it used, from arioso's controls.

    Tags already in ``prompt`` are read and must agree with the arguments (``"140 BPM"``
    with ``bpm=120`` is an error; keys compare by pitch class and mode, so ``"Cb major"``
    agrees with ``"B major"``); a short key tag (``"Am"``) is spelt out. Missing tags go
    in the model card's order, ``..., 8 Bars, 140 BPM, E minor``: bars before the tempo
    (also when only the tempo was in the prompt), the key last.

    With a tempo (``bpm`` or a ``BPM`` tag) the clip is ``bars`` bars of 4/4: ``bars``,
    else a ``Bars`` tag, else the supported count nearest to ``duration * bpm / 240`` (4
    without a duration); a ``duration`` more than a bar away from that warns. Without a
    tempo the clip is ``duration`` seconds (default 10).

    ``note`` makes a one-shot at that pitch: ``"Target Note, <note>"`` is appended (no
    tempo or bars then; default length 3 s; a key goes before it; a ``Target Note`` already
    in the prompt is read like the other tags), and with ``keybed=True`` (the keybeds
    checkpoint) the prompt starts with its single-note prefix ``"Keybed, Timbre Profile"``.

    >>> build_prompt("Synth Lead, Warm, Arp", bpm=140, key="Em", duration=12)
    ('Synth Lead, Warm, Arp, 8 Bars, 140 BPM, E minor', 13.714285714285714, {'bpm': 140, 'bars': 8, 'key': 'E minor', 'note': None})
    >>> build_prompt("Grand Piano, Bright", note="c3", keybed=True)[:2]
    ('Keybed, Timbre Profile, Grand Piano, Bright, Target Note, C3', 3.0)
    """
    tags = [t.strip() for t in prompt.split(",") if t.strip()]

    def find(pattern):
        return next(
            ((i, m) for i, t in enumerate(tags) if (m := pattern.match(t))),
            (None, None),
        )

    def as_number(s):
        f = float(s)
        return int(f) if f.is_integer() else f

    def contradiction(name, given, tag):
        return ValueError(
            f"foundation_1: {name}={given!r} contradicts the prompt's {tag!r}"
        )

    bpm = None if bpm is None else as_number(bpm)
    bpm_at, bpm_tag = find(_BPM_TAG)
    if bpm_tag:
        if bpm is not None and bpm != as_number(bpm_tag.group(1)):
            raise contradiction("bpm", bpm, tags[bpm_at])
        bpm = as_number(bpm_tag.group(1))
    bars_at, bars_tag = find(_BARS_TAG)
    if bars_tag:
        if bars is not None and bars != int(bars_tag.group(1)):
            raise contradiction("bars", bars, tags[bars_at])
        bars = int(bars_tag.group(1))

    given_key = parse_key(normalize_key(key)) if key else None
    if key and given_key is None:
        raise ValueError(f"foundation_1: key={key!r} is not a key like 'A minor'")
    key_at = next((i for i, t in enumerate(tags) if parse_key(t)), None)
    if key_at is not None:
        tagged = parse_key(tags[key_at])
        if given_key and given_key[1:] != tagged[1:]:
            raise contradiction("key", key, tags[key_at])
        tags[key_at] = tagged[0]  # spelt out, as trained
        given_key = tagged
    key = given_key[0] if given_key else None

    target_at = next(
        (i for i, t in enumerate(tags) if t.lower() == TARGET_NOTE_TAG.lower()), None
    )
    if target_at is not None:  # "Target Note, <note>" in the prompt
        if target_at + 1 >= len(tags):
            raise ValueError(f"foundation_1: {TARGET_NOTE_TAG!r} with no note after it")
        tagged_note = normalize_note(tags[target_at + 1])
        if note is not None and normalize_note(note) != tagged_note:
            raise contradiction("note", note, tags[target_at + 1])
        tags[target_at + 1] = note = tagged_note

    if note is not None:
        note = normalize_note(note)
        if bpm is not None or bars is not None:
            raise ValueError("foundation_1: a note is a one-shot: no bpm or bars")
        if target_at is None:
            target_at = len(tags)
            tags += [TARGET_NOTE_TAG, note]
        if (
            key and key_at is None
        ):  # the key goes before the note, which ends the prompt
            tags.insert(target_at, key)
            key_at = target_at
        if keybed and tags[: len(KEYBED_PREFIX)] != list(KEYBED_PREFIX):
            tags = list(KEYBED_PREFIX) + tags
        seconds = DFLT_NOTE_SECONDS if duration is None else float(duration)
    elif bpm is None:
        if bars is not None:
            raise ValueError("foundation_1: bars needs a tempo (bpm=, or a BPM tag)")
        seconds = DFLT_SECONDS if duration is None else float(duration)
    else:
        bar_seconds = BEATS_PER_BAR * 60 / bpm
        if bars is None:
            wanted = 4 if duration is None else float(duration) / bar_seconds
            bars = _nearest(wanted, supported_bars)
        seconds = bars * bar_seconds
        if duration is not None and abs(float(duration) - seconds) > bar_seconds:
            warnings.warn(
                f"foundation_1: with {bpm} BPM the loop is {bars} bars = {seconds:.2f} s, "
                f"not the duration={duration} asked for",
                stacklevel=3,
            )
        if bpm_tag is None:  # after a Bars tag, else before the key, else last
            if bars_tag is not None:
                bpm_at = bars_at + 1
            else:
                bpm_at = len(tags) if key_at is None else key_at
            tags.insert(bpm_at, f"{bpm} BPM")
            if key_at is not None and key_at >= bpm_at:
                key_at += 1
        if bars_tag is None:
            tags.insert(bpm_at, f"{bars} Bars")  # just before the tempo
            if key_at is not None and key_at >= bpm_at:
                key_at += 1
    if key and key_at is None:
        tags.append(key)
    return (
        ", ".join(tags),
        seconds,
        {"bpm": bpm, "bars": bars, "key": key, "note": note},
    )


def _is_supported() -> bool:
    """torch 2.7 ships no Intel macOS wheels: on a Mac, only Apple Silicon."""
    import platform

    return platform.system() != "Darwin" or is_apple_silicon()


class Adapter:
    """Local Foundation-1 adapter (stable-audio-tools, MPS / CUDA / CPU)."""

    def __init__(
        self,
        config: dict = None,
        *,
        make_worker=Worker,
        ensure_env=ensure_env,
        is_supported=_is_supported,
    ):
        self.config = config or PLATFORM_CONFIG
        self._make_worker = make_worker
        self._ensure_env = ensure_env
        self._is_supported = is_supported
        self._worker = None
        self._device = None

    def _python(self):
        """``$ARIOSO_FOUNDATION_1_ENV``'s Python when set, else the built environment's."""
        existing = os.environ.get(self.config["env_var"])
        if existing:
            from ps.isolated import venv_python

            python = venv_python(Path(existing).expanduser())
            if not python.exists():
                raise FileNotFoundError(
                    f"${self.config['env_var']}={existing} has no Python at {python}"
                )
            return python
        return self._ensure_env(self.config["env"])

    def _ensure_worker(self, device):
        if self._worker is not None and device not in (None, self._device):
            self.close()  # another device asked for: a fresh worker
        if self._worker is None:
            if not self._is_supported():
                raise RuntimeError(
                    "foundation_1 needs Apple Silicon on macOS: torch 2.7 (pinned by "
                    "stable-audio-tools) has no Intel macOS wheels"
                )
            python = self._python()
            self._worker = self._make_worker(
                python,
                worker_file(self.config["worker"]),
                init={"device": device},
                env=dict(WORKER_ENV),
                stderr=None,
            )
            self._device = device
        return self._worker

    def close(self):
        """Stop the worker (the loaded model is released)."""
        if self._worker is not None:
            self._worker.close()
            self._worker = None

    def _checkpoint(self, model):
        try:
            return self.config["models"][model]
        except KeyError:
            raise ValueError(
                f"foundation_1: unknown model {model!r}; one of {sorted(self.config['models'])}"
            ) from None

    def _check_timing(self, timing, seconds):
        bpms, bars = self.config["supported_bpms"], self.config["supported_bars"]
        if timing["bpm"] is not None and timing["bpm"] not in bpms:
            warnings.warn(
                f"foundation_1: {timing['bpm']} BPM is outside the tempos it was trained "
                f"on {bpms}; timing may drift",
                stacklevel=3,
            )
        if timing["bars"] is not None and timing["bars"] not in bars:
            warnings.warn(
                f"foundation_1: {timing['bars']} bars is outside the trained {bars}",
                stacklevel=3,
            )
        if not 0 < seconds <= WINDOW_SECONDS:
            raise ValueError(
                f"foundation_1: {seconds:.2f} s is outside the model's 0-{WINDOW_SECONDS:.0f} s window"
            )

    def generate(
        self,
        prompt: str,
        *,
        duration: float = None,
        bpm: float = None,
        key: str = None,
        bars: int = None,
        note: str = None,
        model: str = "foundation-1",
        num_steps: int = 100,
        guidance: float = 7.0,
        seed: int = None,
        negative_prompt: str = None,
        sampler: str = DFLT_SAMPLER,
        device: str = None,
        normalize: bool = True,
        **kwargs,
    ):
        """Render a loop or a one-shot for the tag prompt ``prompt``.

        Args:
            prompt: Foundation-1 tags, e.g. ``"Synth Lead, Warm, Arp, Medium Reverb"``
                (instrument, timbre, notation, FX; see the model card). Passed through,
                with the bar, tempo and key tags appended when given as arguments.
            duration: Seconds; without a tempo, the clip length (default 10), with one,
                only the hint for the bar count.
            bpm: Tempo, appended as ``"<bpm> BPM"`` (trained on 100-150, see the config).
            key: Key, appended as e.g. ``"E minor"`` (``"Em"`` and ``"E minor"`` both work).
            bars: 4 or 8, with a tempo: the loop is exactly that many 4/4 bars.
            note: A one-shot's pitch (``"C3"``), appended as ``"Target Note, C3"``; with
                ``model="1.2-keybeds"`` the prompt takes that checkpoint's single-note
                form (``"Keybed, Timbre Profile, ..."``). Default length 3 s.
            model: ``"foundation-1"`` (loops), ``"1.2-samples"`` (loops and one-shots) or
                ``"1.2-keybeds"`` (pitch-consistent one-shots).
            num_steps: Sampler steps.
            guidance: CFG scale.
            seed: Seed; a fresh one is drawn and recorded when None.
            negative_prompt: What to steer away from.
            sampler: stable-audio-tools sampler type.
            device: ``"mps"``, ``"cuda"`` or ``"cpu"``; default: the best available.
            normalize: Scale the take to full scale (its peak at 0 dBFS). ``False``
                keeps the model's own level (written as float, so nothing clips): takes
                meant to sit side by side, such as a keybed's chunks, keep their balance.

        Returns:
            A complete Song (44.1 kHz stereo wav), the prompt sent in its metadata.
        """
        checkpoint = self._checkpoint(model)
        text, seconds, timing = build_prompt(
            prompt,
            bpm=bpm,
            key=key,
            bars=bars,
            duration=duration,
            note=note,
            keybed=model == "1.2-keybeds",
            supported_bars=self.config["supported_bars"],
        )
        self._check_timing(timing, seconds)
        seed = draw_seed() if seed is None else int(seed)
        weights = self.config["weights"]
        out = Path(tempfile.mkdtemp(prefix="arioso_f1_")) / "out.wav"
        result = self._ensure_worker(device).call(
            "render",
            repo_id=weights["repo_id"],
            revision=weights["revision"],
            config_file=weights["config_file"],
            checkpoint=checkpoint,
            t5=weights["t5"],
            prompt=text,
            seconds=seconds,
            steps=int(num_steps),
            cfg_scale=float(guidance),
            seed=seed,
            sampler=sampler,
            sigma_min=DFLT_SIGMA_MIN,
            sigma_max=DFLT_SIGMA_MAX,
            negative_prompt=negative_prompt,
            out=str(out),
            normalize=bool(normalize),
        )
        # the device the worker resolved (None asked for "the best"): asking for it by
        # name later must not restart the worker and reload the model
        self._device = result.get("device", self._device)
        return song_from_wav(
            result["out"],
            platform="foundation_1",
            remove=True,
            metadata={
                "seed": seed,
                "model": model,
                "prompt_sent": text,
                **timing,
                "num_steps": num_steps,
                "guidance": guidance,
                "sampler": sampler,
                "device": result.get("device"),
            },
        )
