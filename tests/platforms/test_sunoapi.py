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


def test_sunoapi_missing_callback_url_raises():
    """Should raise ValueError when no callback URL is provided."""
    adapter = Adapter.__new__(Adapter)
    adapter.config = PLATFORM_CONFIG
    adapter.base_url = "https://api.sunoapi.org"
    adapter.session = MagicMock()

    with pytest.raises(ValueError, match="callback URL"):
        adapter.generate("test prompt", callback_url="")


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
