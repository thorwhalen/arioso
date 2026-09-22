"""Integration tests: arioso.generate() enforces on_unsupported_param.

Regression tests for thorwhalen/arioso#3 -- the on_unsupported_param policy
used to be enforced only inside the REST-fallback generate built by
make_generate_func, which no shipped platform actually uses (every platform
has a custom adapter.py). A custom Adapter's generate(..., **kwargs) silently
absorbed anything unsupported, regardless of the platform's declared policy.
These tests register a fake platform with exactly that shape -- a custom
adapter whose generate() takes **kwargs and would silently drop anything
unrecognized -- and confirm arioso.generate()/generate_many() now reject
unsupported params *before* ever calling the adapter.
"""

import warnings

import pytest
from arioso.base import Song
from arioso.registry import _registry, register_platform


class _RecordingAdapter:
    """An adapter whose generate() absorbs and silently drops unknown kwargs.

    This is exactly the shape every shipped arioso adapter has (per #3): the
    bug reproduces only if the adapter itself never raises/warns on its own.
    """

    def __init__(self):
        self.calls = []

    def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return Song(platform="fake_platform", status="complete")


@pytest.fixture
def fake_platform():
    """Register a fake platform with a recording adapter; clean up after."""
    adapter = _RecordingAdapter()
    config = {
        "name": "fake_platform",
        "display_name": "Fake Platform",
        "access_type": "python_lib",
        "param_map": {"prompt": {"native_name": "prompt"}},
        "supported_affordances": ["prompt", "duration"],
        "on_unsupported_param": "warn",
    }
    register_platform("fake_platform", config, adapter=adapter)
    yield adapter
    _registry.pop("fake_platform", None)


def test_generate_warns_for_unsupported_param_through_custom_adapter(fake_platform):
    import arioso

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        arioso.generate("test", platform="fake_platform", weirdness=42)
        assert len(w) == 1
        assert "weirdness" in str(w[0].message)
    # The adapter was still called -- 'warn' means "ignore but tell someone",
    # and the kwarg is still passed through unchanged (validation only).
    assert fake_platform.calls == [("test", {"weirdness": 42})]


def test_generate_raises_for_lyrics_through_custom_adapter_regardless_of_policy(
    fake_platform,
):
    """The exact bug from #3: platform's own policy is 'warn', but lyrics
    silently dropped is content loss, not a quality knob -- must raise."""
    import arioso

    with pytest.raises(ValueError, match="lyrics"):
        arioso.generate("test", platform="fake_platform", lyrics="a poem")
    # Must not have reached the adapter at all.
    assert fake_platform.calls == []


def test_generate_many_also_validates(fake_platform):
    import arioso

    with pytest.raises(ValueError, match="lyrics"):
        arioso.generate_many("test", platform="fake_platform", lyrics="a poem")
    assert fake_platform.calls == []


def test_generate_passes_through_supported_params_unchanged(fake_platform):
    import arioso

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        arioso.generate("test", platform="fake_platform", duration=10)
        assert len(w) == 0
    assert fake_platform.calls == [("test", {"duration": 10})]
