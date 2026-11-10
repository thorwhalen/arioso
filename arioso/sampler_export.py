"""Write one-note samples as a playable sampler instrument: an SF2 SoundFont and an SFZ.

Generic: takes ``{midi_key: (mono float array, sample_rate)}`` and knows nothing about
how the notes were made. Each sample plays from its own key up to the midpoint with
its neighbours, at its own pitch at its root key; no loops (one-shots with a release).

Samples are written mono: a phone decodes every sample it plays, and a keybed is
many of them. Stereo is folded to its mid (L+R)/2, or to its left channel where the
mid would cancel (anti-phase content).

The SF2 is what browser SoundFont synths load (timbrel takes it through its ``bank``
seam, as a preset at ``program`` in ``bank``); the SFZ, with one WAV per note, is what
desktop samplers open.
"""

from __future__ import annotations

import math
import struct
from pathlib import Path
from typing import Mapping

import numpy as np

#: SF2 generator numbers used here (SoundFont 2.04, section 8.1.2).
_GEN_RELEASE_VOL_ENV, _GEN_INSTRUMENT, _GEN_KEY_RANGE = 38, 41, 43
_GEN_SAMPLE_ID, _GEN_SAMPLE_MODES = 53, 54
#: Zero samples after each sample, as the format requires (at least 46).
_SF2_PAD = 46


def key_ranges(keys) -> dict:
    """Each root key's ``(low, high)`` range: up to the midpoints with its neighbours,
    the lowest down to 0 and the highest up to 127.

    >>> key_ranges([48, 60, 64])
    {48: (0, 54), 60: (55, 62), 64: (63, 127)}
    """
    keys = sorted(keys)
    if not keys:
        raise ValueError("no samples to map")
    ranges = {}
    for i, key in enumerate(keys):
        low = 0 if i == 0 else (keys[i - 1] + key) // 2 + 1
        high = 127 if i == len(keys) - 1 else (key + keys[i + 1]) // 2
        ranges[key] = (low, high)
    return ranges


def channels_first(audio) -> np.ndarray:
    """``audio`` as a float32 ``(channels, samples)`` array (mono becomes one channel;
    a 2-d array has its channels on the shorter axis)."""
    a = np.asarray(audio, dtype=np.float32)
    if a.ndim == 1:
        a = a[None, :]
    elif a.ndim == 2 and a.shape[0] > a.shape[1]:
        a = a.T
    if a.ndim != 2 or not a.size:
        raise ValueError(
            f"a sample should be a non-empty mono or stereo array, got {a.shape}"
        )
    return a


def choose_fold(audios) -> str:
    """``"mid"`` ((L+R)/2), or ``"left"`` when the mid would lose most of the energy
    (anti-phase content), judged over all of ``audios`` together, so every sample of an
    instrument is folded the same way.

    >>> t = np.linspace(0, 1, 100)
    >>> choose_fold([np.stack([t, t])]), choose_fold([np.stack([t, -t])])
    ('mid', 'left')
    """
    energy = mid_energy = 0.0
    for audio in audios:
        c = channels_first(audio)
        energy += float(np.sum(c**2)) / len(c)
        mid_energy += float(np.sum(c.mean(axis=0) ** 2))
    return "mid" if mid_energy >= 0.25 * energy else "left"


def mono(audio, *, fold: str = None) -> np.ndarray:
    """``audio`` as a 1-d float32 array, folded as ``fold`` says (``"mid"`` or
    ``"left"``; default: :func:`choose_fold` for this audio alone).

    >>> t = np.linspace(0, 1, 100)
    >>> bool(mono(np.stack([t, -t])).max() > 0.9)  # the mid would be silence
    True
    """
    c = channels_first(audio)
    if len(c) == 1:
        return c[0]
    fold = fold or choose_fold([c])
    if fold not in ("mid", "left"):
        raise ValueError(f"fold should be 'mid' or 'left', got {fold!r}")
    return c.mean(axis=0) if fold == "mid" else c[0]


def _int16(a: np.ndarray) -> np.ndarray:
    return (np.clip(a, -1.0, 1.0) * 32767).astype("<i2")


def _name(s: str) -> bytes:
    return s.encode("ascii", "replace")[:19].ljust(20, b"\0")


def _zstr(s: str, *, limit: int = 256) -> bytes:
    """A zero-terminated string padded to an even length (SF2 INFO strings must be)."""
    b = s.encode("ascii", "replace")[: limit - 2] + b"\0"
    return b + b"\0" * (len(b) % 2)


def _timecents(seconds: float) -> int:
    """``seconds`` as SF2 timecents, within the spec's -12000..8000."""
    return max(-12000, min(8000, round(1200 * math.log2(max(seconds, 1e-6)))))


def safe_name(name: str) -> str:
    """``name`` usable as a file name: path separators and control characters replaced.

    >>> safe_name("Bass / Sub: Warm")
    'Bass _ Sub_ Warm'
    """
    cleaned = "".join("_" if c in '/\\:*?"<>|' or ord(c) < 32 else c for c in name)
    return cleaned.strip(" .") or "instrument"


def _chunk(tag: bytes, data: bytes) -> bytes:
    pad = b"\0" if len(data) % 2 else b""
    return tag + struct.pack("<I", len(data)) + data + pad


def _list(kind: bytes, *chunks: bytes) -> bytes:
    return _chunk(b"LIST", kind + b"".join(chunks))


