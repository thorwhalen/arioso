"""Service layer providing rich access to music generation platforms.

Exposes platforms as a nested Mapping/namespace structure with three
access levels: unified (translated + validated), native (adapter's own
signature), and raw (the adapter instance).

Usage::

    import arioso

    # Browse platforms
    list(arioso.services)              # ['sunoapi', 'musicgen', ...]
    s = arioso.services.sunoapi        # ServiceHandle

    # Browse a platform's resources
    list(s)                            # ['generate', 'native_generate', ...]

    # Unified generate (affordance names, validated)
    song = s.generate("jazz piano", duration=30)

    # Native generate (adapter's own parameter names)
    songs = s.native_generate("jazz piano", genre="jazz", model="V4")

    # Platform-specific methods
    url = s.upload_file("/path/to/audio.mp3")

    # Cross-platform slices
    arioso.generators["sunoapi"]("jazz")
    arioso.generators.sunoapi("jazz")
"""

import functools
import warnings
from collections.abc import Mapping


class ServiceCollection(Mapping):
    """Lazy mapping of platform names to :class:`ServiceHandle` objects.

    Supports both ``services["sunoapi"]`` and ``services.sunoapi``,
    both returning the same :class:`ServiceHandle`.
    """

    def __init__(self):
        self._handles: dict[str, ServiceHandle] = {}

    @functools.cached_property
    def _names(self) -> list[str]:
        from arioso.registry import discover_platforms, list_platforms as _list

        if not _list():
            discover_platforms()
        return _list()

    # -- Mapping protocol --------------------------------------------------

    def __getitem__(self, name: str) -> "ServiceHandle":
        return self._get_handle(name)

    def __iter__(self):
        return iter(self._names)

    def __len__(self):
        return len(self._names)

    def __contains__(self, name):
        return name in self._names

    # -- Attribute access ---------------------------------------------------

    def __getattr__(self, name: str) -> "ServiceHandle":
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._get_handle(name)
        except KeyError:
            raise AttributeError(
                f"No platform named {name!r}. Available: {self._names}"
            ) from None

    def __dir__(self):
        return sorted(set(self._names) | set(super().__dir__()))

    def __repr__(self):
        return f"ServiceCollection({', '.join(self._names)})"

    # -- Internal -----------------------------------------------------------

    def _get_handle(self, name: str) -> "ServiceHandle":
        if name not in self._names:
            raise KeyError(
                f"Unknown platform: {name!r}. Known: {self._names}"
            )
        if name not in self._handles:
            self._handles[name] = ServiceHandle(name)
        return self._handles[name]


class ServiceHandle(Mapping):
    """Namespace and mapping for a single platform's resources.

    Exposes:

    - ``generate`` -- unified affordance names, validated + translated.
    - ``native_generate`` -- adapter's own ``generate`` with native params.
    - ``config`` -- full ``PLATFORM_CONFIG`` dict.
    - ``info`` -- lightweight summary dict.
    - ``adapter`` -- the raw adapter instance.
    - Platform-specific methods (e.g. ``upload_file``) via attribute proxy.

    Also iterable: ``list(handle)`` returns resource names.
    """

    # Resources that are always present (beyond adapter-proxied methods)
    _FIXED_KEYS = ("generate", "native_generate", "config", "info", "adapter")

    def __init__(self, name: str):
        self._name = name

    # -- Lazy properties ----------------------------------------------------

    @functools.cached_property
    def config(self) -> dict:
        """Full PLATFORM_CONFIG dict (loaded without instantiating adapter)."""
        from arioso.registry import get_platform

        return get_platform(self._name)["config"]

    @functools.cached_property
    def adapter(self):
        """The raw adapter instance."""
        from arioso.registry import get_platform

        return get_platform(self._name)["adapter"]

    @functools.cached_property
    def info(self) -> dict:
        """Lightweight summary of the platform."""
        c = self.config
        return {
            "name": self._name,
            "display_name": c.get("display_name", self._name),
            "supported_affordances": c.get("supported_affordances", []),
            "access_type": c.get("access_type", ""),
            "tier": c.get("tier", ""),
        }

    @functools.cached_property
    def native_generate(self):
        """The adapter's own generate method (native parameter names)."""
        adapter = self.adapter
        if hasattr(adapter, "generate"):
            return adapter.generate
        if callable(adapter):
            return adapter
        raise TypeError(
            f"Adapter for {self._name!r} is not callable and has no "
            f"generate method"
        )

    @functools.cached_property
    def generate(self):
        """Generate with unified affordance names, validated and translated."""
        return _make_validated_generate(
            self.native_generate, self.config, self._name
        )

    # -- Mapping protocol ---------------------------------------------------

    def __getitem__(self, key: str):
        if key in self._FIXED_KEYS:
            return getattr(self, key)
        # Try adapter-proxied methods
        adapter = self.adapter
        if hasattr(adapter, key) and not key.startswith("_"):
            return getattr(adapter, key)
        raise KeyError(
            f"No resource {key!r} on platform {self._name!r}. "
            f"Available: {list(self)}"
        )

    def __iter__(self):
        yield from self._FIXED_KEYS
        yield from self._adapter_methods()

    def __len__(self):
        return len(self._FIXED_KEYS) + len(self._adapter_methods())

    def __contains__(self, key):
        if key in self._FIXED_KEYS:
            return True
        adapter = self.adapter
        return hasattr(adapter, key) and not key.startswith("_")

    # -- Attribute proxy to adapter -----------------------------------------

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        adapter = self.adapter
        if hasattr(adapter, name):
            return getattr(adapter, name)
        raise AttributeError(
            f"Platform {self._name!r} has no method {name!r}. "
            f"Available: {list(self)}"
        )

    def __dir__(self):
        base = set(self._FIXED_KEYS) | set(super().__dir__())
        base.update(self._adapter_methods())
        return sorted(base)

    def __repr__(self):
        return f"ServiceHandle({self._name!r})"

    # -- Internal -----------------------------------------------------------

    def _adapter_methods(self) -> list[str]:
        """Public callable methods on the adapter, excluding 'generate'."""
        try:
            adapter = self.adapter
        except Exception:
            return []
        return [
            name
            for name in dir(adapter)
            if not name.startswith("_")
            and name != "generate"
            and callable(getattr(adapter, name, None))
        ]


