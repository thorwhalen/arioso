# arioso.platforms.jen.adapter

Jen adapter via REST API.

### Classes

| [`Adapter`](#arioso.platforms.jen.adapter.Adapter)(config)   | Adapter for Jen music generation.   |
|--------------------------------------------------------------------|-------------------------------------|

### *class* arioso.platforms.jen.adapter.Adapter(config)

Bases: `BaseRestAdapter`

Adapter for Jen music generation.

#### generate(prompt, , duration=30, output_format='mp3', continue_from='', \*\*kwargs)

Generate music via Jen.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Text description of desired music.
  * **duration** ([`float`](https://docs.python.org/3/library/functions.html#float)) – Track duration in seconds.
  * **output_format** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Output format (‘mp3’ or ‘wav’).
  * **continue_from** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Track ID or URL to extend from.
* **Return type:**
  [`list`](https://docs.python.org/3/library/stdtypes.html#list)[[`Song`](arioso.base.html.md#arioso.base.Song)]
* **Returns:**
  List containing a single Song object.
