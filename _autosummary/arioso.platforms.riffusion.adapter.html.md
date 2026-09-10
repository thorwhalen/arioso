# arioso.platforms.riffusion.adapter

Riffusion adapter using the riffusion library or diffusers fallback.

### Classes

| [`Adapter`](#arioso.platforms.riffusion.adapter.Adapter)(config)   | Riffusion adapter with dual backend support.   |
|--------------------------------------------------------------------|------------------------------------------------|

### *class* arioso.platforms.riffusion.adapter.Adapter(config)

Bases: [`object`](https://docs.python.org/3/library/functions.html#object)

Riffusion adapter with dual backend support.

Tries the `riffusion` library first for full spectrogram-to-audio
support.  Falls back to the `diffusers` StableDiffusion pipeline
which generates a spectrogram image and converts it to audio via
inverse STFT.

#### generate(prompt, , negative_prompt='', seed=None, guidance=7.0, num_steps=50, audio_input_strength=0.75, \*\*kwargs)

Generate audio from a text prompt via spectrogram synthesis.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Text description of desired music.
  * **negative_prompt** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Elements to avoid in generation.
  * **seed** ([`int`](https://docs.python.org/3/library/functions.html#int)) – Random seed for reproducibility.
  * **guidance** ([`float`](https://docs.python.org/3/library/functions.html#float)) – Classifier-free guidance scale.
  * **num_steps** ([`int`](https://docs.python.org/3/library/functions.html#int)) – Number of diffusion inference steps.
  * **audio_input_strength** ([`float`](https://docs.python.org/3/library/functions.html#float)) – Denoising strength (0-1).
* **Return type:**
  [`Song`](arioso.base.html.md#arioso.base.Song)
* **Returns:**
  A Song with audio_array populated.
