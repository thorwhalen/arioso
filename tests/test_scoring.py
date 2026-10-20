"""Scoring a narration on synthetic signals: phrases, planning, ducking and the mix."""

import numpy as np
import pytest

from arioso.scoring import duck_gain, phrase_starts, plan_starts, score

SR = 8000


def _phrased_music(phrase_times, total_s=40.0, phrase_s=4.0):
    """Tone bursts starting at ``phrase_times`` over a faint bed: phrases with breaths between."""
    t = np.arange(int(total_s * SR)) / SR
    y = 0.003 * np.sin(2 * np.pi * 110 * t)
    for p in phrase_times:
        m = (t >= p) & (t < p + phrase_s)
        y[m] += 0.3 * np.sin(2 * np.pi * 220 * t[m])
    return y.astype(np.float32)


def test_phrase_starts_finds_the_rises():
    found = phrase_starts(_phrased_music([5.0, 12.0, 20.0, 30.0]), SR)
    assert len(found) == 4 and np.allclose(found, [5.0, 12.0, 20.0, 30.0], atol=0.5)


def test_plan_starts_snaps_to_phrases_within_bounds():
    starts = plan_starts([6.0, 6.0, 6.0], [5.0, 14.0, 40.0], intro_s=4.0, min_gap_s=2.0, max_gap_s=6.0,
                         gap_s=3.0, lead_s=0.5)
    assert starts[0] == 5.5 and starts[1] == 14.5  # both on phrases
    assert starts[2] == pytest.approx(14.5 + 6.0 + 3.0)  # no phrase in reach: the default pause


def test_duck_gain_levels_and_ramps():
    g = duck_gain(SR * 30, SR, [(10.0, 20.0)], under_db=-20.0, fade_in_s=0.0)
    at = lambda s: float(g[int(s * SR)])  # noqa: E731
    assert at(5.0) == pytest.approx(1.0, abs=1e-3)
    assert at(15.0) == pytest.approx(0.1, abs=1e-3)  # -20 dB under speech
    assert at(9.7) == pytest.approx(0.1, abs=1e-2)  # ramp done before the voice enters
    assert 0.1 < at(21.0) < 1.0 and at(23.0) == pytest.approx(1.0, abs=1e-3)


def test_score_places_segments_and_sets_levels():
    music = _phrased_music([3.0, 9.0, 16.0, 24.0], total_s=60.0)
    t = np.arange(int(3.0 * SR)) / SR
    voice = (0.2 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
    out = score([voice, voice], music, SR, gap_rel_db=-10.0, under_rel_db=-30.0,
                plan_kwargs={"intro_s": 2.0, "min_gap_s": 2.0, "max_gap_s": 10.0, "lead_s": 0.5})
    assert out.starts[0] == pytest.approx(3.5, abs=0.3) and out.starts[1] > out.starts[0] + 3.0 + 2.0
    assert out.seconds == pytest.approx(out.starts[1] + 3.0 + 6.0, abs=0.05)
    i = int((out.starts[0] + 1.5) * SR)
    seg = out.mix[i: i + SR // 2]
    assert np.sqrt(np.mean(seg ** 2)) == pytest.approx(0.2 / np.sqrt(2), rel=0.1)  # the voice dominates
