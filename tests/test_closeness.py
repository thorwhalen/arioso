"""``arioso.closeness``: whether a take is a cover of its source, from its words or its melody's rank."""
import functools
import json

import numpy as np
import pytest

from arioso.closeness import cover_closeness, lyric_recall

SR = 22050
SONG = "stinky poo stinky poo where are you where are you hiding in the garden under the leaves today"
OTHER = "climbing up the mountain with my mummy every single morning before the sun comes up again"


def _fakes(texts, melodies):
    """A transcriber, a loader and a melody score that read the file's name."""
    transcribe = lambda p: texts.get(p.stem, "")
    load = lambda p: p.stem
    melody = lambda take, source, sr: melodies[(take, source)]
    return dict(transcribe=transcribe, load=load, melody=melody)


def test_a_take_that_sings_the_sources_words_is_a_cover_and_one_that_does_not_is_not(tmp_path):
    texts = {"song": SONG, "take1": SONG + " la la", "take2": OTHER}
    melodies = {("take1", "song"): 0.5, ("take2", "song"): 0.7}  # the melody alone would say the opposite
    got = cover_closeness(tmp_path / "song.wav", [tmp_path / "take1.mp3", tmp_path / "take2.mp3"], **_fakes(texts, melodies))
    assert got["takes"]["take1.mp3"]["verdict"] == "cover"
    assert got["takes"]["take1.mp3"]["lyric_recall"] == 1.0
    assert got["takes"]["take2.mp3"]["verdict"] == "not a cover"


def test_an_instrumental_take_is_judged_by_its_melodys_rank_among_other_songs(tmp_path):
    texts = {"song": SONG}  # the takes have no words
    melodies = {("take1", "song"): 0.66, ("take1", "a"): 0.55, ("take1", "b"): 0.45,
                ("take2", "song"): 0.57, ("take2", "a"): 0.61, ("take2", "b"): 0.40}
    files = [tmp_path / n for n in ("song.wav", "a.wav", "b.wav")]
    got = cover_closeness(files[0], [tmp_path / "take1.mp3", tmp_path / "take2.mp3"], references=files, **_fakes(texts, melodies))
    assert got["references"] == ["a.wav", "b.wav"]  # the source itself is skipped
    one, two = got["takes"]["take1.mp3"], got["takes"]["take2.mp3"]
    assert (one["verdict"], one["melody_rank"]) == ("cover", 1)
    assert (two["verdict"], two["melody_rank"]) == ("not a cover", 2)


def test_without_words_or_other_songs_there_is_no_verdict(tmp_path):
    got = cover_closeness(tmp_path / "song.wav", [tmp_path / "take.mp3"], **_fakes({}, {("take", "song"): 0.9}))
    assert got["takes"]["take.mp3"]["verdict"] == "unclear"
    assert got["takes"]["take.mp3"]["lyric_recall"] is None


def test_the_melody_rank_finds_the_source_among_other_tunes_with_the_real_melody_match(tmp_path):
    rng = np.random.default_rng(0)

    def tune(keys, *, note_s=0.4, harmonics=1):
        t = np.arange(int(note_s * SR)) / SR
        notes = []
        for k in keys:
            f = 440.0 * 2 ** ((k - 69) / 12)
            notes.append(sum(np.sin(2 * np.pi * f * h * t) / h for h in range(1, harmonics + 1)) * np.hanning(len(t)))
        return np.concatenate(notes).astype(np.float32)

    melody = [72, 74, 76, 72, 79, 77, 76, 74] * 3
    audio = {
        "song": tune(melody),
        "take": tune(melody, note_s=0.45, harmonics=3) + 0.01 * rng.standard_normal(int(0.45 * SR) * len(melody)),
        "a": tune([84, 81, 77, 79, 72, 75, 78, 73] * 3),
        "b": tune([73, 78, 82, 80, 75, 83, 77, 85] * 3),
    }
    got = cover_closeness(tmp_path / "song.wav", [tmp_path / "take.wav"], references=[tmp_path / "a.wav", tmp_path / "b.wav"],
                          transcribe=None, load=lambda p: audio[p.stem])
    assert got["takes"]["take.wav"]["melody_rank"] == 1 and got["takes"]["take.wav"]["verdict"] == "cover"


def test_lyric_recall_counts_the_sources_words_in_order():
    assert lyric_recall("a b c d", "a x b y c") == 0.75
    assert lyric_recall("Don’t stop", "don’t STOP") == 1.0


def test_cover_folder_keeps_each_songs_assessment_and_a_failed_check_loses_no_take(tmp_path):
    from arioso.base import AudioResult, Song
    from arioso.cover import cover_folder

    src, dst = tmp_path / "src", tmp_path / "dst"
    src.mkdir()
    for name in ("Lullaby.wav", "Rhyme.wav"):
        (src / name).write_bytes(b"RIFF")

    def fake(prompt, **kw):
        return [Song(id="t1", status="complete", platform="fake", audio=AudioResult(audio_bytes=b"ID3", format="mp3"))]

    def assess(source, takes):
        if source.stem == "Rhyme":
            raise RuntimeError("no audio")
        return {"source": source.name, "takes": {t.name: {"verdict": "cover"} for t in takes}}

    records = cover_folder(src, dst, platform="fake", generate=fake, transcribe=None, assess=assess)
    by = {r["source"]: r for r in records}
    assert by["Lullaby.wav"]["assessment"]["takes"] == {"Lullaby (fake 1).mp3": {"verdict": "cover"}}
    assert by["Rhyme.wav"]["outcome"] == "done" and "RuntimeError" in by["Rhyme.wav"]["assessment_error"]
    assert (dst / "Rhyme (fake 1).mp3").exists()
    written = [json.loads(line) for line in (dst / "covers.jsonl").read_text().splitlines()]
    done = next(r for r in written if r["source"] == "Lullaby.wav" and r["outcome"] == "done")
    assert done["assessment"]["source"] == "Lullaby.wav"  # in the manifest too
