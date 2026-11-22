"""Ragas: a table, motifs mined from a score, and a small composer (alap, pulse, tihai).

:mod:`arioso.seeds` renders a known melody over a drone. This module makes one: a line
*composed* in a raga, from the raga's own phrases and the motifs of a score that fit it,
as a :class:`~arioso.seeds.Contour` for ``seeds.melody_over_drone``.

- :data:`RAGAS`: degrees (aroha, avaroha), vadi and samvadi, and chalan phrases, written in
  sargam (see :func:`swara`) in :data:`RAGA_TABLE`. These are common textbook values;
  schools and gharanas differ, so a :class:`Raga` of your own is one call to
  :meth:`Raga.from_sargam`.
- :func:`raga_motifs`: the recurring n-grams of a score melody whose notes all lie in the
  raga. Phrases are split on onset gaps, not note ends (MIDI notes are often staccato).
- :func:`compose`: alap (raga phrases, free rhythm, held phrase ends, meend), a slow pulse
  (motifs alternating with raga phrases), and a tihai landing on sam. Notes are in
  semitones from Sa; :meth:`Composition.contour` places them on a Sa and glides the alap.

>>> yaman = RAGAS["yaman"]
>>> yaman.degrees, swara("M#"), yaman.vadi
((0, 2, 4, 6, 7, 9, 11), 6, 4)
>>> notes = [(i * 0.5, i * 0.5 + 0.2, 62 + o) for i, o in enumerate([0, 2, 4, 0, 2, 4, 0])]
>>> raga_motifs(notes, yaman, sa="D")[0]
((0, 2, 4, 0), 2)
>>> piece = compose(yaman, motifs=[(0, 2, 4)], seed=1)
>>> sorted(piece.sections), piece.notes()[-1][2]  # the tihai lands on Sa
(['alap', 'pulse', 'tihai'], 0)
>>> c = piece.contour("D")
>>> round(c.seconds) == round(piece.seconds)
True
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence, Union

import numpy as np

#: Semitones above Sa of each swara: shuddha in capitals, komal in lower case, tivra Ma as M#.
SWARAS = {"S": 0, "r": 1, "R": 2, "g": 3, "G": 4, "M": 5, "M#": 6, "P": 7}
SWARAS.update({"d": 8, "D": 9, "n": 10, "N": 11})
#: A leading ``.`` puts a swara in the lower octave (mandra), a trailing ``'`` in the upper (taar).
LOWER, UPPER = ".", "'"


def swara(token: str) -> int:
    """Semitones from Sa of one sargam token: ``"g"`` 3, ``".N"`` -1, ``"S'"`` 12.

    >>> [swara(t) for t in ("S", "r", "M#", ".n", "S'", "R''")]
    [0, 1, 6, -2, 12, 26]
    """
    t = token.strip()
    octave = -t.count(LOWER) + t.count(UPPER)
    name = t.replace(LOWER, "").replace(UPPER, "")
    if name not in SWARAS:
        raise ValueError(
            f"unknown swara {token!r}: use {sorted(SWARAS)}, '.' below, \"'\" above"
        )
    return SWARAS[name] + 12 * octave


def sargam(phrase: str) -> tuple:
    """A space-separated sargam phrase as semitones from Sa.

    >>> sargam(".N R G M# P")
    (-1, 2, 4, 6, 7)
    """
    return tuple(swara(t) for t in phrase.split())


@dataclass(frozen=True)
class Raga:
    """A raga's material, in semitones from Sa."""

    name: str
    aroha: tuple
    avaroha: tuple
    vadi: int
    samvadi: int
    chalan: tuple = ()

    @property
    def degrees(self) -> tuple:
        """The pitch classes the raga uses, from Sa."""
        return tuple(sorted({o % 12 for o in self.aroha + self.avaroha}))

    def allows(self, offsets: Iterable[int]) -> bool:
        """Whether every one of ``offsets`` (semitones from Sa) is a degree of the raga."""
        degrees = set(self.degrees)
        return all(int(o) % 12 in degrees for o in offsets)

    @classmethod
    def from_sargam(
        cls, name: str, *, aroha: str, avaroha: str, vadi: str, samvadi: str, chalan=()
    ) -> "Raga":
        """A raga written in sargam (see :func:`swara`)."""
        return cls(
            name=name,
            aroha=sargam(aroha),
            avaroha=sargam(avaroha),
            vadi=swara(vadi),
            samvadi=swara(samvadi),
            chalan=tuple(sargam(p) for p in chalan),
        )


