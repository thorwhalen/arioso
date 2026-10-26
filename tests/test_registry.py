"""Tests for arioso.registry module."""

import pytest
from arioso.registry import (
    _registry,
    discover_platforms,
    register_platform,
    get_platform,
    list_platforms,
)


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear the registry before each test."""
    _registry.clear()
    yield
    _registry.clear()


def test_discover_platforms():
    discovered = discover_platforms()
    assert "musicgen" in discovered
    assert "sunoapi" in discovered
    assert "elevenlabs" in discovered


def test_list_platforms():
    platforms = list_platforms()
    assert "musicgen" in platforms
    assert "sunoapi" in platforms
    assert "elevenlabs" in platforms


def test_get_platform_config():
    entry = get_platform("musicgen")
    assert "config" in entry
    assert entry["config"]["name"] == "musicgen"
    assert entry["config"]["access_type"] == "python_lib"


def test_get_platform_unknown():
    with pytest.raises(KeyError, match="Unknown platform"):
        get_platform("nonexistent_platform")


def test_register_platform_manual():
    custom_config = {
        "name": "custom_test",
        "display_name": "Custom Test",
        "access_type": "rest_api",
    }
    register_platform("custom_test", custom_config)
    platforms = list_platforms()
    assert "custom_test" in platforms

    entry = get_platform("custom_test")
    assert entry["config"]["name"] == "custom_test"


def test_discover_finds_config():
    discover_platforms()
    entry = _registry.get("musicgen")
    assert entry is not None
    assert entry["config"]["tier"] == "low_level"
    assert entry["config"]["output"]["sample_rate"] == 32000


def test_platform_configs_have_required_keys():
    discover_platforms()
    for name, entry in _registry.items():
        config = entry["config"]
        assert "name" in config, f"{name} missing 'name'"
        assert "access_type" in config, f"{name} missing 'access_type'"
        assert "param_map" in config, f"{name} missing 'param_map'"
        assert "supported_affordances" in config, f"{name} missing 'supported_affordances'"
