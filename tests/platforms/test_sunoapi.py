"""Tests for arioso.platforms.sunoapi (mocked HTTP)."""

import pytest
from unittest.mock import patch, MagicMock

from arioso.platforms.sunoapi.config import PLATFORM_CONFIG
from arioso.platforms.sunoapi.adapter import Adapter, SUNO_MODELS

CALLBACK_URL = "https://example.com/webhook"


def test_sunoapi_config():
    assert PLATFORM_CONFIG["name"] == "sunoapi"
    assert PLATFORM_CONFIG["access_type"] == "rest_api"
    assert PLATFORM_CONFIG["auth"]["type"] == "bearer_token"
    assert PLATFORM_CONFIG["auth"]["env_var"] == "SUNO_API_KEY"


def test_sunoapi_config_param_map():
    pm = PLATFORM_CONFIG["param_map"]
    assert pm["prompt"]["native_name"] == "prompt"
    assert pm["instrumental"]["native_name"] == "instrumental"
    assert pm["genre"]["native_name"] == "style"
    assert pm["model"]["native_default"] == "V4"
    assert "choices" in pm["model"]
    assert "V4" in pm["model"]["choices"]


@patch("arioso.platforms._base_adapter.make_session")
def test_sunoapi_generate_simple(mock_make_session):
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "id": "song-1",
            "title": "Test Song 1",
            "audio_url": "https://cdn.sunoapi.org/song1.mp3",
        },
        {
            "id": "song-2",
            "title": "Test Song 2",
            "audio_url": "https://cdn.sunoapi.org/song2.mp3",
        },
    ]
    mock_session.post.return_value = mock_response
    mock_make_session.return_value = mock_session

    adapter = Adapter(PLATFORM_CONFIG)
    songs = adapter.generate("upbeat pop song", callback_url=CALLBACK_URL)

    assert len(songs) == 2
    assert songs[0].id == "song-1"
    assert songs[0].audio_url == "https://cdn.sunoapi.org/song1.mp3"
    assert songs[0].platform == "sunoapi"
    assert songs[0].status == "complete"
    assert songs[1].id == "song-2"

    # Verify the right endpoint and payload structure
    call_args = mock_session.post.call_args
    assert "/api/v1/generate" in call_args[0][0]
    payload = call_args[1]["json"]
    assert payload["customMode"] is False
    assert payload["callBackUrl"] == CALLBACK_URL


@patch("arioso.platforms._base_adapter.make_session")
def test_sunoapi_generate_with_lyrics(mock_make_session):
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"id": "song-1", "title": "My Song", "audio_url": "https://cdn.sunoapi.org/song1.mp3"},
    ]
    mock_session.post.return_value = mock_response
    mock_make_session.return_value = mock_session

    adapter = Adapter(PLATFORM_CONFIG)
    songs = adapter.generate(
        "pop ballad",
        lyrics="[Verse]\nHello world\n[Chorus]\nGoodbye world",
        title="My Song",
        callback_url=CALLBACK_URL,
    )

    assert len(songs) == 1
    assert songs[0].title == "My Song"

    # customMode should be enabled when lyrics/title provided
    payload = mock_session.post.call_args[1]["json"]
    assert payload["customMode"] is True
    assert payload["prompt"] == "[Verse]\nHello world\n[Chorus]\nGoodbye world"
    assert payload["title"] == "My Song"


@patch("arioso.platforms._base_adapter.make_session")
def test_sunoapi_generate_instrumental(mock_make_session):
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": "s1", "audio_url": "https://x.mp3"}]
    mock_session.post.return_value = mock_response
    mock_make_session.return_value = mock_session

    adapter = Adapter(PLATFORM_CONFIG)
    adapter.generate("ambient chill", instrumental=True, callback_url=CALLBACK_URL)

    payload = mock_session.post.call_args[1]["json"]
    assert payload["instrumental"] is True


@patch("arioso.platforms._base_adapter.make_session")
def test_sunoapi_generate_with_genre_enables_custom_mode(mock_make_session):
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": "s1", "audio_url": "https://x.mp3"}]
    mock_session.post.return_value = mock_response
    mock_make_session.return_value = mock_session

    adapter = Adapter(PLATFORM_CONFIG)
    adapter.generate(
        "summer vibes",
        genre="reggae, tropical",
        instrumental=True,
        callback_url=CALLBACK_URL,
    )

    payload = mock_session.post.call_args[1]["json"]
    assert payload["customMode"] is True
    assert payload["style"] == "reggae, tropical"


