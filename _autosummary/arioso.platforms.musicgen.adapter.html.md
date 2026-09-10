# arioso.platforms.musicgen.adapter

MusicGen adapter using audiocraft (preferred) or transformers.

Supports text-to-music generation and, via `facebook/musicgen-melody`,
melody-conditioned generation (the `melody` affordance / `arioso.enhance`
stage): the output follows the pitch contour of an input audio while taking its
style from the text prompt.

### Classes

| [`Adapter`](#arioso.platforms.musicgen.adapter.Adapter)(config)   | MusicGen adapter with lazy model loading.   |
|--------------------------------------------------------------------|---------------------------------------------|

### *class* arioso.platforms.musicgen.adapter.Adapter(config)

Bases: [`object`](https://docs.python.org/3/library/functions.html#object)

MusicGen adapter with lazy model loading.

Tries `audiocraft` first; if unavailable, falls back to the
HuggingFace `transformers` pipeline.

#### generate(prompt, , duration=8.0, temperature=1.0, top_k=250, top_p=0.0, guidance=3.0, model='facebook/musicgen-small', melody=None, \*\*kwargs)

Generate music from a text prompt, optionally following a melody.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Text description of desired music.
  * **duration** ([`float`](https://docs.python.org/3/library/functions.html#float)) – Length in seconds.
  * **temperature** ([`float`](https://docs.python.org/3/library/functions.html#float)) – Sampling randomness.
  * **top_k** ([`int`](https://docs.python.org/3/library/functions.html#int)) – Top-k sampling parameter.
  * **top_p** ([`float`](https://docs.python.org/3/library/functions.html#float)) – Top-p nucleus sampling.
  * **guidance** ([`float`](https://docs.python.org/3/library/functions.html#float)) – Classifier-free guidance scale.
  * **model** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Model variant name (e.g. ‘facebook/musicgen-small’). When a
    `melody` is supplied and `model` isn’t already a melody
    variant, it is switched to `facebook/musicgen-melody`.
  * **melody** – Optional input audio whose pitch contour the output follows
    (a Song/AudioResult/bytes/path/(array, sample_rate)/waveform).
    This is the `arioso.enhance` path for musicgen.
* **Return type:**
  [`Song`](arioso.base.html.md#arioso.base.Song)
* **Returns:**
  A Song with audio_array populated.