def write_sf2(
    samples: Mapping[int, tuple],
    path,
    *,
    name: str = "instrument",
    program: int = 0,
    bank: int = 0,
    release: float = 0.3,
) -> Path:
    """Write ``samples`` (``{midi_key: (audio, sample_rate)}``) as a one-preset SF2 file.

    16-bit mono samples, one instrument zone per sample over :func:`key_ranges`, the
    preset at ``program`` in ``bank``; ``release`` seconds of fade after note-off.
    """
    ranges = key_ranges(samples)
    smpl, headers = bytearray(), []
    for key in sorted(ranges):
        audio, rate = samples[key]
        pcm = _int16(mono(audio))
        start = len(smpl) // 2
        smpl += pcm.tobytes() + bytes(2 * _SF2_PAD)
        end = start + len(pcm)
        loop = (
            (start + 8, end - 8) if len(pcm) > 16 else (start, end)
        )  # unused: no loop
        headers.append(
            struct.pack(
                "<20sIIIIIBbHH",
                _name(f"{name[:12]}-{key}"),
                start,
                end,
                *loop,
                int(rate),
                key,
                0,
                0,
                1,  # mono
            )
        )
    headers.append(
        struct.pack("<20sIIIIIBbHH", _name("EOS"), 0, 0, 0, 0, 0, 0, 0, 0, 0)
    )

    release_tc = _timecents(release)
    igen, ibag = bytearray(), bytearray()
    for i, key in enumerate(sorted(ranges)):
        low, high = ranges[key]
        ibag += struct.pack("<HH", len(igen) // 4, 0)
        igen += struct.pack("<HBB", _GEN_KEY_RANGE, low, high)  # must come first
        igen += struct.pack("<Hh", _GEN_RELEASE_VOL_ENV, release_tc)
        igen += struct.pack("<HH", _GEN_SAMPLE_MODES, 0)  # no loop
        igen += struct.pack("<HH", _GEN_SAMPLE_ID, i)  # must come last
    ibag += struct.pack("<HH", len(igen) // 4, 0)
    igen += bytes(4)
    inst = struct.pack("<20sH", _name(name), 0) + struct.pack(
        "<20sH", _name("EOI"), len(ranges)
    )

    pgen = struct.pack("<HH", _GEN_INSTRUMENT, 0) + bytes(4)
    pbag = struct.pack("<HH", 0, 0) + struct.pack("<HH", 1, 0)
    phdr = struct.pack("<20sHHHIII", _name(name), program, bank, 0, 0, 0, 0)
    phdr += struct.pack("<20sHHHIII", _name("EOP"), 0, 0, 1, 0, 0, 0)
    terminal_mod = bytes(10)

    info = _list(
        b"INFO",
        _chunk(b"ifil", struct.pack("<HH", 2, 1)),
        _chunk(b"isng", b"EMU8000\0"),
        _chunk(b"INAM", _zstr(name)),
    )
    sdta = _list(b"sdta", _chunk(b"smpl", bytes(smpl)))
    pdta = _list(
        b"pdta",
        _chunk(b"phdr", phdr),
        _chunk(b"pbag", pbag),
        _chunk(b"pmod", terminal_mod),
        _chunk(b"pgen", pgen),
        _chunk(b"inst", inst),
        _chunk(b"ibag", bytes(ibag)),
        _chunk(b"imod", terminal_mod),
        _chunk(b"igen", bytes(igen)),
        _chunk(b"shdr", b"".join(headers)),
    )
    path = Path(path)
    path.write_bytes(_chunk(b"RIFF", b"sfbk" + info + sdta + pdta))
    return path


def write_sfz(
    samples: Mapping[int, tuple],
    folder,
    *,
    name: str = "instrument",
    release: float = 0.3,
) -> Path:
    """Write ``samples`` as ``<name>.sfz`` with one WAV per note in ``folder/<name>/``."""
    import soundfile as sf

    folder, stem = Path(folder), safe_name(name)
    (folder / stem).mkdir(parents=True, exist_ok=True)
    lines = [
        f"// {name}: one-shot samples, one region per note",
        f"<group> ampeg_release={release:g}",
    ]
    for key, (low, high) in key_ranges(samples).items():
        audio, rate = samples[key]
        wav = f"{stem}/{key:03d}.wav"
        sf.write(folder / wav, mono(audio), int(rate), subtype="PCM_16")
        lines.append(  # sample= last: a path with spaces runs to the end of the line
            f"<region> pitch_keycenter={key} lokey={low} hikey={high} sample={wav}"
        )
    path = folder / f"{stem}.sfz"
    path.write_text("\n".join(lines) + "\n")
    return path


def write_instrument(
    samples: Mapping[int, tuple],
    folder,
    *,
    name: str = "instrument",
    formats=("sf2", "sfz"),
    release: float = 0.3,
    **sf2_options,
) -> dict:
    """Write ``samples`` in each of ``formats`` under ``folder``; returns ``{format: path}``.

    Files are named after ``name`` (made safe for a path), so several instruments (the
    layers of one sound, say) can share a folder; ``release`` (seconds) goes to every
    format.
    """
    folder, stem = Path(folder), safe_name(name)
    writers = {
        "sf2": lambda: write_sf2(
            samples, folder / f"{stem}.sf2", name=name, release=release, **sf2_options
        ),
        "sfz": lambda: write_sfz(samples, folder, name=name, release=release),
    }
    unknown = set(formats) - set(writers)
    if unknown:
        raise ValueError(f"unknown formats {sorted(unknown)}; one of {sorted(writers)}")
    folder.mkdir(parents=True, exist_ok=True)
    return {f: writers[f]() for f in formats}