@patch("arioso.platforms._base_adapter.make_session")
def test_sunoapi_api_error_raises(mock_make_session):
    """API-level errors (HTTP 200 but error in body) should raise RuntimeError."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "code": 400,
        "msg": "model cannot be null",
        "data": None,
    }
    mock_session.post.return_value = mock_response
    mock_make_session.return_value = mock_session

    adapter = Adapter(PLATFORM_CONFIG)
    with pytest.raises(RuntimeError, match="model cannot be null"):
        adapter.generate("test prompt", callback_url=CALLBACK_URL)


@patch("arioso.platforms._base_adapter.make_session")
def test_sunoapi_missing_callback_url_falls_back_to_noop(mock_make_session):
    """An empty callback URL is not an error: it falls back to the no-op default
    so polling mode (``wait_for_completion``) works out of the box. A real webhook
    is opt-in via the ``SUNO_CALLBACK_URL`` env var. See the adapter's
    ``_NOOP_CALLBACK_URL`` / ``SUNO_DEFAULT_CALLBACK_URL``.
    """
    from arioso.platforms.sunoapi.adapter import SUNO_DEFAULT_CALLBACK_URL

    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"id": "s1", "title": "T", "audio_url": "https://cdn.sunoapi.org/s1.mp3"},
    ]
    mock_session.post.return_value = mock_response
    mock_make_session.return_value = mock_session

    adapter = Adapter(PLATFORM_CONFIG)
    songs = adapter.generate("test prompt", callback_url="")

    assert len(songs) == 1
    payload = mock_session.post.call_args[1]["json"]
    assert payload["callBackUrl"] == SUNO_DEFAULT_CALLBACK_URL


def test_suno_models_tuple():
    assert "V4" in SUNO_MODELS
    assert "V4_5" in SUNO_MODELS
    assert "V5" in SUNO_MODELS


@patch("arioso.platforms._base_adapter.make_session")
def test_sunoapi_default_model(mock_make_session):
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": "s1", "audio_url": "https://x.mp3"}]
    mock_session.post.return_value = mock_response
    mock_make_session.return_value = mock_session

    adapter = Adapter(PLATFORM_CONFIG)
    adapter.generate("test", callback_url=CALLBACK_URL)

    payload = mock_session.post.call_args[1]["json"]
    # Default model should be populated (not empty)
    assert payload["model"] != ""
    assert payload["model"] in SUNO_MODELS


@patch("arioso.platforms._base_adapter.make_session")
def test_sunoapi_taskid_pending_song(mock_make_session):
    """When API returns a taskId dict, we get a pending Song."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "code": 200,
        "data": {"taskId": "task-abc-123"},
    }
    mock_session.post.return_value = mock_response
    mock_make_session.return_value = mock_session

    adapter = Adapter(PLATFORM_CONFIG)
    songs = adapter.generate("test", callback_url=CALLBACK_URL)

    assert len(songs) == 1
    assert songs[0].id == "task-abc-123"
    assert songs[0].status == "pending"


@patch("arioso.platforms._base_adapter.make_session")
def test_sunoapi_get_status_complete(mock_make_session):
    """get_status returns complete Songs when generation is done."""
    mock_session = MagicMock()
    mock_get_response = MagicMock()
    mock_get_response.json.return_value = {
        "code": 200,
        "data": {
            "taskId": "task-123",
            "status": "SUCCESS",
            "response": {
                "sunoData": [
                    {
                        "id": "clip-1",
                        "title": "Summer Vibes",
                        "audioUrl": "https://cdn.sunoapi.org/clip1.mp3",
                        "streamAudioUrl": "https://stream.sunoapi.org/clip1.mp3",
                        "duration": 120.0,
                    },
                    {
                        "id": "clip-2",
                        "title": "Summer Vibes 2",
                        "audioUrl": "https://cdn.sunoapi.org/clip2.mp3",
                        "streamAudioUrl": "https://stream.sunoapi.org/clip2.mp3",
                        "duration": 115.0,
                    },
                ]
            },
        },
    }
    mock_session.get.return_value = mock_get_response
    mock_make_session.return_value = mock_session

    adapter = Adapter(PLATFORM_CONFIG)
    songs = adapter.get_status("task-123")

    assert len(songs) == 2
    assert songs[0].id == "clip-1"
    assert songs[0].status == "complete"
    assert songs[0].audio_url == "https://cdn.sunoapi.org/clip1.mp3"
    assert songs[0].title == "Summer Vibes"
    assert songs[0].audio.duration_seconds == 120.0
    assert songs[1].id == "clip-2"
    assert songs[1].status == "complete"


