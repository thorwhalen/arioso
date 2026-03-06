"""Tests for arioso.platforms.sunoapi (mocked HTTP)."""

from unittest.mock import patch, MagicMock

from arioso.platforms.sunoapi.config import PLATFORM_CONFIG
from arioso.platforms.sunoapi.adapter import Adapter


def test_sunoapi_config():
    assert PLATFORM_CONFIG["name"] == "sunoapi"
    assert PLATFORM_CONFIG["access_type"] == "rest_api"
    assert PLATFORM_CONFIG["auth"]["type"] == "bearer_token"
    assert PLATFORM_CONFIG["auth"]["env_var"] == "SUNO_API_KEY"


def test_sunoapi_config_param_map():
    pm = PLATFORM_CONFIG["param_map"]
    assert pm["prompt"]["native_name"] == "prompt"
    assert pm["instrumental"]["native_name"] == "make_instrumental"
    assert pm["genre"]["native_name"] == "tags"
    assert pm["model"]["native_default"] == "v3.5"


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
    songs = adapter.generate("upbeat pop song")

    assert len(songs) == 2
    assert songs[0].id == "song-1"
    assert songs[0].audio_url == "https://cdn.sunoapi.org/song1.mp3"
    assert songs[0].platform == "sunoapi"
    assert songs[0].status == "complete"
    assert songs[1].id == "song-2"

    # Verify the right endpoint was called
    call_args = mock_session.post.call_args
    assert "/api/v1/generate" in call_args[0][0]


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
    )

    assert len(songs) == 1
    assert songs[0].title == "My Song"

    # Should use custom_generate endpoint when lyrics provided
    call_args = mock_session.post.call_args
    assert "/api/v1/custom_generate" in call_args[0][0]
    payload = call_args[1]["json"]
    assert payload["prompt"] == "[Verse]\nHello world\n[Chorus]\nGoodbye world"


@patch("arioso.platforms._base_adapter.make_session")
def test_sunoapi_generate_instrumental(mock_make_session):
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": "s1", "audio_url": "https://x.mp3"}]
    mock_session.post.return_value = mock_response
    mock_make_session.return_value = mock_session

    adapter = Adapter(PLATFORM_CONFIG)
    adapter.generate("ambient chill", instrumental=True)

    payload = mock_session.post.call_args[1]["json"]
    assert payload["make_instrumental"] is True
