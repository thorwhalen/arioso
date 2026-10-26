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
- ``tanpura``: a synthesized drone on Sa (strings Pa, Sa, Sa, low Sa). ``recorded_drone`` uses a
  recording instead, retuned to Sa (``varispeed``) and looped with crossfades (``loop_drone``).
- ``melody_over_drone``: renders the contour with a soft bowed timbre over the drone, levels set by
  active RMS, lifting a low line by octaves out of the drone's register. ``musicgen_variation``
  makes a seed in a generator's own phrasing instead: MusicGen-melody on the voice over the drone,
  its bass removed (``highpass``) so the drone carries the bottom.

The core is numpy. ``librosa`` (the default f0 tracker), ``pretty_midi`` (reading MIDI) and
``denote`` (the default voice separator, with ``torch``/``torchaudio``) are imported only when used.

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

import numpy as np

from arioso._audio import to_audio_ref
from arioso.analysis import NOTES, drone_report, index_runs, pitch_class
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


def hdemucs_vocals(
    y: np.ndarray,
    sr: int,
    *,
    segment_s: float = 10.0,
    overlap_s: float = 1.0,
    device: str = "cpu",
) -> tuple[np.ndarray, int]:
    """The voice of a mix, by torchaudio's Hybrid Demucs, through ``denote.separate``.

    The default ``separator``. ``denote`` runs the model in ``segment_s`` chunks overlap-added
    with crossfades of ``overlap_s``, so memory stays flat on a long recording. Returns mono
    vocals at the model's rate (44.1 kHz). Needs ``denote`` with ``torch`` and ``torchaudio``
    (the ``seeds`` extra); the weights (torchaudio's bundle, trained on MUSDB-HQ plus extra
    data) download once; check their terms before commercial use.
    """
    import denote

    result = denote.separate(
        y,
        sr=sr,
        sources=("vocals",),
        segment_s=segment_s,
        overlap_s=overlap_s,
        device=device,
    )
    return result.vocals, result.sr


def _mono(y: np.ndarray, sr: int) -> np.ndarray:
    return to_audio_ref((y, sr)).as_mono()[0]


