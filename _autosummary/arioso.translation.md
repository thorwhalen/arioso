# arioso.translation

Parameter translation layer.

Translates between the unified affordance names and each platform’s
native parameter names, applying type coercions along the way.

### Module Attributes

| [`ALWAYS_RAISE_UNSUPPORTED`](#arioso.translation.ALWAYS_RAISE_UNSUPPORTED)   | Affordances that always raise on an unsupported platform, regardless of that platform's own `on_unsupported_param` policy.   |
|-----------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|

### Functions

| [`check_supported_params`](#arioso.translation.check_supported_params)(kwargs, config, \*[, ...])   | Warn or raise for kwargs not declared in a platform's `supported_affordances`.   |
|------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------|
| [`make_generate_func`](#arioso.translation.make_generate_func)(config)                          | Build a generate() callable from a platform config.                              |
| [`make_kwargs_trans`](#arioso.translation.make_kwargs_trans)(param_map, \*[, on_unsupported])  | Build a kwargs translation function from a platform's param_map.                 |

### arioso.translation.ALWAYS_RAISE_UNSUPPORTED *= ('lyrics',)*

Affordances that always raise on an unsupported platform, regardless of
that platform’s own `on_unsupported_param` policy. Losing these silently
is losing *content*, not a quality knob – e.g. an instrumental with none
of the caller’s words in it, with no signal that happened. See
thorwhalen/arioso#3.

### arioso.translation.check_supported_params(kwargs, config, , always_raise=('lyrics',))

Warn or raise for kwargs not declared in a platform’s `supported_affordances`.

`on_unsupported_param` was, until thorwhalen/arioso#3, only ever enforced
inside [`make_kwargs_trans()`](#arioso.translation.make_kwargs_trans) – reached solely by the REST-fallback
`generate` built by [`make_generate_func()`](#arioso.translation.make_generate_func). Every platform that ships
a custom `adapter.py` (which is all 14, as of this writing) never went
through that translator: its `Adapter.generate(..., **kwargs)` absorbed
and silently dropped anything unsupported, regardless of the config’s
declared policy. Call this once, uniformly, before dispatching to *any*
adapter – see `arioso.generate`/`arioso.generate_many`.

This only validates; it does not translate or drop keys itself. The
caller’s kwargs are passed to the adapter unchanged either way.

* **Parameters:**
  * **kwargs** ([`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)) – The unified-name kwargs about to be passed to an adapter
    (must not include `prompt`).
  * **config** ([`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)) – The platform’s `PLATFORM_CONFIG` dict.
  * **always_raise** ([`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)) – Affordance names that raise unconditionally when
    unsupported, overriding the platform’s own policy.
* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### arioso.translation.make_generate_func(config)

Build a generate() callable from a platform config.

This is the fallback when no custom adapter.py is provided.
For REST API platforms, it builds the HTTP function from the config
and wraps it with parameter translation and output normalization.

* **Parameters:**
  **config** ([`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)) – A PLATFORM_CONFIG dict.
* **Return type:**
  [`Callable`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)
* **Returns:**
  A callable that accepts unified affordance kwargs and returns
  a Song.

### arioso.translation.make_kwargs_trans(param_map, , on_unsupported='warn')

Build a kwargs translation function from a platform’s param_map.

The returned function transforms:

```default
{common_name: value, ...}  ->  {native_name: coerced_value, ...}
```

* **Parameters:**
  * **param_map** ([`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)) – Dict mapping common affordance names to native config
    dicts.  Each value has keys: `native_name` (str),
    `coerce` (optional callable), `adapter_handled` (optional
    bool).
  * **on_unsupported** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – What to do with params not in param_map.
    One of ‘warn’, ‘raise’, or ‘ignore’.
* **Return type:**
  [`Callable`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)[[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)], [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]
* **Returns:**
  A function that translates outer kwargs to inner kwargs.
