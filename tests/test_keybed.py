"""``arioso.keybed`` and ``arioso.sampler_export``: a keybed rendered note by note with a
fake model, cut at the right times, and written as an SF2 a SoundFont synth can read."""

import json
import os
import shutil
import struct

import numpy as np
import pytest

from arioso.base import AudioResult, Song
from arioso.keybed import (
    GAP_SECONDS,
    NOTE_SECONDS,
    chunks,
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
        tail = "Note Sequence, " if "Note Sequence" in prompt else "Target Note, "
        names = prompt.split(tail)[1].split(", ")
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
    notes, info = render_keybed("Rhodes Piano, Warm", keys, generate=model)
    assert sorted(notes) == keys
    prompts, durations, seeds = zip(*model.calls)
    assert prompts == (
        keybed_prompt("Rhodes Piano, Warm", keys[:4]),
        keybed_prompt("Rhodes Piano, Warm", keys[4:]),
    )  # balanced: 4 + 4, not 6 + 2
    assert durations == pytest.approx((4 * 3.0 + 3 * 0.25,) * 2)
    assert set(seeds) == {info["seed"]}
    assert [c["keys"] for c in info["chunks"]] == [keys[:4], keys[4:]]


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

    with pytest.raises(ValueError, match="short of note"):
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
    notes, _ = render_keybed("Pad", [48, 60, 72], generate=FakeModel(), seed=3, chunk=1)
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
    assert "pitch_keycenter=60 lokey=0 hikey=62 sample=Rhodes Piano/060.wav\n" in sfz
    assert (tmp_path / "Rhodes Piano" / "064.wav").is_file()
    meta = json.loads(paths["metadata"].read_text())
    assert meta["seed"] == 11 and meta["keys"] == [60, 64]
    assert meta["chunks"][0]["prompt"] == keybed_prompt("Rhodes Piano, Warm", [60, 64])
    assert meta["render"] == {"seed": 11}


def test_unknown_formats_are_refused_before_writing(tmp_path):
    from arioso.sampler_export import write_instrument

    with pytest.raises(ValueError, match="unknown formats"):
        write_instrument({60: (np.zeros(10), RATE)}, tmp_path, formats=["dspreset"])
    assert not list(tmp_path.iterdir())


def test_the_prompt_follows_the_models_grammar():
    assert keybed_prompt("Pad, Warm", [60, 61, 62]) == (
        "Keybed, Sequence, Timbre Profile, Pad, Warm, Dry, "
        "Chromatic Chunk, Note Sequence, C4, C#4, D4"
    )
    assert "Chromatic Chunk" not in keybed_prompt("Pad", [60, 64])
    assert keybed_prompt("Pad", [60], wet=True) == (
        "Keybed, Timbre Profile, Pad, Wet, Target Note, C4"
    )
    assert keybed_prompt("Pad, dry", [60, 61]).count("ry") == 1  # theirs, not ours too


def test_chunks_are_balanced_and_never_over_the_size():
    for n in range(1, 40):
        sizes = [len(c) for c in chunks(range(20, 20 + n), 6)]
        assert sum(sizes) == n and max(sizes) <= 6 and max(sizes) - min(sizes) <= 1


class Markers:
    """Each note's slot holds a constant unique to it; the gaps hold -1."""

    def __init__(self):
        self.calls = 0

    def __call__(self, prompt, *, duration, seed):
        self.calls += 1
        n = len(prompt.split("Note Sequence, ")[1].split(", "))
        audio = np.full(int(round(duration * RATE)), -1.0, dtype=np.float32)
        step, size = (NOTE_SECONDS + GAP_SECONDS) * RATE, int(NOTE_SECONDS * RATE)
        for i in range(n):
            start = int(round(i * step))
            audio[start : start + size] = (i + 1) / 10
        return Song(audio=AudioResult(audio_array=audio, sample_rate=RATE))


def test_each_note_is_exactly_its_slot_no_gap_no_neighbour():
    notes, _ = render_keybed(
        "Pad", [60, 61, 62, 63], generate=Markers(), seed=1, peak=None
    )
    fade, fade_in = int(0.02 * RATE), int(0.002 * RATE)
    for i, key in enumerate([60, 61, 62, 63]):
        audio, _ = notes[key]
        assert len(audio) == NOTE_SECONDS * RATE
        assert np.all(audio[fade_in : len(audio) - fade] == np.float32((i + 1) / 10)), (
            key
        )
        assert audio[0] == 0 and audio[-1] == 0  # faded in and out


def test_one_gain_for_the_whole_keybed_keeps_the_chunks_balance():
    def levels(prompt, *, duration, seed):  # the second chunk renders half as loud
        level = 0.2 if "C4" in prompt else 0.1
        audio = np.full(int(round(duration * RATE)), level, dtype=np.float32)
        return Song(audio=AudioResult(audio_array=audio, sample_rate=RATE))

    notes, _ = render_keybed(
        "Pad", [60, 72], generate=levels, seed=1, chunk=1, peak=0.8
    )
    assert notes[60][0][100] == pytest.approx(0.8)
    assert notes[72][0][100] == pytest.approx(0.4)


def test_a_chunk_past_the_window_is_refused_before_anything_renders():
    model = FakeModel()
    with pytest.raises(ValueError, match="window"):
        render_keybed("Pad", range(60, 67), generate=model, chunk=7, window_seconds=20)
    assert model.calls == []


def _sf2_records(data):
    chunks_ = _riff_chunks(data)

    def records(tag, size):
        body = chunks_[tag]
        assert len(body) % size == 0, tag
        return [body[i : i + size] for i in range(0, len(body), size)]

    return chunks_, records


@pytest.mark.parametrize("name", ["Pad", "Rhodes Piano", "A very long instrument name"])
def test_the_sf2_is_structurally_valid(tmp_path, name):
    notes, _ = render_keybed("Pad", [48, 60, 72], generate=FakeModel(), seed=3, chunk=1)
    data = write_sf2(notes, tmp_path / "x.sf2", name=name, release=0.5).read_bytes()
    chunks_, records = _sf2_records(data)
    assert len(chunks_[b"INAM"]) % 2 == 0 and chunks_[b"INAM"].endswith(b"\0")
    assert struct.unpack("<HH", chunks_[b"ifil"]) == (2, 1)
    for bag, gen in [(b"pbag", b"pgen"), (b"ibag", b"igen")]:
        gens = records(gen, 4)
        assert gens[-1] == bytes(4), f"{gen} terminal record"
        # the terminal bag points at the terminal generator
        assert struct.unpack("<HH", records(bag, 4)[-1]) == (len(gens) - 1, 0), bag
    for tag in (b"pmod", b"imod"):
        assert chunks_[tag] == bytes(10)
    shdr = [struct.unpack("<20sIIIIIBbHH", r) for r in records(b"shdr", 46)]
    assert len({h[0] for h in shdr}) == len(shdr)  # distinct sample names
    pcm = np.frombuffer(chunks_[b"smpl"], dtype="<i2")
    for h in shdr[:-1]:
        start, end, loop_start, loop_end = h[1:5]
        assert start <= loop_start < loop_end <= end
        assert not pcm[end : end + 46].any() and len(pcm[end : end + 46]) == 46  # pad
    igen = [struct.unpack("<HH", r) for r in records(b"igen", 4)]
    bags = [struct.unpack("<HH", r)[0] for r in records(b"ibag", 4)]
    zones = [igen[a:b] for a, b in zip(bags, bags[1:])]
    assert len(zones) == 3
    for i, zone in enumerate(zones):
        ops = [op for op, _ in zone]
        assert (
            ops[0] == 43 and ops[-1] == 53 and zone[-1][1] == i
        )  # keyRange first, sampleID last
        assert (
            dict(zone)[38] == struct.unpack("<H", struct.pack("<h", -1200))[0]
        )  # 0.5 s


@pytest.mark.skipif(shutil.which("fluidsynth") is None, reason="needs FluidSynth")
@pytest.mark.parametrize("name", ["Pad", "Rhodes Piano"])  # both INAM parities
def test_fluidsynth_plays_each_key_at_its_pitch(tmp_path, name):
    import subprocess

    import mido
    import soundfile as sf

    notes, _ = render_keybed("Pad", [48, 60, 72], generate=FakeModel(), seed=3, chunk=1)
    sf2 = write_sf2(notes, tmp_path / "x.sf2", name=name)
    midi = mido.MidiFile()
    track = mido.MidiTrack()
    midi.tracks.append(track)
    played = [60, 66, 72]  # 66 is 60's sample, shifted
    for key in played:
        track.append(mido.Message("note_on", note=key, velocity=100, time=0))
        track.append(mido.Message("note_off", note=key, time=480))
    midi.save(tmp_path / "t.mid")
    out = tmp_path / "out.wav"
    run = subprocess.run(
        [
            "fluidsynth",
            "-ni",
            "-q",
            "-r",
            "44100",
            "-F",
            str(out),
            str(sf2),
            str(tmp_path / "t.mid"),
        ],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=60,
    )
    assert "Rejecting" not in run.stderr + run.stdout, run.stderr
    audio, rate = sf.read(out)
    audio = audio.mean(axis=1) if audio.ndim > 1 else audio
    for i, key in enumerate(played):
        segment = audio[int((i * 0.5 + 0.05) * rate) : int((i * 0.5 + 0.4) * rate)]
        assert _pitch(segment, rate) == pytest.approx(_freq(key), rel=0.02), key


def test_release_reaches_every_format_and_odd_names_are_safe(tmp_path):
    paths = keybed_instrument(
        "Bass / Sub, Warm",
        tmp_path,
        [40, 45],
        generate=FakeModel(),
        seed=2,
        release=1.5,
    )
    assert "ampeg_release=1.5" in paths["sfz"].read_text()
    assert paths["sf2"].name == "Bass _ Sub.sf2" and paths["sf2"].is_file()
    igen = _riff_chunks(paths["sf2"].read_bytes())[b"igen"]
    gens = [struct.unpack("<Hh", igen[i : i + 4]) for i in range(0, len(igen), 4)]
    assert (38, round(1200 * np.log2(1.5))) in gens


def test_effect_tags_follow_wet_and_are_refused_dry():
    assert keybed_prompt("Pad, Warm, Medium Reverb", [60], wet=True) == (
        "Keybed, Timbre Profile, Pad, Warm, Wet, Medium Reverb, Target Note, C4"
    )
    assert keybed_prompt("Pad, Medium Reverb, Wet", [60]).endswith(
        "Pad, Wet, Medium Reverb, Target Note, C4"
    )
    with pytest.raises(ValueError, match="wet"):
        keybed_prompt("Pad, Medium Reverb", [60])
    with pytest.raises(ValueError, match="both"):
        keybed_prompt("Pad, Wet, Dry", [60])


def test_keys_outside_the_models_range_are_refused():
    with pytest.raises(ValueError, match="C0..C8"):
        chunks([11, 60])
    with pytest.raises(ValueError, match="C0..C8"):
        chunks([109])


def _stereo(prompt, *, duration, seed, anti=False):
    mono_song = FakeModel()(prompt, duration=duration, seed=seed)
    left = mono_song.audio_array
    right = -left if anti else left
    return Song(  # (samples, 2), as soundfile reads a stereo wav
        audio=AudioResult(audio_array=np.stack([left, right], axis=1), sample_rate=RATE)
    )


def test_stereo_takes_fold_to_mono_at_the_right_pitch():
    notes, info = render_keybed("Pad", [48, 60, 72], generate=_stereo, seed=1, chunk=1)
    assert info["fold"] == "mid"
    for key, (audio, rate) in notes.items():
        assert audio.ndim == 1 and len(audio) == NOTE_SECONDS * rate
        assert _pitch(audio, rate) == pytest.approx(_freq(key), rel=0.02)


def test_an_anti_phase_keybed_is_not_folded_to_silence():
    def anti(prompt, *, duration, seed):
        return _stereo(prompt, duration=duration, seed=seed, anti=True)

    notes, info = render_keybed(
        "Pad", [60, 61, 62, 72], generate=anti, seed=1, peak=None
    )
    assert info["fold"] == "left"  # one choice for every chunk
    assert all(np.abs(a).max() > 0.4 for a, _ in notes.values())


def test_the_default_generator_keeps_the_models_level(monkeypatch):
    import arioso

    seen = []

    def generate(prompt, **kwargs):
        seen.append(kwargs)
        return FakeModel()(prompt, duration=kwargs["duration"], seed=kwargs["seed"])

    monkeypatch.setattr(arioso, "generate", generate)
    render_keybed("Pad", [60, 61], seed=1)
    assert seen and all(
        k["normalize"] is False
        and k["platform"] == "foundation_1"
        and k["model"] == "1.2-keybeds"
        for k in seen
    )


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
        audio, rate = sf.read(tmp_path / "Grand Piano" / f"{key:03d}.wav")
        assert _pitch(audio[: rate // 2], rate) == pytest.approx(
            _freq(key), rel=0.03
        ), key
