# arioso.platforms.lyria2.adapter

Google Lyria 2 adapter.

Uses the `google-cloud-aiplatform` SDK when available, falling back to
raw REST calls against the Vertex AI prediction endpoint.

### Classes

| [`Adapter`](#arioso.platforms.lyria2.adapter.Adapter)(config)   | Google Lyria 2 adapter with SDK-first, REST-fallback strategy.   |
|--------------------------------------------------------------------|------------------------------------------------------------------|

### *class* arioso.platforms.lyria2.adapter.Adapter(config)

Bases: `BaseRestAdapter`

Google Lyria 2 adapter with SDK-first, REST-fallback strategy.

#### generate(prompt, , negative_prompt='', seed=None, model='lyria-002', batch_size=1, \*\*kwargs)

Generate music using Google Lyria 2.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Text description of desired music.
  * **negative_prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Elements to avoid in the generation.
  * **seed** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Random seed for reproducibility.
  * **model** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Model version identifier.
  * **batch_size** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Number of samples to generate.
* **Return type:**
  [`Song`](arioso.base.html.md#arioso.base.Song)
* **Returns:**
  A Song with WAV audio bytes (fixed 30 s duration at 48 kHz).
