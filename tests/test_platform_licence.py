"""Every platform declares its weights licence and whether its output may be used commercially."""

import pytest

import arioso
from arioso.base import COMMERCIAL_USE_VALUES
from arioso.registry import _registry, get_config, list_platforms


@pytest.mark.parametrize("name", list_platforms())
def test_every_platform_declares_its_licence(name):
    config = get_config(name)
    assert isinstance(config.get("weights_license"), str) and config["weights_license"]
    assert config.get("commercial_use") in COMMERCIAL_USE_VALUES


@pytest.mark.parametrize(
    "name, license, commercial_use",
    [
        ("musicgen", "CC-BY-NC-4.0", "no"),
        ("stable_audio", "Stability AI Community License", "conditional"),
        ("foundation_1", "Stability AI Community License", "conditional"),
        ("harmonai", "MIT", "yes"),
        ("sunoapi", "proprietary", "provider terms"),
    ],
)
def test_known_licences(name, license, commercial_use):
    config = arioso.get_platform_info(name)
    assert (config["weights_license"], config["commercial_use"]) == (
        license,
        commercial_use,
    )


def test_platform_table_has_one_row_per_platform_with_the_licence_columns():
    rows = arioso.platform_table()

    assert [r["name"] for r in rows] == arioso.list_platforms()
    assert all(tuple(r) == arioso.PLATFORM_TABLE_FIELDS for r in rows)
    musicgen = next(r for r in rows if r["name"] == "musicgen")
    assert musicgen == {
        "name": "musicgen",
        "access_type": "python_lib",
        "weights_license": "CC-BY-NC-4.0",
        "commercial_use": "no",
    }


def test_platform_table_loads_no_adapter():
    _registry.clear()
    try:
        arioso.platform_table()
        assert _registry and all(e["adapter"] is None for e in _registry.values())
    finally:
        _registry.clear()


def test_platform_table_fields_are_selectable():
    rows = arioso.platform_table(fields=("name", "website"))
    assert all(set(r) == {"name", "website"} for r in rows)