class SliceMapping(Mapping):
    """Cross-platform slice: maps platform names to a specific resource.

    For example, ``SliceMapping(services, "generate")`` gives a mapping
    where ``slice["sunoapi"]`` is ``services.sunoapi.generate``.

    Supports both ``slice["name"]`` and ``slice.name`` access.
    """

    def __init__(self, collection: ServiceCollection, attr_name: str):
        self._collection = collection
        self._attr = attr_name

    def __getitem__(self, name: str):
        return getattr(self._collection[name], self._attr)

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self[name]
        except KeyError:
            raise AttributeError(
                f"No platform named {name!r}"
            ) from None

    def __iter__(self):
        return iter(self._collection)

    def __len__(self):
        return len(self._collection)

    def __contains__(self, name):
        return name in self._collection

    def __dir__(self):
        return sorted(set(self._collection) | set(super().__dir__()))

    def __repr__(self):
        return f"SliceMapping({self._attr!r}, platforms={list(self._collection)})"


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _make_validated_generate(native_func, config: dict, platform_name: str):
    """Wrap an adapter's generate with translation and validation.

    The returned function accepts unified affordance names, validates them,
    translates to native names, and calls the underlying adapter.
    """
    from arioso.translation import make_kwargs_trans

    param_map = config.get("param_map", {})
    on_unsupported = config.get("on_unsupported_param", "warn")
    supported = set(config.get("supported_affordances", []))
    kwargs_trans = make_kwargs_trans(param_map, on_unsupported=on_unsupported)

    @functools.wraps(native_func)
    def validated_generate(prompt: str, **kwargs):
        _validate_kwargs(kwargs, supported, param_map, platform_name)
        translated = kwargs_trans({"prompt": prompt, **kwargs})
        # prompt may have been translated; extract it if still present
        prompt_val = translated.pop("prompt", None)
        # Some adapters expect prompt as first positional arg
        if prompt_val is not None:
            # Check if 'prompt' was mapped to a different native name
            prompt_native = param_map.get("prompt", {}).get("native_name", "prompt")
            if prompt_native != "prompt" and prompt_native in translated:
                # prompt was already translated to its native name
                return native_func(**translated)
            return native_func(prompt_val, **translated)
        return native_func(**translated)

    validated_generate.__name__ = "generate"
    validated_generate.__qualname__ = f"{platform_name}.generate"
    validated_generate.__doc__ = (
        f"Generate music via {platform_name} using unified affordance names.\n\n"
        f"Supported affordances: {', '.join(sorted(supported)) or '(see config)'}\n\n"
        f"Translates unified parameter names to {platform_name}'s native names "
        f"and validates before calling the adapter."
    )
    return validated_generate


def _validate_kwargs(
    kwargs: dict,
    supported: set,
    param_map: dict,
    platform_name: str,
):
    """Validate kwargs against the platform's declared capabilities.

    Checks:
    1. Type matches AFFORDANCES declaration (soft warning).
    2. Value is within declared choices/min/max (raises ValueError).
    """
    from arioso.base import AFFORDANCES

    for key, value in kwargs.items():
        if value is None:
            continue

        # Type check against AFFORDANCES (soft warning)
        if key in AFFORDANCES:
            expected_type = AFFORDANCES[key].type
            if not isinstance(value, expected_type):
                # Allow int where float is expected
                if not (expected_type is float and isinstance(value, int)):
                    warnings.warn(
                        f"{platform_name}: parameter {key!r} expects "
                        f"{expected_type.__name__}, got {type(value).__name__}",
                        stacklevel=4,
                    )

        # Choices / range validation from param_map
        if key in param_map:
            mapping = param_map[key]
            choices = mapping.get("choices") or mapping.get("enum")
            if choices and value not in choices:
                raise ValueError(
                    f"{platform_name}: parameter {key!r} must be one of "
                    f"{choices}, got {value!r}"
                )
            min_val = mapping.get("min")
            if min_val is not None and value < min_val:
                raise ValueError(
                    f"{platform_name}: parameter {key!r} must be >= {min_val}, "
                    f"got {value!r}"
                )
            max_val = mapping.get("max")
            if max_val is not None and value > max_val:
                raise ValueError(
                    f"{platform_name}: parameter {key!r} must be <= {max_val}, "
                    f"got {value!r}"
                )
