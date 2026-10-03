"""Tests for the fal.ai-hosted platforms (stable_audio_25, ace_step), mocked.

``fal_run`` / ``fal_upload_audio`` are replaced per adapter module, so no
network, key or fal_client is needed. ``fetch=False`` skips the download.
"""

import pytest

import arioso
import arioso.platforms.ace_step.adapter as ace_mod
import arioso.platforms.stable_audio_25.adapter as sa_mod

_RESULT = {"audio": {"url": "https://fal.media/x.wav", "content_type": "audio/wav"}, "seed": 3}


@pytest.fixture
def capture(monkeypatch):
    calls = {}

    def fake_run(endpoint, arguments):
        calls["endpoint"] = endpoint
        calls["arguments"] = arguments
        return _RESULT

    for mod in (sa_mod, ace_mod):
        monkeypatch.setattr(mod, "fal_run", fake_run)
        monkeypatch.setattr(mod, "fal_upload_audio", lambda a: "https://fal.media/in.wav")
    return calls


def test_both_platforms_take_audio_input():
    assert arioso.supports_audio_input("stable_audio_25")
    assert arioso.supports_audio_input("ace_step")


def test_stable_audio_25_text_to_audio(capture):
    song = sa_mod.Adapter({}).generate("strings", duration=500, fetch=False)
    assert capture["endpoint"].endswith("text-to-audio")
    assert capture["arguments"]["seconds_total"] == 190  # clamped to the max
    assert song.audio.audio_url == _RESULT["audio"]["url"]
    assert song.status == "complete" and song.metadata["seed"] == 3


def test_stable_audio_25_audio_to_audio_strength(capture):
    sa_mod.Adapter({}).generate(
        "strings", audio_input="in.wav", audio_input_strength=0.3, fetch=False
    )
    args = capture["arguments"]
    assert capture["endpoint"].endswith("audio-to-audio")
    assert args["strength"] == 0.3 and args["audio_url"].endswith("in.wav")
    assert "seconds_total" not in args  # defaults to the input's length


def test_stable_audio_25_rejects_bad_strength(capture):
    with pytest.raises(ValueError):
        sa_mod.Adapter({}).generate("x", audio_input="in.wav", audio_input_strength=2)


def test_enhance_routes_strength_to_stable_audio_25(capture, monkeypatch):
    arioso.enhance("in.wav", "strings", platform="stable_audio_25", strength=0.25, fetch=False)
    assert capture["arguments"]["strength"] == 0.25


def test_ace_step_text_to_music_is_instrumental_by_default(capture):
    ace_mod.Adapter({}).generate("orchestral, march", duration=30, fetch=False)
    args = capture["arguments"]
    assert capture["endpoint"] == "fal-ai/ace-step"
    assert args["tags"] == "orchestral, march" and args["lyrics"] == "[inst]"
    assert args["duration"] == 30.0


def test_ace_step_remix_defaults_original_tags(capture):
    ace_mod.Adapter({}).generate("orchestral", audio_input="in.wav", fetch=False)
    args = capture["arguments"]
    assert capture["endpoint"].endswith("audio-to-audio")
    assert args["original_tags"] == "orchestral" and args["edit_mode"] == "remix"
    assert "duration" not in args


def test_ace_step_needs_tags(capture):
    with pytest.raises(ValueError):
        ace_mod.Adapter({}).generate("")
