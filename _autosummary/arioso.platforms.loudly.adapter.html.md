# arioso.platforms.loudly.adapter

Loudly adapter via REST API.

### Classes

| [`Adapter`](#arioso.platforms.loudly.adapter.Adapter)(config)   | Adapter for Loudly music generation.   |
|--------------------------------------------------------------------|----------------------------------------|

### *class* arioso.platforms.loudly.adapter.Adapter(config)

Bases: `BaseRestAdapter`

Adapter for Loudly music generation.

Loudly may return the audio URL directly or require polling,
depending on the generation complexity.

#### generate(prompt, , duration=30, genre='', bpm=None, key='', energy=None, instruments=None, structure=None, wait_for_completion=True, poll_interval=5.0, timeout=300.0, \*\*kwargs)

Generate music via Loudly.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Text description of desired music.
  * **duration** ([`float`](https://docs.python.org/3/library/functions.html#float)) – Track duration in seconds.
  * **genre** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Genre tag (50+ options available).
  * **bpm** ([`int`](https://docs.python.org/3/library/functions.html#int) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Tempo in beats per minute.
  * **key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Musical key (e.g. ‘C major’).
  * **energy** ([`float`](https://docs.python.org/3/library/functions.html#float) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Energy level (0-1).
  * **instruments** ([`list`](https://docs.python.org/3/library/stdtypes.html#list)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – List of instruments (up to 7).
  * **structure** ([`list`](https://docs.python.org/3/library/stdtypes.html#list) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Song section structure.
  * **wait_for_completion** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – If True, poll until audio is ready.
  * **poll_interval** ([`float`](https://docs.python.org/3/library/functions.html#float)) – Seconds between status checks.
  * **timeout** ([`float`](https://docs.python.org/3/library/functions.html#float)) – Max seconds to wait for completion.
* **Return type:**
  [`list`](https://docs.python.org/3/library/stdtypes.html#list)[[`Song`](arioso.base.html.md#arioso.base.Song)]
* **Returns:**
  List containing a single Song object.
