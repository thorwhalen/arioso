# arioso.schema

Machine-readable parameter schemas: what each platform accepts, as JSON Schema.

A front end, an agent or a form generator needs more than the parameter names: it
needs each parameter’s type, its bounds or choices, a display title and whether it
is shared across platforms. [`param_schema()`](#arioso.schema.param_schema) assembles that from the two places
arioso already keeps it, so nothing is restated:

- **common** parameters are the unified affordances (`arioso.base.AFFORDANCES`)
  a platform lists in `supported_affordances`; their type, description and bounds
  come from the affordance, overridden by the platform’s `param_map` entry
  (`title`, `description`, `minimum`/`min`, `maximum`/`max`,
  `choices`, `default`, `type`).
- **extra** parameters are the platform’s own `adapter_params`. A platform may
  declare them as a dict of name to spec (the same keys as a `param_map` entry,
  `type` being a Python type); a bare list of names is still accepted, and such
  extras are marked `untyped` so a form can leave them out.

`native_default` is never used as a default: it is in the platform’s units
(milliseconds, a noise level), not the unified ones. A unified default is the
`default` key.

Example:

```default
>>> schema = param_schema("sunoapi")
>>> schema["properties"]["weirdness"]["x-arioso"]["group"]
'extra'
>>> schema["properties"]["audio_input_strength"]["maximum"]
1
```

### Module Attributes

| [`AUDIO_AFFORDANCES`](#arioso.schema.AUDIO_AFFORDANCES)     | Affordances whose value is audio (a file, bytes, a waveform), not a scalar.                  |
|------------------------------------------------------------------------|----------------------------------------------------------------------------------------------|
| [`MECHANICS_AFFORDANCES`](#arioso.schema.MECHANICS_AFFORDANCES) | Affordances that steer the call rather than the music; left out of schemas.                  |
| [`OPERATION_AFFORDANCES`](#arioso.schema.OPERATION_AFFORDANCES) | Operations a platform supports, from the affordance that enables each.                       |
| [`MECHANICS_EXTRAS`](#arioso.schema.MECHANICS_EXTRAS)      | Extras that steer the call (transport, process, device), not the music; left out of schemas. |

### Functions

| [`common_params`](#arioso.schema.common_params)(platforms)   | The unified parameters every one of `platforms` supports, in the first one's order.                                                                                                                    |
|-----------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`operations`](#arioso.schema.operations)(config)         | What a platform can do, from its config: `generate` plus the operations its supported affordances enable (`cover` for `audio_input`, ...), or the config's own `operations` list when it declares one. |
| [`param_schema`](#arioso.schema.param_schema)(platform)     | The JSON Schema (draft 2020-12) of the parameters `platform` accepts.                                                                                                                                  |
| [`schema_from_config`](#arioso.schema.schema_from_config)(config) | The JSON Schema of a platform config (see [`param_schema()`](#arioso.schema.param_schema)).                                                                                            |

### arioso.schema.AUDIO_AFFORDANCES *= frozenset({'audio_input', 'melody', 'reference_audio'})*

Affordances whose value is audio (a file, bytes, a waveform), not a scalar.

### arioso.schema.MECHANICS_AFFORDANCES *= frozenset({'wait_for_completion'})*

Affordances that steer the call rather than the music; left out of schemas.

### arioso.schema.MECHANICS_EXTRAS *= frozenset({'device', 'fetch', 'runtime', 'timeout'})*

Extras that steer the call (transport, process, device), not the music;
left out of schemas. A spec can also say `"mechanics": True`.

### arioso.schema.OPERATION_AFFORDANCES *= {'cover': 'audio_input', 'extend': 'continue_from', 'inpaint': 'mask_start', 'melody': 'melody', 'style_reference': 'reference_audio'}*

Operations a platform supports, from the affordance that enables each.

### arioso.schema.common_params(platforms)

The unified parameters every one of `platforms` supports, in the first one’s order.

Use it to lay out the part of a form that does not change when the user
switches platform.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### arioso.schema.operations(config)

What a platform can do, from its config: `generate` plus the operations its
supported affordances enable (`cover` for `audio_input`, …), or the
config’s own `operations` list when it declares one.

```pycon
>>> operations({"supported_affordances": ["prompt", "audio_input"]})
['generate', 'cover']
```

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### arioso.schema.param_schema(platform)

The JSON Schema (draft 2020-12) of the parameters `platform` accepts.

Each property carries `x-arioso.group`: `"common"` for a unified
affordance (the same name on every platform that has it) or `"extra"` for a
parameter only this platform has. The schema’s own `x-arioso` lists both
groups and the platform’s `operations`. Reads the config only, so no adapter
or optional dependency is loaded.

* **Parameters:**
  **platform** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Platform identifier (see [`arioso.list_platforms()`](arioso.html.md#arioso.list_platforms)).
* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)
* **Returns:**
  A JSON-ready dict.

### arioso.schema.schema_from_config(config)

The JSON Schema of a platform config (see [`param_schema()`](#arioso.schema.param_schema)).

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)
