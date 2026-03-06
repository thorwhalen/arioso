"""Platform registry with auto-discovery and lazy loading."""

import importlib
import pkgutil
from typing import Any

_registry: dict[str, dict] = {}


def discover_platforms() -> list[str]:
    """Scan arioso.platforms for valid platform packages.

    A valid platform package is a directory under arioso/platforms/ that:
    1. Is a Python package (__init__.py exists)
    2. Contains a config.py with a PLATFORM_CONFIG dict

    Returns:
        List of discovered platform names.
    """
    import arioso.platforms as platforms_pkg

    discovered = []
    for _importer, modname, ispkg in pkgutil.iter_modules(platforms_pkg.__path__):
        if ispkg and not modname.startswith("_"):
            try:
                config_module = importlib.import_module(
                    f"arioso.platforms.{modname}.config"
                )
                config = getattr(config_module, "PLATFORM_CONFIG", None)
                if config and isinstance(config, dict):
                    _registry[modname] = {
                        "config": config,
                        "adapter": None,  # lazy-loaded
                    }
                    discovered.append(modname)
            except ImportError:
                pass
    return discovered


def register_platform(name: str, config: dict, adapter: Any = None):
    """Manually register a platform (for third-party plugins).

    Args:
        name: Platform identifier.
        config: PLATFORM_CONFIG dict following the standard schema.
        adapter: Optional pre-instantiated adapter object or class.
    """
    _registry[name] = {
        "config": config,
        "adapter": adapter,
    }


def get_platform(name: str) -> dict:
    """Get registered platform info, lazy-loading the adapter if needed.

    Args:
        name: Platform identifier.

    Returns:
        Dict with 'config' and 'adapter' keys.

    Raises:
        KeyError: If the platform is not found.
    """
    if name not in _registry:
        discover_platforms()
    if name not in _registry:
        raise KeyError(f"Unknown platform: {name!r}. Known: {list(_registry)}")
    entry = _registry[name]
    if entry["adapter"] is None:
        entry["adapter"] = _load_adapter(name, entry["config"])
    return entry


def list_platforms() -> list[str]:
    """Return names of all registered platforms."""
    if not _registry:
        discover_platforms()
    return list(_registry)


def _load_adapter(name: str, config: dict):
    """Lazy-load the platform's adapter module and instantiate.

    Tries to import ``arioso.platforms.<name>.adapter`` and find an
    ``Adapter`` class. If that fails, falls back to auto-generating
    a generate function from the config via the translation layer.
    """
    try:
        adapter_module = importlib.import_module(f"arioso.platforms.{name}.adapter")
        adapter_class = getattr(adapter_module, "Adapter", None)
        if adapter_class:
            return adapter_class(config)
    except ImportError:
        pass
    # Fall back to auto-generated adapter from config
    from arioso.translation import make_generate_func

    return make_generate_func(config)
