"""cover_folder: one cover per song, takes saved, refusals recorded, resumable, no double pay."""

import json

import pytest

import arioso.cover as cover
from arioso.base import AudioResult, CatalogMatchError, Song
from arioso.cover import cover_folder, find_suno_task, read_manifest, wait_for_songs


def _take(i, platform="fake"):
    return Song(
        id=f"take{i}",
        status="complete",
        platform=platform,
        audio=AudioResult(audio_bytes=b"ID3" + bytes([i]), format="mp3"),
    )


class FakeCover:
    """A platform that records each call and answers with two complete takes."""

    def __init__(self, refuse=(), fail=()):
        self.calls, self.refuse, self.fail = [], set(refuse), set(fail)

    def __call__(self, prompt, **kwargs):
        self.calls.append({"prompt": prompt, **kwargs})
        if kwargs["title"] in self.refuse:
            raise CatalogMatchError("matches an existing recording", task_id="t-r")
        if kwargs["title"] in self.fail:
            raise ConnectionError("network down")
        return [_take(1), _take(2)]


@pytest.fixture
def songs(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    for name in ("A song.wav", "B song.m4a", "C hum.mp3", "notes.txt", ".hidden.wav"):
        (src / name).write_bytes(b"x")
    return src


def _lyrics(path):
    return "" if path.stem == "C hum" else f"words of {path.stem}"


def test_every_song_is_covered_with_its_lyrics_and_takes_saved(songs, tmp_path):
    dst, fake = tmp_path / "out", FakeCover()
    records = cover_folder(songs, dst, platform="fake", generate=fake, transcribe=_lyrics)
    assert [r["source"] for r in records] == ["A song.wav", "B song.m4a", "C hum.mp3"]
    assert {r["outcome"] for r in records} == {"done"}
    assert fake.calls[0]["lyrics"] == "words of A song"
    assert fake.calls[0]["audio_input_strength"] == cover.DFLT_STRENGTH
    assert fake.calls[0]["title"] == "A song"
    hum = fake.calls[2]
    assert hum["instrumental"] is True and "lyrics" not in hum  # no words heard
    assert (dst / "A song (fake 1).mp3").read_bytes() == b"ID3\x01"
    assert (dst / "A song (fake 2).mp3").is_file()
    assert set(read_manifest(dst / "covers.jsonl")) == {r["source"] for r in records}


def test_a_refusal_is_final_and_an_error_is_retried(songs, tmp_path):
    dst = tmp_path / "out"
    fake = FakeCover(refuse={"A song"}, fail={"B song"})
    first = cover_folder(songs, dst, platform="fake", generate=fake, transcribe=_lyrics)
    assert [r["outcome"] for r in first] == ["refused", "error", "done"]
    assert first[0]["task_id"] == "t-r"
    assert "network down" in first[1]["error"]

    fake.fail.clear()
    again = cover_folder(songs, dst, platform="fake", generate=fake, transcribe=_lyrics)
    assert [(r["source"], r["outcome"]) for r in again] == [("B song.m4a", "done")]
    assert len(fake.calls) == 4  # one more call, for the song that errored


def test_a_task_already_submitted_is_reused_not_paid_again(songs, tmp_path):
    fake, waited = FakeCover(), []

    def wait(pending):
        waited.append(pending[0].id)
        return [_take(1), _take(2)]

    records = cover_folder(
        songs,
        tmp_path / "out",
        platform="fake",
        generate=fake,
        transcribe=None,
        find_task=lambda title: "old-task" if title == "A song" else None,
        wait=wait,
        only=["A song", "C hum"],
    )
    assert [r["reused_task"] for r in records] == [True, False]
    assert [c["title"] for c in fake.calls] == ["C hum"]
    assert waited[0] == "old-task"
    assert "lyrics" not in fake.calls[0] and "instrumental" not in fake.calls[0]


def test_style_is_sent_as_genre_and_as_the_prompt(songs, tmp_path):
    fake = FakeCover()
    cover_folder(
        songs,
        tmp_path / "out",
        platform="fake",
        generate=fake,
        transcribe=None,
        style=lambda path: f"lullaby for {path.stem}",
        only=["A song"],
        model="V5",
    )
    (call,) = fake.calls
    assert call["genre"] == call["prompt"] == "lullaby for A song"
    assert call["model"] == "V5"


def test_find_suno_task_skips_failed_and_other_operations(monkeypatch):
    tasks = {
        "t1": {"operation": "generate", "request_params": {"title": "A"}},
        "t2": {"operation": "upload_cover", "status": "CREATE_TASK_FAILED", "request_params": {"title": "A"}},
        "t3": {"operation": "upload_cover", "status": "SUCCESS", "request_params": {"title": "A"}},
    }

    class Adapter:
        pass

    adapter = Adapter()
    adapter.tasks = tasks
    monkeypatch.setattr(
        "arioso.registry.get_platform", lambda name: {"adapter": adapter}
    )
    assert find_suno_task("A") == "t3"
    assert find_suno_task("B") is None


def test_wait_polls_until_complete_and_raises_on_error_or_timeout():
    pending = [Song(id="t", status="pending", platform="fake")]
    answers = iter([pending, [_take(1), _take(2)]])
    done = wait_for_songs(pending, poll_interval=0, check=lambda s: next(answers))
    assert [s.status for s in done] == ["complete", "complete"]

    failed = [Song(id="t", status="error", platform="fake")]
    with pytest.raises(RuntimeError, match="cover failed"):
        wait_for_songs(failed, poll_interval=0, check=lambda s: failed)
    with pytest.raises(TimeoutError):
        wait_for_songs(pending, poll_interval=0, timeout=0, check=lambda s: pending)


def test_vocal_lyrics_transcribes_the_vocal_stem(tmp_path):
    import numpy as np
    import soundfile as sf

    path = tmp_path / "song.wav"
    sf.write(path, np.zeros((8000, 2), dtype=np.float32), 8000)
    seen = {}

    class Stems:
        vocals, sr = np.zeros((2, 8000), dtype=np.float32), 8000

    class Segment:
        def __init__(self, text):
            self.text = text

    def separate(audio, *, sr):
        seen["shape"], seen["sr"] = audio.shape, sr
        return Stems()

    def transcribe(wav, **kw):
        seen["wav"] = sf.read(wav)[0].shape
        seen["kw"] = kw
        return [Segment(" la la "), Segment("  "), Segment("hush")]

    text = cover.vocal_lyrics(path, separate=separate, transcribe=transcribe, language="en")
    assert text == "la la\nhush"
    assert seen == {"shape": (2, 8000), "sr": 8000, "wav": (8000, 2), "kw": {"language": "en"}}
