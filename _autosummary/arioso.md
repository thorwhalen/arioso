# arioso

Arioso - Unified facade for AI music generation platforms.

Usage:

```default
import arioso

# Generate with the default platform (musicgen)
song = arioso.generate("upbeat jazz piano", duration=10)

# Generate with a specific platform
song = arioso.generate("epic orchestral", platform="elevenlabs", duration=30)

# List available platforms
arioso.list_platforms()  # ['musicgen', 'sunoapi', 'elevenlabs', ...]

# Get platform config
arioso.get_platform_info("musicgen")

# Rich platform access via services
s = arioso.services.sunoapi
s.generate("jazz piano", duration=30)       # unified names
s.native_generate("jazz", genre="jazz")     # native names
s.upload_file("/path/to/audio.mp3")         # platform-specific

# Cross-platform slices
arioso.generators["sunoapi"]("jazz")
arioso.generators.sunoapi("jazz")
```

### Module Attributes

| [`AUDIO_INPUT_AFFORDANCES`](#arioso.AUDIO_INPUT_AFFORDANCES)   | Affordances that carry caller-supplied *input* audio (used by [`enhance()`](#arioso.enhance)).   |
|----------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|

### Functions

| [`check_status`](#arioso.check_status)(song)                                | Check the current status of a pending Song and return updated Songs.    |
|----------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------|
| [`enhance`](#arioso.enhance)(audio[, prompt, platform, strength, as_]) | Transform existing audio into AI-enhanced audio (pipeline stage 3->4).  |
| [`fetch_audio`](#arioso.fetch_audio)(song)                                 | Download the audio bytes for a Song that has an audio_url.              |
| [`generate`](#arioso.generate)(prompt, \*[, platform])                  | Generate music using the specified platform.                            |
| [`generate_many`](#arioso.generate_many)(prompt, \*[, platform])             | Generate music, returning all results (some platforms return multiple). |
| [`get_platform_info`](#arioso.get_platform_info)(name)                           | Get configuration info for a platform.                                  |
| [`list_platforms`](#arioso.list_platforms)()                                  | Return names of all available platforms.                                |
| [`supports_audio_input`](#arioso.supports_audio_input)(platform)                    | Whether *platform* can condition on caller-supplied input audio.        |

### arioso.AUDIO_INPUT_AFFORDANCES *= ('audio_input', 'melody', 'reference_audio')*

Affordances that carry caller-supplied *input* audio (used by [`enhance()`](#arioso.enhance)).
Distinct from clip-extension affordances like `continue_from` (which
reference a prior generation by id/URL rather than uploaded audio).

### arioso.check_status(song)

Check the current status of a pending Song and return updated Songs.

For platforms that use async/callback-based generation (like sunoapi),
this polls the platform’s status endpoint to get the latest state,
including audio URLs once generation is complete.

* **Parameters:**
  **song** ([`Song`](arioso.base.md#arioso.base.Song)) – A Song object (typically with status=’pending’).
* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Song`](arioso.base.md#arioso.base.Song)]
* **Returns:**
  List of updated Song objects with current status and audio URLs.

Example:

```default
songs = arioso.generate_many("reggae", platform="sunoapi", ...)
# ... wait a bit ...
updated = arioso.check_status(songs[0])
if updated[0].status == "complete":
    print(updated[0].audio_url)
```

### arioso.enhance(audio, prompt='', , platform='stable_audio', strength=None, as_='auto', \*\*kwargs)

Transform existing audio into AI-enhanced audio (pipeline stage 3->4).

Progressive-disclosure sugar over [`generate()`](#arioso.generate): routes *audio* into the
platform’s audio-conditioning affordance and generates. This is the entry
point for the “rendered MIDI audio -> AI-enhanced audio” step.

* **Parameters:**
  * **audio** – The input audio to transform – a [`Song`](arioso.base.md#arioso.base.Song),
    [`AudioResult`](arioso.base.md#arioso.base.AudioResult), `bytes`, a file path, an
    `(array, sample_rate)` pair, or a NumPy waveform (normalized by
    `arioso._audio.to_audio_ref`).
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Optional text guiding the transformation.
  * **platform** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – An audio-capable platform (default `'stable_audio'`); verify
    with [`supports_audio_input()`](#arioso.supports_audio_input).
  * **strength** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – How much the input audio influences the output (0-1), where the
    platform supports it. (Note: `stable_audio` via diffusers has no
    strength knob and will warn if one is passed.)
  * **as_** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Which affordance to route *audio* into – `'auto'` (default; picks
    `audio_input` > `melody` > `reference_audio`) or an explicit
    affordance name from [`AUDIO_INPUT_AFFORDANCES`](#arioso.AUDIO_INPUT_AFFORDANCES).
  * **\*\*kwargs** – Further unified affordance parameters (duration, seed, …).
* **Return type:**
  [`Song`](arioso.base.md#arioso.base.Song)
* **Returns:**
  A [`Song`](arioso.base.md#arioso.base.Song) with the enhanced audio.

Example:

```default
rendered = ...  # a Song from a score2audio render
better = arioso.enhance(rendered, "warm analog studio band")
```

### arioso.fetch_audio(song)

Download the audio bytes for a Song that has an audio_url.

* **Parameters:**
  **song** ([`Song`](arioso.base.md#arioso.base.Song)) – A Song with a populated audio_url (status=’complete’).
* **Return type:**
  [`Song`](arioso.base.md#arioso.base.Song)
* **Returns:**
  A new Song with audio_bytes populated.

Example:

```default
updated = arioso.check_status(song)
if updated[0].status == "complete":
    song_with_audio = arioso.fetch_audio(updated[0])
    # song_with_audio.audio_bytes is now the raw MP3 data
```

### arioso.generate(prompt, , platform='musicgen', \*\*kwargs)

Generate music using the specified platform.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Text description of desired music.
  * **platform** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Name of the generation platform (default: ‘musicgen’).
  * **\*\*kwargs** – Parameters using unified affordance names.
    See `arioso.base.AFFORDANCES` for the full list.
* **Return type:**
  [`Song`](arioso.base.md#arioso.base.Song)
* **Returns:**
  A Song object containing the generated audio and metadata.

Example:

```default
song = generate("upbeat jazz piano", platform="musicgen", duration=10)
```

### arioso.generate_many(prompt, , platform='musicgen', \*\*kwargs)

Generate music, returning all results (some platforms return multiple).

Same interface as [`generate()`](#arioso.generate) but always returns a list.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Song`](arioso.base.md#arioso.base.Song)]

### arioso.get_platform_info(name)

Get configuration info for a platform.

* **Parameters:**
  **name** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Platform identifier.
* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)
* **Returns:**
  The platform’s PLATFORM_CONFIG dict.

### arioso.list_platforms()

Return names of all available platforms.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### arioso.supports_audio_input(platform)

Whether *platform* can condition on caller-supplied input audio.

Returns True if the platform declares any of
[`AUDIO_INPUT_AFFORDANCES`](#arioso.AUDIO_INPUT_AFFORDANCES) (`audio_input` / `melody` /
`reference_audio`) in its config’s `supported_affordances`.

Example:

```default
arioso.supports_audio_input("stable_audio")  # True
arioso.supports_audio_input("mubert")        # False
```

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### Modules

| [`base`](arioso.base.md#module-arioso.base)                   | Core types and constants for arioso.                                        |
|--------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| [`named_prompts`](arioso.named_prompts.md#module-arioso.named_prompts) | Named prompts: a ledger of (name, prompt_text) pairs organized by category. |
| [`platforms`](arioso.platforms.md#module-arioso.platforms)         | Platform packages for arioso.                                               |
| [`registry`](arioso.registry.md#module-arioso.registry)           | Platform registry with auto-discovery and lazy loading.                     |
| [`services`](arioso.services.md#arioso.services)                  | Lazy mapping of platform names to `ServiceHandle` objects.                  |
| [`tools`](arioso.tools.md#module-arioso.tools)                 | High-level tools for common arioso workflows (submit, poll, download).      |
| [`translation`](arioso.translation.md#module-arioso.translation)     | Parameter translation layer.                                                |
