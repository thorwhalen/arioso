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


def test_services_path_keeps_unified_params(capture):
    """arioso.services.<p>.generate must not rename params the adapter maps itself."""
    arioso.services.stable_audio_25.generate(
        "strings", audio_input="in.wav", audio_input_strength=0.2, num_steps=50,
        guidance=3.0, fetch=False,
    )
    args = capture["arguments"]
    assert (args["strength"], args["num_inference_steps"], args["guidance_scale"]) == (0.2, 50, 3.0)
    arioso.services.ace_step.generate("rock, guitar", fetch=False)
    assert capture["arguments"]["tags"] == "rock, guitar"


def test_adapter_params_do_not_warn(capture, recwarn):
    arioso.enhance("in.wav", "x", platform="ace_step", original_tags="midi", fetch=False)
    assert not [w for w in recwarn if "not supported" in str(w.message)]
    assert capture["arguments"]["original_tags"] == "midi"


def test_stable_audio_25_duration_names_per_endpoint(capture):
    a = sa_mod.Adapter({})
    a.generate("x", audio_input="in.wav", duration=10.4, fetch=False)
    assert capture["arguments"]["total_seconds"] == 10
    assert "seconds_total" not in capture["arguments"]
    a.generate("x", fetch=False)
    assert capture["arguments"]["seconds_total"] == 30  # not fal's 190 s default
    a.generate("x", duration=0.4, fetch=False)
    assert capture["arguments"]["seconds_total"] == 1


def test_ace_step_passes_documented_native_extras(capture):
    ace_mod.Adapter({}).generate("x", tag_guidance_scale=7, bogus=1, fetch=False)
    assert capture["arguments"]["tag_guidance_scale"] == 7
    assert "bogus" not in capture["arguments"]


@pytest.mark.parametrize(
    "content_type, url, fmt",
    [
        ("audio/wav;rate=44100", "https://x/a", "wav"),
        ("audio/ogg; codecs=opus", "https://x/a", "ogg"),
        ("audio/mpeg", "https://x/a", "mp3"),
        ("application/octet-stream", "https://x/a.flac?sig=1", "flac"),
        ("", "https://x/noext", "wav"),
    ],
)
def test_format_of(content_type, url, fmt):
    from arioso._fal import _format_of

    assert _format_of(content_type, url) == fmt


def test_a_new_fal_model_is_a_config_entry(monkeypatch):
    """A platform declared by config alone (no adapter module) runs through FalAdapter."""
    from arioso import registry
    from arioso._fal import FalAdapter

    calls = {}
    config = {
        "name": "demo_fal",
        "fal": {
            "shared": {
                "text": {"from": ["prompt"], "required": True},
                "steps": {"from": ["num_steps"], "default": 4},
            },
            "endpoints": {
                "text_to_audio": {"endpoint": "fal-ai/demo", "arguments": {"len": {"from": ["duration"], "type": "int", "clamp": [1, 5]}}},
            },
        },
    }
    adapter = FalAdapter(
        config,
        run=lambda endpoint, arguments: calls.update(endpoint=endpoint, arguments=arguments) or _RESULT,
    )
    song = adapter.generate("hi", duration=9.2, bogus=1, fetch=False)
    assert calls == {"endpoint": "fal-ai/demo", "arguments": {"text": "hi", "steps": 4, "len": 5}}
    assert song.platform == "demo_fal"
    registry.register_platform("demo_fal", config)
    assert isinstance(registry._load_adapter("demo_fal", config), FalAdapter)


def test_fal_specs_agree_with_the_platform_config():
    """The fal section, param_map and supported_affordances are one story."""
    for module in (sa_mod, ace_mod):
        config = module.PLATFORM_CONFIG
        adapter = module.Adapter(config)
        accepted = adapter.accepted_params()
        declared = set(config["supported_affordances"]) | set(config["adapter_params"])
        assert set(config["supported_affordances"]) <= accepted
        assert accepted - {"prompt"} <= declared | set(config["fal"].get("native_extras", ()))
