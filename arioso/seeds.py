"""
Seeds for a cover: one melodic line over a tanpura drone, from a recording or a score.

To make a generator keep a known melody with no harmony (Suno upload-cover, MusicGen-melody), the
best source is the melody alone over a drone: a cover keeps its source's harmony static, so a
source with no harmony gives takes that hold the drone. Check the takes with
``arioso.analysis.drone_report`` (does it hold the drone?) and ``arioso.analysis.melody_match``
(does it keep the tune?).

Three steps, each a function whose seams are keyword arguments:

- ``melody_contour``: the melody as a pitch curve, a :class:`Contour` (fractional MIDI per frame,
  NaN when silent). From a recording (``audio_contour``): separate the voice, track f0, clean the
  track. From a score (``midi_contour``): the monophonic skyline of one MIDI track, with short
  glides between touching notes and late vibrato.
- ``tanpura``: a synthesized drone on Sa (strings Pa, Sa, Sa, low Sa). ``loop_drone`` repeats a
  recorded drone instead, with crossfades.
- ``melody_over_drone``: renders the contour with a soft bowed timbre over the drone, levels set by
  active RMS, lifting a low line by octaves out of the drone's register.

The core is numpy. ``librosa`` (the default f0 tracker), ``pretty_midi`` (reading MIDI) and
``torch``/``torchaudio`` (the default voice separator) are imported only when used.

>>> notes = [(0.0, 1.0, 62), (1.0, 2.0, 64)]  # (start s, end s, MIDI pitch)
>>> c = notes_contour(notes, fps=100)
>>> float(c.midi[20]), float(c.midi[120]), c.seconds  # before the vibrato starts
(62.0, 64.0, 2.0)
>>> y, sr = melody_over_drone(c, "D", sr=8000)
>>> sr, y.shape[0] > 2 * sr
(8000, True)
"""

import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from functools import lru_cache

import numpy as np

from arioso._audio import to_audio_ref
from arioso.analysis import index_runs, pitch_class
from arioso.scoring import SILENCE_DB, active_db

#: drone_report reads the bass from C1 up three octaves, so a melody whose median sits under C4
#: (MIDI 60) reads as part of the drone. melody_over_drone lifts it above this by octaves.
DRONE_BAND_TOP_MIDI = 60.0


@dataclass
class Contour:
    """A melody as a pitch curve: fractional MIDI pitch per frame, NaN where silent."""

    midi: np.ndarray
    fps: float

    @property
    def seconds(self) -> float:
        return len(self.midi) / self.fps

    def transposed(self, semitones: float) -> "Contour":
        return replace(self, midi=self.midi + semitones)

    def at_rate(self, sr: int) -> np.ndarray:
        """The pitch per sample at ``sr`` (linear between frames, NaN where silent)."""
        n = int(round(self.seconds * sr))
        idx = np.minimum((np.arange(n) * self.fps / sr), len(self.midi) - 1)
        lo = np.floor(idx).astype(int)
        hi = np.minimum(lo + 1, len(self.midi) - 1)
        frac = idx - lo
        a, b = self.midi[lo], self.midi[hi]
        # interpolate inside a note, hold the last value up to a silence
        return np.where(np.isnan(b), a, a + (b - a) * frac)


# --------------------------------------------------------------------------------------------
# From a recording


