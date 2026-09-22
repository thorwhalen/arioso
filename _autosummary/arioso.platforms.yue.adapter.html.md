# arioso.platforms.yue.adapter

YuE adapter supporting fal.ai REST API and local CLI backends.

### Classes

| [`Adapter`](#arioso.platforms.yue.adapter.Adapter)(config)   | YuE adapter with dual backend support.   |
|--------------------------------------------------------------------|------------------------------------------|

### *class* arioso.platforms.yue.adapter.Adapter(config)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

YuE adapter with dual backend support.

Prefers the fal.ai hosted API when `FAL_KEY` is set.  Falls back to
local subprocess invocation of `infer.py` otherwise.

#### generate(prompt, , lyrics='', duration=30.0, model='m-a-p/YuE-s1-7B-anneal-en-cot', batch_size=4, max_tokens=3000, repetition_penalty=1.1, audio_input='', \*\*kwargs)

Generate music from genre description and lyrics.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Genre/style description (mapped to `genre_txt`).
  * **lyrics** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Lyrics text (mapped to `lyrics_txt`).
  * **duration** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Desired length in seconds (converted to segments).
  * **model** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Stage-1 model identifier.
  * **batch_size** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Stage-2 batch size.
  * **max_tokens** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Maximum new tokens for generation.
  * **repetition_penalty** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Token repetition penalty.
  * **audio_input** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Path to a vocal track prompt file, if any.
* **Return type:**
  [`Song`](arioso.base.html.md#arioso.base.Song)
* **Returns:**
  A Song with audio_url or audio_bytes populated.
