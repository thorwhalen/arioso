"""Keybeds: a playable sampler instrument from one descriptor, rendered note by note.

Foundation-1.2-Keybeds (the ``foundation_1`` platform, ``model="1.2-keybeds"``) keeps one
timbre across pitch when it renders several notes of the same instrument in one clip.
Its author's workflow (``keybed_training_strategy.md`` in the model repository, and the
prompt builders of the RC-stable-audio-tools fork, MIT), which this follows: the
register is split into chunks of up to six notes, each rendered as one sequence (3.0 s
per note, 0.25 s apart) under ``"Keybed, Sequence, Timbre Profile, <descriptor>, Dry,
Chromatic Chunk, Note Sequence, C4, C#4, ..."`` (``Chromatic Chunk`` only for adjacent
semitones; a lone note takes the single-note form, ``"..., Target Note, C5"``), with one
seed for every chunk. The clips keep the model's level (no per-clip normalising, so the
chunks stay balanced) and are cut back into notes at those known times; one gain then
brings the loudest note of the whole keybed to ``peak``, and the notes are mapped across
the keyboard (:mod:`arioso.sampler_export`: an SF2 that browser SoundFont synths load,
and an SFZ).

Every chunk sent is chromatic (``fill=True``), as the model was trained: keys that are
not adjacent are rendered inside the chromatic run that spans them (a short run padded to
a full chunk), and only the asked notes are kept. Measured on real renders (arioso#73,
"Rhodes Piano, Warm", seed 7): in a non-chromatic sequence (A3, C4, E4, G4, C5) the
octave below dominated E4, G4 and C5 (+0.7 to +9 dB over the asked pitch); in chromatic
chunks every note peaked at its asked pitch, the octave below 6 to 16 dB under it; a
lone ``Target Note`` C4 was ambiguous (+2 dB). Each note's :func:`sub_octave_db` is kept
in the render's info, and a note where it dominates is warned about. (A periodicity
tracker such as pyin follows that sub-octave and reads every note an octave low.)

>>> keybed_prompt("Rhodes Piano, Warm", [60, 61])
'Keybed, Sequence, Timbre Profile, Rhodes Piano, Warm, Dry, Chromatic Chunk, Note Sequence, C4, C#4'
>>> keybed_prompt("Bass, Wet", [40, 45])
'Keybed, Sequence, Timbre Profile, Bass, Wet, Note Sequence, E2, A2'
>>> keybed_prompt("Pad", [72])
'Keybed, Timbre Profile, Pad, Dry, Target Note, C5'
"""

from __future__ import annotations

import json
import math
import warnings
from pathlib import Path
from typing import Callable, Iterable, Optional

import re

import numpy as np

from arioso.analysis import NOTES

_NOTE_TAG = re.compile(r"^[A-G](#|b)?-?\d+$")

#: Seconds per note and between notes in a sequence render, as the model was trained.
NOTE_SECONDS, GAP_SECONDS = 3.0, 0.25
#: Most notes per sequence render (six fill the model's ~20 s window).
CHUNK_NOTES = 6
#: The default register: C3 to C5, every key.
DFLT_KEYS = tuple(range(48, 73))
#: Fades at the end and the start of each cut note, so neither cut clicks (the start
#: one is short: a wet note's neighbour's tail can run into its slot).
FADE_SECONDS, FADE_IN_SECONDS = 0.02, 0.002
#: The notes the model was trained on: C0 to C8.
KEY_RANGE = (12, 108)
#: Words that make a descriptor tag an effect (the RC fork's ``KEYBED_FX_WORDS``).
FX_WORDS = ("reverb", "delay", "distortion", "phaser", "bitcrush")
#: How much shorter than asked a render may come back (rounding) before it is an error.
SHORTFALL_SECONDS = 0.01
#: The level of the loudest note after the keybed's one gain (about -1 dBFS).
DFLT_PEAK = 0.89
#: The start of a note whose spectrum :func:`sub_octave_db` reads.
PITCH_CHECK_SECONDS = 0.5
#: A note whose octave below is louder than its pitch by more than this (dB) is warned about.
SUB_OCTAVE_WARN_DB = 0.0


def note_name(key: int) -> str:
    """The note name of MIDI ``key``, C4 = 60 (the RC fork's ``midi_to_note_name``).

    >>> note_name(60), note_name(49), note_name(21)
    ('C4', 'C#3', 'A0')
    """
    return f"{NOTES[key % 12]}{key // 12 - 1}"