def hz_to_midi(hz: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return 69.0 + 12.0 * np.log2(np.asarray(hz, dtype=float) / 440.0)


def midi_to_hz(midi: np.ndarray) -> np.ndarray:
    return 440.0 * 2.0 ** ((np.asarray(midi, dtype=float) - 69.0) / 12.0)


def pyin_f0(
    y: np.ndarray,
    sr: int,
    *,
    fmin_hz: float = 65.0,
    fmax_hz: float = 1050.0,
    hop_s: float = 0.01,
) -> tuple[np.ndarray, np.ndarray, float]:
    """f0 by librosa's pYIN: ``(f0_hz, voiced, fps)``, the default ``f0_tracker``.

    ``voiced`` is pYIN's HMM voicing decision. Its frame probabilities are no use as a gate: they
    run under 0.5 on most real singing, so a probability threshold drops most of it.
    """
    import librosa

    hop = max(1, int(round(hop_s * sr)))
    f0, voiced, _ = librosa.pyin(
        np.asarray(y, dtype=float), fmin=fmin_hz, fmax=fmax_hz, sr=sr, hop_length=hop
    )
    return f0, voiced, sr / hop


@lru_cache(maxsize=2)
def _hdemucs(device: str):
    import torchaudio

    bundle = torchaudio.pipelines.HDEMUCS_HIGH_MUSDB_PLUS
    return bundle.get_model().to(device).eval(), bundle.sample_rate


def hdemucs_vocals(
    y: np.ndarray,
    sr: int,
    *,
    segment_s: float = 10.0,
    overlap_s: float = 1.0,
    device: str = "cpu",
) -> tuple[np.ndarray, int]:
    """The voice of a mix, by torchaudio's Hybrid Demucs (``HDEMUCS_HIGH_MUSDB_PLUS``).

    The default ``separator``. Runs in ``segment_s`` chunks overlap-added with linear crossfades
    of ``overlap_s``, so memory stays flat on a long recording. Returns mono vocals at the
    model's rate (44.1 kHz). Needs ``torch`` and ``torchaudio``; the weights (torchaudio's
    bundle, trained on MUSDB-HQ plus extra data) download once; check their terms before
    commercial use.
    """
    import torch
    import torchaudio

    model_sr = torchaudio.pipelines.HDEMUCS_HIGH_MUSDB_PLUS.sample_rate
    seg, ov = int(segment_s * model_sr), int(overlap_s * model_sr)
    if seg <= ov:  # in samples: the loop would never advance
        raise ValueError(
            f"segment_s ({segment_s}) must be longer than overlap_s ({overlap_s})"
        )
    model, _ = _hdemucs(device)
    x = to_audio_ref((y, sr)).as_waveform().float()
    if x.shape[0] == 1:
        x = x.repeat(2, 1)
    x = torchaudio.functional.resample(x[:2], sr, model_sr)
    mean, std = x.mean(), x.std() + 1e-8
    x = (x - mean) / std

    n = x.shape[1]
    out = torch.zeros(n)
    weight = torch.zeros(n)
    vocals = model.sources.index("vocals")
    start = 0
    with torch.no_grad():
        while start < n:
            end = min(n, start + seg)
            chunk = x[:, start:end][None].to(device)
            est = model(chunk)[0, vocals].mean(0).cpu()
            w = torch.ones(end - start)
            ramp = torch.linspace(0, 1, min(ov, end - start) + 2)[1:-1]
            if start > 0:
                w[: len(ramp)] = ramp
            if end < n:
                w[-len(ramp) :] = ramp.flip(0)
            out[start:end] += est * w
            weight[start:end] += w
            if end == n:
                break
            start = end - ov
    return (out / weight.clamp_min(1e-8) * std + mean).numpy(), model_sr


def _mono(y: np.ndarray, sr: int) -> np.ndarray:
    return to_audio_ref((y, sr)).as_mono()[0]


def _frame_rms(y: np.ndarray, hop: int, n_frames: int, *, win: int) -> np.ndarray:
    """RMS of ``win``-sample frames centered every ``hop`` samples (as pYIN frames them), from a
    running sum of squares so a long recording needs no frames-by-window array."""
    padded = np.pad(np.asarray(y, dtype=float), (win // 2, win // 2 + hop * n_frames))
    energy = np.concatenate([[0.0], np.cumsum(padded**2)])
    starts = np.arange(n_frames) * hop
    return np.sqrt(np.maximum(energy[starts + win] - energy[starts], 0) / win)


def drop_blips(midi: np.ndarray, fps: float, *, min_s: float = 0.12) -> np.ndarray:
    """Silence voiced stretches shorter than ``min_s`` (tracker noise, consonants)."""
    out = midi.copy()
    for a, b in index_runs(~np.isnan(midi)):
        if (b - a) / fps < min_s:
            out[a:b] = np.nan
    return out


def fix_octaves(
    midi: np.ndarray, fps: float, *, window_s: float = 0.5, min_jump: float = 9.5
) -> np.ndarray:
    """Move frames an octave (or two) away from the local median back next to it.

    f0 trackers jump an octave on breathy or loud notes. Only frames at least ``min_jump``
    semitones from the median of the surrounding ``window_s`` move, so a real leap of a fifth or
    a sixth stays; a real leap of a seventh or more inside the window is rare enough to sacrifice.
    """
    out = midi.copy()
    half = max(1, int(window_s * fps) // 2)
    for i in np.flatnonzero(~np.isnan(midi)):
        dev = midi[i] - np.nanmedian(midi[max(0, i - half) : i + half + 1])
        if abs(dev) >= min_jump:
            out[i] = midi[i] - 12 * np.round(dev / 12)
    return out


def tuning_offset(midi: np.ndarray) -> float:
    """The singer's tuning against 12-TET, in semitones (-0.5..0.5): the circular mean of the
    cents, so 49 cents sharp and 49 flat average to a quarter-tone, not to zero."""
    voiced = midi[~np.isnan(midi)]
    if not len(voiced):
        return 0.0
    angle = np.angle(np.mean(np.exp(2j * np.pi * voiced)))
    return float(angle / (2 * np.pi))


def audio_contour(
    audio,
    sr: int | None = None,
    *,
    separator: Callable | None = hdemucs_vocals,
    f0_tracker: Callable = pyin_f0,
    gate_db: float = -35.0,
    min_note_s: float = 0.12,
    octave_window_s: float = 0.5,
    retune: bool = True,
) -> Contour:
    """The sung (or played) melody of a recording as a :class:`Contour`.

    Args:
        audio: The recording: an ``(array, sample_rate)`` pair, an array with ``sr``, or any form
            ``arioso._audio.to_audio_ref`` accepts (path, bytes, Song).
        sr: The sample rate when ``audio`` is a bare array.
        separator: ``(y, sr) -> (voice, sr)``. The default, :func:`hdemucs_vocals`, isolates the
            voice of a mix; pass ``None`` for a recording that is already one line.
        f0_tracker: ``(y, sr) -> (f0_hz, voiced, fps)``. Default :func:`pyin_f0`; a
            ``denote.get_pitch`` backend fits behind a two-line lambda.
        gate_db: Frames quieter than this, relative to the 95th-percentile frame level, are
            silent whatever the tracker says (reverb tails, bleed).
        min_note_s: Voiced stretches shorter than this are dropped (:func:`drop_blips`).
        octave_window_s: Window of the octave-jump fix (:func:`fix_octaves`).
        retune: Shift the whole line onto 12-TET by its :func:`tuning_offset`.
    """
    ref = to_audio_ref(audio if sr is None else (audio, sr))
    y, rate = ref.as_array(), ref.sample_rate
    if separator is not None:
        y, rate = separator(y, rate)
    y = _mono(y, rate)
    f0, voiced, fps = f0_tracker(y, rate)
    midi = np.where(np.asarray(voiced, dtype=bool), hz_to_midi(f0), np.nan)

    hop = int(round(rate / fps))
    level = _frame_rms(y, hop, len(midi), win=4 * hop)
    loud = level > np.percentile(level, 95) * 10 ** (gate_db / 20)
    midi[~loud] = np.nan

    midi = drop_blips(midi, fps, min_s=min_note_s)
    midi = fix_octaves(midi, fps, window_s=octave_window_s)
    if np.all(np.isnan(midi)):
        raise ValueError(
            "no melody found: nothing in the recording is voiced and loud enough (with a "
            "separator, it may have found no voice; try separator=None or a lower gate_db)"
        )
    if retune:
        midi = midi - tuning_offset(midi)
    return Contour(midi=midi, fps=fps)


# --------------------------------------------------------------------------------------------
# From a score


def notes_contour(
    notes: Iterable[tuple[float, float, float]],
    *,
    fps: float = 100.0,
    glide_s: float = 0.06,
    vibrato_delay_s: float = 0.35,
    vibrato_ramp_s: float = 0.3,
    vibrato_hz: float = 5.5,
    vibrato_semitones: float = 0.15,
    restrike_s: float = 0.05,
) -> Contour:
    """The monophonic skyline of ``(start_s, end_s, midi_pitch)`` notes, made singable.

    Where notes overlap the highest sounds. A note that starts where the previous one ends glides
    into its pitch over ``glide_s``; a note held past ``vibrato_delay_s`` gets a vibrato that
    ramps in over ``vibrato_ramp_s``. ``glide_s=0`` or ``vibrato_semitones=0`` turns either off.
    A note that starts where one of the same pitch ends would merge into one tone, so the earlier
    one ends ``restrike_s`` early (longer than ``bowed``'s fade, so the breath is heard).
    """

    def segments(owner):
        cuts = np.flatnonzero(np.diff(owner)) + 1
        bounds = np.concatenate([[0], cuts, [len(owner)]])
        return [(a, b) for a, b in zip(bounds[:-1], bounds[1:]) if owner[a] >= 0]

    # paint low to high (then early to late), so the highest note wins and ties are stable
    notes = sorted(notes, key=lambda n: (n[2], n[0]))
    if not notes:
        raise ValueError("no notes to make a contour from")
    n = int(np.ceil(max(end for _, end, _ in notes) * fps))
    pitch = np.full(n, np.nan)
    owner = np.full(n, -1)  # which note sounds at each frame
    for k, (start, end, p) in enumerate(notes):
        a, b = int(round(start * fps)), int(round(end * fps))
        pitch[a:b], owner[a:b] = p, k
    breath = max(1, int(round(restrike_s * fps)))
    for i in np.flatnonzero(
        (owner[1:] != owner[:-1]) & (owner[:-1] >= 0) & (pitch[1:] == pitch[:-1])
    ):
        a = max(0, i + 1 - breath)
        pitch[a : i + 1], owner[a : i + 1] = np.nan, -1

    midi = pitch.copy()
    notes_at = segments(owner)  # one per sounding note
    for i, (a, b) in enumerate(notes_at):
        t = np.arange(b - a) / fps
        if vibrato_semitones and (b - a) / fps > vibrato_delay_s:
            tv = np.maximum(t - vibrato_delay_s, 0)
            depth = vibrato_semitones * np.minimum(tv / max(vibrato_ramp_s, 1e-9), 1)
            midi[a:b] += depth * np.sin(2 * np.pi * vibrato_hz * tv)
        prev = notes_at[i - 1] if i else None
        if glide_s and prev and prev[1] == a and pitch[prev[0]] != pitch[a]:
            g = min(b - a, max(1, int(glide_s * fps)))
            midi[a : a + g] += (pitch[prev[0]] - pitch[a]) * (1 - np.arange(g) / g)
    return Contour(midi=midi, fps=fps)


def midi_contour(
    midi,
    *,
    track: int | str | None = None,
    min_mono: float = 0.95,
    min_median_midi: float = 55.0,
    **kwargs,
) -> Contour:
    """The melody of one track of a MIDI file as a :class:`Contour` (see :func:`notes_contour`).

    Args:
        midi: A path, the file's bytes, or a ``pretty_midi.PrettyMIDI``.
        track: The instrument's index or name. By default, the track with the most notes among
            those that play one note at a time (at least ``min_mono`` of their sounding time)
            above the bass (median pitch at least ``min_median_midi``); when none qualifies, a
            ``ValueError`` lists the tracks so you can name one.
        **kwargs: Passed to :func:`notes_contour` (``fps``, ``glide_s``, vibrato knobs).
    """
    import io

    import pretty_midi

    if isinstance(midi, (bytes, bytearray)):
        midi = pretty_midi.PrettyMIDI(io.BytesIO(midi))
    elif not isinstance(midi, pretty_midi.PrettyMIDI):
        midi = pretty_midi.PrettyMIDI(str(midi))
    if track is None:
        inst = _melody_track(
            midi.instruments, min_mono=min_mono, min_median_midi=min_median_midi
        )
    elif isinstance(track, int):
        inst = midi.instruments[track]
    else:
        named = [i for i in midi.instruments if i.name == track]
        if not named:
            names = [i.name for i in midi.instruments]
            raise ValueError(f"no track named {track!r}; tracks: {names}")
        inst = named[0]
    return notes_contour(((n.start, n.end, n.pitch) for n in inst.notes), **kwargs)


def _melody_track(instruments, *, min_mono: float, min_median_midi: float):
    stats = [
        (
            k,
            inst,
            len(inst.notes),
            mono_share(inst.notes),
            float(np.median([n.pitch for n in inst.notes])),
        )
        for k, inst in enumerate(instruments)
        if not inst.is_drum and inst.notes
    ]
    if not stats:
        raise ValueError("the MIDI file has no pitched notes")
    lines = [s for s in stats if s[3] >= min_mono and s[4] >= min_median_midi]
    if not lines:
        table = "\n".join(
            f"  {k}: {inst.name!r} notes={n} mono={mono:.2f} median={med:.0f}"
            for k, inst, n, mono, med in stats
        )
        raise ValueError(
            f"no track is a single line above the bass (mono >= {min_mono}, median >= "
            f"{min_median_midi}); pass track= one of:\n{table}"
        )
    return max(lines, key=lambda s: s[2])[1]


def mono_share(notes, *, fps: float = 20.0) -> float:
    """Share of the sounding time of ``notes`` (objects with ``start`` and ``end`` in seconds)
    when exactly one of them sounds: 1 for a melodic line, about 0.3 for a three-note pad."""
    notes = [(n.start, n.end) for n in notes]
    count = np.zeros(int(np.ceil(max(end for _, end in notes) * fps)) + 1)
    for start, end in notes:
        a = int(start * fps)
        count[a : max(a + 1, int(end * fps))] += 1
    sounding = count > 0
    return float(np.mean(count[sounding] == 1)) if sounding.any() else 0.0


def _is_midi(source) -> bool:
    if type(source).__name__ == "PrettyMIDI":
        return True
    if isinstance(source, (bytes, bytearray)):
        return bytes(source[:4]) == b"MThd"
    if isinstance(source, (str, os.PathLike)):
        return os.fspath(source).lower().endswith((".mid", ".midi"))
    return False


def melody_contour(source, sr: int | None = None, **kwargs) -> Contour:
    """A :class:`Contour` from a MIDI file (:func:`midi_contour`) or a recording
    (:func:`audio_contour`), told apart by the source; ``kwargs`` go to the one chosen."""
    if _is_midi(source):
        return midi_contour(source, **kwargs)
    return audio_contour(source, sr, **kwargs)


# --------------------------------------------------------------------------------------------
# Drones


def sa_midi(sa: str | float, *, octave: int = 3) -> float:
    """Sa as a MIDI number: a note name placed in ``octave`` (C#3 = 49), or a MIDI number as is."""
    if isinstance(sa, str):
        return 12 * (octave + 1) + pitch_class(sa)
    return float(sa)


def tanpura(
    sa: str | float,
    *,
    seconds: float = 30.0,
    sr: int = 32000,
    second: int = 7,
    cycle_s: float = 3.2,
    decay_s: float = 2.5,
    harmonics: int = 24,
    octave: int = 3,
    seed: int = 0,
) -> np.ndarray:
    """A synthesized tanpura on Sa: four strings plucked in turn, low ``second``, Sa, Sa, low Sa.

    Args:
        sa: The tonic, a note name (in ``octave``) or a MIDI number.
        seconds: Length of the drone.
        sr: Sample rate.
        second: Semitones above Sa of the first string, played an octave down: 7 for Pa, 5 for Ma,
            11 for Ni.
        cycle_s: Time for one round of the four strings.
        decay_s: Decay time of a pluck.
        harmonics: Partials per string. Higher ones bloom late, the jawari buzz.
        octave: The octave a note-name Sa sits in.
        seed: Fixes the small detuning between strings (the beating that makes it shimmer).
    """
    root = sa_midi(sa, octave=octave)
    strings = [root - 12 + second, root, root, root - 12]
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    pluck_len = int(min(cycle_s * 1.5, seconds) * sr)
    t = np.arange(pluck_len) / sr
    out = np.zeros(n + pluck_len)
    for k, midi in enumerate(strings):
        f0 = midi_to_hz(midi + rng.normal(0, 0.02))
        wave = np.zeros(pluck_len)
        for h in range(1, harmonics + 1):
            if h * f0 >= sr / 2:
                break
            bloom = 1 - np.exp(-t / (0.01 + 0.25 * h / harmonics))
            wave += (
                h**-0.9
                * bloom
                * np.sin(2 * np.pi * h * f0 * t + rng.uniform(0, 2 * np.pi))
            )
        wave *= np.exp(-t / decay_s)
        tail = pluck_len // 4  # fade the last quarter, so a pluck never ends in a tick
        wave[-tail:] *= np.cos(np.linspace(0, np.pi / 2, tail)) ** 2
        for start in np.arange(k * cycle_s / 4, seconds, cycle_s):
            i = int(start * sr)
            out[i : i + pluck_len] += wave
    return _peak(out[:n])


def loop_drone(
    y: np.ndarray, sr: int, seconds: float, *, crossfade_s: float = 1.0
) -> np.ndarray:
    """A recorded drone repeated to ``seconds`` with equal-power crossfades at the joins."""
    y = _mono(y, sr)
    n, fade = int(seconds * sr), int(crossfade_s * sr)
    if len(y) <= 2 * fade:
        raise ValueError(
            f"a {len(y) / sr:.1f} s drone is too short for {crossfade_s} s crossfades"
        )
    theta = np.linspace(0, np.pi / 2, fade)
    fade_in, fade_out = np.sin(theta), np.cos(theta)  # equal power: squares sum to 1
    step = len(y) - fade
    out = np.zeros(n + len(y))
    for start in range(0, n, step):
        piece = y.copy()
        if start:
            piece[:fade] *= fade_in
            out[start : start + fade] *= fade_out
        out[start : start + len(y)] += piece
    return out[:n].astype(y.dtype)


# --------------------------------------------------------------------------------------------
# Rendering


def bowed(
    pitch: np.ndarray,
    sr: int,
    *,
    harmonics: int = 7,
    rolloff: float = 1.5,
    fade_s: float = 0.04,
) -> np.ndarray:
    """A soft bowed line following ``pitch`` (fractional MIDI per sample, NaN where silent).

    The default ``timbre`` of :func:`melody_over_drone`: ``harmonics`` partials falling off as
    ``1 / k**rolloff``, phase-continuous through glides, faded in and out over ``fade_s``.
    """
    voiced = ~np.isnan(pitch)
    if not voiced.any():
        return np.zeros(len(pitch))
    # carry a pitch through silences so the phase never jumps: the last note's for the first
    # half of a rest, the next note's for the second, so the fade-in already sounds the entry
    filled = pitch.copy()
    for a, b in index_runs(~voiced):
        before = pitch[a - 1] if a else pitch[b]
        after = pitch[b] if b < len(pitch) else before
        mid = 0 if a == 0 else (a + b) // 2
        filled[a:mid], filled[mid:b] = before, after
    f0 = midi_to_hz(filled)
    phase = 2 * np.pi * np.cumsum(f0) / sr
    y = sum(
        k**-rolloff * np.sin(k * phase) * (k * f0 < sr / 2)
        for k in range(1, harmonics + 1)
    )
    w = max(1, int(fade_s * sr))
    env = np.convolve(voiced.astype(float), np.ones(w) / w, mode="same")
    return y * env


def _peak(y: np.ndarray, peak: float = 0.9) -> np.ndarray:
    top = np.max(np.abs(y)) if len(y) else 0.0
    return y * (peak / top) if top > 0 else y


def melody_over_drone(
    contour: Contour,
    sa: str | float,
    *,
    sr: int = 32000,
    drone: Callable | np.ndarray = tanpura,
    timbre: Callable = bowed,
    transpose: float = 0.0,
    floor_midi: float | None = DRONE_BAND_TOP_MIDI,
    melody_db: float = 0.0,
    drone_db: float = -8.0,
    lead_in_s: float = 2.0,
    peak: float = 0.9,
) -> tuple[np.ndarray, int]:
    """Render ``contour`` over a drone on ``sa``: the seed for a cover. Returns ``(y, sr)``.

    Args:
        contour: The melody (:func:`melody_contour`), already in Sa's key.
        sa: The drone's tonic, a note name or MIDI number.
        sr: Output sample rate.
        drone: ``(sa, *, seconds, sr) -> array`` (default :func:`tanpura`), or a recorded drone
            array at ``sr``, looped to length by :func:`loop_drone`.
        timbre: ``(pitch_per_sample, sr) -> array`` (default :func:`bowed`).
        transpose: Semitones to move the melody before rendering.
        floor_midi: Lift the melody by octaves until its median pitch is at least this. The
            default keeps it above the bass band ``drone_report`` reads, where a low (male) line
            would otherwise sit inside the drone and fail the check. ``None`` turns it off.
        melody_db, drone_db: Levels, as active RMS (``arioso.scoring.active_db``, frames
            within 40 dB of the loudest) relative to each other.
        lead_in_s: Drone alone before the melody starts, to set Sa.
        peak: Peak level of the mix.
    """
    c = contour.transposed(transpose)
    if floor_midi is not None and np.any(~np.isnan(c.midi)):
        lift = max(0.0, np.ceil((floor_midi - np.nanmedian(c.midi)) / 12))
        c = c.transposed(12 * lift)
    lead = np.full(int(round(lead_in_s * c.fps)), np.nan)
    c = replace(c, midi=np.concatenate([lead, c.midi]))

    melody = timbre(c.at_rate(sr), sr)
    seconds = len(melody) / sr
    if callable(drone):
        bed = drone(sa, seconds=seconds, sr=sr)
    else:
        bed = loop_drone(drone, sr, seconds)
    bed = np.pad(bed[: len(melody)], (0, max(0, len(melody) - len(bed))))

    def at(y, db):
        level = active_db(y, sr, floor_rel_db=-40.0)
        return y * 10 ** ((db - level) / 20) if level > SILENCE_DB else y

    return _peak(at(melody, melody_db) + at(bed, drone_db), peak), sr
