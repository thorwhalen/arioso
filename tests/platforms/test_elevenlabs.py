"""Tests for arioso.platforms.elevenlabs (mocked HTTP)."""

from unittest.mock import patch, MagicMock

from arioso.platforms.elevenlabs.config import PLATFORM_CONFIG
from arioso.platforms.elevenlabs.adapter import Adapter


def test_elevenlabs_config():
    assert PLATFORM_CONFIG["name"] == "elevenlabs"
    assert PLATFORM_CONFIG["access_type"] == "rest_api"
    assert PLATFORM_CONFIG["auth"]["type"] == "api_key"
    assert PLATFORM_CONFIG["auth"]["env_var"] == "ELEVENLABS_API_KEY"
    assert PLATFORM_CONFIG["auth"]["header_name"] == "xi-api-key"


def test_elevenlabs_config_param_map():
    pm = PLATFORM_CONFIG["param_map"]
    assert pm["prompt"]["native_name"] == "prompt"
    assert pm["duration"]["native_name"] == "music_length_ms"
    assert pm["instrumental"]["native_name"] == "force_instrumental"
    assert pm["model"]["native_default"] == "music_v1"

    # Test coercion
    coerce = pm["duration"]["coerce"]
    assert coerce(30.0) == 30000
    assert coerce(10) == 10000


def test_elevenlabs_config_coerce_back():
    coerce_back = PLATFORM_CONFIG["param_map"]["duration"]["coerce_back"]
    assert coerce_back(30000) == 30.0


@patch("arioso.platforms._base_adapter.make_session")
def test_elevenlabs_generate(mock_make_session):
    mock_session = MagicMock()
    mock_make_session.return_value = mock_session

    adapter = Adapter(PLATFORM_CONFIG)
    # Set up the fallback function to return bytes
    adapter._raw_func = MagicMock(return_value=b"fake mp3 audio data")

    song = adapter.generate("epic orchestral", duration=30.0)

    assert song.status == "complete"
    assert song.platform == "elevenlabs"
    assert song.audio.audio_bytes == b"fake mp3 audio data"
    assert song.audio.format == "mp3"
    assert song.audio.sample_rate == 44100
    assert song.audio.duration_seconds == 30.0

    # Verify native kwargs were passed
    call_kwargs = adapter._raw_func.call_args[1]
    assert call_kwargs["prompt"] == "epic orchestral"
    assert call_kwargs["music_length_ms"] == 30000
    assert call_kwargs["model_id"] == "music_v1"


@patch("arioso.platforms._base_adapter.make_session")
def test_elevenlabs_generate_with_lyrics(mock_make_session):
    mock_session = MagicMock()
    mock_make_session.return_value = mock_session

    adapter = Adapter(PLATFORM_CONFIG)
    adapter._raw_func = MagicMock(return_value=b"audio")

    adapter.generate(
        "pop song",
        lyrics="Hello world",
        title="My Song",
    )

    call_kwargs = adapter._raw_func.call_args[1]
    assert "composition_plan" in call_kwargs
    plan = call_kwargs["composition_plan"]
    assert plan["title"] == "My Song"
    assert plan["sections"] == [{"lyrics": "Hello world"}]


@patch("arioso.platforms._base_adapter.make_session")
def test_elevenlabs_generate_instrumental(mock_make_session):
    mock_session = MagicMock()
    mock_make_session.return_value = mock_session

    adapter = Adapter(PLATFORM_CONFIG)
    adapter._raw_func = MagicMock(return_value=b"audio")

    adapter.generate("ambient", instrumental=True)

    call_kwargs = adapter._raw_func.call_args[1]
    assert call_kwargs["force_instrumental"] is True


@patch("arioso.platforms._base_adapter.make_session")
def test_elevenlabs_output_format_parsing(mock_make_session):
    mock_session = MagicMock()
    mock_make_session.return_value = mock_session

    adapter = Adapter(PLATFORM_CONFIG)
    adapter._raw_func = MagicMock(return_value=b"audio")

    song = adapter.generate("test", output_format="wav_44100_16")
    assert song.audio.format == "wav"
