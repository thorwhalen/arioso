"""Tests for arioso.translation module."""

import warnings

import pytest
from arioso.translation import make_kwargs_trans, check_supported_params


def test_simple_rename():
    param_map = {
        "instrumental": {"native_name": "make_instrumental"},
    }
    trans = make_kwargs_trans(param_map)
    result = trans({"instrumental": True})
    assert result == {"make_instrumental": True}


def test_coercion():
    param_map = {
        "duration": {
            "native_name": "duration_ms",
            "coerce": lambda x: int(x * 1000),
        },
    }
    trans = make_kwargs_trans(param_map)
    result = trans({"duration": 30.0})
    assert result == {"duration_ms": 30000}


def test_same_name():
    param_map = {
        "prompt": {"native_name": "prompt"},
    }
    trans = make_kwargs_trans(param_map)
    result = trans({"prompt": "jazz piano"})
    assert result == {"prompt": "jazz piano"}


def test_adapter_handled():
    param_map = {
        "lyrics": {"native_name": None, "adapter_handled": True},
    }
    trans = make_kwargs_trans(param_map)
    result = trans({"lyrics": "Hello world"})
    assert result == {"lyrics": "Hello world"}


def test_native_name_none_not_adapter_handled():
    param_map = {
        "skip_me": {"native_name": None},
    }
    trans = make_kwargs_trans(param_map)
    result = trans({"skip_me": "value"})
    assert result == {}


def test_unsupported_warn():
    param_map = {"prompt": {"native_name": "prompt"}}
    trans = make_kwargs_trans(param_map, on_unsupported="warn")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = trans({"prompt": "test", "unknown_param": 42})
        assert len(w) == 1
        assert "unknown_param" in str(w[0].message)
    assert result == {"prompt": "test"}


def test_unsupported_raise():
    param_map = {"prompt": {"native_name": "prompt"}}
    trans = make_kwargs_trans(param_map, on_unsupported="raise")
    with pytest.raises(ValueError, match="not supported"):
        trans({"prompt": "test", "unknown_param": 42})


def test_unsupported_ignore():
    param_map = {"prompt": {"native_name": "prompt"}}
    trans = make_kwargs_trans(param_map, on_unsupported="ignore")
    result = trans({"prompt": "test", "unknown_param": 42})
    assert result == {"prompt": "test"}


def _config(*, on_unsupported="warn", supported=("prompt", "duration")):
    return {
        "name": "fake_platform",
        "supported_affordances": list(supported),
        "on_unsupported_param": on_unsupported,
    }


def test_check_supported_params_no_warning_for_supported_key():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        check_supported_params({"duration": 10}, _config())
        assert len(w) == 0


def test_check_supported_params_warns_by_default():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        check_supported_params({"bogus": 1}, _config(on_unsupported="warn"))
        assert len(w) == 1
        assert "bogus" in str(w[0].message)


def test_check_supported_params_raise_policy():
    with pytest.raises(ValueError, match="bogus"):
        check_supported_params({"bogus": 1}, _config(on_unsupported="raise"))


def test_check_supported_params_ignore_policy_is_silent():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        check_supported_params({"bogus": 1}, _config(on_unsupported="ignore"))
        assert len(w) == 0


def test_check_supported_params_lyrics_always_raises_even_under_warn_policy():
    """Regression test for thorwhalen/arioso#3.

    lyrics is content, not a quality knob: silently dropping it must raise
    regardless of the platform's own on_unsupported_param policy.
    """
    with pytest.raises(ValueError, match="lyrics"):
        check_supported_params({"lyrics": "a poem"}, _config(on_unsupported="warn"))


def test_check_supported_params_lyrics_ok_when_platform_supports_it():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        check_supported_params(
            {"lyrics": "a poem"}, _config(supported=("prompt", "lyrics"))
        )
        assert len(w) == 0


def test_multiple_params():
    param_map = {
        "prompt": {"native_name": "prompt", "required": True},
        "duration": {"native_name": "music_length_ms", "coerce": lambda x: int(x * 1000)},
        "instrumental": {"native_name": "force_instrumental"},
    }
    trans = make_kwargs_trans(param_map)
    result = trans({"prompt": "jazz", "duration": 30.0, "instrumental": True})
    assert result == {
        "prompt": "jazz",
        "music_length_ms": 30000,
        "force_instrumental": True,
    }
