# arioso.translation

Parameter translation layer.

Translates between the unified affordance names and each platform’s
native parameter names, applying type coercions along the way.

### Functions

| [`make_generate_func`](#arioso.translation.make_generate_func)(config)                         | Build a generate() callable from a platform config.              |
|-----------------------------------------------------------------------------------------------------|------------------------------------------------------------------|
| [`make_kwargs_trans`](#arioso.translation.make_kwargs_trans)(param_map, \*[, on_unsupported]) | Build a kwargs translation function from a platform's param_map. |

### arioso.translation.make_generate_func(config)

Build a generate() callable from a platform config.

This is the fallback when no custom adapter.py is provided.
For REST API platforms, it builds the HTTP function from the config
and wraps it with parameter translation and output normalization.

* **Parameters:**
  **config** ([`dict`](https://docs.python.org/3/library/stdtypes.html#dict)) – A PLATFORM_CONFIG dict.
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
  * **param_map** ([`dict`](https://docs.python.org/3/library/stdtypes.html#dict)) – Dict mapping common affordance names to native config
    dicts.  Each value has keys: `native_name` (str),
    `coerce` (optional callable), `adapter_handled` (optional
    bool).
  * **on_unsupported** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – What to do with params not in param_map.
    One of ‘warn’, ‘raise’, or ‘ignore’.
* **Return type:**
  [`Callable`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)[[[`dict`](https://docs.python.org/3/library/stdtypes.html#dict)], [`dict`](https://docs.python.org/3/library/stdtypes.html#dict)]
* **Returns:**
  A function that translates outer kwargs to inner kwargs.
