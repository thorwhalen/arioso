"""Melody-over-drone seeds on synthetic signals (thorwhalen/arioso#27).

The contour cleaning, the score skyline, the drone and the render are numpy only; the f0 tracker is
faked so the recording path runs without librosa. The drone check and melody check close the loop:
a rendered seed must hold its drone, and a low line must be lifted out of it.
"""

import numpy as np
import pytest

from arioso.analysis import drone_report
from arioso.seeds import (
    Contour,
    audio_contour,
    drop_blips,
    fix_octaves,
    loop_drone,
    melody_contour,
    melody_over_drone,
    notes_contour,
    sa_midi,
    tanpura,
    tuning_offset,
)

SR = 8000
NAN = np.nan


def test_drop_blips_silences_short_stretches():
    midi = np.array([60.0] * 5 + [NAN] * 3 + [62.0] * 30)
    out = drop_blips(midi, fps=100, min_s=0.12)
    assert np.all(np.isnan(out[:8])) and np.all(out[8:] == 62.0)


def test_fix_octaves_moves_jumps_back():
    midi = np.full(100, 62.0)
    midi[40:45] = 74.0  # tracker jumped an octave up
    midi[70:72] = 38.0  # and two down
    out = fix_octaves(midi, fps=100, window_s=0.5)
    assert np.allclose(out, 62.0)


def test_tuning_offset_is_circular():
    assert tuning_offset(np.array([60.3, 62.3, NAN, 64.3])) == pytest.approx(0.3)
    # 49 cents sharp and 49 flat average to the quarter-tone, not to in-tune
    assert abs(tuning_offset(np.array([60.49, 61.51]))) == pytest.approx(0.5)


def _fake_tracker(f0_hz, voiced, fps=100.0):
    def track(y, sr):
        return f0_hz, voiced, fps

    return track


def test_audio_contour_gates_cleans_and_retunes():
    fps, n = 100.0, 300
    f0 = np.full(n, 440.0 * 2 ** (0.2 / 12))  # A4, 20 cents sharp
    f0[100:105] = 880.0 * 2 ** (0.2 / 12)  # an octave slip
    voiced = np.ones(n, bool)
    voiced[200:203] = False  # a 30 ms gap
    y = np.ones(int(n / fps * SR))
    y[int(2.5 * SR) :] = 0.0  # silence the tracker still calls voiced: gated

    c = audio_contour(
        (y, SR), separator=None, f0_tracker=_fake_tracker(f0, voiced, fps)
    )

    assert c.fps == fps and len(c.midi) == n
    assert np.allclose(c.midi[:200][~np.isnan(c.midi[:200])], 69.0)
    assert np.all(np.isnan(c.midi[260:]))


def test_audio_contour_runs_the_separator():
    seen = {}

    def separator(y, sr):
        seen["shape"] = np.shape(y)
        return np.ones(SR), SR

    track = _fake_tracker(np.full(100, 220.0), np.ones(100, bool))
    c = audio_contour((np.ones((SR, 2)), SR), separator=separator, f0_tracker=track)
    assert seen["shape"] == (SR, 2)
    assert np.allclose(c.midi, 57.0)


def test_notes_contour_skyline_glide_and_vibrato():
    notes = [(0.0, 2.0, 55), (0.5, 1.0, 67), (2.0, 3.0, 60)]  # 67 sits over 55
    c = notes_contour(
        notes, fps=100, glide_s=0.1, vibrato_delay_s=0.3, vibrato_semitones=0.2
    )
    assert c.midi[20] == 55 and c.midi[70] == 67  # the highest note sounds
    assert 55 < c.midi[201] < 60  # glides from 55 into the touching 60
    assert c.midi[215] == 60
    late = c.midi[260:300]
    assert 0.3 < late.max() - late.min() <= 0.4  # vibrato, +-0.2 once ramped in


def test_notes_contour_needs_notes():
    with pytest.raises(ValueError):
        notes_contour([])