def _check_keys(keys) -> None:
    low, high = KEY_RANGE
    wrong = [k for k in keys if not low <= k <= high]
    if wrong:
        raise ValueError(
            f"keybed: the model knows {note_name(low)}..{note_name(high)} "
            f"(MIDI {low}..{high}), got {wrong}"
        )


#: The model's control tags, which the descriptor must not repeat (a pasted prompt).
_CONTROL_TAGS = {
    "keybed",
    "sequence",
    "timbre profile",
    "chromatic chunk",
    "note sequence",
    "target note",
}


def _descriptor_tags(descriptor: str) -> list:
    """The descriptor's own tags: control tags and note names dropped, duplicates once."""
    tags = []
    for t in (t.strip() for t in descriptor.split(",")):
        if t and t.lower() not in _CONTROL_TAGS and not _NOTE_TAG.match(t):
            if t.lower() not in (x.lower() for x in tags):
                tags.append(t)
    return tags


def keybed_prompt(descriptor: str, keys: Iterable[int], *, wet: bool = False) -> str:
    """The prompt for ``keys``: the model's control grammar around ``descriptor``.

    The descriptor's sound tags come first, then ``"Wet"`` or ``"Dry"`` (a tag in the
    descriptor wins over ``wet``), then its effect tags (reverb, delay, ...), which only
    a wet keybed can have.
    """
    keys = [int(k) for k in keys]
    _check_keys(keys)
    tags = _descriptor_tags(descriptor)
    said = [t for t in tags if t.lower() in ("wet", "dry")]
    if len({t.lower() for t in said}) > 1:
        raise ValueError(f"keybed: {descriptor!r} says both Wet and Dry")
    is_wet = said[0].lower() == "wet" if said else wet
    fx = [t for t in tags if any(w in t.lower() for w in FX_WORDS)]
    body = [t for t in tags if t not in fx and t not in said]
    if fx and not is_wet:
        raise ValueError(
            f"keybed: effect tags {fx} need a wet keybed (wet=True, or 'Wet' in the descriptor)"
        )
    tags = [*body, "Wet" if is_wet else "Dry", *fx]
    if len(keys) == 1:
        return ", ".join(
            ["Keybed", "Timbre Profile", *tags, "Target Note", note_name(keys[0])]
        )
    chromatic = all(b - a == 1 for a, b in zip(keys, keys[1:]))
    return ", ".join(
        ["Keybed", "Sequence", "Timbre Profile", *tags]
        + (["Chromatic Chunk"] if chromatic else [])
        + ["Note Sequence", *(note_name(k) for k in keys)]
    )


def chunks(keys, size: int = CHUNK_NOTES) -> list:
    """``keys`` (sorted, distinct) in the fewest chunks of at most ``size``, as even as can be.

    >>> [len(c) for c in chunks(range(48, 73))]  # 25 keys: not 6, 6, 6, 6, 1
    [5, 5, 5, 5, 5]
    """
    keys = sorted(set(int(k) for k in keys))
    if not keys:
        raise ValueError("no keys to render")
    _check_keys(keys)
    n = math.ceil(len(keys) / size)
    q, r = divmod(len(keys), n)
    out, i = [], 0
    for j in range(n):
        m = q + (j < r)
        out.append(keys[i : i + m])
        i += m
    return out


