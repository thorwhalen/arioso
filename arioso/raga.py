"""Ragas: a table, motifs mined from a score, and a small composer (alap, pulse, tihai).

:mod:`arioso.seeds` renders a known melody over a drone. This module makes one: a line
*composed* in a raga, from the raga's own phrases and the motifs of a score that fit it,
as a :class:`~arioso.seeds.Contour` for ``seeds.melody_over_drone``.

- :data:`RAGAS`: degrees (aroha, avaroha), vadi and samvadi, and chalan phrases, written in
  sargam (see :func:`swara`) in :data:`RAGA_TABLE`. These are common textbook values
  (Bhatkhande); schools and gharanas differ, so a :class:`Raga` of your own is one call
  to :meth:`Raga.from_sargam`, and ``ragas=`` takes a table of your own.
- :func:`raga_motifs`: the recurring n-grams of a score melody that the raga permits
  (its notes, rising by the aroha and falling by the avaroha). Chords are reduced to their
  top note; phrases are split where a long onset gap is also a rest, so staccato notes
  and long held notes both stay inside their phrase.
- :func:`compose`: alap (raga phrases, free rhythm, held vadi and phrase ends, meend,
  home to Sa by a chalan phrase), a slow pulse (motifs alternating with raga phrases,
  continuing up to the tihai), and a tihai whose last Sa lands on sam. Notes are in
  semitones from Sa; :meth:`Composition.contour` places them on a Sa.

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

import warnings
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Optional, Sequence, Union

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

    def permits(self, phrase: Sequence[int]) -> bool:
        """Whether ``phrase`` moves as the raga does: each note reached by a rise is in
        the aroha, each reached by a fall is in the avaroha (pitch classes).

        >>> RAGAS["bhimpalasi"].permits((0, 2, 3)), RAGAS["bhimpalasi"].permits((3, 2, 0))
        (False, True)
        """
        up = {o % 12 for o in self.aroha}
        down = {o % 12 for o in self.avaroha}
        if not self.allows(phrase):
            return False
        for a, b in zip(phrase, phrase[1:]):
            if (b > a and b % 12 not in up) or (b < a and b % 12 not in down):
                return False
        return True

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
        aroha=".N R G M# P D N S'",
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


def _raga(raga: Union[str, Raga], ragas: Mapping = RAGAS) -> Raga:
    if isinstance(raga, Raga):
        return raga
    try:
        return ragas[raga.lower()]
    except KeyError:
        raise KeyError(
            f"unknown raga {raga!r}: one of {sorted(ragas)}, or a Raga"
        ) from None


# --------------------------------------------------------------------------------------------
# Motifs from a score

#: Onsets this close (seconds) are one chord, of which the skyline keeps the top note.
CHORD_S = 0.03
#: A phrase ends where the onset gap exceeds ``gap_ratio`` times the median one AND the rest
#: before the next onset exceeds ``rest_ratio`` times it (a held note is not a phrase end).
GAP_RATIO, REST_RATIO = 1.8, 0.5
#: Below this share of the melody's notes in the raga, raga_motifs warns (wrong Sa or raga?).
IN_RAGA_WARN_SHARE = 0.7


def _sa_pc(sa) -> int:
    from arioso.analysis import pitch_class

    return pitch_class(sa) if isinstance(sa, str) else int(round(sa)) % 12


def skyline(notes: Iterable[tuple], *, chord_s: float = CHORD_S) -> list:
    """``(start, end, pitch)`` notes, one per onset: the highest of those starting within
    ``chord_s`` of the first (a chord, however its notes are spread)."""
    out = []
    for note in sorted(notes):
        if out and note[0] - out[-1][0] <= chord_s:
            if note[2] > out[-1][2]:
                out[-1] = (out[-1][0], note[1], note[2])
        else:
            out.append(tuple(note))
    return out


def phrases(
    notes: Sequence[tuple],
    *,
    gap_ratio: float = GAP_RATIO,
    rest_ratio: float = REST_RATIO,
) -> list:
    """Split onset-ordered notes into phrases where the onset gap exceeds ``gap_ratio``
    times the median one and the silence before the next onset exceeds ``rest_ratio``
    times it. Staccato notes (long silences, regular onsets) and held notes (long onset
    gap, no silence) stay inside their phrase."""
    if len(notes) < 2:
        return [list(notes)] if notes else []
    onsets = np.array([n[0] for n in notes], dtype=float)
    ends = np.array([n[1] for n in notes], dtype=float)
    gaps = np.diff(onsets)
    med = np.median(gaps[gaps > 0]) if np.any(gaps > 0) else 0.0
    rests = onsets[1:] - np.minimum(ends[:-1], onsets[1:])
    cut = (gaps > gap_ratio * med) & (rests > rest_ratio * med)
    out, cur = [], [notes[0]]
    for note, new in zip(notes[1:], cut):
        if new:
            out.append(cur)
            cur = []
        cur.append(note)
    out.append(cur)
    return out


def _tuning(pitches: np.ndarray) -> float:
    """The melody's offset from 12-TET in semitones (-0.5..0.5), as a circular mean."""
    angle = np.angle(np.mean(np.exp(2j * np.pi * pitches)))
    return float(angle / (2 * np.pi))


