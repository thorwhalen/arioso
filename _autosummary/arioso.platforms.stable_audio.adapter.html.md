# arioso.platforms.stable_audio.adapter

Stable Audio Open adapter using HuggingFace Diffusers.

Runs on `arioso._util.torch_device()` (CUDA, else Apple MPS, else CPU), in
float16 on CUDA only. The Stability AI repositories are gated: accept the
licence on the model’s Hugging Face page and log in before the first load.

### Module Attributes

| [`SEED_BOUND`](#arioso.platforms.stable_audio.adapter.SEED_BOUND)   | Seeds are drawn below this bound when none is given, so every take records one.   |
|---------------------------------------------------------------|-----------------------------------------------------------------------------------|

### Functions

| [`load_pipeline`](#arioso.platforms.stable_audio.adapter.load_pipeline)(model)               | `diffusers.StableAudioPipeline` for *model*, on the shared torch device.   |
|-------------------------------------------------------------------------------------|----------------------------------------------------------------------------|
| [`make_torch_generator`](#arioso.platforms.stable_audio.adapter.make_torch_generator)(device, seed) | A `torch.Generator` on *device* seeded with *seed*.                        |

### Classes

| [`Adapter`](#arioso.platforms.stable_audio.adapter.Adapter)(config, \*[, load_pipeline, ...])   | Stable Audio Open adapter with lazy model loading.   |
|----------------------------------------------------------------------------------------------|------------------------------------------------------|

### *class* arioso.platforms.stable_audio.adapter.Adapter(config, \*, load_pipeline=<function load_pipeline>, make_generator=<function make_torch_generator>)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Stable Audio Open adapter with lazy model loading.

Uses `diffusers.StableAudioPipeline` for local inference. `load_pipeline`
(model id -> pipeline) and `make_generator` ((device, seed) -> generator)
are the seams that keep tests free of torch, diffusers and the gated weights.

#### generate(prompt, , negative_prompt=None, duration=10.0, num_steps=200, guidance=7.0, seed=None, batch_size=1, sampler='dpmpp-3m-sde', audio_input=None, audio_input_strength=None, model='stabilityai/stable-audio-open-1.0', \*\*kwargs)

Generate audio from a text prompt, optionally conditioned on input audio.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Text description of desired audio.
  * **negative_prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Text description of undesired characteristics.
  * **duration** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Length in seconds.
  * **num_steps** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Number of diffusion inference steps.
  * **guidance** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Classifier-free guidance scale.
  * **seed** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Random seed for reproducibility. When omitted, one is drawn
    and recorded in `metadata['seed']`, so every take can be redone.
  * **batch_size** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Number of waveforms to generate.
  * **sampler** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Sampler type for the diffusion process.
  * **audio_input** – Optional input audio to condition on (audio-to-audio):
    a Song/AudioResult/bytes/path/(array, sample_rate)/NumPy waveform.
    Passed to the pipeline as `initial_audio_waveforms` – i.e. the
    model continues/initializes from this audio.
  * **audio_input_strength** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Accepted for API symmetry but **ignored** –
    the diffusers `StableAudioPipeline` exposes no denoise/strength
    control (that is a stable-audio-tools/ComfyUI feature). A warning
    is emitted if a value is passed alongside `audio_input`.
  * **model** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Hugging Face id of a Stable Audio checkpoint that
    `StableAudioPipeline` loads.
* **Return type:**
  [`Song`](arioso.base.html.md#arioso.base.Song)
* **Returns:**
  A Song with audio_array populated.

### arioso.platforms.stable_audio.adapter.SEED_BOUND *= 2147483648*

Seeds are drawn below this bound when none is given, so every take records one.

### arioso.platforms.stable_audio.adapter.load_pipeline(model)

`diffusers.StableAudioPipeline` for *model*, on the shared torch device.

### arioso.platforms.stable_audio.adapter.make_torch_generator(device, seed)

A `torch.Generator` on *device* seeded with *seed*.
