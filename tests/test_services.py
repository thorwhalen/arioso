"""Tests for arioso.services module."""

import warnings

import pytest
from arioso.registry import _registry, discover_platforms, register_platform
from arioso.services import ServiceCollection, ServiceHandle, SliceMapping


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear the registry before each test."""
    _registry.clear()
    yield
    _registry.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeAdapter:
    """Minimal adapter for testing."""

    def __init__(self, config):
        self._config = config

    def generate(self, prompt, **kwargs):
        return {"prompt": prompt, **kwargs}

    def upload_file(self, path):
        return f"uploaded:{path}"

    def get_status(self, task_id):
        return [{"id": task_id, "status": "complete"}]


def _register_fake(name="fake_platform", *, extra_config=None):
    """Register a fake platform for testing."""
    config = {
        "name": name,
        "display_name": f"Fake {name}",
        "access_type": "rest_api",
        "tier": "simple",
        "param_map": {
            "prompt": {"native_name": "prompt"},
            "duration": {
                "native_name": "duration_sec",
                "coerce": float,
            },
            "model": {
                "native_name": "model_version",
                "choices": ["v1", "v2", "v3"],
            },
        },
        "supported_affordances": ["prompt", "duration", "model"],
        "on_unsupported_param": "warn",
        **(extra_config or {}),
    }
    adapter = _FakeAdapter(config)
    register_platform(name, config, adapter)
    return config, adapter


# ---------------------------------------------------------------------------
# ServiceCollection tests
# ---------------------------------------------------------------------------


class TestServiceCollection:
    def test_iter_lists_platforms(self):
        _register_fake("alpha")
        _register_fake("beta")
        sc = ServiceCollection()
        names = list(sc)
        assert "alpha" in names
        assert "beta" in names

    def test_len(self):
        _register_fake("alpha")
        _register_fake("beta")
        sc = ServiceCollection()
        assert len(sc) >= 2

    def test_contains(self):
        _register_fake("alpha")
        sc = ServiceCollection()
        assert "alpha" in sc
        assert "nonexistent" not in sc

    def test_getitem_returns_service_handle(self):
        _register_fake("alpha")
        sc = ServiceCollection()
        handle = sc["alpha"]
        assert isinstance(handle, ServiceHandle)

    def test_getattr_returns_service_handle(self):
        _register_fake("alpha")
        sc = ServiceCollection()
        handle = sc.alpha
        assert isinstance(handle, ServiceHandle)

    def test_getitem_and_getattr_return_same_handle(self):
        _register_fake("alpha")
        sc = ServiceCollection()
        assert sc["alpha"] is sc.alpha

    def test_getitem_unknown_raises_key_error(self):
        sc = ServiceCollection()
        discover_platforms()
        with pytest.raises(KeyError, match="Unknown platform"):
            sc["nonexistent_platform_xyz"]

    def test_getattr_unknown_raises_attribute_error(self):
        sc = ServiceCollection()
        discover_platforms()
        with pytest.raises(AttributeError, match="No platform named"):
            sc.nonexistent_platform_xyz

    def test_dir_includes_platform_names(self):
        _register_fake("alpha")
        sc = ServiceCollection()
        assert "alpha" in dir(sc)

    def test_repr(self):
        _register_fake("alpha")
        sc = ServiceCollection()
        r = repr(sc)
        assert "ServiceCollection" in r
        assert "alpha" in r


# ---------------------------------------------------------------------------
# ServiceHandle tests
# ---------------------------------------------------------------------------


class TestServiceHandle:
    def test_config(self):
        config, _ = _register_fake("fake_plat")
        sh = ServiceHandle("fake_plat")
        assert sh.config["name"] == "fake_plat"
        assert sh.config is sh.config  # cached_property

    def test_adapter(self):
        _, adapter = _register_fake("fake_plat")
        sh = ServiceHandle("fake_plat")
        assert sh.adapter is adapter

    def test_info(self):
        _register_fake("fake_plat")
        sh = ServiceHandle("fake_plat")
        info = sh.info
        assert info["name"] == "fake_plat"
        assert "display_name" in info
        assert "supported_affordances" in info
        assert "prompt" in info["supported_affordances"]

    def test_native_generate(self):
        _register_fake("fake_plat")
        sh = ServiceHandle("fake_plat")
        result = sh.native_generate("hello")
        assert result["prompt"] == "hello"

    def test_generate_passes_unified_names(self):
        """Adapters take unified names; translating here hid them in **kwargs
        (thorwhalen/arioso#15), so services must pass them unchanged, as
        ``arioso.generate`` does."""
        _register_fake("fake_plat")
        sh = ServiceHandle("fake_plat")
        result = sh.generate("hello", duration=10)
        assert result.get("duration") == 10
        assert "duration_sec" not in result

    def test_generate_validates_choices(self):
        _register_fake("fake_plat")
        sh = ServiceHandle("fake_plat")
        with pytest.raises(ValueError, match="must be one of"):
            sh.generate("hello", model="invalid_model")

    def test_generate_warns_on_unsupported(self):
        _register_fake("fake_plat")
        sh = ServiceHandle("fake_plat")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            sh.generate("hello", energy=0.5)
            assert any("not supported" in str(x.message) for x in w)

    def test_generate_raises_on_unsupported_lyrics_regardless_of_policy(self):
        """Same guard as arioso.generate() (thorwhalen/arioso#6)."""
        _, adapter = _register_fake("fake_plat")
        sh = ServiceHandle("fake_plat")
        with pytest.raises(ValueError, match="lyrics"):
            sh.generate("hello", lyrics="a poem")

    def test_generate_lyrics_ok_when_supported(self):
        _register_fake(
            "fake_plat",
            extra_config={
                "supported_affordances": ["prompt", "duration", "model", "lyrics"],
                "param_map": {
                    "prompt": {"native_name": "prompt"},
                    "lyrics": {"native_name": "lyrics"},
                },
            },
        )
        sh = ServiceHandle("fake_plat")
        assert sh.generate("hello", lyrics="a poem")["lyrics"] == "a poem"

    def test_generate_unsupported_warns_exactly_once(self):
        _register_fake("fake_plat")
        sh = ServiceHandle("fake_plat")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            sh.generate("hello", energy=0.5)
        assert len([x for x in w if "energy" in str(x.message)]) == 1

    def test_generate_warns_on_type_mismatch(self):
        """Type warning fires for params without coercion in param_map.

        For params *with* coercion (like duration -> float), the coerce
        step in make_kwargs_trans will raise on bad types. We test a param
        that has no coercion but is declared as int in AFFORDANCES.
        """
        _register_fake("fake_plat", extra_config={
            "param_map": {
                "prompt": {"native_name": "prompt"},
                "duration": {"native_name": "duration_sec", "coerce": float},
                "model": {"native_name": "model_version", "choices": ["v1", "v2", "v3"]},
                "seed": {"native_name": "seed_val"},
            },
            "supported_affordances": ["prompt", "duration", "model", "seed"],
        })
        sh = ServiceHandle("fake_plat")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # seed is declared as int in AFFORDANCES but we pass a string;
            # no coercion is defined so it won't crash, but should warn.
            sh.generate("hello", seed="not_an_int")
            type_warnings = [
                x for x in w if "expects" in str(x.message)
            ]
            assert len(type_warnings) > 0

    def test_proxy_to_adapter_methods(self):
        _register_fake("fake_plat")
        sh = ServiceHandle("fake_plat")
        result = sh.upload_file("/test/path.mp3")
        assert result == "uploaded:/test/path.mp3"

    def test_proxy_unknown_method_raises(self):
        _register_fake("fake_plat")
        sh = ServiceHandle("fake_plat")
        with pytest.raises(AttributeError, match="has no method"):
            sh.nonexistent_method()

    def test_mapping_protocol_iter(self):
        _register_fake("fake_plat")
        sh = ServiceHandle("fake_plat")
        keys = list(sh)
        assert "generate" in keys
        assert "native_generate" in keys
        assert "config" in keys
        assert "info" in keys
        assert "adapter" in keys
        assert "upload_file" in keys

    def test_mapping_protocol_getitem(self):
        _register_fake("fake_plat")
        sh = ServiceHandle("fake_plat")
        assert sh["config"] == sh.config
        assert sh["info"] == sh.info

    def test_mapping_protocol_len(self):
        _register_fake("fake_plat")
        sh = ServiceHandle("fake_plat")
        assert len(sh) >= 5  # at least the fixed keys

    def test_mapping_protocol_contains(self):
        _register_fake("fake_plat")
        sh = ServiceHandle("fake_plat")
        assert "generate" in sh
        assert "upload_file" in sh
        assert "nonexistent" not in sh

    def test_getitem_unknown_raises_key_error(self):
        _register_fake("fake_plat")
        sh = ServiceHandle("fake_plat")
        with pytest.raises(KeyError, match="No resource"):
            sh["nonexistent_resource"]

    def test_dir_includes_adapter_methods(self):
        _register_fake("fake_plat")
        sh = ServiceHandle("fake_plat")
        d = dir(sh)
        assert "generate" in d
        assert "upload_file" in d
        assert "get_status" in d

    def test_repr(self):
        _register_fake("fake_plat")
        sh = ServiceHandle("fake_plat")
        assert "fake_plat" in repr(sh)


# ---------------------------------------------------------------------------
# SliceMapping tests
# ---------------------------------------------------------------------------


class TestSliceMapping:
    def test_getitem(self):
        _register_fake("alpha")
        sc = ServiceCollection()
        gen_slice = SliceMapping(sc, "generate")
        gen_func = gen_slice["alpha"]
        assert callable(gen_func)

    def test_getattr(self):
        _register_fake("alpha")
        sc = ServiceCollection()
        gen_slice = SliceMapping(sc, "generate")
        gen_func = gen_slice.alpha
        assert callable(gen_func)

    def test_iter(self):
        _register_fake("alpha")
        _register_fake("beta")
        sc = ServiceCollection()
        gen_slice = SliceMapping(sc, "generate")
        names = list(gen_slice)
        assert "alpha" in names
        assert "beta" in names

    def test_len(self):
        _register_fake("alpha")
        _register_fake("beta")
        sc = ServiceCollection()
        gen_slice = SliceMapping(sc, "generate")
        assert len(gen_slice) >= 2

    def test_contains(self):
        _register_fake("alpha")
        sc = ServiceCollection()
        gen_slice = SliceMapping(sc, "generate")
        assert "alpha" in gen_slice
        assert "nonexistent" not in gen_slice

    def test_info_slice(self):
        _register_fake("alpha")
        sc = ServiceCollection()
        info_slice = SliceMapping(sc, "info")
        info = info_slice["alpha"]
        assert isinstance(info, dict)
        assert info["name"] == "alpha"

    def test_config_slice(self):
        _register_fake("alpha")
        sc = ServiceCollection()
        config_slice = SliceMapping(sc, "config")
        config = config_slice["alpha"]
        assert config["name"] == "alpha"

    def test_getattr_unknown_raises(self):
        sc = ServiceCollection()
        discover_platforms()
        gen_slice = SliceMapping(sc, "generate")
        with pytest.raises(AttributeError, match="No platform named"):
            gen_slice.nonexistent_xyz

    def test_dir_includes_platform_names(self):
        _register_fake("alpha")
        sc = ServiceCollection()
        gen_slice = SliceMapping(sc, "generate")
        assert "alpha" in dir(gen_slice)

    def test_repr(self):
        _register_fake("alpha")
        sc = ServiceCollection()
        gen_slice = SliceMapping(sc, "generate")
        r = repr(gen_slice)
        assert "SliceMapping" in r
        assert "generate" in r


# ---------------------------------------------------------------------------
# Integration: arioso top-level access
# ---------------------------------------------------------------------------


class TestAriosoIntegration:
    def test_services_accessible(self):
        import arioso

        assert hasattr(arioso, "services")
        assert isinstance(arioso.services, ServiceCollection)

    def test_slice_views_accessible(self):
        import arioso

        assert isinstance(arioso.generators, SliceMapping)
        assert isinstance(arioso.native_generators, SliceMapping)
        assert isinstance(arioso.infos, SliceMapping)
        assert isinstance(arioso.configs, SliceMapping)
        assert isinstance(arioso.adapters, SliceMapping)

    def test_existing_facade_still_works(self):
        import arioso

        platforms = arioso.list_platforms()
        assert isinstance(platforms, list)
        assert len(platforms) > 0

    def test_services_discovers_same_as_list_platforms(self):
        import arioso

        facade_list = set(arioso.list_platforms())
        services_list = set(arioso.services)
        assert facade_list == services_list


# ---------------------------------------------------------------------------
# thorwhalen/arioso#13: one source of truth for "supported"
# ---------------------------------------------------------------------------


def _warned_keys(fn, kwargs):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            fn("hello", **kwargs)
        except (ValueError, TypeError):
            pass  # a probe value a coercion refuses; the check has run by then
    return {k for k in kwargs if any(repr(k) in str(x.message) for x in w)}


def test_both_entry_points_judge_supported_alike_on_every_platform():
    """For every shipped config, the services wrapper warns for exactly the
    keys ``arioso.generate``'s check warns for (both read
    ``supported_affordances``; the services path used to read ``param_map``)."""
    from arioso.base import AFFORDANCES
    from arioso.registry import _registry
    from arioso.services import _make_validated_generate
    from arioso.translation import check_supported_params

    import arioso

    arioso.list_platforms()  # discovery
    probe = {k: None for k in AFFORDANCES if k not in ("prompt", "lyrics")}
    for name in list(_registry):
        config = {**_registry[name]["config"], "on_unsupported_param": "warn"}
        wrapped = _make_validated_generate(lambda *a, **k: None, config, name)
        via_generate = _warned_keys(
            lambda prompt, **kw: check_supported_params(kw, config), probe
        )
        assert _warned_keys(wrapped, probe) == via_generate, name


def test_a_supported_affordance_without_a_param_map_entry_reaches_the_adapter():
    """sunoapi's ``audio_input`` is supported but not in its param_map: the
    services path used to warn "not supported" and drop it."""
    _register_fake(
        "fake_plat",
        extra_config={
            "supported_affordances": ["prompt", "duration", "model", "audio_input"],
        },
    )
    sh = ServiceHandle("fake_plat")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = sh.generate("hello", audio_input="clip.wav")
    assert not [x for x in w if "audio_input" in str(x.message)]
    assert result["audio_input"] == "clip.wav"


def test_the_prompt_reaches_the_adapter_even_when_undeclared():
    """harmonai declares no ``prompt``: the services path used to drop it with a
    "not supported" warning, while arioso.generate passes it (arioso#13 review)."""
    _register_fake(
        "fake_plat",
        extra_config={"supported_affordances": ["duration"], "param_map": {}},
    )
    sh = ServiceHandle("fake_plat")
    assert sh.generate("hello")["prompt"] == "hello"