def raga_motifs(
    notes: Iterable[tuple],
    raga: Union[str, Raga],
    *,
    sa,
    lengths: Iterable[int] = (3, 4, 5),
    min_count: int = 2,
    gap_ratio: float = GAP_RATIO,
    rest_ratio: float = REST_RATIO,
    chord_s: float = CHORD_S,
    top: Optional[int] = None,
    ragas: Mapping = RAGAS,
) -> list:
    """The recurring n-grams of a score melody that ``raga`` permits: ``[(motif, count)]``.

    ``notes`` are ``(start_s, end_s, midi_pitch)`` (from a MIDI track, say), reduced to their
    :func:`skyline`, retuned to 12-TET, and split into :func:`phrases`; n-grams never cross a
    phrase and must move as the raga does (:meth:`Raga.permits`). A motif is in semitones
    from the Sa at or below the melody's median pitch (``sa``: a note name or a MIDI
    number, only its pitch class counts). A motif inside a longer one that occurs as often
    is dropped (the longer one says it). Most notes covered first. Warns when few of the
    melody's notes are in the raga (a wrong ``sa`` or raga).
    """
    r = _raga(raga, ragas)
    line = skyline(notes, chord_s=chord_s)
    if not line:
        return []
    pitches = np.array([p for *_, p in line], dtype=float)
    pitches = pitches - _tuning(pitches)
    pcs = _sa_pc(sa)
    median = float(np.median(pitches))
    base = round(median) - ((round(median) - pcs) % 12)  # the Sa at or below the median
    offsets = np.rint(pitches - base).astype(int)
    share = np.mean([r.allows([o]) for o in offsets])
    if share < IN_RAGA_WARN_SHARE:
        warnings.warn(
            f"raga_motifs: only {share:.0%} of the melody's notes are in {r.name} on "
            f"Sa={sa!r}; is that the right Sa (or raga)?"
        )
    counts, i = Counter(), 0
    for phrase in phrases(line, gap_ratio=gap_ratio, rest_ratio=rest_ratio):
        offs = [int(o) for o in offsets[i : i + len(phrase)]]
        i += len(phrase)
        for n in lengths:
            for j in range(len(offs) - n + 1):
                gram = tuple(offs[j : j + n])
                if r.permits(gram):
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

