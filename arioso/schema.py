"""Machine-readable parameter schemas: what each platform accepts, as JSON Schema.

A front end, an agent or a form generator needs more than the parameter names: it
needs each parameter's type, its bounds or choices, a display title and whether it
is shared across platforms. :func:`param_schema` assembles that from the two places
arioso already keeps it, so nothing is restated:

- **common** parameters are the unified affordances (:data:`arioso.base.AFFORDANCES`)
  a platform lists in ``supported_affordances``; their type, description and bounds
  come from the affordance, overridden by the platform's ``param_map`` entry
  (``title``, ``description``, ``minimum``/``min``, ``maximum``/``max``,
  ``choices``, ``default``, ``type``).
- **extra** parameters are the platform's own ``adapter_params``. A platform may
  declare them as a dict of name to spec (the same keys as a ``param_map`` entry,
  ``type`` being a Python type); a bare list of names is still accepted, and such
  extras are marked ``untyped`` so a form can leave them out.

``native_default`` is never used as a default: it is in the platform's units
(milliseconds, a noise level), not the unified ones. A unified default is the
``default`` key.

Example::

    >>> schema = param_schema("sunoapi")
    >>> schema["properties"]["weirdness"]["x-arioso"]["group"]
    'extra'
    >>> schema["properties"]["audio_input_strength"]["maximum"]
    1
"""

from __future__ import annotations

from typing import Any

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"

#: Affordances whose value is audio (a file, bytes, a waveform), not a scalar.
AUDIO_AFFORDANCES = frozenset({"audio_input", "melody", "reference_audio"})

#: Affordances that steer the call rather than the music; left out of schemas.
MECHANICS_AFFORDANCES = frozenset({"wait_for_completion"})

#: Operations a platform supports, from the affordance that enables each.
OPERATION_AFFORDANCES = {
    "cover": "audio_input",
    "extend": "continue_from",
    "inpaint": "mask_start",
    "style_reference": "reference_audio",
    "melody": "melody",
}

_JSON_TYPES = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}

# Spec keys copied onto a property under their JSON Schema names.
_SPEC_KEYS = {
    "title": "title",
    "description": "description",
    "default": "default",
    "minimum": "minimum",
    "min": "minimum",
    "maximum": "maximum",
    "max": "maximum",
    "choices": "enum",
    "enum": "enum",
    "multiple_of": "multipleOf",
}

# Spec keys that are hints for a form or an agent, kept under ``x-arioso``:
# ``neutral`` (where a control starts; never sent by itself), ``scale_labels``
# (the two ends of a slider), ``multiline``, ``advanced`` (fold it away),
# ``requires`` (every one of these must be given too), ``requires_any`` (at
# least one), ``operations`` (only for these operations), ``unset`` (the value
# that means "not given"), ``examples``.
_HINT_KEYS = (
    "neutral",
    "scale_labels",
    "multiline",
    "advanced",
    "requires",
    "requires_any",
    "operations",
    "unset",
    "examples",
)

#: Extras that steer the call (transport, process, device), not the music;
#: left out of schemas. A spec can also say ``"mechanics": True``.
MECHANICS_EXTRAS = frozenset({"fetch", "timeout", "device", "runtime"})


def _title(name: str) -> str:
    """``"audio_input_strength"`` -> ``"Audio input strength"``."""
    return name.replace("_", " ").capitalize()


def _json_type(py_type) -> str | None:
    return _JSON_TYPES.get(py_type)


def _apply_spec(prop: dict, spec: dict) -> dict:
    """Overlay a ``param_map``/``adapter_params`` spec onto a property."""
    if "type" in spec and isinstance(spec["type"], type):
        json_type = _json_type(spec["type"])
        if json_type:
            prop["type"] = json_type
    for key, json_key in _SPEC_KEYS.items():
        if spec.get(key) is not None:
            value = spec[key]
            prop[json_key] = list(value) if json_key == "enum" else value
    hints = {k: spec[k] for k in _HINT_KEYS if spec.get(k) is not None}
    if hints:
        prop.setdefault("x-arioso", {}).update(hints)
    return prop


