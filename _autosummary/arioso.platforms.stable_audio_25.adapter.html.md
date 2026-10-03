# arioso.platforms.stable_audio_25.adapter

Stable Audio 2.5 adapter (fal.ai): text-to-audio and audio-to-audio.

Unlike the local `stable_audio` platform (Stable Audio Open via diffusers,
which has no strength knob), the hosted 2.5 audio-to-audio endpoint takes a
`strength` in [0, 1]: low values keep the input nearly intact, high values
let the prompt take over. That makes it the arioso backend for “the same piece,
subtly changed”.

### Classes

| [`Adapter`](#arioso.platforms.stable_audio_25.adapter.Adapter)(config)   | fal.ai Stable Audio 2.5 adapter.   |
|--------------------------------------------------------------------|------------------------------------|

### *class* arioso.platforms.stable_audio_25.adapter.Adapter(config)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

fal.ai Stable Audio 2.5 adapter.

#### generate(prompt, , duration=None, num_steps=8, guidance=1.0, seed=None, audio_input=None, audio_input_strength=0.8, fetch=True, \*\*kwargs)

Generate audio from a prompt, or transform `audio_input` toward it.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Text description of the desired audio (required).
  * **duration** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Output length in seconds (1-190). Text-to-audio
    defaults to 30 s (fal’s own default is its 190 s maximum, the
    most expensive clip); audio-to-audio defaults to the input’s
    length.
  * **num_steps** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Denoising steps (`num_inference_steps`, default 8).
  * **guidance** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Prompt adherence (`guidance_scale`, default 1).
  * **seed** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Random seed for reproducibility.
  * **audio_input** – Audio to transform (path, bytes, Song, URL, …).
    When given, the audio-to-audio endpoint is used.
  * **audio_input_strength** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Denoising strength for audio-to-audio
    (0-1, default 0.8); lower keeps more of the input.
  * **fetch** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Download the result so `audio_bytes` is populated.
* **Return type:**
  [`Song`](arioso.base.html.md#arioso.base.Song)
* **Returns:**
  A completed Song (`audio_bytes` and `audio_url`).