def _frame_rms(y: np.ndarray, centers: np.ndarray, *, win: int) -> np.ndarray:
    """RMS of ``win``-sample frames centered on the sample indices ``centers`` (an f0
    tracker's own frame times, so the gate cannot drift from its frames), from a running sum
    of squares so a long recording needs no frames-by-window array."""
    centers = np.asarray(centers, dtype=int)
    tail = win + max(0, int(centers.max(initial=0)) - len(y))
    padded = np.pad(np.asarray(y, dtype=float), (win // 2, tail))
    energy = np.concatenate([[0.0], np.cumsum(padded**2)])
    return np.sqrt(np.maximum(energy[centers + win] - energy[centers], 0) / win)


def _separated(result) -> tuple:
    """A separator's ``(voice, sr)``, from the pair or from a result with ``.vocals`` and
    ``.sr`` (``denote.separate``'s ``SeparationResult``)."""
    if hasattr(result, "vocals") and hasattr(result, "sr"):
        return result.vocals, result.sr
    return result


def _tracked(result) -> tuple:
    """An f0 tracker's ``(f0_hz, voiced, times, fps)``: from an ``(f0_hz, voiced, fps)`` triple, or
    from a result with ``.times`` and ``.frequencies`` (``denote.get_pitch``'s ``PitchResult``).
    A frame is voiced only where its frequency is finite and positive (trackers mark unvoiced
    frames with NaN or with 0)."""
    if hasattr(result, "frequencies") and hasattr(result, "times"):
        f0 = np.asarray(result.frequencies, dtype=float)
        times = np.asarray(result.times, dtype=float)
        voiced = np.ones(f0.shape, dtype=bool)
        fps = None
    else:
        f0, voiced, fps = result
        f0, voiced = np.asarray(f0, dtype=float), np.asarray(voiced, dtype=bool)
        times = np.arange(len(f0)) / fps
    if f0.ndim != 1 or f0.shape != times.shape or f0.shape != voiced.shape:
        raise ValueError(
            f"the f0 tracker returned frequencies {f0.shape}, times {times.shape} and "
            f"voicing {voiced.shape}; one 1-D value of each per frame is needed"
        )
    if len(f0) < 2 or not (np.diff(times) > 0).all():
        raise ValueError(
            "the f0 tracker must return two or more frames at increasing times"
        )
    fps = fps or 1.0 / float(np.median(np.diff(times)))
    with np.errstate(invalid="ignore"):
        return f0, voiced & np.isfinite(f0) & (f0 > 0), times, fps


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
        separator: ``(y, sr) -> (voice, sr)``, or a result with ``.vocals`` and ``.sr``. The
            default, :func:`hdemucs_vocals`, isolates the voice of a mix; pass ``None`` for a
            recording that is already one line. ``lambda y, sr: denote.separate(y, sr=sr)``
            plugs in denote's separators.
        f0_tracker: ``(y, sr) -> (f0_hz, voiced, fps)``, or a result with ``.times`` and
            ``.frequencies`` (NaN where unvoiced). Default :func:`pyin_f0`;
            ``lambda y, sr: denote.get_pitch(y, sr=sr)`` plugs in denote's trackers.
        gate_db: Frames quieter than this, relative to the 95th-percentile frame level, are
            silent whatever the tracker says (reverb tails, bleed).
        min_note_s: Voiced stretches shorter than this are dropped (:func:`drop_blips`).
        octave_window_s: Window of the octave-jump fix (:func:`fix_octaves`).
        retune: Shift the whole line onto 12-TET by its :func:`tuning_offset`.
    """
    ref = to_audio_ref(audio if sr is None else (audio, sr))
    y, rate = ref.as_array(), ref.sample_rate
    if separator is not None:
        y, rate = _separated(separator(y, rate))
    y = _mono(y, rate)
    f0, voiced, times, fps = _tracked(f0_tracker(y, rate))
    midi = np.where(voiced, hz_to_midi(np.where(voiced, f0, 1.0)), np.nan)

    win = 4 * int(round(rate / fps))
    level = _frame_rms(y, np.round(times * rate), win=win)
    loud = level > np.percentile(level, 95) * 10 ** (gate_db / 20)
    midi[~loud] = np.nan
    # the Contour's grid starts at 0: a tracker whose first frame is later is shifted to it
    midi = np.concatenate([np.full(int(round(times[0] * fps)), np.nan), midi])

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


def varispeed(
    y: np.ndarray, sr: int, *, semitones: float = 0.0, sr_out: int | None = None
) -> np.ndarray:
    """``y`` played ``semitones`` higher (pitch and tempo move together, a tape sped up) and
    resampled to ``sr_out``, in one band-limited FFT resampling.

    For a drone this beats a phase vocoder: no smearing of the strings' attacks, and a cycle a
    few percent faster or slower goes unnoticed.
    """
    ratio = (sr / (sr_out or sr)) * 2 ** (
        semitones / 12
    )  # input samples per output sample
    if ratio == 1:
        return np.asarray(y, dtype=float)
    n_out = int(round(len(y) / ratio))
    spectrum = np.fft.rfft(y)[: n_out // 2 + 1]
    return np.fft.irfft(spectrum, n=n_out) * (n_out / len(y))


def drone_tonic(
    y: np.ndarray, sr: int, *, sa: str | None = None, band_midi: tuple = (36, 72)
) -> float:
    """The tonic of a drone recording as a fractional pitch class (0 = C, 4.45 = E 45 cents
    sharp): the Sa of :func:`drone_sa` (or the given ``sa`` name), refined to the strongest
    spectral peak within half a semitone of it in ``band_midi``, interpolated between bins.

    Raises when there is no peak there (silence, or an ``sa`` the recording does not play):
    the strongest bin would then sit on the window's edge and the estimate would be a guess.
    """
    pc = pitch_class(sa) if sa is not None else pitch_class(drone_sa(y, sr))
    spectrum = np.abs(np.fft.rfft(np.asarray(y, dtype=float) * np.hanning(len(y))))
    midi = hz_to_midi(np.fft.rfftfreq(len(y), 1 / sr))
    near = (midi >= band_midi[0]) & (midi < band_midi[1])
    near &= np.abs((midi - pc + 6) % 12 - 6) < 0.5
    near[[0, -1]] = False  # a peak needs a bin on each side
    k = int(np.flatnonzero(near)[np.argmax(spectrum[near])]) if near.any() else 0
    if not k or not (spectrum[k] > spectrum[k - 1] and spectrum[k] > spectrum[k + 1]):
        raise ValueError(f"no spectral peak at {NOTES[pc]} in the recording")
    a, b, c = np.log(spectrum[k - 1 : k + 2] + 1e-12)
    bin_offset = float(np.clip(0.5 * (a - c) / (a - 2 * b + c), -0.5, 0.5))
    return float(hz_to_midi((k + bin_offset) * sr / len(y)) % 12)


def drone_sa(y: np.ndarray, sr: int) -> str:
    """The Sa of a drone recording, assuming the usual Pa tuning: of the two notes
    ``drone_report`` finds a fifth apart, the lower one of the fifth (whichever string is
    louder). A Ma-tuned recording reads as its Ma; name its Sa instead."""
    a, b = (pitch_class(n) for n in drone_report(y, sr).drone)
    return NOTES[a if (b - a) % 12 == 7 else b]


def _loud_span(y: np.ndarray, sr: int, *, floor_db: float, frame_s: float = 0.05):
    """``y`` from its first to its last frame within ``floor_db`` of the 95th-percentile
    frame level: a recording without its fade-in, fade-out and silences at either end."""
    hop = max(1, int(frame_s * sr))
    frames = y[: len(y) // hop * hop].reshape(-1, hop)
    level = np.sqrt(np.mean(frames**2, axis=1))
    loud = np.flatnonzero(level >= np.percentile(level, 95) * 10 ** (floor_db / 20))
    return y[loud[0] * hop : (loud[-1] + 1) * hop] if len(loud) else y


def recorded_drone(
    y: np.ndarray,
    sr: int,
    *,
    rec_sa: str | None = None,
    max_shift: float = 2.0,
    min_on_drone: float = 0.6,
    trim_db: float = -6.0,
    crossfade_s: float = 1.0,
) -> Callable:
    """A ``drone`` for :func:`melody_over_drone` from a recording (a real tanpura sounds less
    synthetic than :func:`tanpura`): ``(sa, *, seconds, sr) -> array``.

    The recording is read once:

    - whether it is a drone at all: ``drone_report``'s on-drone share at least
      ``min_on_drone`` (a song with a tanpura in it is not);
    - its Sa: :func:`drone_sa` (Pa tuning assumed; a louder Pa string does not fool it), or
      ``rec_sa``, which must be one of the two notes it plays; then to the cent by
      :func:`drone_tonic`, so a tanpura tuned off 12-TET lands on the requested Sa, not a
      quarter-tone beside it;
    - its steady part: fades and silences at either end, quieter than ``trim_db`` under its
      level, are cut, or every loop would dip.

    Each call moves it to the requested Sa by :func:`varispeed` and loops it by
    :func:`loop_drone`. A move of more than ``max_shift`` semitones (at most 6 can be asked:
    the nearest Sa is never further) raises: it changes the instrument's size, and it sounds
    it. A CC0 recording to start from: "Tanpura in E" by iluppai,
    https://freesound.org/s/148850/ (22.8 s, Sa and Pa).
    """
    rec, rec_sr = to_audio_ref((y, sr)).as_mono()
    report = drone_report(rec, rec_sr)
    if report.on_drone_share < min_on_drone:
        raise ValueError(
            f"the recording holds a drone only {report.on_drone_share:.0%} of the time "
            f"(min_on_drone={min_on_drone}); it is not a drone bed"
        )
    if rec_sa is not None and pitch_class(rec_sa) not in map(pitch_class, report.drone):
        raise ValueError(
            f"rec_sa={rec_sa!r} is not one of the notes the recording plays: {report.drone}"
        )
    tonic = drone_tonic(rec, rec_sr, sa=rec_sa or drone_sa(rec, rec_sr))
    rec = _loud_span(rec, rec_sr, floor_db=trim_db)

    def drone(sa, *, seconds: float, sr: int = rec_sr) -> np.ndarray:
        shift = (sa_midi(sa) - tonic + 6) % 12 - 6
        if abs(shift) > max_shift:
            raise ValueError(
                f"the recording's Sa ({NOTES[round(tonic) % 12]}) is {-shift:+.2f} semitones "
                f"from the requested one; moving it more than max_shift={max_shift} would "
                f"sound wrong. Use a recording nearer the Sa you want."
            )
        return loop_drone(
            varispeed(rec, rec_sr, semitones=shift, sr_out=sr),
            sr,
            seconds,
            crossfade_s=crossfade_s,
        )

    return drone


def _as_drone(drone, sr: int) -> Callable:
    """A ``drone`` callable as is; a recording as ``(y, its_sr)``, or a bare array taken to be
    at ``sr``, made into one by :func:`recorded_drone` (analysed once, here)."""
    if callable(drone):
        return drone
    if isinstance(drone, tuple):
        return recorded_drone(*drone)
    return recorded_drone(drone, sr)


def highpass(
    y: np.ndarray, sr: int, cutoff_hz: float, *, width_hz: float | None = None
) -> np.ndarray:
    """``y`` with nothing left under ``cutoff_hz``: an FFT mask that is zero up to the cutoff
    and rises to one over the next ``width_hz`` (default half the cutoff) as a raised cosine, so
    there is no ringing edge."""
    if not len(y):
        raise ValueError("highpass needs a non-empty signal")
    width = cutoff_hz / 2 if width_hz is None else width_hz
    spectrum = np.fft.rfft(y)
    freqs = np.fft.rfftfreq(len(y), 1 / sr)
    rise = np.clip((freqs - cutoff_hz) / max(width, 1e-9), 0, 1)
    return np.fft.irfft(spectrum * np.sin(rise * np.pi / 2) ** 2, n=len(y))


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
        drone: ``(sa, *, seconds, sr) -> array`` (default :func:`tanpura`), or a recording,
            ``(y, its_sr)`` or an array at ``sr``, retuned to ``sa`` and looped by
            :func:`recorded_drone`.
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
    bed = _drone_bed(_as_drone(drone, sr), sa, n=len(melody), sr=sr)
    return _mix([(melody, melody_db), (bed, drone_db)], sr, peak=peak), sr


def _drone_bed(drone: Callable, sa, *, n: int, sr: int) -> np.ndarray:
    """``n`` samples of ``drone`` on ``sa``, trimmed or padded to length."""
    bed = drone(sa, seconds=n / sr, sr=sr)
    return np.pad(bed[:n], (0, max(0, n - len(bed))))


def _mix(parts, sr: int, *, peak: float) -> np.ndarray:
    """Sum ``(y, db)`` parts of equal length, each set to ``db`` of active RMS
    (``arioso.scoring.active_db``, frames within 40 dB of the loudest), then peak-normalized."""

    def at(y, db):
        level = active_db(y, sr, floor_rel_db=-40.0)
        return y * 10 ** ((db - level) / 20) if level > SILENCE_DB else y

    return _peak(sum(at(y, db) for y, db in parts), peak)


# --------------------------------------------------------------------------------------------
# A generator's own phrasing as the source


def musicgen_melody(
    audio: np.ndarray, sr: int, *, prompt: str, seconds: float
) -> tuple[np.ndarray, int]:
    """The default ``generate`` of :func:`musicgen_variation`: local MusicGen-melody following
    ``audio`` (``arioso.enhance(..., platform="musicgen")``), as mono ``(y, sr)``."""
    import arioso

    song = arioso.enhance(
        (audio, sr), prompt, platform="musicgen", as_="melody", duration=seconds
    )
    return to_audio_ref(song).as_mono()


def musicgen_variation(
    voice,
    sa: str | float,
    *,
    prompt: str,
    sr: int | None = None,
    transpose: float = 0.0,
    slow: float = 1.0,
    drone: Callable | np.ndarray = tanpura,
    voice_db: float = 0.0,
    drone_db: float = -8.0,
    seconds: float | None = None,
    max_seconds: float = 30.0,
    highpass_hz: float = float(midi_to_hz(DRONE_BAND_TOP_MIDI)),
    generate: Callable = musicgen_melody,
    peak: float = 0.9,
) -> tuple[np.ndarray, int]:
    """A cover source in a generator's own phrasing: MusicGen-melody following a voice over the
    drone, its low end removed so the drone alone carries the bottom. Returns ``(y, sr)``.

    A first take of this kind held the drone 94 % of the time, and generators covering it then
    held 77-83 %: the variation keeps the tune and the drone but sounds less like a synthesizer
    than :func:`melody_over_drone`.

    Args:
        voice: The sung line (a separated voice, e.g. by :func:`hdemucs_vocals`): an array with
            ``sr``, an ``(array, sample_rate)`` pair, a path, or a Song.
        sa: The drone's tonic.
        prompt: What the generator should make of it ("sarangi and soft tabla, slow").
        sr: The voice's sample rate when ``voice`` is a bare array.
        transpose: Semitones to move the voice onto Sa (pitch only, ``librosa``).
        slow: Stretch the voice by this factor (1.25 is a quarter slower; ``librosa``).
        drone: A ``(sa, *, seconds, sr)`` callable, or a recording, ``(y, its_sr)`` or an array
            at the voice's rate (see :func:`recorded_drone`).
        voice_db, drone_db: Levels in the conditioning mix and of the drone under the result.
        seconds: Length to generate; default the voice's, up to ``max_seconds`` (MusicGen's
            window).
        highpass_hz: The generated take keeps nothing under this, by default the top of the
            band ``drone_report`` reads, where its own bass and tenor would move the harmony. A
            take that follows a low (male) voice in its octave loses that melody too: move the
            voice up with ``transpose``.
        generate: ``(audio, sr, *, prompt, seconds) -> (y, sr)``; default :func:`musicgen_melody`.
        peak: Peak level of the result.
    """
    v, rate = to_audio_ref(voice if sr is None else (voice, sr)).as_mono()
    drone = _as_drone(drone, rate)
    if transpose or slow != 1:
        import librosa

        if transpose:
            v = librosa.effects.pitch_shift(v, sr=rate, n_steps=transpose)
        if slow != 1:
            v = librosa.effects.time_stretch(v, rate=1 / slow)
    seconds = min(seconds or len(v) / rate, max_seconds)
    v = v[: int(seconds * rate)]

    condition = _mix(
        [(v, voice_db), (_drone_bed(drone, sa, n=len(v), sr=rate), drone_db)],
        rate,
        peak=peak,
    )
    take, take_sr = generate(condition, rate, prompt=prompt, seconds=seconds)
    take = highpass(np.asarray(take, dtype=float), take_sr, highpass_hz)
    bed = _drone_bed(drone, sa, n=len(take), sr=take_sr)
    return _mix([(take, 0.0), (bed, drone_db)], take_sr, peak=peak), take_sr
