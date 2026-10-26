# arioso.platforms.musicgen.adapter

MusicGen adapter using audiocraft (preferred) or transformers.

The adapter holds the modes; `backends.py` holds how each library runs them.

Supports text-to-music generation and, via `facebook/musicgen-melody`,
melody-conditioned generation (the `melody` affordance / `arioso.enhance`
stage): the output follows the pitch contour of an input audio while taking its
style from the text prompt.

It also *continues* a recording (the `continue_from` affordance): the last
`prompt_seconds` of the audio are fed to the model as an audio prompt and it
generates what comes next, chained over `rounds` calls for longer extensions.
This is the local fallback for extending audio that a hosted extend route
refuses (`sunoapi.upload_extend` rejects uploads matching a catalogued
composition; thorwhalen/arioso#29).

### Module Attributes

| [`WINDOW_SECONDS`](#arioso.platforms.musicgen.adapter.WINDOW_SECONDS)         | an audio prompt plus the new audio it generates must fit in it (transformers caps generation at 1500 frames).                                         |
|-------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`SEAM_CROSSFADE_SECONDS`](#arioso.platforms.musicgen.adapter.SEAM_CROSSFADE_SECONDS) | Crossfade from the original audio into the model's re-decoded prompt at each seam, hiding the codec's reconstruction error there (a click otherwise). |

### Classes

| [`Adapter`](#arioso.platforms.musicgen.adapter.Adapter)(config)   | MusicGen adapter with lazy model loading.   |
|--------------------------------------------------------------------|---------------------------------------------|

### *class* arioso.platforms.musicgen.adapter.Adapter(config)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

MusicGen adapter with lazy model loading.

Tries `audiocraft` first; if unavailable, falls back to the
HuggingFace `transformers` pipeline.

#### generate(prompt, , duration=8.0, temperature=1.0, top_k=250, top_p=0.0, guidance=3.0, model='facebook/musicgen-small', melody=None, continue_from=None, continue_at=None, prompt_seconds=10.0, extend_seconds=None, rounds=1, \*\*kwargs)

Generate music from a text prompt, optionally following a melody or
continuing a recording.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Text description of desired music.
  * **duration** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Length in seconds.
  * **temperature** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Sampling randomness.
  * **top_k** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Top-k sampling parameter.
  * **top_p** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Top-p nucleus sampling.
  * **guidance** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Classifier-free guidance scale.
  * **model** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Model variant name (e.g. ‘facebook/musicgen-small’). When a
    `melody` is supplied and `model` isn’t already a melody
    variant, it is switched to `facebook/musicgen-melody`.
  * **melody** – Optional input audio whose pitch contour the output follows
    (a Song/AudioResult/bytes/path/(array, sample_rate)/waveform).
    This is the `arioso.enhance` path for musicgen.
  * **continue_from** – Optional audio to extend, in any of the forms
    `melody` accepts. The result is this audio followed by its
    continuation (mono, at the model’s sample rate); the
    continuation alone is in `metadata['continuation']`. Each
    seam crossfades over 10 ms into the model’s re-decoded prompt,
    so join the result, not the original plus the continuation.
  * **continue_at** ([`float`](https://docs.python.org/3/builtins/functions.html#float) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – Continue from this time (seconds) in
    `continue_from` instead of from its end; what follows it is
    dropped.
  * **prompt_seconds** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Length of the tail of the audio fed to the model as
    the prompt for each round.
  * **extend_seconds** ([`float`](https://docs.python.org/3/builtins/functions.html#float) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – New audio per round, in seconds (default
    `duration`). `prompt_seconds + extend_seconds` must fit in
    [`WINDOW_SECONDS`](#arioso.platforms.musicgen.adapter.WINDOW_SECONDS).
  * **rounds** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Number of chained continuation calls, each prompted by the
    tail of the audio so far, so the extension totals
    `rounds * extend_seconds`.
* **Return type:**
  [`Song`](arioso.base.html.md#arioso.base.Song)
* **Returns:**
  A Song with audio_array populated.

### arioso.platforms.musicgen.adapter.SEAM_CROSSFADE_SECONDS *= 0.01*

Crossfade from the original audio into the model’s re-decoded prompt at each
seam, hiding the codec’s reconstruction error there (a click otherwise).

### arioso.platforms.musicgen.adapter.WINDOW_SECONDS *= 30.0*

an audio prompt plus the new audio it
generates must fit in it (transformers caps generation at 1500 frames).

* **Type:**
  MusicGen’s context window in seconds
