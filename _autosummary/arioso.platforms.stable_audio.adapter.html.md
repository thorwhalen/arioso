# arioso.platforms.stable_audio.adapter

Stable Audio Open adapter using HuggingFace Diffusers.

### Classes

| [`Adapter`](#arioso.platforms.stable_audio.adapter.Adapter)(config)   | Stable Audio Open adapter with lazy model loading.   |
|--------------------------------------------------------------------|------------------------------------------------------|

### *class* arioso.platforms.stable_audio.adapter.Adapter(config)

Bases: [`object`](https://docs.python.org/3/library/functions.html#object)

Stable Audio Open adapter with lazy model loading.

Uses `diffusers.StableAudioPipeline` for local inference.

#### generate(prompt, , negative_prompt=None, duration=10.0, num_steps=200, guidance=7.0, seed=None, batch_size=1, sampler='dpmpp-3m-sde', audio_input=None, audio_input_strength=None, \*\*kwargs)

Generate audio from a text prompt, optionally conditioned on input audio.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Text description of desired audio.
  * **negative_prompt** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Text description of undesired characteristics.
  * **duration** ([`float`](https://docs.python.org/3/library/functions.html#float)) – Length in seconds.
  * **num_steps** ([`int`](https://docs.python.org/3/library/functions.html#int)) – Number of diffusion inference steps.
  * **guidance** ([`float`](https://docs.python.org/3/library/functions.html#float)) – Classifier-free guidance scale.
  * **seed** ([`int`](https://docs.python.org/3/library/functions.html#int)) – Random seed for reproducibility.
  * **batch_size** ([`int`](https://docs.python.org/3/library/functions.html#int)) – Number of waveforms to generate.
  * **sampler** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Sampler type for the diffusion process.
  * **audio_input** – 

    Optional input audio to condition on (audio-to-audio):
    ```default
    a Song/AudioResult/bytes/path/(array, sample_rate)/NumPy waveform.
    Passed to the pipeline as ``initial_audio_waveforms`` -- i.e. the
    model continues/initializes from this audio.
    ```
  * **audio_input_strength** ([`float`](https://docs.python.org/3/library/functions.html#float)) – Accepted for API symmetry but **ignored** –
    the diffusers `StableAudioPipeline` exposes no denoise/strength
    control (that is a stable-audio-tools/ComfyUI feature). A warning
    is emitted if a value is passed alongside `audio_input`.
* **Return type:**
  [`Song`](arioso.base.html.md#arioso.base.Song)
* **Returns:**
  A Song with audio_array populated.