def test_melody_contour_sends_midi_to_the_score_path(monkeypatch):
    import arioso.seeds as seeds

    monkeypatch.setattr(seeds, "midi_contour", lambda src, **kw: ("midi", src))
    monkeypatch.setattr(seeds, "audio_contour", lambda src, sr, **kw: ("audio", src))
    assert melody_contour("song.MID")[0] == "midi"
    assert melody_contour(b"MThd\x00\x00")[0] == "midi"
    assert melody_contour("song.wav")[0] == "audio"


def test_sa_midi():
    assert sa_midi("C#") == 49 and sa_midi("Db", octave=4) == 61 and sa_midi(50) == 50


def test_tanpura_holds_its_drone():
    r = drone_report(tanpura("C#", seconds=20, sr=SR), SR, sa="C#")
    assert r.drone == ("C#", "G#") and r.sa_offset == 0 and r.holds()


def test_tanpura_ma_tuning():
    r = drone_report(tanpura("D", second=5, seconds=20, sr=SR), SR, sa="D")
    assert set(r.drone) == {"D", "G"} and r.sa_offset == 0


def test_loop_drone_length_and_smooth_joins():
    t = np.arange(3 * SR) / SR
    y = np.sin(2 * np.pi * 110 * t) * (0.5 + 0.1 * t)  # rises: joins must not jump
    out = loop_drone(y, SR, 10, crossfade_s=0.5)
    assert len(out) == 10 * SR
    assert np.max(np.abs(np.diff(out))) < 2 * np.max(np.abs(np.diff(y)))
    with pytest.raises(ValueError):
        loop_drone(y[: SR // 2], SR, 10, crossfade_s=0.5)


def _tune(seconds=12.0, base=50):
    """A slow line of whole notes around ``base`` (a low, male-register melody)."""
    steps = [0, 2, 4, 5, 7, 5, 4, 2]
    dur = seconds / len(steps)
    return notes_contour(
        [(i * dur, (i + 1) * dur - 0.1, base + s) for i, s in enumerate(steps)]
    )


def test_melody_over_drone_lifts_a_low_line_out_of_the_drone():
    y, sr = melody_over_drone(_tune(), "D", sr=SR)
    assert sr == SR and np.max(np.abs(y)) == pytest.approx(0.9)
    r = drone_report(y, sr, sa="D")
    assert r.drone == ("D", "A") and r.holds()

    low, _ = melody_over_drone(_tune(), "D", sr=SR, floor_midi=None)
    assert not drone_report(low, SR, sa="D").holds()


def test_melody_over_drone_takes_a_recorded_bed():
    bed = tanpura("D", seconds=4, sr=SR)  # shorter than the melody: looped
    y, _ = melody_over_drone(_tune(), "D", sr=SR, drone=bed, lead_in_s=0)
    assert len(y) == pytest.approx(_tune().seconds * SR, abs=2)


def test_contour_at_rate_holds_into_silence():
    c = Contour(midi=np.array([60.0, 62.0, NAN, 64.0]), fps=1.0)
    p = c.at_rate(4)
    assert p[0] == 60 and p[2] == 61  # interpolates inside a note
    assert np.all(p[4:8] == 62.0)  # holds up to the silence
    assert np.all(np.isnan(p[8:12])) and np.all(p[12:] == 64)


def test_melody_match_ranks_the_right_seed():
    pytest.importorskip("librosa")
    from arioso.analysis import melody_match

    seed, sr = melody_over_drone(_tune(base=62), "D", sr=SR)
    slower = Contour(midi=_tune(base=62).midi, fps=100 / 1.1)
    take, _ = melody_over_drone(slower, "D", sr=SR, drone_db=-4)
    other_notes = [
        (i * 1.5, i * 1.5 + 1.4, 62 + s)
        for i, s in enumerate([7, 0, 9, 3, 11, 1, 8, 2])
    ]
    other, _ = melody_over_drone(notes_contour(other_notes), "D", sr=SR)
    assert melody_match(take, seed, sr) > melody_match(other, seed, sr) + 0.1
