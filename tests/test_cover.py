"""cover_folder: one cover per song, takes saved, refusals recorded, resumable, no double pay."""

import pytest

import arioso.cover as cover
from arioso.base import AudioResult, CatalogMatchError, Song
from arioso.cover import cover_folder, read_manifest, wait_for_songs


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
        title = kwargs["audio_input"].rsplit("/", 1)[-1].rsplit(".", 1)[0]
        if title in self.refuse:
            raise CatalogMatchError("matches an existing recording", task_id="t-r")
        if title in self.fail:
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


def test_a_run_that_stopped_while_waiting_reuses_its_task(songs, tmp_path):
    dst, fake = tmp_path / "out", FakeCover()

    def crash(pending):
        raise KeyboardInterrupt  # the process dies after submitting, before saving

    with pytest.raises(KeyboardInterrupt):
        cover_folder(songs, dst, platform="fake", generate=fake, transcribe=None, wait=crash)
    assert read_manifest(dst / "covers.jsonl")["A song.wav"]["outcome"] == "submitted"

    waited = []

    def wait(pending):
        waited.append(pending[0].id)
        return [_take(1), _take(2)]

    records = cover_folder(
        songs, dst, platform="fake", generate=fake, transcribe=None, wait=wait
    )
    assert [r["reused_task"] for r in records] == [True, False, False]
    assert waited[0] == "take1"  # the task the first run submitted
    assert len(fake.calls) == 3  # A once, then B and C: never A again


def test_an_error_reuses_its_task_once_then_submits_anew(songs, tmp_path):
    dst, fake = tmp_path / "out", FakeCover()

    def expired(pending):
        raise RuntimeError("audio expired")

    run = dict(platform="fake", generate=fake, transcribe=None, only=["A song"])
    assert cover_folder(songs, dst, wait=expired, **run)[0]["outcome"] == "error"
    second = cover_folder(songs, dst, wait=expired, **run)[0]
    assert second["reused_task"] and len(fake.calls) == 1
    third = cover_folder(songs, dst, wait=lambda s: s, **run)[0]
    assert third["outcome"] == "done" and not third["reused_task"]
    assert len(fake.calls) == 2


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


def test_parameters_the_platform_does_not_take_are_dropped(songs, tmp_path):
    fake = FakeCover()
    cover_folder(
        songs,
        tmp_path / "out",
        platform="musicgen",
        generate=fake,
        transcribe=lambda p: "words",
        only=["A song"],
    )
    (call,) = fake.calls
    assert "lyrics" not in call and "title" not in call
    assert call["audio_input"].endswith("A song.wav")


def test_lyrics_are_transcribed_only_for_a_platform_that_takes_them(
    songs, tmp_path, monkeypatch
):
    heard = []
    monkeypatch.setattr(cover, "vocal_lyrics", lambda p: heard.append(p.stem) or "la")
    fake = FakeCover()
    run = dict(generate=fake, only=["A song"], transcribe=cover.AUTO)
    cover_folder(songs, tmp_path / "m", platform="musicgen", **run)
    assert heard == []
    cover_folder(songs, tmp_path / "s", platform="sunoapi", **run)
    assert heard == ["A song"] and fake.calls[-1]["lyrics"] == "la"


def test_two_files_with_one_stem_are_refused(tmp_path):
    (tmp_path / "Song.wav").write_bytes(b"x")
    (tmp_path / "Song.mp3").write_bytes(b"x")
    with pytest.raises(ValueError, match="share the stems"):
        cover_folder(tmp_path, tmp_path / "out", platform="fake", generate=FakeCover())


def test_a_torn_manifest_line_is_skipped(tmp_path):
    path = tmp_path / "covers.jsonl"
    path.write_text('{"source": "a.wav", "outcome": "done"}\n{"source": "b.wa')
    assert list(read_manifest(path)) == ["a.wav"]


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
    with pytest.raises(ValueError, match="returned none"):
        wait_for_songs([])


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

    text = cover.vocal_lyrics(
        path, separate=separate, transcribe=transcribe, language="en"
    )
    assert text == "la la\nhush"
    assert seen == {
        "shape": (2, 8000),
        "sr": 8000,
        "wav": (8000, 2),
        "kw": {"language": "en"},
    }


def test_a_catalog_refusal_at_submit_is_a_catalog_match_error():
    from arioso.platforms.sunoapi.adapter import _check_api_error

    with pytest.raises(CatalogMatchError):
        _check_api_error({"code": 413, "msg": "matches an existing recording in our catalog"})
    with pytest.raises(RuntimeError) as e:
        _check_api_error({"code": 500, "msg": "boom"})
    assert not isinstance(e.value, CatalogMatchError)
