"""Keybeds: a playable sampler instrument from one descriptor, rendered note by note.

Foundation-1.2-Keybeds (the ``foundation_1`` platform, ``model="1.2-keybeds"``) keeps one
timbre across pitch when it renders several notes of the same instrument in one clip.
Its author's workflow (``keybed_training_strategy.md`` in the model repository), which
this follows: the register is split into chunks of up to six notes, each rendered as
one sequence (3.0 s per note, 0.25 s apart) under the prompt
``"Keybed, Sequence, Timbre Profile, <descriptor>, Chromatic Chunk, Note Sequence, C4,
C#4, ..."``, with one seed for every chunk; the clip is then cut back into notes at those
known times, and the notes are mapped across the keyboard
(:mod:`arioso.sampler_export`: an SF2 that browser SoundFont synths load, and an SFZ).

>>> keybed_prompt("Rhodes Piano, Warm", [60, 61])
'Keybed, Sequence, Timbre Profile, Rhodes Piano, Warm, Chromatic Chunk, Note Sequence, C4, C#4'
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Iterable, Optional

import numpy as np

#: Seconds per note and between notes in a sequence render, as the model was trained.
NOTE_SECONDS, GAP_SECONDS = 3.0, 0.25
#: Notes per sequence render (six fill the model's ~20 s window).
CHUNK_NOTES = 6
#: The default register: C3 to C5, every key.
DFLT_KEYS = tuple(range(48, 73))
#: Fade at the end of each cut note, so the cut does not click.
FADE_SECONDS = 0.02

_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def note_name(key: int) -> str:
    """The note name of MIDI ``key``, with C4 = 60 (the model's note names).

    >>> note_name(60), note_name(49), note_name(21)
    ('C4', 'C#3', 'A0')
    """
    return f"{_NAMES[key % 12]}{key // 12 - 1}"


def keybed_prompt(descriptor: str, keys: Iterable[int]) -> str:
    """The sequence prompt for ``keys`` (the model's control grammar around ``descriptor``)."""
    notes = ", ".join(note_name(k) for k in keys)
    return (
        f"Keybed, Sequence, Timbre Profile, {descriptor.strip().strip(',')}, "
        f"Chromatic Chunk, Note Sequence, {notes}"
    )


def _chunks(keys, size):
    keys = sorted(set(int(k) for k in keys))
    if not keys:
        raise ValueError("no keys to render")
    if not all(0 <= k <= 127 for k in keys):
        raise ValueError(f"keys are MIDI numbers 0..127, got {keys}")
    return [keys[i : i + size] for i in range(0, len(keys), size)]


def _default_generate(prompt, **kwargs):
    import arioso

    return arioso.generate(
        prompt, platform="foundation_1", model="1.2-keybeds", **kwargs
    )


def _mono(song) -> tuple:
    audio = np.asarray(song.audio_array, dtype=np.float32)
    if audio.ndim == 2:  # channels on the shorter axis
        audio = audio.mean(axis=0 if audio.shape[0] < audio.shape[1] else 1)
    return audio, int(song.sample_rate)


def render_keybed(
    descriptor: str,
    keys: Iterable[int] = DFLT_KEYS,
    *,
    seed: Optional[int] = None,
    generate: Callable = None,
    chunk: int = CHUNK_NOTES,
    note_seconds: float = NOTE_SECONDS,
    gap_seconds: float = GAP_SECONDS,
    **generate_kwargs,
) -> tuple:
    """Render one note per key of ``keys``; returns ``({key: (audio, rate)}, seed)``.

    ``generate(prompt, *, duration, seed, **generate_kwargs)`` returns a Song; the
    default is the local ``foundation_1`` platform with the keybeds checkpoint. The seed
    is drawn once (when None) and used for every chunk.
    """
    from arioso._isolated import draw_seed

    generate = generate or _default_generate
    seed = draw_seed() if seed is None else int(seed)
    step = note_seconds + gap_seconds
    notes = {}
    for keys_ in _chunks(keys, chunk):
        duration = len(keys_) * note_seconds + (len(keys_) - 1) * gap_seconds
        song = generate(
            keybed_prompt(descriptor, keys_),
            duration=duration,
            seed=seed,
            **generate_kwargs,
        )
        audio, rate = _mono(song)
        length, fade = int(note_seconds * rate), int(FADE_SECONDS * rate)
        for i, key in enumerate(keys_):
            start = int(round(i * step * rate))
            note = audio[start : start + length].copy()
            if len(note) < length // 2:
                raise ValueError(
                    f"keybed: the render for {keys_} is {len(audio) / rate:.2f} s, "
                    f"too short for note {note_name(key)} at {start / rate:.2f} s"
                )
            note[-fade:] *= np.linspace(
                1.0, 0.0, min(fade, len(note)), dtype=np.float32
            )
            notes[key] = (note, rate)
    return notes, seed


def keybed_instrument(
    descriptor: str,
    folder,
    keys: Iterable[int] = DFLT_KEYS,
    *,
    name: Optional[str] = None,
    formats=("sf2", "sfz"),
    program: int = 0,
    **render_kwargs,
) -> dict:
    """Render a keybed and write it as a sampler instrument in ``folder``.

    Returns ``{format: path}`` plus ``"metadata"``: a JSON file with the descriptor, the
    seed, the keys and the prompts, so the instrument can be rendered again or extended.

    >>> from arioso.base import AudioResult, Song
    >>> def fake(prompt, *, duration, seed):  # a tone per note, as a model would
    ...     rate = 8000
    ...     return Song(audio=AudioResult(audio_array=np.zeros(int(duration * rate)) + 0.1,
    ...                                   sample_rate=rate))
    >>> import tempfile
    >>> paths = keybed_instrument("Rhodes Piano, Warm", tempfile.mkdtemp(), [60, 64, 67],
    ...                           generate=fake, seed=7)
    >>> sorted(paths)
    ['metadata', 'sf2', 'sfz']
    """
    from arioso.sampler_export import write_instrument

    keys = sorted(set(int(k) for k in keys))
    notes, seed = render_keybed(descriptor, keys, **render_kwargs)
    name = name or descriptor.split(",")[0].strip() or "keybed"
    folder = Path(folder)
    paths = write_instrument(notes, folder, name=name, formats=formats, program=program)
    chunk = render_kwargs.get("chunk", CHUNK_NOTES)
    meta = {
        "descriptor": descriptor,
        "seed": seed,
        "keys": keys,
        "prompts": [keybed_prompt(descriptor, c) for c in _chunks(keys, chunk)],
        "program": program,
    }
    paths["metadata"] = folder / f"{name}.json"
    paths["metadata"].write_text(json.dumps(meta, indent=2))
    return paths
