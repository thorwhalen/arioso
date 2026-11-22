"""arioso.raga: the raga table, motif mining from a score, and the composer."""

import numpy as np
import pytest

from arioso.raga import (
    RAGAS,
    Raga,
    compose,
    phrases,
    raga_motifs,
    sargam,
    skyline,
    swara,
)


def test_sargam_tokens_cover_komal_tivra_and_octaves():
    assert sargam("S r R g G M M# P d D n N S'") == tuple(range(13))
    assert swara(".n") == -2 and swara("..S") == -24 and swara("G'") == 16
    with pytest.raises(ValueError, match="unknown swara"):
        swara("m")


@pytest.mark.parametrize("name", sorted(RAGAS))
def test_every_raga_is_self_consistent(name):
    r = RAGAS[name]
    assert r.aroha[-1] == 12 and r.avaroha[0] == 12 and r.avaroha[-1] == 0
    assert r.allows([r.vadi, r.samvadi])
    assert r.chalan and all(r.allows(p) for p in r.chalan)
    assert r.vadi % 12 != r.samvadi % 12


def test_degrees_agree_with_tonal_where_it_has_the_raga():
    notes = pytest.importorskip("tonal.notes")
    for name in ("bhairav", "malkauns", "bhupali"):
        quality = notes.scale_quality_alias.get(name, name)
        assert RAGAS[name].degrees == tuple(notes.scale_quality[quality]), name


def test_phrases_split_on_onset_gaps_not_on_note_ends():
    staccato = [(i * 0.5, i * 0.5 + 0.05, 60) for i in range(4)]  # short notes, one phrase
    later = [(4.0 + i * 0.5, 4.0 + i * 0.5 + 0.05, 62) for i in range(3)]
    assert [len(p) for p in phrases(staccato + later)] == [4, 3]


def test_skyline_keeps_the_top_note_of_a_chord():
    assert skyline([(0, 1, 60), (0, 1, 67), (1, 2, 62)]) == [(0, 1, 67), (1, 2, 62)]


def _score(offsets_per_phrase, *, sa=62, step=0.5, gap=3.0):
    notes, t = [], 0.0
    for offs in offsets_per_phrase:
        for o in offs:
            notes.append((t, t + 0.1, sa + o))
            t += step
        t += gap
    return notes


def test_motifs_are_recurring_ngrams_in_the_raga_within_phrases():
    yaman = RAGAS["yaman"]
    score = _score([[4, 6, 7, 9], [4, 6, 7, 9], [5, 4, 2, 0], [5, 4, 2, 0]])  # M (5) is not Yaman's
    motifs = dict(raga_motifs(score, yaman, sa="D"))
    assert motifs[(4, 6, 7, 9)] == 2
    assert not any(5 in m for m in motifs)  # shuddha Ma is outside Yaman
    assert (4, 2, 0) in motifs  # the in-raga tail of the out-of-raga phrase
    assert not any(m[-1] == 9 and m[0] == 9 for m in motifs)  # no n-gram crosses a phrase


def test_motifs_are_relative_to_the_sa_below_the_melody():
    low, high = _score([[0, 2, 4]] * 2, sa=50), _score([[0, 2, 4]] * 2, sa=74)
    assert raga_motifs(low, "yaman", sa="D") == raga_motifs(high, "yaman", sa="D")


def _onsets(part):
    return [a for a, _, _ in part]


def test_compose_gives_alap_pulse_and_a_tihai_on_sam():
    bpm, cycle = 50.0, 16
    piece = compose("yaman", motifs=[((4, 6, 7, 9), 3)], seed=3, bpm=bpm, beats_per_cycle=cycle)
    alap, pulse, tihai = (piece.sections[k] for k in ("alap", "pulse", "tihai"))
    assert RAGAS["yaman"].allows(o for _, _, o in piece.notes())
    assert alap[-1][2] == 0  # the alap comes home to Sa
    ends = [part[-1][1] for part in (alap, pulse)]
    starts = [part[0][0] for part in (pulse, tihai)]
    assert ends[0] <= starts[0] and ends[1] <= starts[1]  # sections in order, no overlap
    beat = 60 / bpm
    on_beats = (np.array(_onsets(pulse)) - pulse[0][0]) / beat
    assert np.allclose(on_beats, np.round(on_beats))  # the pulse moves on the beat
    assert tuple(o for *_, o in pulse[:4]) == (4, 6, 7, 9)  # the motif opens the pulse
    third = len(tihai) // 3
    reps = [tuple(o for *_, o in tihai[i * third : (i + 1) * third]) for i in range(3)]
    assert reps[0] == reps[1] == reps[2] and reps[0][-1] == 0
    sam = (tihai[-1][0] - pulse[0][0]) / (cycle * beat)
    assert sam == pytest.approx(round(sam)) and round(sam) >= 1


def test_compose_is_reproducible_and_checks_its_motifs():
    a, b = compose("bhupali", seed=7), compose("bhupali", seed=7)
    assert a.notes() == b.notes()
    assert compose("bhupali", seed=8).notes() != a.notes()
    with pytest.raises(ValueError, match="outside"):
        compose("bhupali", motifs=[(0, 5, 7)])  # Ma is not in Bhupali


def test_a_custom_raga_composes_too():
    durga = Raga.from_sargam(
        "durga", aroha="S R M P D S'", avaroha="S' D P M R S", vadi="M", samvadi="S",
        chalan=["S R M P", "M P D S'", "S' D P M", "M R S"],
    )
    assert durga.degrees == (0, 2, 5, 7, 9)
    assert durga.allows(o for *_, o in compose(durga, seed=1).notes())


def test_the_contour_places_the_line_on_sa_and_renders_over_the_drone():
    from arioso.seeds import melody_over_drone

    piece = compose("yaman", seed=2, alap_phrases=2, pulse_phrases=2)
    c = piece.contour("D", octave=4, fps=50)
    assert c.seconds == pytest.approx(piece.seconds, abs=0.05)
    first = piece.sections["alap"][0][2]
    assert c.midi[1] == pytest.approx(62 + first, abs=0.01)
    assert np.isnan(c.midi).any()  # breaths and the gaps between sections are silent
    y, sr = melody_over_drone(c, "D", sr=8000, lead_in_s=0.5)
    assert y.shape[0] / sr > piece.seconds
