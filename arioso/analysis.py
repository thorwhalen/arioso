"""
Check generated music before anyone listens to it. Does a take hold one drone (``drone_report``)?
Does it keep its seed's melody (``melody_match``)?

Generators ignore "no chord changes": asked for one unchanging drone (Hindustani raga music, say),
they still move the harmony in blocks. ``drone_report`` measures it from the bass alone:

- the bass chroma (pitch classes from C1 to B3) over time, median-smoothed over ``smooth_s``;
- the drone pair actually played: the two pitch classes a fifth (or a fourth) apart that carry the
  most bass energy (Sa: the requested ``sa`` if it is one of them, else the lower note of the fifth,
  which is Sa in the usual Pa tuning even when the Pa string is the louder), and its offset from a
  requested ``sa`` (a static but off-key take can be transposed, a moving one cannot);
- the off-drone runs: stretches of at least ``min_run_s`` where the bass's strongest pitch class
  leaves the pair, or the pair's share of the bass falls under ``min_share``. Those are the
  harmony moves.

A held drone scores ``off_ratio == 0`` with no runs. Pure numpy over a mono float array; read files
with ``arioso.scoring.read_audio``.

``melody_match`` compares the treble (C4 to B6) chroma of a take and of its seed, each pitch class
less its steady background so the drone does not count, aligned by dynamic time warping, and
returns their mean cosine similarity along the path. On a melody-over-drone seed: the separated
voice it was made from scored 0.88, a slower re-timbred render 0.94, another song's seed or the
drone alone about 0.43. It needs ``librosa`` for the warping.

>>> sr = 4000
>>> t = np.arange(20 * sr) / sr
>>> drone = sum(np.sin(2 * np.pi * f * t) for f in (61.7, 92.5, 123.5))  # B1, F#2, B2
>>> r = drone_report(drone, sr, sa="B")
>>> r.drone, r.sa_offset, r.off_runs
(('B', 'F#'), 0, [])
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

from arioso._audio import hz_to_midi

NOTES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
_FLATS = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#", "H": "B"}
C1_HZ = 32.703
C4_HZ = 261.626
#: Semitones of a perfect fifth and of its inversion, a fourth.
FIFTH, FOURTH = 7, 5


@dataclass
class DroneReport:
    """What ``drone_report`` found. Times are in seconds; ``chroma`` is kept for plotting."""

    drone: tuple[str, str]
    sa_offset: int | None  # semitones from the requested sa to the played one, in -5..6
    on_drone_share: float  # share of the playing frames that stay on the drone
    off_runs: list[tuple[float, float]]
    off_seconds: float
    off_ratio: float  # off_seconds over the playing time
    playing_seconds: float
    fps: float = field(repr=False)
    chroma: np.ndarray = field(repr=False)

    def holds(self, *, max_off_ratio: float = 0.0, max_runs: int = 0) -> bool:
        """True when the take stays on its drone within the given tolerances."""
        return self.off_ratio <= max_off_ratio and len(self.off_runs) <= max_runs

    def to_dict(self) -> dict:
        """JSON-friendly summary (no chroma)."""
        return {
            "drone": list(self.drone),
            "sa_offset": self.sa_offset,
            "on_drone_share": round(self.on_drone_share, 3),
            "off_runs": [[round(a, 1), round(b, 1)] for a, b in self.off_runs],
            "off_seconds": round(self.off_seconds, 1),
            "off_ratio": round(self.off_ratio, 3),
            "playing_seconds": round(self.playing_seconds, 1),
        }


def pitch_class(name: str) -> int:
    """Index of a note name in ``NOTES`` (sharps, flats, or German H).

    >>> pitch_class("F#"), pitch_class("Gb"), pitch_class("H")
    (6, 6, 11)
    """
    note = _FLATS.get(name, name)
    if note not in NOTES:
        raise ValueError(
            f"not a note name: {name!r}; use one of {NOTES} (or a flat, or H)"
        )
    return NOTES.index(note)


def bass_chroma(
    y: np.ndarray,
    sr: int,
    *,
    octaves: int = 3,
    fmin_hz: float = C1_HZ,
    window_s: float = 1.5,
    hop_s: float = 0.2,
) -> tuple[np.ndarray, float]:
    """Pitch-class energy of the bass, ``octaves`` up from ``fmin_hz``: a (12, frames) array and its fps.

    A long-window STFT, each bin assigned to its nearest semitone. The window must be long enough to
    split semitones at the bottom (C1 to C#1 is 1.9 Hz): 1.5 s gives 0.67 Hz bins.
    """
    y = np.asarray(y, dtype=np.float64)
    n_fft = int(2 ** np.ceil(np.log2(window_s * sr)))
    hop = max(1, int(hop_s * sr))
    if len(y) < n_fft:
        y = np.pad(y, (0, n_fft - len(y)))
    frames = np.lib.stride_tricks.sliding_window_view(y, n_fft)[::hop]
    spec = np.abs(np.fft.rfft(frames * np.hanning(n_fft), axis=1)) ** 2
    freqs = np.fft.rfftfreq(n_fft, 1 / sr)
    semis = 12 * np.log2(np.maximum(freqs, 1e-9) / fmin_hz)
    keep = (semis > -0.5) & (semis < 12 * octaves - 0.5)
    pcs = np.round(semis[keep]).astype(int) % 12
    chroma = np.zeros((12, len(frames)))
    np.add.at(chroma, pcs, spec[:, keep].T)
    # fmin_hz is C1 by default; shift so row 0 is C whatever fmin is
    shift = int(round(12 * np.log2(fmin_hz / C1_HZ))) % 12
    return np.roll(np.sqrt(chroma), shift, axis=0), sr / hop


def _median_filter_rows(x: np.ndarray, n: int) -> np.ndarray:
    if n <= 1:
        return x
    pad = np.pad(x, ((0, 0), (n // 2, n - 1 - n // 2)), mode="edge")
    return np.median(np.lib.stride_tricks.sliding_window_view(pad, n, axis=1), axis=2)


def index_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """``(start, end)`` index pairs of the runs of True in a boolean mask (end exclusive).

    >>> index_runs(np.array([0, 1, 1, 0, 1], bool))
    [(1, 3), (4, 5)]
    """
    edges = np.diff(np.concatenate([[0], mask.astype(int), [0]]))
    starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    return [(int(a), int(b)) for a, b in zip(starts, ends)]


def _runs(mask: np.ndarray, fps: float, min_len_s: float) -> list[tuple[float, float]]:
    return [
        (a / fps, b / fps) for a, b in index_runs(mask) if (b - a) / fps >= min_len_s
    ]


def drone_report(
    y: np.ndarray,
    sr: int,
    *,
    sa: str | None = None,
    min_run_s: float = 3.0,
    smooth_s: float = 2.0,
    min_share: float = 0.35,
    loud_rel: float = 0.05,
    intervals: Sequence[int] = (FIFTH, FOURTH),
) -> DroneReport:
    """Does ``y`` hold one drone? See the module docstring for the measure.

    Args:
        y: Mono audio.
        sr: Its sample rate.
        sa: The requested tonic (``"B"``, ``"F#"``, ``"Gb"``, ``"H"``), to report ``sa_offset``.
        min_run_s: Shortest off-drone stretch counted as a harmony move.
        smooth_s: Median smoothing of the chroma, so passing melody notes do not count.
        min_share: The drone pair's share of bass energy under which a frame is off the drone.
        loud_rel: Frames quieter than this fraction of the 95th-percentile level are ignored
            (silences, fades).
        intervals: Semitones between the drone's two notes to consider (fifth, fourth).
    """
    chroma, fps = bass_chroma(y, sr)
    chroma = _median_filter_rows(chroma, int(smooth_s * fps))
    level = chroma.sum(0)
    loud = level > loud_rel * np.percentile(level, 95)
    total = chroma[:, loud].sum(1)
    root, iv = max(
        ((k, iv) for k in range(12) for iv in intervals),
        key=lambda p: total[p[0]] + total[(p[0] + p[1]) % 12],
    )
    # Sa: the requested one when it is in the pair (a Ma tuning plays Sa and its fourth below),
    # else the lower note of the fifth: the Pa tuning's Sa, whichever string is louder
    want = pitch_class(sa) if sa is not None else None
    pair = [root, (root + iv) % 12]
    if (pair[1] - pair[0]) % 12 == FOURTH:
        pair.reverse()
    pair.sort(key=lambda k: k != want)
    root = pair[0]
    share = chroma[pair].sum(0) / np.maximum(level, 1e-12)
    off = loud & (~np.isin(chroma.argmax(0), pair) | (share < min_share))
    runs = _runs(off, fps, min_run_s)
    off_s = sum(b - a for a, b in runs)
    playing_s = loud.sum() / fps
    offset = None if want is None else (root - want + 5) % 12 - 5
    return DroneReport(
        drone=(NOTES[pair[0]], NOTES[pair[1]]),
        sa_offset=offset,
        on_drone_share=float(np.mean(~off[loud])) if loud.any() else 0.0,
        off_runs=runs,
        off_seconds=off_s,
        off_ratio=off_s / playing_s if playing_s else 0.0,
        playing_seconds=playing_s,
        fps=fps,
        chroma=chroma,
    )


def drone_sa(y: np.ndarray, sr: int, **report_kwargs) -> str:
    """The Sa of a drone recording, assuming the usual Pa tuning: ``drone_report``'s first
    note, the lower one of the fifth it finds (whichever string is louder). A Ma-tuned
    recording reads as its Ma; name its Sa instead."""
    return drone_report(y, sr, **report_kwargs).drone[0]


def drone_tonic(
    y: np.ndarray,
    sr: int,
    *,
    sa: str | None = None,
    band_midi: tuple = (36, 72),
    lowest_rel: float = 0.1,
) -> float:
    """The tonic of a drone recording as a fractional pitch class (0 = C, 4.45 = E 45 cents
    sharp): the Sa of :func:`drone_sa` (or the given ``sa`` name), refined to a spectral peak
    within half a semitone of it in ``band_midi``, interpolated between bins.

    Sa sounds in every octave of the band, and a stiff string's upper partials run sharp (about
    6 cents at the second partial of a thick string), so the strongest copy reads sharp. The
    estimate is the lowest copy whose peak is at least ``lowest_rel`` of the strongest one's,
    the least stretched that still stands out of the noise.

    The band is half-open, ``[band_midi[0], band_midi[1])``: a copy a few cents under its
    bottom edge is not seen. (Unlike ``librosa.estimate_tuning``, which gives one offset for all
    pitches, this follows one pitch class through its octave copies.)

    Raises when there is no peak there (silence, or an ``sa`` the recording does not play):
    the strongest bin would then sit on the window's edge and the estimate would be a guess.
    """
    if not 0 < lowest_rel <= 1:
        raise ValueError(f"lowest_rel must be in (0, 1], got {lowest_rel}")
    pc = pitch_class(sa) if sa is not None else pitch_class(drone_sa(y, sr))
    spectrum = np.abs(np.fft.rfft(np.asarray(y, dtype=float) * np.hanning(len(y))))
    midi = hz_to_midi(np.fft.rfftfreq(len(y), 1 / sr))
    in_band = (midi >= band_midi[0]) & (midi < band_midi[1])
    near = in_band & (np.abs((midi - pc + 6) % 12 - 6) < 0.5)
    near[[0, -1]] = False  # a peak needs a bin on each side
    copies = np.round((midi - pc) / 12)  # which octave's window a bin is in
    peaks = []  # (bin of an octave copy's strongest peak, in ascending pitch)
    for octave in np.unique(copies[near]):
        window = np.flatnonzero(near & (copies == octave))
        k = int(window[np.argmax(spectrum[window])])
        if spectrum[k] > spectrum[k - 1] and spectrum[k] > spectrum[k + 1]:
            peaks.append(k)
    if not peaks:
        raise ValueError(f"no spectral peak at {NOTES[pc]} in the recording")
    strongest = max(spectrum[k] for k in peaks)
    k = next(k for k in peaks if spectrum[k] >= lowest_rel * strongest)
    a, b, c = np.log(spectrum[k - 1 : k + 2] + 1e-12)
    bin_offset = float(np.clip(0.5 * (a - c) / (a - 2 * b + c), -0.5, 0.5))
    return float(hz_to_midi((k + bin_offset) * sr / len(y)) % 12)


#: DTW steps for melody_match: without single steps the path's slope stays within [1/2, 2], so a
#: take may run at half to double its seed's tempo but cannot sit on one frame (as in denote.align).
_MELODY_STEPS = np.array([[1, 1], [1, 2], [2, 1]])


def melody_match(
    take: np.ndarray,
    seed: np.ndarray,
    sr: int,
    *,
    seed_sr: int | None = None,
    fmin_hz: float = C4_HZ,
    octaves: int = 3,
    window_s: float = 0.2,
    hop_s: float = 0.1,
    loud_rel: float = 0.05,
    background_pct: float = 20.0,
) -> float:
    """How well a take keeps its seed's melody: mean cosine similarity of their treble chroma
    along a DTW alignment, so tempo drift does not count against it.

    The shorter of the two is aligned as a subsequence of the longer (both ways, keeping the
    better, when they are as long), so the score does not depend on argument order and an intro
    or outro on the longer side does not count against it. A take that holds only part of its
    seed's melody, inside material of its own, scores lower.

    Each pitch class's ``background_pct`` percentile over time is removed first: a drone's
    partials reach the treble band and sit there throughout, and without this a take with the
    drone and no melody scores nearly as well as a real one. (A low percentile, not the median,
    so the melody's most-held note, often Sa, is not removed with the drone.)

    Args:
        take: Mono audio of the generated take.
        seed: Mono audio of the seed it covered.
        sr: The take's sample rate (and the seed's, unless ``seed_sr`` is given).
        fmin_hz, octaves: The band read, C4 up three octaves by default: above the drone, where
            the melody is.
        window_s, hop_s: Chroma frame length and step.
        loud_rel: Frames quieter than this fraction of the 95th-percentile level are dropped.
        background_pct: Percentile of each pitch class removed as the steady background.
    """
    import librosa

    def melody_chroma(y, rate):
        chroma, _ = bass_chroma(
            y, rate, octaves=octaves, fmin_hz=fmin_hz, window_s=window_s, hop_s=hop_s
        )
        level = chroma.sum(0)
        chroma = chroma[:, level > loud_rel * np.percentile(level, 95)]
        background = np.percentile(chroma, background_pct, axis=1, keepdims=True)
        chroma = np.maximum(chroma - background, 0)
        return chroma / np.maximum(np.linalg.norm(chroma, axis=0), 1e-12)

    def inside(query, ref):  # query no longer than ref, or librosa transposes the path
        similarity = query.T @ ref
        _, path = librosa.sequence.dtw(
            C=1 - similarity, subseq=True, step_sizes_sigma=_MELODY_STEPS
        )
        return float(np.mean(similarity[path[:, 0], path[:, 1]]))

    a, b = melody_chroma(take, sr), melody_chroma(seed, seed_sr or sr)
    if a.shape[1] < 2 or b.shape[1] < 2:
        raise ValueError("take or seed has fewer than two playing frames to compare")
    if a.shape[1] == b.shape[1]:
        return max(inside(a, b), inside(b, a))
    return inside(*sorted((a, b), key=lambda c: c.shape[1]))