@patch("arioso.platforms._base_adapter.make_session")
def test_sunoapi_get_status_pending(mock_make_session):
    """get_status returns pending Song when still processing."""
    mock_session = MagicMock()
    mock_get_response = MagicMock()
    mock_get_response.json.return_value = {
        "code": 200,
        "data": {
            "taskId": "task-123",
            "status": "PENDING",
            "response": {},
        },
    }
    mock_session.get.return_value = mock_get_response
    mock_make_session.return_value = mock_session

    adapter = Adapter(PLATFORM_CONFIG)
    songs = adapter.get_status("task-123")

    assert len(songs) == 1
    assert songs[0].status == "pending"


@patch("arioso.platforms._base_adapter.make_session")
def test_sunoapi_get_status_error_raises(mock_make_session):
    """get_status raises on generation failure."""
    mock_session = MagicMock()
    mock_get_response = MagicMock()
    mock_get_response.json.return_value = {
        "code": 200,
        "data": {
            "taskId": "task-123",
            "status": "GENERATE_AUDIO_FAILED",
        },
    }
    mock_session.get.return_value = mock_get_response
    mock_make_session.return_value = mock_session

    adapter = Adapter(PLATFORM_CONFIG)
    with pytest.raises(RuntimeError, match="GENERATE_AUDIO_FAILED"):
        adapter.get_status("task-123")


@patch("arioso.platforms._base_adapter.make_session")
def test_sunoapi_fetch_audio(mock_make_session):
    """fetch_audio downloads bytes from audio_url."""
    mock_session = MagicMock()
    mock_get_response = MagicMock()
    mock_get_response.content = b"fake mp3 audio bytes"
    mock_session.get.return_value = mock_get_response
    mock_make_session.return_value = mock_session

    from arioso.base import AudioResult, Song

    song = Song(
        id="clip-1",
        audio=AudioResult(audio_url="https://cdn.sunoapi.org/clip1.mp3", format="mp3"),
        platform="sunoapi",
        status="complete",
    )

    adapter = Adapter(PLATFORM_CONFIG)
    result = adapter.fetch_audio(song)

    assert result.audio_bytes == b"fake mp3 audio bytes"
    assert result.audio_url == "https://cdn.sunoapi.org/clip1.mp3"
    assert result.id == "clip-1"


@patch("arioso.platforms._base_adapter.make_session")
def test_sunoapi_get_timestamped_lyrics(mock_make_session):
    from arioso.base import Song

    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "code": 200,
        "msg": "success",
        "data": {
            "alignedWords": [
                {"word": "[Intro]\nカ ", "success": True, "startS": 2.87, "endS": 3.43, "palign": 0},
                {"word": "ン\n", "success": True, "startS": 5.19, "endS": 7.58, "palign": 0},
            ],
            "hootCer": 0.43,
        },
    }
    mock_session.post.return_value = mock_response
    mock_make_session.return_value = mock_session

    adapter = Adapter(PLATFORM_CONFIG)
    song = Song(id="audio-1", platform="sunoapi", status="complete", metadata={"task_id": "task-1"})
    out = adapter.get_timestamped_lyrics(song)

    url = mock_session.post.call_args[0][0]
    assert url.endswith("/api/v1/generate/get-timestamped-lyrics")
    assert mock_session.post.call_args[1]["json"] == {"taskId": "task-1", "audioId": "audio-1"}
    assert out["hoot_cer"] == 0.43
    assert [w["text"] for w in out["aligned_words"]] == ["カ", "ン"]
    assert [w["line_end"] for w in out["aligned_words"]] == [False, True]
    assert out["aligned_words"][0]["start"] == 2.87
    assert [w["section"] for w in out["aligned_words"]] == ["Intro", None]


@patch("arioso.platforms._base_adapter.make_session")
def test_sunoapi_get_timestamped_lyrics_refuses_pending_and_empty(mock_make_session):
    from arioso.base import Song

    mock_session = MagicMock()
    mock_session.post.return_value.json.return_value = {"code": 200, "data": {}}
    mock_make_session.return_value = mock_session
    adapter = Adapter(PLATFORM_CONFIG)
    with pytest.raises(ValueError, match="complete"):
        adapter.get_timestamped_lyrics(Song(id="t", platform="sunoapi", status="pending", metadata={"task_id": "t"}))
    with pytest.raises(ValueError, match="no aligned words"):
        adapter.get_timestamped_lyrics("task-1", "audio-1")


@patch("arioso.platforms._base_adapter.make_session")
def test_sunoapi_get_timestamped_lyrics_needs_task_id(mock_make_session):
    from arioso.base import Song

    mock_make_session.return_value = MagicMock()
    adapter = Adapter(PLATFORM_CONFIG)
    with pytest.raises(ValueError, match="task_id"):
        adapter.get_timestamped_lyrics(Song(id="audio-1", platform="sunoapi", status="complete"))


