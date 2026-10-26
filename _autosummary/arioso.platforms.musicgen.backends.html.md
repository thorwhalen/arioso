# arioso.platforms.musicgen.backends

The two ways to run MusicGen, behind one interface (thorwhalen/arioso#31).

The adapter holds the modes (text, melody, continuation: window checks, chaining, splicing); a
backend holds what one library needs to load a model and run it in each of them. `audiocraft`
is Meta’s library, `transformers` the HuggingFace port the adapter falls back to. Each backend
wraps a model that is already loaded, so building one is free; `load` is what loads one.

Both return the model’s own output layout for text and melody, `(channels, frames)` from
audiocraft and `(frames,)` from transformers’ first channel, and mono for a continuation.

### Module Attributes

| [`DEFAULT_FRAME_RATE`](#arioso.platforms.musicgen.backends.DEFAULT_FRAME_RATE)   | Codec frames per second, used when a model does not report its own.   |
|-----------------------------------------------------------------------|-----------------------------------------------------------------------|

### Classes

| [`AudiocraftBackend`](#arioso.platforms.musicgen.backends.AudiocraftBackend)(model)                          | A loaded `audiocraft.models.MusicGen`.                                              |
|----------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------|
| [`Backend`](#arioso.platforms.musicgen.backends.Backend)(\*args, \*\*kwargs)                       | What the adapter needs from a library that runs a loaded MusicGen model.            |
| [`Sampling`](#arioso.platforms.musicgen.backends.Sampling)(\*, temperature, top_k, top_p, guidance) | Sampling settings shared by every MusicGen mode.                                    |
| [`TransformersBackend`](#arioso.platforms.musicgen.backends.TransformersBackend)(model, processor)             | A loaded transformers `Musicgen(Melody)ForConditionalGeneration` and its processor. |

### *class* arioso.platforms.musicgen.backends.AudiocraftBackend(model)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A loaded `audiocraft.models.MusicGen`.

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

### *class* arioso.platforms.musicgen.backends.Backend(\*args, \*\*kwargs)

Bases: [`Protocol`](https://docs.python.org/3/library/typing.html#typing.Protocol)

What the adapter needs from a library that runs a loaded MusicGen model.

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

### *class* arioso.platforms.musicgen.backends.Sampling(, temperature, top_k, top_p, guidance)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Sampling settings shared by every MusicGen mode.

### *class* arioso.platforms.musicgen.backends.TransformersBackend(model, processor)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A loaded transformers `Musicgen(Melody)ForConditionalGeneration` and its processor.

#### *property* audio_channels *: [int](https://docs.python.org/3/builtins/functions.html#int)*

Channels the decoder generates (2 for the stereo checkpoints); 1 when its
config does not say, or it has none.

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

Load `model_variant` and its processor with transformers, on `_device()`.

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
