"""The drone check on synthetic signals: a held drone passes, a chord change is caught, the key is read."""

import numpy as np

import pytest

from arioso.analysis import drone_report, drone_sa, drone_tonic

SR = 4000


def _tones(freqs, seconds):
    t = np.arange(int(seconds * SR)) / SR
    return sum(np.sin(2 * np.pi * f * t) for f in freqs)


def _hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


B_DRONE = [_hz(35), _hz(42), _hz(47)]  # B1, F#2, B2
C_CHORD = [_hz(36), _hz(43), _hz(48), _hz(52)]  # C2, G2, C3, E3


def test_held_drone_has_no_runs():
    r = drone_report(_tones(B_DRONE, 30), SR, sa="B")
    assert r.drone == ("B", "F#") and r.sa_offset == 0
    assert r.off_runs == [] and r.holds()


def test_chord_change_is_one_run():
    y = np.concatenate([_tones(B_DRONE, 20), _tones(C_CHORD, 8), _tones(B_DRONE, 20)])
    r = drone_report(y, SR, sa="B")
    assert r.drone == ("B", "F#")
    assert len(r.off_runs) == 1
    a, b = r.off_runs[0]
    assert abs(a - 20) < 1.5 and abs(b - 28) < 1.5
    assert not r.holds()


def test_off_key_drone_reports_offset():
    r = drone_report(_tones([_hz(36), _hz(43), _hz(48)], 20), SR, sa="B")  # a held C drone
    assert r.drone == ("C", "G") and r.sa_offset == 1 and r.holds()


def test_short_melody_note_off_drone_is_ignored():
    y = _tones(B_DRONE, 30)
    i, j = 10 * SR, int(11.5 * SR)
    y[i:j] += 3 * _tones([_hz(40)], 1.5)  # a loud E2 for 1.5 s
    assert drone_report(y, SR).off_runs == []


def test_sa_is_the_lower_note_of_the_fifth_even_when_pa_is_louder():
    # Sa E soft, Pa B loud: "the stronger of the pair" would call B the Sa
    y = _tones([_hz(40), _hz(52)], 20) * 0.4 + _tones([_hz(47)], 20)
    r = drone_report(y, SR)
    assert r.drone == ("E", "B")
    assert drone_sa(y, SR) == "E"


def test_a_requested_sa_wins_over_the_pa_reading():
    y = _tones([_hz(40), _hz(52)], 20) * 0.4 + _tones([_hz(47)], 20)
    r = drone_report(y, SR, sa="B")  # told the Sa is B, so B leads and E is 5 below it
    assert r.drone == ("B", "E") and r.sa_offset == 0


def _stiff_string(midi, *, stiffness, partials, seconds=8, sr=8000):
    """Partial ``h`` of a stiff string sits at ``h * f0 * sqrt(1 + B h**2)``; ``partials``
    maps ``h`` to its gain. Returns the signal (a weak fundamental, a strong second partial)."""
    t = np.arange(int(seconds * sr)) / sr
    f0 = _hz(midi)
    return sum(
        gain * np.sin(2 * np.pi * h * f0 * np.sqrt(1 + stiffness * h * h) * t)
        for h, gain in partials.items()
    )


def test_drone_tonic_takes_the_lowest_copy_not_the_stiffest():
    # the strongest copy is the 2nd partial, about 6 cents sharp; the 1st is within 2
    y = _stiff_string(40, stiffness=0.0017, partials={1: 0.3, 2: 1.0, 4: 0.8})
    assert drone_tonic(y, 8000, sa="E") == pytest.approx(4.0, abs=0.03)
    strongest_only = drone_tonic(y, 8000, sa="E", lowest_rel=1.0)
    assert strongest_only == pytest.approx(4.06, abs=0.02)


def test_drone_tonic_ignores_a_lowest_copy_that_is_only_noise():
    y = _stiff_string(40, stiffness=0.0017, partials={1: 0.01, 2: 1.0})
    assert drone_tonic(y, 8000, sa="E") == pytest.approx(4.06, abs=0.02)
