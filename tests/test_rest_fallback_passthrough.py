"""The REST fallback keeps every name its platform takes (thorwhalen/arioso#17).

``make_generate_func`` (used when a platform ships no ``adapter.py``) used to
translate with ``param_map`` alone, so a supported affordance with no
``param_map`` entry, and any ``adapter_params`` name, was warned about and
dropped. Drive a config-only platform through both public entry points.
"""

import warnings

import pytest

import arioso
from arioso import translation
from arioso.registry import _registry, register_platform
from arioso.services import ServiceCollection

NAME = "config_only_fake"


@pytest.fixture
def sent(monkeypatch):
    """Register a config-only platform whose HTTP call records its kwargs."""
    calls = []

    def fake_rest_func(config):
        def raw(**native_kwargs):
            calls.append(native_kwargs)
            return b"RIFF"

        return raw

    monkeypatch.setattr(translation, "_build_rest_func", fake_rest_func)
    config = {
        "name": NAME,
        "display_name": "Config-only fake",
        "access_type": "rest_api",
        "param_map": {
            "prompt": {"native_name": "text"},
            "duration": {"native_name": "seconds", "coerce": float},
        },
        # audio_input: supported, but no param_map entry (the sunoapi shape)
        "supported_affordances": ["prompt", "duration", "audio_input"],
        "adapter_params": ["fetch"],
        "on_unsupported_param": "warn",
        "output": {"returns": "bytes", "default_format": "wav"},
    }
    saved = dict(_registry)
    register_platform(NAME, config)  # adapter=None -> the REST fallback
    yield calls
    _registry.clear()
    _registry.update(saved)


def _assert_kept(native_kwargs):
    assert native_kwargs["text"] == "a song"
    assert native_kwargs["seconds"] == 10.0
    assert native_kwargs["audio_input"] == "ref.wav"
    assert native_kwargs["fetch"] is False


def test_arioso_generate_keeps_unmapped_supported_and_adapter_params(sent):
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # nothing supported may be "ignored"
        arioso.generate(
            "a song", platform=NAME, duration=10, audio_input="ref.wav", fetch=False
        )
    (native_kwargs,) = sent
    _assert_kept(native_kwargs)


def test_services_generate_keeps_them_too(sent):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        # a fresh collection: the module-level one caches the platform names it first saw
        ServiceCollection()[NAME].generate(
            "a song", duration=10, audio_input="ref.wav", fetch=False
        )
    (native_kwargs,) = sent
    _assert_kept(native_kwargs)


def test_an_unsupported_name_is_still_warned_about_and_dropped(sent):
    with pytest.warns(UserWarning, match="bogus"):
        arioso.generate("a song", platform=NAME, bogus=1)
    (native_kwargs,) = sent
    assert "bogus" not in native_kwargs


def test_a_name_param_map_covers_keeps_its_rename_even_if_in_adapter_params(
    monkeypatch,
):
    calls = []
    monkeypatch.setattr(
        translation,
        "_build_rest_func",
        lambda config: lambda **kw: calls.append(kw) or b"",
    )
    generate = translation.make_generate_func(
        {
            "name": "overlap_fake",
            "param_map": {
                "prompt": {"native_name": "text"},
                "duration": {"native_name": "seconds", "coerce": float},
            },
            "supported_affordances": ["prompt", "duration"],
            "adapter_params": ["duration"],
            "output": {"returns": "bytes"},
        }
    )
    generate("a song", duration=10)
    assert calls == [{"text": "a song", "seconds": 10.0}]
