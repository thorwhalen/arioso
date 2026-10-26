"""The drone check on synthetic signals: a held drone passes, a chord change is caught, the key is read."""

import numpy as np

from arioso.analysis import drone_report

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
    r = drone_report(
        _tones([_hz(36), _hz(43), _hz(48)], 20), SR, sa="B"
    )  # a held C drone
    assert r.drone == ("C", "G") and r.sa_offset == 1 and r.holds()


def test_short_melody_note_off_drone_is_ignored():
    y = _tones(B_DRONE, 30)
    i, j = 10 * SR, int(11.5 * SR)
    y[i:j] += 3 * _tones([_hz(40)], 1.5)  # a loud E2 for 1.5 s
    assert drone_report(y, SR).off_runs == []