def render_plan(keys, size: int = CHUNK_NOTES) -> list:
    """The chromatic chunks that render ``keys``: their span filled in, padded to ``size``.

    Chunks holding none of ``keys`` are left out, so far-apart keys cost one render each.

    >>> render_plan([57, 60, 64, 67, 72])  # A3..C5: three chromatic chunks
    [[57, 58, 59, 60, 61, 62], [63, 64, 65, 66, 67], [68, 69, 70, 71, 72]]
    >>> render_plan([60])  # a lone key sits in a chromatic chunk too
    [[58, 59, 60, 61, 62, 63]]
    >>> [(c[0], c[-1]) for c in render_plan([24, 96])]
    [(24, 29), (92, 96)]
    """
    keys = sorted(set(int(k) for k in keys))
    if not keys:
        raise ValueError("no keys to render")
    _check_keys(keys)
    low, high = keys[0], keys[-1]
    short = size - (high - low + 1)
    if short > 0:  # widen to a full chunk, around the keys, inside the model's range
        low = max(KEY_RANGE[0], low - short // 2)
        high = min(KEY_RANGE[1], low + size - 1)
        low = max(KEY_RANGE[0], high - size + 1)
    asked = set(keys)
    return [c for c in chunks(range(low, high + 1), size) if asked.intersection(c)]


def sub_octave_db(
    audio, rate: int, key: int, *, seconds: float = PITCH_CHECK_SECONDS
) -> float:
    """How much louder the octave below ``key`` is than ``key`` itself, in dB, in the
    first ``seconds`` of ``audio`` (energy within a quarter tone of each). Above 0, a
    listener or a pitch tracker may hear the note an octave low.

    >>> rate = 8000; t = np.arange(rate) / rate
    >>> f = 440.0 * 2 ** ((60 - 69) / 12)
    >>> round(sub_octave_db(np.sin(2 * np.pi * f * t) + 0.1 * np.sin(np.pi * f * t), rate, 60))
    -20
    """
    seg = np.asarray(audio, dtype=float)[: max(1, int(seconds * rate))]
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2
    freqs = np.fft.rfftfreq(len(seg), 1 / rate)
    f = 440.0 * 2 ** ((key - 69) / 12)

    def band(x):
        return float(
            spec[(freqs > x * 2 ** (-1 / 24)) & (freqs < x * 2 ** (1 / 24))].sum()
        )

    tiny = 1e-20
    return 10 * np.log10((band(f / 2) + tiny) / (band(f) + tiny))


def _default_generate(prompt, **kwargs):
    import arioso

    kwargs.setdefault("normalize", False)  # the chunks keep their balance
    return arioso.generate(
        prompt, platform="foundation_1", model="1.2-keybeds", **kwargs
    )


def _window_seconds() -> float:
    from arioso.platforms.foundation_1.adapter import WINDOW_SECONDS

    return WINDOW_SECONDS


def render_keybed(
    descriptor: str,
    keys: Iterable[int] = DFLT_KEYS,
    *,
    seed: Optional[int] = None,
    wet: bool = False,
    generate: Callable = None,
    chunk: int = CHUNK_NOTES,
    note_seconds: float = NOTE_SECONDS,
    gap_seconds: float = GAP_SECONDS,
    peak: Optional[float] = DFLT_PEAK,
    window_seconds: Optional[float] = None,
    fill: bool = True,
    **generate_kwargs,
) -> tuple:
    """Render one note per key; returns ``({key: (audio, rate)}, info)``.

    ``generate(prompt, *, duration, seed, **generate_kwargs)`` returns a Song; the
    default is the local ``foundation_1`` platform with the keybeds checkpoint, its
    takes left at the model's level. The seed is drawn once (when None) and used for
    every chunk. Every chunk is checked against the model's window (``window_seconds``,
    default the platform's) before anything renders. ``peak``: one gain for the whole
    keybed so its loudest note is there (None: leave the level as rendered).
    ``fill``: render every chunk chromatic (:func:`render_plan`) and keep the asked
    notes; ``False`` sends the asked keys as they are (non-adjacent keys as a plain
    note sequence, a lone key as a ``Target Note``), which can come back an octave low.
    ``info`` holds the seed, per chunk its keys and the prompt actually sent, and per
    kept key its :func:`sub_octave_db`.
    """
    from arioso._isolated import draw_seed
    from arioso.sampler_export import channels_first, choose_fold, mono

    keys = sorted(set(int(k) for k in keys))
    groups = render_plan(keys, chunk) if fill else chunks(keys, chunk)
    asked = set(keys)
    window = _window_seconds() if window_seconds is None else window_seconds

    def length(group):
        return len(group) * note_seconds + (len(group) - 1) * gap_seconds

    too_long = [g for g in groups if length(g) > window]
    if too_long:
        raise ValueError(
            f"keybed: {len(too_long[0])} notes take {length(too_long[0]):.2f} s, more than "
            f"the model's {window:g} s window; use a smaller chunk="
        )
    generate = generate or _default_generate
    seed = draw_seed() if seed is None else int(seed)
    step = note_seconds + gap_seconds
    renders, sent = [], []
    for (
        group
    ) in groups:  # every chunk first: the fold to mono is chosen over all of them
        prompt = keybed_prompt(descriptor, group, wet=wet)
        song = generate(prompt, duration=length(group), seed=seed, **generate_kwargs)
        sent.append(
            {"keys": group, "prompt": (song.metadata or {}).get("prompt_sent", prompt)}
        )
        if song.audio_array is None:
            raise ValueError(f"keybed: the render for {group} came back with no audio")
        renders.append((group, channels_first(song.audio_array), int(song.sample_rate)))
    fold = choose_fold([audio for _, audio, _ in renders])
    notes = {}
    for group, channels, rate in renders:
        audio = mono(channels, fold=fold)
        if len(channels) > 1 and choose_fold([channels]) != fold:
            warnings.warn(
                f"keybed: the chunk {[note_name(k) for k in group]} is largely anti-phase; "
                f"folded to {fold!r} like the rest of the keybed, it comes out quieter"
            )
        size = int(round(note_seconds * rate))
        fade, fade_in = (
            int(round(FADE_SECONDS * rate)),
            int(round(FADE_IN_SECONDS * rate)),
        )
        for i, key in enumerate(group):
            start = int(round(i * step * rate))
            note = audio[start : start + size].copy()
            if size - len(note) > SHORTFALL_SECONDS * rate:
                raise ValueError(
                    f"keybed: the render for {[note_name(k) for k in group]} is "
                    f"{len(audio) / rate:.2f} s, short of note {note_name(key)}, which "
                    f"ends at {(start + size) / rate:.2f} s"
                )
            if key not in asked:  # rendered only to keep the chunk chromatic
                continue
            k = min(fade, len(note))
            note[len(note) - k :] *= np.linspace(1.0, 0.0, k, dtype=np.float32)
            k = min(fade_in, len(note))
            note[:k] *= np.linspace(0.0, 1.0, k, dtype=np.float32)
            notes[key] = (note, rate)
    sub = {k: round(sub_octave_db(a, r, k), 1) for k, (a, r) in notes.items()}
    low = [note_name(k) for k, db in sub.items() if db > SUB_OCTAVE_WARN_DB]
    if low:
        warnings.warn(
            f"keybed: the octave below dominates {low}; they may sound an octave low "
            f"(sub_octave_db in the render's info)"
        )
    if peak is not None:
        loudest = max(float(np.abs(a).max()) for a, _ in notes.values())
        if loudest > 0:
            gain = peak / loudest
            notes = {k: (a * gain, r) for k, (a, r) in notes.items()}
    return notes, {"seed": seed, "fold": fold, "chunks": sent, "sub_octave_db": sub}


def keybed_instrument(
    descriptor: str,
    folder,
    keys: Iterable[int] = DFLT_KEYS,
    *,
    name: Optional[str] = None,
    formats=("sf2", "sfz"),
    program: int = 0,
    release: float = 0.3,
    **render_kwargs,
) -> dict:
    """Render a keybed and write it as a sampler instrument in ``folder``.

    Returns ``{format: path}`` plus ``"metadata"``: a JSON file with what was asked
    (descriptor, keys, the render arguments) and what came of it (the seed, the prompt
    each chunk was sent), enough to render the same instrument again.

    >>> from arioso.base import AudioResult, Song
    >>> def fake(prompt, *, duration, seed):  # a constant level, as a model would not
    ...     rate = 8000
    ...     return Song(audio=AudioResult(audio_array=np.zeros(int(duration * rate)) + 0.1,
    ...                                   sample_rate=rate))
    >>> import tempfile
    >>> paths = keybed_instrument("Rhodes Piano, Warm", tempfile.mkdtemp(), [60, 64, 67],
    ...                           generate=fake, seed=7)
    >>> sorted(paths)
    ['metadata', 'sf2', 'sfz']
    """
    from arioso.sampler_export import safe_name, write_instrument

    keys = sorted(set(int(k) for k in keys))
    notes, info = render_keybed(descriptor, keys, **render_kwargs)
    name = name or descriptor.split(",")[0].strip() or "keybed"
    folder = Path(folder)
    paths = write_instrument(
        notes, folder, name=name, formats=formats, program=program, release=release
    )
    asked = {k: v for k, v in render_kwargs.items() if k != "generate" and _is_json(v)}
    meta = {
        "descriptor": descriptor,
        "keys": keys,
        "program": program,
        "release": release,
        "render": asked,
        **info,
    }
    paths["metadata"] = folder / f"{safe_name(name)}.json"
    paths["metadata"].write_text(json.dumps(meta, indent=2))
    return paths


def _is_json(value) -> bool:
    try:
        json.dumps(value)
    except TypeError:
        return False
    return True
