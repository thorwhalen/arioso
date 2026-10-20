"""
Score a narration: music under speech, quiet while it talks, up in the pauses, with the pauses
timed so each spoken segment starts as a musical phrase begins.

Pure numpy over mono float arrays at one sample rate; ``read_audio`` / ``write_audio`` go through
ffmpeg. The steps, each usable alone:

- ``phrase_starts(music, sr)``: where phrases begin, found as a rise after a dip in loudness (a
  breath between phrases). Works on free-rhythm music (an alap) where beat trackers have nothing
  to hold on to. Any other finder (beat_this downbeats, allin1 sections) can replace it: the
  planner only needs a list of times.
- ``plan_starts(durations, phrases)``: the start of each segment, so each one enters ``lead_s``
  after a phrase start, with pauses between ``min_gap_s`` and ``max_gap_s``.
- ``duck_gain(n, sr, spans)``: a gain curve, ``under_db`` while speech plays and 0 dB between,
  with raised-cosine ramps that finish before the voice enters and start after it stops.
- ``score(segments, music, sr)``: all of the above, plus levels set relative to the speech's own
  loudness (``gap_rel_db`` between segments, ``under_rel_db`` under them); returns the mix and the
  timeline.

Research and alternatives: misc/docs/research/general/scoring-narration.md.

>>> plan_starts([10.0, 10.0], [4.0, 18.0, 30.0], intro_s=3.0, min_gap_s=3.0, max_gap_s=9.0, lead_s=0.5)
[4.5, 18.5]
"""

import os
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

import numpy as np

DFLT_SR = 44100
FRAME_S = 0.05  # loudness analysis hop
SILENCE_DB = -60.0


def read_audio(path: str | os.PathLike, sr: int = DFLT_SR) -> np.ndarray:
    """Decode any audio file to mono float32 at ``sr`` (needs ffmpeg)."""
    raw = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-f",
            "f32le",
            "-ac",
            "1",
            "-ar",
            str(sr),
            "pipe:1",
        ],
        capture_output=True,
        check=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def write_audio(
    path: str | os.PathLike, y: np.ndarray, sr: int = DFLT_SR, *, quality: str = "2", bitrate: str | None = None
) -> str:
    """Encode a mono float array to a file; MP3 or anything ffmpeg infers from the name.

    MP3 is VBR at ``quality`` unless ``bitrate`` (e.g. ``"128k"``) asks for constant bitrate, which
    browsers can seek precisely (VBR seeking goes through a coarse table and can land a second or
    more away from the requested time).
    """
    mp3 = ["-b:a", bitrate] if bitrate else ["-q:a", quality]
    codec = ["-c:a", "libmp3lame", *mp3] if str(path).lower().endswith(".mp3") else []
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "f32le",
            "-ac",
            "1",
            "-ar",
            str(sr),
            "-i",
            "pipe:0",
            *codec,
            str(path),
        ],
        input=np.asarray(y, dtype=np.float32).tobytes(),
        check=True,
    )
    return str(path)


def loudness_db(y: np.ndarray, sr: int, *, frame_s: float = FRAME_S) -> np.ndarray:
    """Frame RMS in dBFS, one value per ``frame_s``."""
    hop = max(1, int(frame_s * sr))
    n = len(y) // hop
    if n == 0:
        return np.array([SILENCE_DB])
    frames = y[: n * hop].reshape(n, hop)
    rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1))
    return np.maximum(20 * np.log10(rms + 1e-12), SILENCE_DB)


def active_db(y: np.ndarray, sr: int, *, floor_db: float = -45.0) -> float:
    """RMS level (dBFS) over the frames that are not near-silent: the level of the sound itself."""
    db = loudness_db(y, sr)
    active = db[db > floor_db]
    if not len(active):
        return SILENCE_DB
    return float(10 * np.log10(np.mean(10 ** (active / 10))))


