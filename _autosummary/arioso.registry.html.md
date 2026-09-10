# arioso.registry

Platform registry with auto-discovery and lazy loading.

### Functions

| [`discover_platforms`](#arioso.registry.discover_platforms)()                       | Scan arioso.platforms for valid platform packages.                |
|---------------------------------------------------------------------------------------------|-------------------------------------------------------------------|
| [`get_platform`](#arioso.registry.get_platform)(name)                         | Get registered platform info, lazy-loading the adapter if needed. |
| [`list_platforms`](#arioso.registry.list_platforms)()                           | Return names of all registered platforms.                         |
| [`register_platform`](#arioso.registry.register_platform)(name, config[, adapter]) | Manually register a platform (for third-party plugins).           |

### arioso.registry.discover_platforms()

Scan arioso.platforms for valid platform packages.

A valid platform package is a directory under arioso/platforms/ that:

1. Is a Python package (_\_init_\_.py exists)
2. Contains a config.py with a PLATFORM_CONFIG dict

* **Return type:**
  [`list`](https://docs.python.org/3/library/stdtypes.html#list)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)]
* **Returns:**
  List of discovered platform names.

### arioso.registry.get_platform(name)

Get registered platform info, lazy-loading the adapter if needed.

* **Parameters:**
  **name** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Platform identifier.
* **Return type:**
  [`dict`](https://docs.python.org/3/library/stdtypes.html#dict)
* **Returns:**
  Dict with ‘config’ and ‘adapter’ keys.
* **Raises:**
  [**KeyError**](https://docs.python.org/3/library/exceptions.html#KeyError) – If the platform is not found.

### arioso.registry.list_platforms()

Return names of all registered platforms.

* **Return type:**
  [`list`](https://docs.python.org/3/library/stdtypes.html#list)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)]

### arioso.registry.register_platform(name, config, adapter=None)

Manually register a platform (for third-party plugins).

* **Parameters:**
  * **name** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Platform identifier.
  * **config** ([`dict`](https://docs.python.org/3/library/stdtypes.html#dict)) – PLATFORM_CONFIG dict following the standard schema.
  * **adapter** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – Optional pre-instantiated adapter object or class.
