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
    assert props["weirdness"]["x-arioso"] == {
        "scale_labels": ["Safe", "Chaos"],
        "group": "extra",
        "kind": "value",
    }
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


def test_validation_honours_minimum_maximum(monkeypatch):
    """An out-of-range value is refused before any request (a fake transport proves it)."""
    import requests

    def no_network(*args, **kwargs):
        raise AssertionError("validation let the call through to the network")

    monkeypatch.setattr(requests.Session, "request", no_network)
    with pytest.raises(ValueError, match="<= 1"):
        arioso.services.sunoapi.generate("x", audio_input_strength=1.5)


def test_cli_schema_prints_json():
    from arioso.cli import schema

    assert json.loads(schema("sunoapi"))["x-arioso"]["platform"] == "sunoapi"
    with pytest.raises(ValueError, match="Unknown platform"):
        schema("nope")