#: Alap: seconds per note (drawn between), the held vadi and phrase end, and the breath.
ALAP_NOTE_S, ALAP_HOLD_S, ALAP_BREATH_S = (0.5, 1.4), (1.8, 3.0), 0.6
#: Meend: the glide between touching notes of a section (the alap's notes touch; the pulse's
#: and tihai's are detached, so they do not glide).
MEEND_S = 0.25
DFLT_GLIDES = {"alap": MEEND_S}
#: The share of its slot a pulse note sounds (the rest is articulation).
PULSE_LEGATO, TIHAI_LEGATO = 0.95, 0.9


@dataclass
class Composition:
    """A composed line: per section, ``(start_s, end_s, semitones_from_sa)`` notes, and
    the pulse's tempo, tala length and sam (seconds), for anything played along."""

    sections: dict = field(default_factory=dict)
    bpm: Optional[float] = None
    beats_per_cycle: Optional[int] = None
    pulse_start_s: Optional[float] = None
    sam_s: Optional[float] = None

    def notes(self, sa=0, *, octave: int = 4) -> list:
        """Every note in time order, pitched from ``sa`` (a note name, put in ``octave``,
        or a MIDI number; 0 keeps the offsets)."""
        from arioso.seeds import sa_midi

        base = sa_midi(sa, octave=octave) if isinstance(sa, str) else sa
        return sorted(
            (a, b, base + o) for part in self.sections.values() for a, b, o in part
        )

    @property
    def seconds(self) -> float:
        return max(
            (b for part in self.sections.values() for _, b, _ in part), default=0.0
        )

    def contour(
        self,
        sa,
        *,
        octave: int = 4,
        fps: float = 100.0,
        glides: Mapping = DFLT_GLIDES,
        **notes_kwargs,
    ):
        """The line as a :class:`~arioso.seeds.Contour` on ``sa`` (a note name, put in
        ``octave``, or a MIDI number). ``glides``: seconds of glide between touching notes,
        per section (others none). ``notes_kwargs`` go to ``seeds.notes_contour``; vibrato
        is off unless asked (``vibrato_semitones=``): Sa and Pa are held steady."""
        from arioso.seeds import Contour, notes_contour, sa_midi

        notes_kwargs.setdefault("vibrato_semitones", 0.0)
        base = sa_midi(sa, octave=octave)
        midi = np.full(int(np.ceil(self.seconds * fps)), np.nan)
        for name, part in self.sections.items():
            if not part:
                continue
            t0 = part[0][0]
            local = [(a - t0, b - t0, base + o) for a, b, o in part]
            c = notes_contour(
                local, fps=fps, glide_s=glides.get(name, 0.0), **notes_kwargs
            )
            i = int(round(t0 * fps))
            n = min(len(c.midi), len(midi) - i)
            midi[i : i + n] = c.midi[:n]
        return Contour(midi=midi, fps=fps)


