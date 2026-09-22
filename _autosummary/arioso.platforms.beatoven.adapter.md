# arioso.platforms.beatoven.adapter

Beatoven.ai adapter via REST API.

### Classes

| [`Adapter`](#arioso.platforms.beatoven.adapter.Adapter)(config)   | Adapter for Beatoven.ai music generation.   |
|--------------------------------------------------------------------|---------------------------------------------|

### *class* arioso.platforms.beatoven.adapter.Adapter(config)

Bases: `BaseRestAdapter`

Adapter for Beatoven.ai music generation.

Beatoven uses a three-step flow:

1. POST /tracks to create a track and get a track_id.
2. Poll GET /tracks/{track_id} until status is ‘composed’.
3. GET /tracks/{track_id}/audio to retrieve the download URL.

#### generate(prompt, , duration=30, negative_prompt='', seed=None, guidance=16, num_steps=100, looping=False, wait_for_completion=True, poll_interval=5.0, timeout=300.0, \*\*kwargs)

Generate music via Beatoven.ai.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Text description of desired music.
  * **duration** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Track duration in seconds (5-150).
  * **negative_prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Elements to avoid in generation.
  * **seed** ([`int`](https://docs.python.org/3/builtins/functions.html#int) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – Random seed for reproducibility.
  * **guidance** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Creativity/guidance scale (default 16).
  * **num_steps** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Refinement steps (default 100).
  * **looping** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Whether to generate loopable audio.
  * **wait_for_completion** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – If True, poll until audio is ready.
  * **poll_interval** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Seconds between status checks.
  * **timeout** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Max seconds to wait for completion.
* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Song`](arioso.base.md#arioso.base.Song)]
* **Returns:**
  List containing a single Song object.

#### get_audio_url(track_id)

Retrieve the audio download URL for a completed track.

* **Parameters:**
  **track_id** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The track ID of a composed track.
* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
* **Returns:**
  The audio download URL.

#### get_status(track_id)

Check the generation status of a track.

* **Parameters:**
  **track_id** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The track ID returned from generate().
* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
* **Returns:**
  Status string from the API (e.g. ‘composing’, ‘composed’).
