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

_BARS_TAG = re.compile(r"\b(\d+)\s*Bars?\b", re.IGNORECASE)
_BPM_TAG = re.compile(r"\b(\d+(?:\.\d+)?)\s*BPM\b", re.IGNORECASE)
_KEY_TAG = re.compile(r"\b[A-G][#b]?\s+(?:major|minor)\b", re.IGNORECASE)
_KEY_SHORT = re.compile(
    r"^\s*([A-Ga-g])\s*([#b]?)\s*(m|min|minor|maj|major)?\s*$", re.IGNORECASE
)


def normalize_key(key: str) -> str:
    """A key as Foundation-1's tags spell it: ``"Am"`` -> ``"A minor"``, ``"f#"`` -> ``"F# major"``.

    >>> normalize_key("Am"), normalize_key("C# minor"), normalize_key("eb")
    ('A minor', 'C# minor', 'Eb major')
    """
    m = _KEY_SHORT.match(key)
    if not m:
        m2 = re.match(r"^\s*([A-Ga-g][#b]?)\s+(major|minor)\s*$", key, re.IGNORECASE)
        if m2:
            return f"{m2.group(1)[0].upper()}{m2.group(1)[1:]} {m2.group(2).lower()}"
        return key.strip()
    letter, accidental, quality = m.groups()
    quality = (quality or "major").lower()
    mode = "major" if quality in ("maj", "major") else "minor"
    return f"{letter.upper()}{accidental} {mode}"


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
    supported_bars=PLATFORM_CONFIG["supported_bars"],
) -> "tuple[str, float, dict]":
    """The tag prompt, the clip's seconds and the timing it used, from arioso's controls.

    Tags already in ``prompt`` win over nothing and must agree with the arguments: a prompt
    saying ``"140 BPM"`` with ``bpm=120`` is an error. The bar, tempo and key tags are
    appended in the model card's order (``..., 8 Bars, 140 BPM, E minor``).

    With a tempo (``bpm`` or a ``BPM`` tag) the clip is ``bars`` bars long: ``bars``, else a
    ``Bars`` tag, else the supported count nearest to ``duration * bpm / 240`` (4 when no
    duration is given). Without a tempo the clip is ``duration`` seconds (default 10).

    >>> build_prompt("Synth Lead, Warm, Arp", bpm=140, key="Em", duration=12)
    ('Synth Lead, Warm, Arp, 8 Bars, 140 BPM, E minor', 13.714285714285714, {'bpm': 140, 'bars': 8, 'key': 'E minor'})
    >>> build_prompt("Grand Piano, Bright, Hit", duration=3)
    ('Grand Piano, Bright, Hit', 3.0, {'bpm': None, 'bars': None, 'key': None})
    """
    text = prompt.strip().rstrip(",").strip()
    tagged_bpm = _BPM_TAG.search(text)
    tagged_bars = _BARS_TAG.search(text)
    tagged_key = _KEY_TAG.search(text)

    def agree(name, given, tagged, cast):
        if tagged is None:
            return given, False
        value = cast(tagged.group(1) if name != "key" else tagged.group(0))
        if given is not None and given != value:
            raise ValueError(
                f"foundation_1: {name}={given!r} contradicts the prompt's {tagged.group(0)!r}"
            )
        return value, True

    def as_number(s):
        f = float(s)
        return int(f) if f.is_integer() else f

    bpm, bpm_in_text = agree(
        "bpm", None if bpm is None else as_number(bpm), tagged_bpm, as_number
    )
    bars, bars_in_text = agree("bars", bars, tagged_bars, int)
    key = normalize_key(key) if key else None
    key, key_in_text = agree("key", key, tagged_key, normalize_key)

    tags = []
    if bpm is None:
        if bars is not None:
            raise ValueError("foundation_1: bars needs a tempo (bpm=, or a BPM tag)")
        seconds = 10.0 if duration is None else float(duration)
    else:
        if bars is None:
            wanted = (
                4 if duration is None else float(duration) * bpm / (60 * BEATS_PER_BAR)
            )
            bars = _nearest(wanted, supported_bars)
        seconds = bars * BEATS_PER_BAR * 60 / bpm
        if not bars_in_text:
            tags.append(f"{bars} Bars")
        if not bpm_in_text:
            tags.append(f"{bpm} BPM")
    if key and not key_in_text:
        tags.append(key)
    text = ", ".join([t for t in [text] if t] + tags)
    return text, seconds, {"bpm": bpm, "bars": bars, "key": key}


class Adapter:
    """Local Foundation-1 adapter (stable-audio-tools, MPS / CUDA / CPU)."""

    def __init__(
        self, config: dict = None, *, make_worker=Worker, ensure_env=ensure_env
    ):
        self.config = config or PLATFORM_CONFIG
        self._make_worker = make_worker
        self._ensure_env = ensure_env
        self._worker = None
        self._device = None

    def _ensure_worker(self, device):
        if self._worker is not None and device not in (None, self._device):
            self.close()  # another device asked for: a fresh worker
        if self._worker is None:
            python = self._ensure_env(self.config["env"])
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
        model: str = "foundation-1",
        num_steps: int = 100,
        guidance: float = 7.0,
        seed: int = None,
        negative_prompt: str = None,
        sampler: str = DFLT_SAMPLER,
        device: str = None,
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
            model: ``"foundation-1"`` (loops), ``"1.2-samples"`` (loops and one-shots) or
                ``"1.2-keybeds"`` (pitch-consistent one-shots).
            num_steps: Sampler steps.
            guidance: CFG scale.
            seed: Seed; a fresh one is drawn and recorded when None.
            negative_prompt: What to steer away from.
            sampler: stable-audio-tools sampler type.
            device: ``"mps"``, ``"cuda"`` or ``"cpu"``; default: the best available.

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
        )
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
