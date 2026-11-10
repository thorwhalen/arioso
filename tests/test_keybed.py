"""``arioso.keybed`` and ``arioso.sampler_export``: a keybed rendered note by note with a
fake model, cut at the right times, and written as an SF2 a SoundFont synth can read."""

import json
import os
import struct

import numpy as np
import pytest

from arioso.base import AudioResult, Song
from arioso.keybed import (
    GAP_SECONDS,
    NOTE_SECONDS,
    keybed_instrument,
    keybed_prompt,
    note_name,
    render_keybed,
)
from arioso.sampler_export import key_ranges, write_sf2

RATE = 8000


def _freq(key):
    return 440.0 * 2 ** ((key - 69) / 12)


class FakeModel:
    """Renders each note of the prompt's sequence as a sine at its pitch, in its slot."""

    def __init__(self):
        self.calls = []

    def __call__(self, prompt, *, duration, seed):
        self.calls.append((prompt, duration, seed))
        names = prompt.split("Note Sequence, ")[1].split(", ")
        by_name = {note_name(k): k for k in range(128)}
        audio = np.zeros(int(round(duration * RATE)), dtype=np.float32)
        t = np.arange(int(NOTE_SECONDS * RATE)) / RATE
        for i, name in enumerate(names):
            start = int(round(i * (NOTE_SECONDS + GAP_SECONDS) * RATE))
            tone = 0.5 * np.sin(2 * np.pi * _freq(by_name[name]) * t)
            audio[start : start + len(t)] = tone[: len(audio) - start]
        return Song(audio=AudioResult(audio_array=audio, sample_rate=RATE))


def _pitch(audio, rate):
    spectrum = np.abs(np.fft.rfft(audio * np.hanning(len(audio))))
    return np.fft.rfftfreq(len(audio), 1 / rate)[np.argmax(spectrum)]


def test_note_names_follow_c4_is_60():
    assert [note_name(k) for k in (59, 60, 61, 72)] == ["B3", "C4", "C#4", "C5"]


def test_keys_are_rendered_in_chunks_of_six_with_one_seed():
    model = FakeModel()
    keys = list(range(60, 68))  # 8 keys: a chunk of 6, then 2
    notes, seed = render_keybed("Rhodes Piano, Warm", keys, generate=model)
    assert sorted(notes) == keys
    prompts, durations, seeds = zip(*model.calls)
    assert prompts == (
        keybed_prompt("Rhodes Piano, Warm", keys[:6]),
        keybed_prompt("Rhodes Piano, Warm", keys[6:]),
    )
    assert durations == pytest.approx((6 * 3.0 + 5 * 0.25, 2 * 3.0 + 0.25))
    assert set(seeds) == {seed}


def test_each_note_is_cut_from_its_own_slot():
    notes, _ = render_keybed(
        "Pad", [48, 55, 60, 64, 67, 72, 79], generate=FakeModel(), seed=3
    )
    for key, (audio, rate) in notes.items():
        assert len(audio) == NOTE_SECONDS * rate
        assert _pitch(audio, rate) == pytest.approx(_freq(key), rel=0.02), key
        assert abs(audio[-1]) < 1e-3  # faded, no click


def test_a_render_too_short_for_its_notes_is_refused():
    def short(prompt, *, duration, seed):
        return Song(audio=AudioResult(audio_array=np.zeros(RATE), sample_rate=RATE))

    with pytest.raises(ValueError, match="too short"):
        render_keybed("Pad", [60, 61, 62], generate=short, seed=1)


def test_key_ranges_cover_the_keyboard_without_overlap():
    ranges = key_ranges([60, 48, 72, 50])
    covered = [k for low, high in ranges.values() for k in range(low, high + 1)]
    assert sorted(covered) == list(range(128))
    assert all(low <= root <= high for root, (low, high) in ranges.items())


