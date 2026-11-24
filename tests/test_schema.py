"""param_schema: the JSON Schema of each platform's parameters, built from its config."""

import json

import pytest

import arioso
from arioso.base import AFFORDANCES
from arioso.schema import common_params, operations, param_schema, schema_from_config


@pytest.mark.parametrize("platform", arioso.list_platforms())
def test_every_platform_has_a_json_ready_schema(platform):
    schema = param_schema(platform)
    json.dumps(schema)  # JSON-ready, no Python types or callables leak
    meta = schema["x-arioso"]
    assert meta["platform"] == platform
    assert meta["operations"][0] == "generate"
    assert set(meta["common"]) <= set(AFFORDANCES)
    assert not set(meta["common"]) & set(meta["extra"])
    for name, prop in schema["properties"].items():
        assert prop["x-arioso"]["group"] in ("common", "extra"), name


def test_suno_common_and_extras():
    schema = param_schema("sunoapi")
    props = schema["properties"]
    assert props["genre"]["title"] == "Styles"  # Suno's own UI name
    strength = props["audio_input_strength"]
    assert (strength["minimum"], strength["maximum"]) == (0, 1)
    assert strength["x-arioso"]["group"] == "common"
    assert props["audio_input"]["x-arioso"]["kind"] == "audio"
    weird = props["weirdness"]
    assert "default" not in weird  # the API decides; a form must not send it
    assert weird["x-arioso"]["neutral"] == 0.5
    assert weird["x-arioso"]["scale_labels"] == ["Safe", "Chaos"]
    assert weird["x-arioso"]["requires_any"] == ["genre", "title", "lyrics"]
    assert weird["x-arioso"]["group"] == "extra"
    assert props["audio_input_strength"]["x-arioso"]["requires"] == ["audio_input"]
    assert props["audio_input"]["format"] == "uri"
    assert props["continue_from"]["x-arioso"]["kind"] == "clip"
    assert props["vocal_gender"]["enum"] == ["m", "f"]
    assert props["variety"]["type"] == "integer"
    assert "V6" in props["model"]["enum"]
    assert schema["required"] == ["prompt"]
    assert "cover" in schema["x-arioso"]["operations"]


def test_native_default_never_leaks_as_default():
    """ElevenLabs keeps duration in ms natively; the schema speaks seconds."""
    duration = param_schema("elevenlabs")["properties"]["duration"]
    assert duration["default"] == 30 and duration["maximum"] == 600


def test_untyped_extras_are_marked():
    config = {"name": "x", "supported_affordances": ["prompt"], "adapter_params": ["knob"]}
    prop = schema_from_config(config)["properties"]["knob"]
    assert prop["x-arioso"]["untyped"] is True


def test_operations_from_affordances_or_config():
    assert operations({"supported_affordances": ["continue_from", "mask_start"]}) == [
        "generate",
        "extend",
        "inpaint",
    ]
    assert operations({"operations": ["generate", "cover"]}) == ["generate", "cover"]


def test_common_params_is_the_intersection_in_order():
    shared = common_params(["sunoapi", "elevenlabs"])
    assert shared[0] == "prompt" and "lyrics" in shared and "genre" not in shared


@pytest.fixture
def no_network(monkeypatch):
    """Fail any HTTP request: these tests must never reach a paid API."""
    import requests

    def refuse(*args, **kwargs):
        raise AssertionError("a request reached the network")

    monkeypatch.setattr(requests.Session, "request", refuse)


@pytest.mark.parametrize(
    "entry",
    [
        lambda **kw: arioso.services.sunoapi.generate("x", **kw),
        lambda **kw: arioso.generate("x", platform="sunoapi", **kw),
    ],
    ids=["services", "facade"],
)
@pytest.mark.parametrize(
    "bad",
    [{"audio_input_strength": 1.5}, {"weirdness": 2.0}, {"vocal_gender": "x"}],
    ids=["affordance-bound", "extra-bound", "extra-choice"],
)
def test_both_entry_points_validate_before_any_request(no_network, entry, bad):
    with pytest.raises(ValueError):
        entry(**bad)


def test_unset_values_pass_validation():
    from arioso.services import validate_params
    from arioso.registry import get_config

    validate_params({"duration": 0, "vocal_gender": ""}, get_config("sunoapi"), "sunoapi")


def test_cover_forwards_custom_controls_and_refuses_the_rest(monkeypatch):
    from arioso.platforms.sunoapi.adapter import Adapter

    seen = {}
    adapter = Adapter({})
    monkeypatch.setattr(adapter, "upload_cover", lambda src, **kw: seen.update(kw) or [])
    adapter.generate(
        "x", genre="jazz", audio_input="https://h/a.mp3", style_weight=0.7, weirdness=0.2
    )
    assert (seen["style_weight"], seen["weirdness"]) == (0.7, 0.2)
    with pytest.raises(ValueError, match="variety"):
        adapter.generate("x", genre="jazz", audio_input="https://h/a.mp3", variety=2)
    # no custom mode on upload-cover: the controls go through without Styles
    adapter.generate("x", audio_input="https://h/a.mp3", weirdness=0.3)
    assert seen["weirdness"] == 0.3


def test_mechanics_extras_are_left_out():
    props = param_schema("stable_audio_25")["properties"]
    assert "fetch" not in props


def test_open_parameters_are_not_rejected():
    """ElevenLabs' model list is open: a new model id must not be refused."""
    from arioso.services import validate_params
    from arioso.registry import get_config

    validate_params({"model": "music_v2"}, get_config("elevenlabs"), "elevenlabs")


def test_cli_schema_prints_json():
    from arioso.cli import schema

    assert json.loads(schema("sunoapi"))["x-arioso"]["platform"] == "sunoapi"
    with pytest.raises(ValueError, match="Unknown platform"):
        schema("nope")


def test_lyrics_and_prompt_are_multiline_on_every_platform():
    """Line breaks in lyrics matter, so every platform's schema says ``multiline``
    for them (from the affordance, not a per-platform opt-in): a form that drew a
    one-line input for them would glue the lines together."""
    from arioso.base import AFFORDANCES
    from arioso.registry import list_platforms

    multiline = {n for n, a in AFFORDANCES.items() if a.multiline}
    assert {"lyrics", "prompt"} <= multiline
    seen = 0
    for name in list_platforms():
        props = param_schema(name)["properties"]
        for field in multiline & props.keys():
            assert props[field]["x-arioso"].get("multiline") is True, (name, field)
            seen += 1
    assert seen
    assert "multiline" not in param_schema("sunoapi")["properties"]["title"]["x-arioso"]


def test_ace_step_asks_for_no_prompt_and_says_what_an_empty_one_does():
    """ACE-Step's style tags come from genre, else prompt, else a default style: nothing is
    required, and the schema carries the default so a form can show what an empty field does."""
    from arioso.platforms.ace_step.config import DFLT_STYLE

    schema = param_schema("ace_step")
    assert "prompt" not in schema.get("required", [])
    prompt = schema["properties"]["prompt"]
    assert prompt["default"] == DFLT_STYLE
    assert prompt["x-arioso"]["optional_with"] == ["genre"]  # Styles stands in for it
    # the same names as on Suno, since a form keeps the values when the platform changes
    assert prompt["title"] == "Song description"
    assert schema["properties"]["genre"]["title"] == "Styles"