#: The raga table, in sargam: common textbook values (Bhatkhande's thaat system).
RAGA_TABLE = {
    "yaman": dict(
        aroha=".N R G M# D N S'",
        avaroha="S' N D P M# G R S",
        vadi="G",
        samvadi="N",
        chalan=[".N R G", "R G M# P", "M# D N S'", "S' N D P", "M# G R S"],
    ),
    "bhupali": dict(
        aroha="S R G P D S'",
        avaroha="S' D P G R S",
        vadi="G",
        samvadi="D",
        chalan=["S R G", "G P D S'", "S' D P G", "G R S .D S"],
    ),
    "malkauns": dict(
        aroha=".n S g M d n S'",
        avaroha="S' n d M g S",
        vadi="M",
        samvadi="S",
        chalan=[".n S g M", "g M d n S'", "S' n d M", "M g M g S"],
    ),
    "bhairav": dict(
        aroha="S r G M P d N S'",
        avaroha="S' N d P M G r S",
        vadi="d",
        samvadi="r",
        chalan=["S r G M", "G M d P", "d N S'", "S' N d P", "M G r S"],
    ),
    "kafi": dict(
        aroha="S R g M P D n S'",
        avaroha="S' n D P M g R S",
        vadi="P",
        samvadi="S",
        chalan=["S R g M P", "M P D n S'", "S' n D P", "M g R S"],
    ),
    "bhimpalasi": dict(
        aroha=".n S g M P n S'",
        avaroha="S' n D P M g R S",
        vadi="M",
        samvadi="S",
        chalan=[".n S g M", "g M P n S'", "S' n D P M", "P M g R S"],
    ),
}
RAGAS = {name: Raga.from_sargam(name, **spec) for name, spec in RAGA_TABLE.items()}


def _raga(raga: Union[str, Raga]) -> Raga:
    if isinstance(raga, Raga):
        return raga
    try:
        return RAGAS[raga.lower()]
    except KeyError:
        raise KeyError(f"unknown raga {raga!r}: one of {sorted(RAGAS)}, or a Raga") from None


# --------------------------------------------------------------------------------------------
# Motifs from a score


def _sa_pc(sa) -> int:
    from arioso.analysis import pitch_class

    return pitch_class(sa) if isinstance(sa, str) else int(round(sa)) % 12


def skyline(notes: Iterable[tuple]) -> list:
    """``(start, end, pitch)`` notes, one per onset: the highest of those starting together."""
    top = {}
    for start, end, pitch in notes:
        if start not in top or pitch > top[start][2]:
            top[start] = (start, end, pitch)
    return [top[s] for s in sorted(top)]


def phrases(notes: Sequence[tuple], *, gap_ratio: float = 1.8) -> list:
    """Split onset-ordered notes into phrases where an onset gap exceeds ``gap_ratio`` times
    the median one. Note ends are ignored: staccato notes still make one phrase."""
    if len(notes) < 2:
        return [list(notes)] if notes else []
    onsets = np.array([n[0] for n in notes], dtype=float)
    gaps = np.diff(onsets)
    cut = gaps > gap_ratio * np.median(gaps)
    out, cur = [], [notes[0]]
    for note, new in zip(notes[1:], cut):
        if new:
            out.append(cur)
            cur = []
        cur.append(note)
    out.append(cur)
    return out


def raga_motifs(
    notes: Iterable[tuple],
    raga: Union[str, Raga],
    *,
    sa,
    lengths: Iterable[int] = (3, 4, 5),
    min_count: int = 2,
    gap_ratio: float = 1.8,
    top: Optional[int] = None,
) -> list:
    """The recurring n-grams of a score melody that lie in ``raga``: ``[(motif, count)]``.

    ``notes`` are ``(start_s, end_s, midi_pitch)`` (from a MIDI track, say), reduced to their
    :func:`skyline` and split into :func:`phrases`; n-grams never cross a phrase. A motif
    is in semitones from the Sa at or below the melody's median pitch (``sa``: a note name or
    a MIDI number, only its pitch class counts). A motif inside a longer one that occurs as
    often is dropped (the longer one says it). Most notes covered first.
    """
    r = _raga(raga)
    line = skyline(notes)
    if not line:
        return []
    pcs = _sa_pc(sa)
    median = float(np.median([p for *_, p in line]))
    base = median - ((median - pcs) % 12)  # the Sa at or below the median
    counts = Counter()
    for phrase in phrases(line, gap_ratio=gap_ratio):
        offs = [int(round(p - base)) for *_, p in phrase]
        for n in lengths:
            for i in range(len(offs) - n + 1):
                gram = tuple(offs[i : i + n])
                if r.allows(gram):
                    counts[gram] += 1
    kept = {g: c for g, c in counts.items() if c >= min_count}

    def inside(short, long):
        return any(
            long[i : i + len(short)] == short for i in range(len(long) - len(short) + 1)
        )

    maximal = [
        (g, c)
        for g, c in kept.items()
        if not any(len(h) > len(g) and kept[h] == c and inside(g, h) for h in kept)
    ]
    maximal.sort(key=lambda gc: (-gc[1] * len(gc[0]), -gc[1], gc[0]))
    return maximal[:top] if top else maximal


# --------------------------------------------------------------------------------------------
# A small composer

#: Alap: seconds per note (drawn between), the held phrase end, and the breath between phrases.
ALAP_NOTE_S, ALAP_HOLD_S, ALAP_BREATH_S = (0.5, 1.4), (1.8, 3.0), 0.6
#: Meend: the glide between touching alap notes (the pulse and tihai glide less).
MEEND_S, GLIDE_S = 0.25, 0.06


