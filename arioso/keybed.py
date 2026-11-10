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
from pathlib import Path
from typing import Callable, Iterable, Optional

import numpy as np

from arioso.analysis import NOTES

#: Seconds per note and between notes in a sequence render, as the model was trained.
NOTE_SECONDS, GAP_SECONDS = 3.0, 0.25
#: Most notes per sequence render (six fill the model's ~20 s window).
CHUNK_NOTES = 6
#: The default register: C3 to C5, every key.
DFLT_KEYS = tuple(range(48, 73))
#: Fade at the end of each cut note, so the cut does not click.
FADE_SECONDS = 0.02
#: How much shorter than asked a render may come back (rounding) before it is an error.
SHORTFALL_SECONDS = 0.01
#: The level of the loudest note after the keybed's one gain (about -1 dBFS).
DFLT_PEAK = 0.89


def note_name(key: int) -> str:
    """The note name of MIDI ``key``, C4 = 60 (the RC fork's ``midi_to_note_name``).

    >>> note_name(60), note_name(49), note_name(21)
    ('C4', 'C#3', 'A0')
    """
    return f"{NOTES[key % 12]}{key // 12 - 1}"


def keybed_prompt(descriptor: str, keys: Iterable[int], *, wet: bool = False) -> str:
    """The prompt for ``keys``: the model's control grammar around ``descriptor``.

    ``"Wet"`` or ``"Dry"`` (``wet``) follows the descriptor unless it already says which.
    """
    keys = [int(k) for k in keys]
    tags = [t.strip() for t in descriptor.split(",") if t.strip()]
    if not any(t.lower() in ("wet", "dry") for t in tags):
        tags.append("Wet" if wet else "Dry")
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
    if not all(0 <= k <= 127 for k in keys):
        raise ValueError(f"keys are MIDI numbers 0..127, got {keys}")
    n = math.ceil(len(keys) / size)
    q, r = divmod(len(keys), n)
    out, i = [], 0
    for j in range(n):
        m = q + (j < r)
        out.append(keys[i : i + m])
        i += m
    return out


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
    **generate_kwargs,
) -> tuple:
    """Render one note per key; returns ``({key: (audio, rate)}, info)``.

    ``generate(prompt, *, duration, seed, **generate_kwargs)`` returns a Song; the
    default is the local ``foundation_1`` platform with the keybeds checkpoint, its
    takes left at the model's level. The seed is drawn once (when None) and used for
    every chunk. Every chunk is checked against the model's window (``window_seconds``,
    default the platform's) before anything renders. ``peak``: one gain for the whole
    keybed so its loudest note is there (None: leave the level as rendered).
    ``info`` holds the seed and, per chunk, its keys and the prompt actually sent.
    """
    from arioso._isolated import draw_seed
    from arioso.sampler_export import mono

    groups = chunks(keys, chunk)
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
    notes, sent = {}, []
    for group in groups:
        prompt = keybed_prompt(descriptor, group, wet=wet)
        song = generate(prompt, duration=length(group), seed=seed, **generate_kwargs)
        sent.append(
            {"keys": group, "prompt": (song.metadata or {}).get("prompt_sent", prompt)}
        )
        if song.audio_array is None:
            raise ValueError(f"keybed: the render for {group} came back with no audio")
        audio, rate = mono(song.audio_array), int(song.sample_rate)
        size, fade = int(round(note_seconds * rate)), int(round(FADE_SECONDS * rate))
        for i, key in enumerate(group):
            start = int(round(i * step * rate))
            note = audio[start : start + size].copy()
            if size - len(note) > SHORTFALL_SECONDS * rate:
                raise ValueError(
                    f"keybed: the render for {[note_name(k) for k in group]} is "
                    f"{len(audio) / rate:.2f} s, short of note {note_name(key)}, which "
                    f"ends at {(start + size) / rate:.2f} s"
                )
            k = min(fade, len(note))
            note[len(note) - k :] *= np.linspace(1.0, 0.0, k, dtype=np.float32)
            notes[key] = (note, rate)
    if peak is not None:
        loudest = max(float(np.abs(a).max()) for a, _ in notes.values())
        if loudest > 0:
            gain = peak / loudest
            notes = {k: (a * gain, r) for k, (a, r) in notes.items()}
    return notes, {"seed": seed, "chunks": sent}


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