def _common_property(name: str, mapping: dict) -> dict:
    from arioso.base import AFFORDANCES

    affordance = AFFORDANCES[name]
    is_clip_id = mapping.get("type") is str
    if name in AUDIO_AFFORDANCES or (name == "continue_from" and not is_clip_id):
        # In JSON the audio is a URL (a form uploads first, then passes the URL).
        prop = {"type": "string", "format": "uri", "contentMediaType": "audio/*"}
        kind = "audio"
    elif name == "continue_from":
        prop = {"type": "string"}
        kind = "clip"
    else:
        prop = {}
        json_type = _json_type(affordance.type)
        if json_type:
            prop["type"] = json_type
        kind = "value"
    prop["title"] = affordance.title or _title(name)
    prop["description"] = affordance.description
    for attr in ("default", "minimum", "maximum"):
        value = getattr(affordance, attr)
        if value is not None:
            prop[attr] = value
    prop = _apply_spec(prop, mapping)
    xa = prop.setdefault("x-arioso", {})
    xa.update(group="common", kind=kind)
    if mapping.get("native_name"):
        xa["native_name"] = mapping["native_name"]
    return prop


def _extra_property(name: str, spec: dict | None) -> dict:
    prop = {"title": _title(name)}
    if spec is None:
        prop["x-arioso"] = {"group": "extra", "kind": "value", "untyped": True}
        return prop
    prop = _apply_spec(prop, spec)
    prop.setdefault("x-arioso", {}).update(group="extra", kind="value")
    return prop


def _extras(config: dict) -> dict:
    """``{name: spec or None}`` from ``adapter_params`` (a dict, or a list of names)."""
    extras = config.get("adapter_params") or {}
    if isinstance(extras, dict):
        return dict(extras)
    return {name: None for name in extras}


def operations(config: dict) -> list[str]:
    """What a platform can do, from its config: ``generate`` plus the operations its
    supported affordances enable (``cover`` for ``audio_input``, ...), or the
    config's own ``operations`` list when it declares one.

    >>> operations({"supported_affordances": ["prompt", "audio_input"]})
    ['generate', 'cover']
    """
    if config.get("operations"):
        return list(config["operations"])
    supported = set(config.get("supported_affordances", ()))
    return ["generate"] + [
        op for op, aff in OPERATION_AFFORDANCES.items() if aff in supported
    ]


def schema_from_config(config: dict) -> dict:
    """The JSON Schema of a platform config (see :func:`param_schema`)."""
    from arioso.base import AFFORDANCES

    param_map = config.get("param_map", {})
    properties: dict[str, Any] = {}
    required = []
    common, extra = [], []
    for name in config.get("supported_affordances", ()):
        if name not in AFFORDANCES or name in MECHANICS_AFFORDANCES:
            continue
        mapping = param_map.get(name, {})
        properties[name] = _common_property(name, mapping)
        common.append(name)
        if mapping.get("required"):
            required.append(name)
    for name, spec in _extras(config).items():
        if name in properties or name in MECHANICS_EXTRAS or (spec or {}).get("mechanics"):
            continue
        properties[name] = _extra_property(name, spec)
        extra.append(name)
    schema = {
        "$schema": JSON_SCHEMA_DIALECT,
        "title": config.get("display_name") or config.get("name", ""),
        "type": "object",
        "properties": properties,
        "x-arioso": {
            "platform": config.get("name", ""),
            "operations": operations(config),
            "common": common,
            "extra": extra,
            "access_type": config.get("access_type"),
            "commercial_use": config.get("commercial_use"),
        },
    }
    if required:
        schema["required"] = required
    return schema


def param_schema(platform: str) -> dict:
    """The JSON Schema (draft 2020-12) of the parameters ``platform`` accepts.

    Each property carries ``x-arioso.group``: ``"common"`` for a unified
    affordance (the same name on every platform that has it) or ``"extra"`` for a
    parameter only this platform has. The schema's own ``x-arioso`` lists both
    groups and the platform's ``operations``. Reads the config only, so no adapter
    or optional dependency is loaded.

    Args:
        platform: Platform identifier (see :func:`arioso.list_platforms`).

    Returns:
        A JSON-ready dict.
    """
    from arioso.registry import get_config

    return schema_from_config(get_config(platform))


def common_params(platforms) -> list[str]:
    """The unified parameters every one of ``platforms`` supports, in the first one's order.

    Use it to lay out the part of a form that does not change when the user
    switches platform.
    """
    schemas = [param_schema(p)["x-arioso"]["common"] for p in platforms]
    if not schemas:
        return []
    shared = set(schemas[0]).intersection(*schemas[1:])
    return [name for name in schemas[0] if name in shared]