@dataclass
class Composition:
    """A composed line: per section, ``(start_s, end_s, semitones_from_sa)`` notes."""

    sections: dict = field(default_factory=dict)

    def notes(self, sa=0) -> list:
        """Every note in time order, pitched from ``sa`` (a MIDI number; 0 keeps offsets)."""
        return [(a, b, sa + o) for part in self.sections.values() for a, b, o in part]

    @property
    def seconds(self) -> float:
        return max((b for part in self.sections.values() for _, b, _ in part), default=0.0)

    def contour(
        self, sa, *, octave: int = 4, fps: float = 100.0, meend_s: float = MEEND_S, glide_s=GLIDE_S
    ):
        """The line as a :class:`~arioso.seeds.Contour` on ``sa`` (a note name, put in
        ``octave``, or a MIDI number); the alap glides ``meend_s`` between notes."""
        from arioso.seeds import Contour, notes_contour, sa_midi

        base = sa_midi(sa, octave=octave)
        midi = np.full(int(np.ceil(self.seconds * fps)), np.nan)
        for name, part in self.sections.items():
            if not part:
                continue
            t0 = part[0][0]
            local = [(a - t0, b - t0, base + o) for a, b, o in part]
            g = meend_s if name == "alap" else glide_s
            c = notes_contour(local, fps=fps, glide_s=g)
            i = int(round(t0 * fps))
            n = min(len(c.midi), len(midi) - i)
            midi[i : i + n] = c.midi[:n]
        return Contour(midi=midi, fps=fps)


def compose(
    raga: Union[str, Raga],
    *,
    motifs: Iterable = (),
    seed: Optional[int] = None,
    alap_phrases: int = 4,
    pulse_phrases: int = 6,
    bpm: float = 50.0,
    beats_per_cycle: int = 16,
    tihai: Optional[Sequence[int]] = None,
    rng: Optional[np.random.Generator] = None,
) -> Composition:
    """Compose alap, then a slow pulse, then a tihai in ``raga``.

    Args:
        raga: A name in :data:`RAGAS` or a :class:`Raga`.
        motifs: Phrases in semitones from Sa (:func:`raga_motifs`' motifs, or its
            ``(motif, count)`` pairs); the pulse alternates them with the raga's chalan.
            Motifs outside the raga are refused.
        seed, rng: The alap's free rhythm is drawn from ``rng`` (default from ``seed``).
        alap_phrases: Chalan phrases in the alap, each ending held, with a breath between.
        pulse_phrases: Phrases in the pulse, one note per beat, the last held two beats.
        bpm, beats_per_cycle: The pulse's tempo and tala length (16: tintal).
        tihai: The phrase played three times to land on sam (default: the first motif, or
            the last chalan phrase), with Sa added at its end when it lacks one.
    """
    r = _raga(raga)
    motifs = [tuple(m[0]) if m and isinstance(m[0], tuple) else tuple(m) for m in motifs]
    wrong = [m for m in motifs if not r.allows(m)]
    if wrong:
        raise ValueError(f"motifs outside {r.name}: {wrong}")
    if not r.chalan:
        raise ValueError(f"{r.name} has no chalan phrases to compose from")
    rng = rng or np.random.default_rng(seed)
    beat = 60.0 / bpm

    alap, t = [], 0.0
    for k in range(alap_phrases):
        phrase = r.chalan[k % len(r.chalan)]
        if k == alap_phrases - 1 and phrase[-1] != 0:
            phrase = phrase + (0,)  # the alap comes home to Sa
        for i, o in enumerate(phrase):
            last = i == len(phrase) - 1
            d = rng.uniform(*(ALAP_HOLD_S if last else ALAP_NOTE_S))
            alap.append((t, t + d, o))
            t += d
        t += ALAP_BREATH_S

    # the pulse starts on a beat after the alap
    t = np.ceil(t / beat) * beat
    pulse, start = [], t
    chalan = list(r.chalan)
    for k in range(pulse_phrases):
        if motifs and k % 2 == 0:
            phrase = motifs[(k // 2) % len(motifs)]
        else:
            phrase = chalan[k % len(chalan)]
        for i, o in enumerate(phrase):
            d = 2 * beat if i == len(phrase) - 1 else beat
            pulse.append((t, t + d * 0.95, o))
            t += d
        t += beat  # a beat's rest between phrases

    phrase = tuple(tihai) if tihai else (motifs[0] if motifs else r.chalan[-1])
    if not r.allows(phrase):
        raise ValueError(f"tihai {phrase} is outside {r.name}")
    if phrase[-1] != 0:
        phrase = phrase + (0,)
    unit, gap = beat / 2, beat  # half-beat notes, a beat between the three
    span = 3 * len(phrase) * unit + 2 * gap - unit  # from first onset to the last onset
    cycle = beats_per_cycle * beat
    sam = np.ceil((t + span - start) / cycle) * cycle + start  # the last Sa lands here
    t = sam - span
    tih = []
    for rep in range(3):
        for i, o in enumerate(phrase):
            final = rep == 2 and i == len(phrase) - 1
            tih.append((t, t + (2 * beat if final else unit * 0.9), o))
            t += unit
        t += gap
    return Composition({"alap": alap, "pulse": pulse, "tihai": tih})