# --- audio_input routes to upload-cover (thorwhalen/arioso#15) ---------------


def _cover_session(mock_make_session):
    mock_session = MagicMock()
    mock_session.post.return_value.json.return_value = {
        "code": 200,
        "data": {"taskId": "cover-task"},
    }
    mock_make_session.return_value = mock_session
    return mock_session


@patch("arioso.platforms._base_adapter.make_session")
def test_sunoapi_audio_input_goes_to_upload_cover(mock_make_session):
    """audio_input / audio_input_strength used to be declared but never read."""
    session = _cover_session(mock_make_session)
    songs = Adapter(PLATFORM_CONFIG).generate(
        "dreamy synth pop",
        audio_input="https://example.com/seed.mp3",
        audio_input_strength=0.7,
        callback_url=CALLBACK_URL,
    )
    url, kwargs = session.post.call_args[0][0], session.post.call_args[1]
    assert url.endswith("/api/v1/generate/upload-cover")
    payload = kwargs["json"]
    assert payload["uploadUrl"] == "https://example.com/seed.mp3"
    assert payload["audioWeight"] == 0.7
    assert payload["customMode"] is False
    assert payload["prompt"] == "dreamy synth pop"
    assert songs[0].id == "cover-task"


@patch("arioso.platforms._base_adapter.make_session")
def test_sunoapi_audio_input_keeps_generate_custom_mode_rules(mock_make_session):
    """Lyrics + genre: style is the genre and the prompt carries the lyrics,
    exactly as plain generation builds its customMode payload."""
    session = _cover_session(mock_make_session)
    Adapter(PLATFORM_CONFIG).generate(
        "ignored as style",
        genre="folk",
        lyrics="la la la",
        title="T",
        audio_input="https://example.com/seed.mp3",
        callback_url=CALLBACK_URL,
    )
    payload = session.post.call_args[1]["json"]
    assert payload["customMode"] is True
    assert (payload["style"], payload["prompt"], payload["title"]) == ("folk", "la la la", "T")
    assert "audioWeight" not in payload  # 0 leaves it to the API


@patch("arioso.platforms._base_adapter.make_session")
def test_sunoapi_audio_input_with_continue_from_is_refused(mock_make_session):
    _cover_session(mock_make_session)
    with pytest.raises(ValueError, match="audio_input and continue_from"):
        Adapter(PLATFORM_CONFIG).generate(
            "x", audio_input="https://example.com/a.mp3", continue_from="clip-1"
        )


@patch("arioso.platforms._base_adapter.make_session")
def test_sunoapi_audio_input_accepts_the_affordance_forms(mock_make_session, tmp_path):
    """Song (remote URL), bytes and Path all reach upload-cover (review of #16)."""
    import os
    from pathlib import Path
    from arioso.base import AudioResult, Song

    session = _cover_session(mock_make_session)
    adapter = Adapter(PLATFORM_CONFIG)
    uploaded = []
    adapter.upload_file = lambda path: (uploaded.append(path), "https://files.example/up.wav")[1]

    remote = Song(audio=AudioResult(audio_url="https://cdn.example/s.mp3"), platform="sunoapi")
    adapter.generate("x", audio_input=remote, callback_url=CALLBACK_URL)
    assert session.post.call_args[1]["json"]["uploadUrl"] == "https://cdn.example/s.mp3"
    assert uploaded == []

    adapter.generate("x", audio_input=b"RIFF....", callback_url=CALLBACK_URL)
    assert session.post.call_args[1]["json"]["uploadUrl"] == "https://files.example/up.wav"
    assert len(uploaded) == 1 and not os.path.exists(uploaded[0]), "temp file cleaned up"

    clip = tmp_path / "seed.wav"
    clip.write_bytes(b"RIFF....")
    adapter.generate("x", audio_input=Path(clip), callback_url=CALLBACK_URL)
    assert uploaded[-1] == str(clip) and clip.exists(), "a caller's file is not deleted"

    with pytest.raises(ValueError, match="local file path or a URL"):
        adapter.generate("x", audio_input=tmp_path / "missing.wav")


@patch("arioso.platforms._base_adapter.make_session")
def test_sunoapi_audio_input_warns_on_what_upload_cover_cannot_do(mock_make_session):
    _cover_session(mock_make_session)
    adapter = Adapter(PLATFORM_CONFIG)
    with pytest.warns(UserWarning, match="continue_at is ignored"):
        adapter.generate("x", audio_input="https://e.x/a.mp3", continue_at=12)
    with pytest.warns(UserWarning, match="non-custom mode"):
        adapter.generate("", lyrics="la", audio_input="https://e.x/a.mp3")
