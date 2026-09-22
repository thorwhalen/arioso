# arioso.platforms.mubert.adapter

Mubert adapter via REST API.

### Classes

| [`Adapter`](#arioso.platforms.mubert.adapter.Adapter)(config)   | Adapter for Mubert music generation.   |
|--------------------------------------------------------------------|----------------------------------------|

### *class* arioso.platforms.mubert.adapter.Adapter(config)

Bases: `BaseRestAdapter`

Adapter for Mubert music generation.

Mubert uses a two-step flow: POST to /RecordTrackTTM to start a task,
then poll until the download_link becomes available.

#### generate(prompt, , duration=30, output_format='mp3', bitrate=320, energy=None, wait_for_completion=True, poll_interval=5.0, timeout=300.0, \*\*kwargs)

Generate music via Mubert.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Text description of desired music.
  * **duration** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Track duration in seconds (15-1500).
  * **output_format** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Output format (‘mp3’ or ‘wav’).
  * **bitrate** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Audio bitrate (128 or 320).
  * **energy** ([`float`](https://docs.python.org/3/builtins/functions.html#float) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – Energy level 0-1 (coerced to low/medium/high).
  * **wait_for_completion** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – If True, poll until audio is ready.
  * **poll_interval** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Seconds between status checks.
  * **timeout** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Max seconds to wait for completion.
* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Song`](arioso.base.html.md#arioso.base.Song)]
* **Returns:**
  List containing a single Song object.