def _motif(m) -> tuple:
    """A motif, or a ``(motif, count)`` pair, as a tuple of ints (JSON lists welcome)."""
    if len(m) == 2 and not np.isscalar(m[0]):
        m = m[0]
    m = tuple(int(o) for o in m)
    if not m:
        raise ValueError("an empty motif")
    return m


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
    ragas: Mapping = RAGAS,
) -> Composition:
    """Compose alap, then a slow pulse, then a tihai in ``raga``.

    Args:
        raga: A name in ``ragas`` (default :data:`RAGAS`) or a :class:`Raga`.
        motifs: Phrases in semitones from Sa (:func:`raga_motifs`' motifs, or its
            ``(motif, count)`` pairs); the pulse alternates them with the raga's chalan.
            Motifs the raga does not permit are refused.
        seed, rng: The alap's free rhythm is drawn from ``rng`` (default from ``seed``).
        alap_phrases: Phrases in the alap (the last one a chalan phrase home to Sa), each
            ending held, the vadi held too, with a breath between.
        pulse_phrases: Phrases in the pulse at least, one note per beat, the last of each
            held two beats; more follow, and the last note holds, up to the tihai.
        bpm, beats_per_cycle: The pulse's tempo and tala length (16: tintal).
        tihai: The phrase played three times to land on sam (default: the first motif, or
            the last chalan phrase), with Sa added at its end when it lacks one.
    """
    r = _raga(raga, ragas)
    if bpm <= 0 or beats_per_cycle < 1:
        raise ValueError(
            f"compose: bpm ({bpm}) must be > 0, beats_per_cycle ({beats_per_cycle}) >= 1"
        )
    motifs = [_motif(m) for m in motifs]
    wrong = [m for m in motifs if not r.permits(m)]
    if wrong:
        raise ValueError(f"motifs outside {r.name}: {wrong}")
    if not r.chalan:
        raise ValueError(f"{r.name} has no chalan phrases to compose from")
    rng = rng or np.random.default_rng(seed)
    beat = 60.0 / bpm

    # alap: chalan phrases in order, then one that comes home to Sa
    home = [p for p in r.chalan if p[-1] == 0]
    home = home[-1] if home else r.chalan[-1] + (0,)
    rising = [p for p in r.chalan if p is not home]
    plan = [rising[k % len(rising)] for k in range(max(0, alap_phrases - 1))] + [home]
    alap, t = [], 0.0
    for phrase in plan[-alap_phrases:] if alap_phrases else []:
        for i, o in enumerate(phrase):
            held = i == len(phrase) - 1 or o % 12 == r.vadi % 12
            d = rng.uniform(*(ALAP_HOLD_S if held else ALAP_NOTE_S))
            alap.append((t, t + d, o))
            t += d
        t += ALAP_BREATH_S

    # pulse and tihai, counted in half beats so sam is exact
    half = beat / 2
    start = int(
        np.ceil(t / half - 1e-9)
    )  # the pulse starts on a half beat after the alap
    phrase_t = tuple(tihai) if tihai else (motifs[0] if motifs else r.chalan[-1])
    phrase_t = _motif(phrase_t)
    if phrase_t[-1] != 0:
        phrase_t = phrase_t + (0,)
    if not r.permits(phrase_t):
        raise ValueError(f"tihai {phrase_t} is outside {r.name}")
    tihai_span = 3 * len(phrase_t) + 2 * 2 - 1  # half beats, first onset to last onset

    def pulse_phrase(k):
        if motifs and k % 2 == 0:
            return motifs[(k // 2) % len(motifs)]
        return r.chalan[k % len(r.chalan)]

    def length(p):  # half beats: one beat a note, the last two, then a beat's rest
        return 2 * (len(p) - 1) + 4 + 2

    cycle = 2 * beats_per_cycle
    pulse, h, k = [], start, 0
    while True:
        p = pulse_phrase(k)
        if k >= pulse_phrases:  # enough: continue only while a whole phrase still fits
            sam = start + -(-(h + tihai_span - start) // cycle) * cycle
            if h + length(p) > sam - tihai_span:
                break
        for i, o in enumerate(p):
            n = 4 if i == len(p) - 1 else 2
            pulse.append([h, h + n * PULSE_LEGATO, o])
            h += n
        h += 2
        k += 1
    sam = (
        start + -(-(h + tihai_span - start) // cycle) * cycle
    )  # the last Sa lands here
    first = sam - tihai_span
    if pulse:  # hold the last note up to the tihai
        pulse[-1][1] = max(pulse[-1][1], first - 1)
    tih, h = [], first
    for rep in range(3):
        for i, o in enumerate(phrase_t):
            final = rep == 2 and i == len(phrase_t) - 1
            tih.append((h, h + (4 if final else TIHAI_LEGATO), o))
            h += 1
        h += 2

    def seconds(notes):
        return [(a * half, b * half, o) for a, b, o in notes]

    return Composition(
        {"alap": alap, "pulse": seconds(pulse), "tihai": seconds(tih)},
        bpm=bpm,
        beats_per_cycle=beats_per_cycle,
        pulse_start_s=start * half,
        sam_s=sam * half,
    )