def _smooth(x: np.ndarray, n: int) -> np.ndarray:
    if n <= 1:
        return x
    pad = np.pad(x, (n // 2, n - 1 - n // 2), mode="edge")
    return np.convolve(pad, np.ones(n) / n, mode="valid")


def phrase_starts(
    music: np.ndarray,
    sr: int,
    *,
    smooth_s: float = 0.6,
    depth_db: float = 4.0,
    window_s: float = 2.5,
    min_spacing_s: float = 3.0,
) -> list[float]:
    """Times (s) where musical phrases begin: the rise after a dip in loudness.

    A low point counts when the smoothed loudness rises at least ``depth_db`` above it within the
    next ``window_s`` (after a breath, or out of a quiet stretch). The phrase starts where loudness
    has climbed halfway up. Starts closer than ``min_spacing_s`` keep the one with the larger rise.
    """
    db = _smooth(loudness_db(music, sr), max(1, int(smooth_s / FRAME_S)))
    w = max(1, int(window_s / FRAME_S))
    found = []  # (time, depth)
    for i in range(1, len(db) - 1):
        if not (db[i] <= db[i - 1] and db[i] < db[i + 1]):
            continue
        after = db[i + 1 : i + 1 + w]
        if not len(after):
            continue
        depth = after.max() - db[i]
        if depth < depth_db:
            continue
        target = db[i] + (after.max() - db[i]) / 2
        j = i + 1 + int(np.argmax(after >= target))
        found.append((j * FRAME_S, depth))
    kept: list[tuple[float, float]] = []
    for t, depth in sorted(found):
        if kept and t - kept[-1][0] < min_spacing_s:
            if depth > kept[-1][1]:
                kept[-1] = (t, depth)
            continue
        kept.append((t, depth))
    return [round(t, 2) for t, _ in kept]


def plan_starts(
    durations: Sequence[float],
    phrases: Iterable[float] = (),
    *,
    intro_s: float = 5.0,
    min_gap_s: float = 3.0,
    max_gap_s: float = 8.0,
    gap_s: float = 4.5,
    lead_s: float = 0.6,
) -> list[float]:
    """When each segment starts, so it enters ``lead_s`` after a phrase start.

    The first segment starts at or after ``intro_s``, each next one between ``min_gap_s`` and
    ``max_gap_s`` after the previous ends (at the phrase closest to ``gap_s``). Where no phrase falls
    in the window, the pause is ``gap_s``.
    """
    phrases = sorted(phrases)
    starts: list[float] = []
    for k, d in enumerate(durations):
        if k == 0:
            lo, hi, preferred = intro_s, intro_s + max_gap_s, intro_s
        else:
            end = starts[-1] + durations[k - 1]
            lo, hi, preferred = end + min_gap_s, end + max_gap_s, end + gap_s
        candidates = [p + lead_s for p in phrases if lo <= p + lead_s <= hi]
        start = (
            min(candidates, key=lambda c: abs(c - preferred))
            if candidates
            else preferred
        )
        starts.append(round(start, 2))
    return starts


def _merge(spans: Iterable[tuple[float, float]], bridge_s: float) -> list[list[float]]:
    merged: list[list[float]] = []
    for s, e in sorted(spans):
        if merged and s - merged[-1][1] <= bridge_s:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged


def _ramp(t: np.ndarray, t0: float, t1: float) -> np.ndarray:
    """0 before t0, 1 after t1, a raised cosine between."""
    if t1 <= t0:
        return (t >= t0).astype(float)
    x = np.clip((t - t0) / (t1 - t0), 0, 1)
    return 0.5 - 0.5 * np.cos(np.pi * x)


def duck_gain(
    n: int,
    sr: int,
    spans: Iterable[tuple[float, float]],
    *,
    under_db: float = -14.0,
    ramp_down_s: float = 1.5,
    ramp_up_s: float = 2.0,
    pre_s: float = 0.3,
    post_s: float = 0.4,
    fade_in_s: float = 2.0,
    fade_out_s: float = 4.0,
    end_s: float | None = None,
    control_hz: int = 100,
) -> np.ndarray:
    """A linear gain per sample: 1 between spans, ``under_db`` during them, gentle ramps.

    Each ramp down ends ``pre_s`` before speech starts; each ramp up starts ``post_s`` after it
    stops. Pauses too short for both ramps stay ducked. The music fades in over ``fade_in_s`` and,
    if ``end_s`` is given, fades out over ``fade_out_s`` ending there.
    """
    t = np.arange(int(np.ceil(n / sr * control_hz)) + 1) / control_hz
    duck = np.zeros_like(t)  # 0 = gap level, 1 = fully under
    bridge = ramp_down_s + ramp_up_s + pre_s + post_s
    for s, e in _merge(spans, bridge):
        down = _ramp(t, s - pre_s - ramp_down_s, s - pre_s)
        up = 1 - _ramp(t, e + post_s, e + post_s + ramp_up_s)
        duck = np.maximum(duck, np.minimum(down, up))
    gain_db = duck * under_db
    gain = 10 ** (gain_db / 20) * _ramp(t, 0, fade_in_s)
    if end_s is not None:
        gain *= 1 - _ramp(t, end_s - fade_out_s, end_s)
    return np.interp(np.arange(n) / sr, t, gain).astype(np.float32)


@dataclass
class Scored:
    """A scored narration: the mix and its timeline (seconds)."""

    mix: np.ndarray
    sr: int
    starts: list[float]
    durations: list[float]
    phrases: list[float] = field(default_factory=list)
    music_gain_db: float = 0.0

    @property
    def spans(self) -> list[tuple[float, float]]:
        return [(s, s + d) for s, d in zip(self.starts, self.durations)]

    @property
    def seconds(self) -> float:
        return len(self.mix) / self.sr


def score(
    segments: Sequence[np.ndarray],
    music: np.ndarray,
    sr: int,
    *,
    phrases: Sequence[float] | None = None,
    starts: Sequence[float] | None = None,
    gap_rel_db: float = -12.0,
    under_rel_db: float = -26.0,
    outro_s: float = 6.0,
    peak: float = 0.95,
    plan_kwargs: dict | None = None,
    duck_kwargs: dict | None = None,
) -> Scored:
    """Lay ``segments`` (spoken parts, in order) over ``music``, ducked and phrase-timed.

    Music sits ``gap_rel_db`` below the speech's level between segments and ``under_rel_db`` below
    it during them (levels are RMS over non-silent frames). ``phrases`` default to
    ``phrase_starts(music)``; ``starts`` (given) skip the planning. The mix lasts until ``outro_s``
    after the last segment, where the music fades out; music shorter than that fades at its end.
    """
    durations = [len(s) / sr for s in segments]
    if phrases is None:
        phrases = phrase_starts(music, sr)
    if starts is None:
        starts = plan_starts(durations, phrases, **(plan_kwargs or {}))
    if len(starts) != len(segments):
        raise ValueError(f"{len(starts)} starts for {len(segments)} segments")
    end_s = starts[-1] + durations[-1] + outro_s
    n = int(np.ceil(end_s * sr))
    voice = np.zeros(n, dtype=np.float32)
    for s, seg in zip(starts, segments):
        i = int(round(s * sr))
        voice[i : i + len(seg)] += seg[: n - i]
    speech_db = active_db(np.concatenate(list(segments)), sr)
    music_db = active_db(music, sr)
    music_gain_db = speech_db + gap_rel_db - music_db
    bed = np.zeros(n, dtype=np.float32)
    bed[: min(n, len(music))] = music[:n]
    music_end = min(end_s, len(music) / sr)
    gain = duck_gain(
        n,
        sr,
        [(s, s + d) for s, d in zip(starts, durations)],
        under_db=under_rel_db - gap_rel_db,
        end_s=music_end,
        **(duck_kwargs or {}),
    )
    mix = voice + bed * gain * 10 ** (music_gain_db / 20)
    top = float(np.max(np.abs(mix))) if len(mix) else 0.0
    if top > peak:
        mix *= peak / top
    return Scored(
        mix.astype(np.float32),
        sr,
        list(starts),
        durations,
        list(phrases),
        round(music_gain_db, 1),
    )
