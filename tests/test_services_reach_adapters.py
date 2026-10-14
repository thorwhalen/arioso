"""Every supported affordance reaches its adapter under the name it reads.

thorwhalen/arioso#15: ``services.<platform>.generate`` translated unified names
to native ones (``guidance -> cfg_coef``), but every shipped adapter reads the
unified names, so its ``**kwargs`` swallowed them and the default was used.
These tests pin both halves, per platform, without any network or model:

* the services wrapper hands the adapter exactly the unified names it was given;
* each name a platform declares in ``supported_affordances`` is an explicit
  parameter of its ``Adapter.generate`` (so it is read, not absorbed).
"""

import importlib
import inspect

import pytest

from arioso.registry import discover_platforms, list_platforms
from arioso.services import _make_validated_generate

discover_platforms()
PLATFORMS = sorted(list_platforms())


def _config(name):
    return importlib.import_module(f"arioso.platforms.{name}.config").PLATFORM_CONFIG


def _sample(name, config):
    """A value the validator accepts for one affordance."""
    spec = config.get("param_map", {}).get(name, {})
    allowed = spec.get("choices") or spec.get("enum")
    if allowed:
        return allowed[0]
    from arioso.base import AFFORDANCES

    aff = AFFORDANCES.get(name)
    kind = getattr(aff, "type", str)
    lo = spec.get("min", getattr(aff, "min", None))
    if kind is bool:
        return True
    if kind in (int, float):
        return kind(lo if lo is not None else 1)
    return "x"


@pytest.mark.parametrize("platform", PLATFORMS)
def test_supported_affordances_are_explicit_adapter_parameters(platform):
    adapter_cls = importlib.import_module(f"arioso.platforms.{platform}.adapter").Adapter
    params = set(inspect.signature(adapter_cls.generate).parameters)
    unread = [a for a in _config(platform)["supported_affordances"] if a not in params]
    assert not unread, (
        f"{platform} declares {unread} but its Adapter.generate never names them, "
        "so they are silently swallowed by **kwargs"
    )


@pytest.mark.parametrize("platform", PLATFORMS)
def test_services_generate_passes_unified_names_unchanged(platform):
    config = _config(platform)
    seen = {}

    def recorder(prompt, **kwargs):
        seen.update(kwargs, prompt=prompt)
        return "song"

    generate = _make_validated_generate(recorder, config, platform)
    sent = {
        a: _sample(a, config)
        for a in config["supported_affordances"]
        if a != "prompt"
    }
    assert generate("a prompt", **sent) == "song"
    assert seen == {"prompt": "a prompt", **sent}
