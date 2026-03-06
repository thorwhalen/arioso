"""Tests for arioso.base module."""

from arioso.base import AudioResult, Song, Affordance, AFFORDANCES


def test_audio_result_defaults():
    ar = AudioResult()
    assert ar.audio_bytes is None
    assert ar.audio_url == ""
    assert ar.audio_array is None
    assert ar.sample_rate == 0
    assert ar.format == ""
    assert ar.duration_seconds == 0.0


def test_audio_result_with_bytes():
    ar = AudioResult(audio_bytes=b"fake audio", format="mp3", sample_rate=44100)
    assert ar.audio_bytes == b"fake audio"
    assert ar.format == "mp3"
    assert ar.sample_rate == 44100


def test_song_defaults():
    song = Song()
    assert song.id == ""
    assert song.title == ""
    assert song.status == "pending"
    assert song.platform == ""
    assert isinstance(song.audio, AudioResult)
    assert isinstance(song.metadata, dict)


def test_song_convenience_properties():
    audio = AudioResult(
        audio_bytes=b"data", audio_url="https://example.com/song.mp3", sample_rate=44100
    )
    song = Song(audio=audio)
    assert song.audio_bytes == b"data"
    assert song.audio_url == "https://example.com/song.mp3"
    assert song.audio_array is None
    assert song.sample_rate == 44100


def test_song_with_metadata():
    song = Song(
        id="abc123",
        title="Test Song",
        status="complete",
        platform="musicgen",
        metadata={"model": "facebook/musicgen-small"},
    )
    assert song.id == "abc123"
    assert song.title == "Test Song"
    assert song.status == "complete"
    assert song.platform == "musicgen"
    assert song.metadata["model"] == "facebook/musicgen-small"


def test_affordance_frozen():
    aff = Affordance("prompt", str, "Text description")
    assert aff.name == "prompt"
    assert aff.type is str
    assert aff.default is None


def test_affordances_completeness():
    # Should have all 40 affordances
    assert len(AFFORDANCES) == 40
    # Key ones must exist
    for name in ["prompt", "duration", "lyrics", "instrumental", "seed", "guidance"]:
        assert name in AFFORDANCES, f"Missing affordance: {name}"


def test_song_is_error():
    # Normal song is not an error
    song = Song(status="complete")
    assert not song.is_error
    assert song.error_message == ""

    # Status "error" is detected
    song = Song(status="error")
    assert song.is_error
    assert song.error_message == "Unknown error"

    # API-level error in metadata (HTTP 200 but code != 200)
    song = Song(
        status="pending",
        metadata={"code": 400, "msg": "model cannot be null"},
    )
    assert song.is_error
    assert "model cannot be null" in song.error_message
    assert "400" in song.error_message


def test_affordances_types():
    assert AFFORDANCES["prompt"].type is str
    assert AFFORDANCES["duration"].type is float
    assert AFFORDANCES["bpm"].type is int
    assert AFFORDANCES["instrumental"].type is bool
    assert AFFORDANCES["instruments"].type is list
