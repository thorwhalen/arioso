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

    # The documented music_v1 plan (POST /v1/music, 2026-11): prompt and plan are
    # mutually exclusive, and the API has no title (a title-only plan was a 422).
    call_kwargs = adapter._raw_func.call_args[1]
    assert "prompt" not in call_kwargs and "music_length_ms" not in call_kwargs
    plan = call_kwargs["composition_plan"]
    assert "title" not in plan
    assert plan["positive_global_styles"] == ["pop song"]
    (section,) = plan["sections"]
    assert section["lines"] == ["Hello world"]
    assert set(section) == {"section_name", "positive_local_styles", "negative_local_styles", "duration_ms", "lines"}


@patch("arioso.platforms._base_adapter.make_session")
def test_elevenlabs_title_alone_keeps_the_plain_prompt(mock_make_session):
    """The 422: a title used to turn a plain prompt into an invalid title-only plan."""
    mock_make_session.return_value = MagicMock()
    adapter = Adapter(PLATFORM_CONFIG)
    adapter._raw_func = MagicMock(return_value=b"audio")
    song = adapter.generate("Lied with chamber music accompaniment", title="Cora Kisses", seed=3)
    call_kwargs = adapter._raw_func.call_args[1]
    assert call_kwargs["prompt"] == "Lied with chamber music accompaniment"
    assert "composition_plan" not in call_kwargs and "seed" not in call_kwargs
    assert song.title == "Cora Kisses"


def test_elevenlabs_lyric_sections_respect_the_limits():
    from arioso.platforms.elevenlabs.adapter import _music_request

    lyrics = "[Verse]\n" + "\n".join(f"line {i}" for i in range(40)) + "\n\n[Chorus]\nla"
    body = _music_request("x", duration=600, instrumental=False, model="music_v1", lyrics=lyrics)
    sections = body["composition_plan"]["sections"]
    assert [len(s["lines"]) for s in sections] == [30, 10, 1]
    assert all(3000 <= s["duration_ms"] <= 120000 for s in sections)
    v2 = _music_request("x", duration=60, instrumental=False, model="music_v2", lyrics="a\nb")
    assert v2["composition_plan"]["chunks"][0]["text"] == "a\nb"


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


def test_elevenlabs_falls_back_when_generated_signature_cannot_bind():
    """ho may demand optional spec fields as required args; use plain requests."""
    adapter = Adapter(PLATFORM_CONFIG)

    def strict(**kwargs):
        raise TypeError("missing a required argument: 'generation_mode'")

    adapter._raw_func = strict
    response = MagicMock(content=b"ID3audio", headers={"content-type": "audio/mpeg"})
    with patch.object(adapter.session, "post", return_value=response) as post:
        song = adapter.generate("strings", duration=10)
    assert song.audio.audio_bytes == b"ID3audio"
    _, kwargs = post.call_args
    assert kwargs["params"] == {"output_format": "mp3_44100_128"}
    assert "output_format" not in kwargs["json"]


def test_bind_header_param_prefills_the_key():
    from arioso.platforms.elevenlabs.adapter import _bind_header_param

    def f(prompt, xi_api_key):
        return xi_api_key

    assert _bind_header_param(f, "xi-api-key", "K")(prompt="p") == "K"
    assert _bind_header_param(len, "xi-api-key", "K") is len
