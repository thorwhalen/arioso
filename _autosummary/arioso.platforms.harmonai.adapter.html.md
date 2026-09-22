# arioso.platforms.harmonai.adapter

Harmonai (Dance Diffusion) adapter using diffusers.

### Classes

| [`Adapter`](#arioso.platforms.harmonai.adapter.Adapter)(config)   | Dance Diffusion adapter with lazy model loading.   |
|--------------------------------------------------------------------|----------------------------------------------------|

### *class* arioso.platforms.harmonai.adapter.Adapter(config)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Dance Diffusion adapter with lazy model loading.

Uses the `diffusers` library to run unconditional audio generation
via the Dance Diffusion pipeline.

#### generate(prompt='', , num_steps=100, seed=None, batch_size=1, \*\*kwargs)

Generate audio unconditionally.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Ignored (unconditional model). A warning is emitted
    if a non-empty prompt is provided.
  * **num_steps** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Number of diffusion inference steps.
  * **seed** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Random seed for reproducibility.
  * **batch_size** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Number of audio samples to generate.
* **Return type:**
  [`Song`](arioso.base.html.md#arioso.base.Song)
* **Returns:**
  A Song with audio_array populated.
