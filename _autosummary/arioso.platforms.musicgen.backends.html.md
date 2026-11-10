# arioso.platforms.musicgen.backends

The ways to run MusicGen, behind one interface (thorwhalen/arioso#31, #54).

The adapter holds the modes (text, melody, continuation: window checks, chaining, splicing); a
backend holds what one library needs to load a model and run it in each of them. `audiocraft`
is Meta’s library, `transformers` the HuggingFace port, and `mlx` Apple’s MLX port
(`ml-explore/mlx-examples`), which runs in its own environment through a worker and only
does text. Each backend wraps a model that is already loaded, so building one is free;
`load` is what loads one.

Which one runs ([`select_backend_class()`](#arioso.platforms.musicgen.backends.select_backend_class)): `$ARIOSO_MUSICGEN_BACKEND` when set; else
MLX for a text take on Apple Silicon when its runtime is installed; else audiocraft when it
imports; else transformers. On Apple Silicon, transformers runs on the CPU unless
`$ARIOSO_TORCH_DEVICE` says otherwise: on MPS it was 15-30x slower and grew Metal memory
on every decoding step (42 GB after three 10 s clips on an M1 Max).

audiocraft and transformers return the model’s own layout for text and melody,
`(channels, frames)` from audiocraft and `(frames,)` from transformers’ first channel, and
mono for a continuation; MLX returns `(frames,)`.

### Module Attributes

| [`DEFAULT_FRAME_RATE`](#arioso.platforms.musicgen.backends.DEFAULT_FRAME_RATE)   | Codec frames per second, used when a model does not report its own.                   |
|-----------------------------------------------------------------------|---------------------------------------------------------------------------------------|
| [`BACKEND_ENV_VAR`](#arioso.platforms.musicgen.backends.BACKEND_ENV_VAR)      | `audiocraft`, `transformers` or `mlx`.                                                |
| [`MLX_MAX_SECONDS`](#arioso.platforms.musicgen.backends.MLX_MAX_SECONDS)      | MusicGen's context in seconds (1500 frames); the MLX port does not stop there itself. |
| [`MLX_CHECKPOINTS`](#arioso.platforms.musicgen.backends.MLX_CHECKPOINTS)      | The checkpoints the MLX port loads.                                                   |
| [`TASKS`](#arioso.platforms.musicgen.backends.TASKS)                | plain text, follow a melody, or continue audio.                                       |
| [`BACKENDS`](#arioso.platforms.musicgen.backends.BACKENDS)             | The backends by the name `$ARIOSO_MUSICGEN_BACKEND` takes.                            |

### Functions

| [`select_backend_class`](#arioso.platforms.musicgen.backends.select_backend_class)(model_variant, \*[, task])   | The library that runs `model_variant` for `task` (see the module docstring).   |
|----------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------|

### Classes

| [`AudiocraftBackend`](#arioso.platforms.musicgen.backends.AudiocraftBackend)(model)                          | A loaded `audiocraft.models.MusicGen`.                                              |
|----------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------|
| [`Backend`](#arioso.platforms.musicgen.backends.Backend)(\*args, \*\*kwargs)                       | What the adapter needs from a library that runs a loaded MusicGen model.            |
| [`MlxBackend`](#arioso.platforms.musicgen.backends.MlxBackend)(worker, model_variant, info)           | MusicGen on MLX, in the `mlx-examples` runtime's own process (text only).           |
| [`Sampling`](#arioso.platforms.musicgen.backends.Sampling)(\*, temperature, top_k, top_p, guidance) | Sampling settings shared by every MusicGen mode.                                    |
| [`TransformersBackend`](#arioso.platforms.musicgen.backends.TransformersBackend)(model, processor)             | A loaded transformers `Musicgen(Melody)ForConditionalGeneration` and its processor. |

### *class* arioso.platforms.musicgen.backends.AudiocraftBackend(model)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A loaded `audiocraft.models.MusicGen`.

#### *classmethod* can_continue(model_variant)

Every checkpoint takes an audio prompt to extend.

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

#### continuation(prompt, tail, , seconds, sampling)

Continue `tail` (mono, at `sample_rate`) by `seconds`.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Text description of the music.
  * **tail** (`ndarray`) – The audio prompt to continue.
  * **seconds** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Length of new audio to generate after `tail`.
  * **sampling** ([`Sampling`](#arioso.platforms.musicgen.backends.Sampling)) – Sampling settings.
* **Return type:**
  `ndarray`
* **Returns:**
  The re-decoded `tail` followed by the new audio, mono.

#### *property* frame_rate *: [int](https://docs.python.org/3/builtins/functions.html#int)*

Codec frames per second (50 for every MusicGen checkpoint).

#### *classmethod* load(model_variant)

Load `model_variant` (e.g. `'facebook/musicgen-small'`) with audiocraft.

* **Parameters:**
  **model_variant** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – A MusicGen checkpoint name.
* **Return type:**
  [`AudiocraftBackend`](#arioso.platforms.musicgen.backends.AudiocraftBackend)
* **Returns:**
  The backend wrapping the loaded model.
* **Raises:**
  [**ImportError**](https://docs.python.org/3/builtins/exceptions.html#ImportError) – If audiocraft is not installed.

#### melody(prompt, ref, , seconds, sampling)

Generate from a text prompt, following the chroma of `ref`.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Text description of the music.
  * **ref** (`AudioRef`) – The audio whose melody to follow.
  * **seconds** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Length to generate.
  * **sampling** ([`Sampling`](#arioso.platforms.musicgen.backends.Sampling)) – Sampling settings.
* **Return type:**
  `ndarray`
* **Returns:**
  The audio, `(channels, frames)`.

#### *property* sample_rate *: [int](https://docs.python.org/3/builtins/functions.html#int)*

Output samples per second.

#### text(prompt, , seconds, sampling)

Generate from a text prompt.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Text description of the music.
  * **seconds** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Length to generate.
  * **sampling** ([`Sampling`](#arioso.platforms.musicgen.backends.Sampling)) – Sampling settings.
* **Return type:**
  `ndarray`
* **Returns:**
  The audio, `(channels, frames)`.

### arioso.platforms.musicgen.backends.BACKENDS *= {'audiocraft': <class 'arioso.platforms.musicgen.backends.AudiocraftBackend'>, 'mlx': <class 'arioso.platforms.musicgen.backends.MlxBackend'>, 'transformers': <class 'arioso.platforms.musicgen.backends.TransformersBackend'>}*

The backends by the name `$ARIOSO_MUSICGEN_BACKEND` takes.

### arioso.platforms.musicgen.backends.BACKEND_ENV_VAR *= 'ARIOSO_MUSICGEN_BACKEND'*

`audiocraft`, `transformers` or `mlx`.

* **Type:**
  Forces a backend

### *class* arioso.platforms.musicgen.backends.Backend(\*args, \*\*kwargs)

Bases: [`Protocol`](https://docs.python.org/3/library/typing.html#typing.Protocol)

What the adapter needs from a library that runs a loaded MusicGen model.

#### *classmethod* can_continue(model_variant)

Whether this library can continue audio with `model_variant` (cheap: loads nothing).

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

#### continuation(prompt, tail, , seconds, sampling)

The re-decoded `tail` and `seconds` after it, mono.

* **Return type:**
  `ndarray`

#### *property* frame_rate *: [int](https://docs.python.org/3/builtins/functions.html#int)*

Codec frames per second.

#### melody(prompt, ref, , seconds, sampling)

`seconds` of audio for `prompt` that follows the chroma of `ref`.

* **Return type:**
  `ndarray`

#### *property* sample_rate *: [int](https://docs.python.org/3/builtins/functions.html#int)*

Output samples per second.

#### text(prompt, , seconds, sampling)

`seconds` of audio for the text `prompt`.

* **Return type:**
  `ndarray`

### arioso.platforms.musicgen.backends.DEFAULT_FRAME_RATE *= 50*

Codec frames per second, used when a model does not report its own.

### arioso.platforms.musicgen.backends.MLX_CHECKPOINTS *= frozenset({'facebook/musicgen-large', 'facebook/musicgen-medium', 'facebook/musicgen-small'})*

The checkpoints the MLX port loads.

### arioso.platforms.musicgen.backends.MLX_MAX_SECONDS *= 30.0*

MusicGen’s context in seconds (1500 frames); the MLX port does not stop there itself.

### *class* arioso.platforms.musicgen.backends.MlxBackend(worker, model_variant, info)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

MusicGen on MLX, in the `mlx-examples` runtime’s own process (text only).

The model lives in a `Worker` running
`arioso/_workers/musicgen_mlx_worker.py`; audio comes back through a `.npy` file.
`top_p` has no MLX counterpart (a non-zero one is warned about and ignored).

#### *classmethod* available(model_variant)

Apple Silicon, a supported checkpoint, and the runtime installed (cheap).

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

#### *classmethod* can_continue(model_variant)

No: the MLX port generates from text only.

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

#### close()

Stop the worker (the model is released).

#### continuation(prompt, tail, , seconds, sampling)

Not on MLX: the selection sends continuations to another backend.

#### *property* frame_rate *: [int](https://docs.python.org/3/builtins/functions.html#int)*

Codec frames per second.

#### *classmethod* load(model_variant, , make_worker=None)

Start the worker and load `model_variant` in it.

* **Raises:**
  * [**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – For a checkpoint the MLX port does not run.
  * **arioso._isolated.RuntimeNotInstalled** – With the commands that install it.
* **Return type:**
  [`MlxBackend`](#arioso.platforms.musicgen.backends.MlxBackend)

#### melody(prompt, ref, , seconds, sampling)

Not on MLX: the selection sends melody takes to another backend.

#### *static* runtime()

The `mlx-examples` runtime (see the musicgen config’s `mlx_runtime`).

#### *property* sample_rate *: [int](https://docs.python.org/3/builtins/functions.html#int)*

Output samples per second.

#### *classmethod* supports(model_variant)

Whether the MLX port runs `model_variant`: Meta’s mono text checkpoints only
(the port reads their audiocraft `state_dict.bin`; fine-tunes in transformers
format have none).

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

#### text(prompt, , seconds, sampling)

`seconds` of mono audio for `prompt`, `(frames,)`.

* **Return type:**
  `ndarray`

### *class* arioso.platforms.musicgen.backends.Sampling(, temperature, top_k, top_p, guidance)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Sampling settings shared by every MusicGen mode.

### arioso.platforms.musicgen.backends.TASKS *= ('text', 'melody', 'continuation')*

plain text, follow a melody, or continue audio.

* **Type:**
  What a backend is asked to do

### *class* arioso.platforms.musicgen.backends.TransformersBackend(model, processor)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A loaded transformers `Musicgen(Melody)ForConditionalGeneration` and its processor.

#### *property* audio_channels *: [int](https://docs.python.org/3/builtins/functions.html#int)*

Channels the decoder generates (2 for the stereo checkpoints); 1 when its
config does not say, or it has none.

#### *classmethod* can_continue(model_variant)

Not a melody checkpoint: its audio input is melody chroma, not a prompt to extend.

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

#### continuation(prompt, tail, , seconds, sampling)

Continue `tail` (mono, at `sample_rate`) by `seconds`.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Text description of the music.
  * **tail** (`ndarray`) – The audio prompt to continue (duplicated for a stereo model).
  * **seconds** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Length of new audio to generate after `tail`.
  * **sampling** ([`Sampling`](#arioso.platforms.musicgen.backends.Sampling)) – Sampling settings.
* **Return type:**
  `ndarray`
* **Returns:**
  The re-decoded `tail` followed by the new audio, mono.

#### *property* delay_frames *: [int](https://docs.python.org/3/builtins/functions.html#int)*

Frames the codebook delay pattern consumes from `max_new_tokens` (3 for the
4-codebook checkpoints), so a call yields the seconds asked for.

#### *property* frame_rate *: [int](https://docs.python.org/3/builtins/functions.html#int)*

Codec frames per second (50 for every MusicGen checkpoint).

#### *classmethod* load(model_variant)

Load `model_variant` and its processor with transformers, on `_transformers_device()`.

* **Parameters:**
  **model_variant** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – A MusicGen checkpoint name; a melody variant gets the
  melody-specific model class.
* **Return type:**
  [`TransformersBackend`](#arioso.platforms.musicgen.backends.TransformersBackend)
* **Returns:**
  The backend wrapping the loaded model and processor.

#### melody(prompt, ref, , seconds, sampling)

Generate from a text prompt, following the chroma of `ref`.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Text description of the music.
  * **ref** (`AudioRef`) – The audio whose melody to follow, resampled to the processor’s rate.
  * **seconds** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Length to generate.
  * **sampling** ([`Sampling`](#arioso.platforms.musicgen.backends.Sampling)) – Sampling settings.
* **Return type:**
  `ndarray`
* **Returns:**
  The first channel of the audio, `(frames,)`.

#### *property* sample_rate *: [int](https://docs.python.org/3/builtins/functions.html#int)*

Output samples per second.

#### text(prompt, , seconds, sampling)

Generate from a text prompt.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Text description of the music.
  * **seconds** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Length to generate.
  * **sampling** ([`Sampling`](#arioso.platforms.musicgen.backends.Sampling)) – Sampling settings.
* **Return type:**
  `ndarray`
* **Returns:**
  The first channel of the audio, `(frames,)`.

### arioso.platforms.musicgen.backends.select_backend_class(model_variant, , task='text')

The library that runs `model_variant` for `task` (see the module docstring).

Loads no checkpoint, so it can be asked before a multi-GB one is read; a present but
broken audiocraft install falls back like a missing one.

* **Return type:**
  [`type`](https://docs.python.org/3/builtins/functions.html#type)[[`Backend`](#arioso.platforms.musicgen.backends.Backend)]