def _riff_chunks(data, offset=12, end=None):
    """{tag: bytes} for the chunks inside a RIFF/LIST body, LISTs flattened."""
    end = len(data) if end is None else end
    found = {}
    while offset < end:
        tag, size = (
            data[offset : offset + 4],
            struct.unpack("<I", data[offset + 4 : offset + 8])[0],
        )
        body = offset + 8
        if tag == b"LIST":
            found.update(_riff_chunks(data, body + 4, body + size))
        else:
            found[tag] = data[body : body + size]
        offset = body + size + (size % 2)
    return found


def test_the_sf2_maps_each_sample_to_its_root_key_and_range(tmp_path):
    notes, _ = render_keybed("Pad", [48, 60, 72], generate=FakeModel(), seed=3)
    data = write_sf2(notes, tmp_path / "pad.sf2", name="Pad", program=5).read_bytes()
    assert data[:4] == b"RIFF" and data[8:12] == b"sfbk"
    assert struct.unpack("<I", data[4:8])[0] == len(data) - 8
    chunks = _riff_chunks(data)
    name, program, bank = struct.unpack("<20sHH", chunks[b"phdr"][:24])
    assert (name.rstrip(b"\0"), program, bank) == (b"Pad", 5, 0)
    shdr = [
        struct.unpack("<20sIIIIIBbHH", chunks[b"shdr"][i : i + 46])
        for i in range(0, len(chunks[b"shdr"]), 46)
    ]
    assert [h[6] for h in shdr[:-1]] == [48, 60, 72] and shdr[-1][0].startswith(b"EOS")
    assert all(h[2] - h[1] == NOTE_SECONDS * RATE and h[5] == RATE for h in shdr[:-1])
    pcm = np.frombuffer(chunks[b"smpl"], dtype="<i2")
    start, end = shdr[1][1], shdr[1][2]
    assert _pitch(pcm[start:end].astype(float), RATE) == pytest.approx(
        _freq(60), rel=0.02
    )
    igen = [
        struct.unpack("<HBB", chunks[b"igen"][i : i + 4])
        for i in range(0, len(chunks[b"igen"]), 4)
    ]
    key_ranges_written = [(lo, hi) for op, lo, hi in igen if op == 43]
    assert key_ranges_written == [(0, 54), (55, 66), (67, 127)]


def test_the_instrument_folder_has_sf2_sfz_wavs_and_metadata(tmp_path):
    paths = keybed_instrument(
        "Rhodes Piano, Warm", tmp_path, [60, 64], generate=FakeModel(), seed=11
    )
    assert paths["sf2"].name == "Rhodes Piano.sf2"
    sfz = paths["sfz"].read_text()
    assert "sample=samples/060.wav pitch_keycenter=60 lokey=0 hikey=62" in sfz
    assert (tmp_path / "samples" / "064.wav").is_file()
    meta = json.loads(paths["metadata"].read_text())
    assert meta["seed"] == 11 and meta["keys"] == [60, 64]


def test_unknown_formats_are_refused_before_writing(tmp_path):
    from arioso.sampler_export import write_instrument

    with pytest.raises(ValueError, match="unknown formats"):
        write_instrument({60: (np.zeros(10), RATE)}, tmp_path, formats=["dspreset"])
    assert not list(tmp_path.iterdir())


def _keybed_weights():
    from arioso.platforms.foundation_1.adapter import cached_weights

    return cached_weights("1.2-keybeds")


@pytest.mark.skipif(
    not os.environ.get("ARIOSO_RUN_INTEGRATION") or _keybed_weights() is None,
    reason="real keybed render: needs the 1.2-keybeds weights and ARIOSO_RUN_INTEGRATION=1 (~14 GB peak)",
)
def test_a_real_keybed_is_three_notes_at_their_pitches(tmp_path):
    paths = keybed_instrument("Grand Piano, Warm", tmp_path, [57, 60, 64], seed=7)
    import soundfile as sf

    assert paths["sf2"].read_bytes()[:4] == b"RIFF"
    for key in (
        57,
        60,
        64,
    ):  # the model was asked for these pitches: check it gave them
        audio, rate = sf.read(tmp_path / "samples" / f"{key:03d}.wav")
        assert _pitch(audio[: rate // 2], rate) == pytest.approx(
            _freq(key), rel=0.03
        ), key
