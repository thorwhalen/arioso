# arioso.platforms.elevenlabs.adapter

ElevenLabs Music adapter.

Uses `ho.route_to_func` to auto-generate the raw callable from the
ElevenLabs OpenAPI spec, then handles parameter translation for
complex fields like `composition_plan`.

### Module Attributes

| [`SECTION_MS`](#arioso.platforms.elevenlabs.adapter.SECTION_MS)   | ElevenLabs' limits on a composition plan (POST /v1/music, docs 2026-11).   |
|---------------------------------------------------------------|----------------------------------------------------------------------------|

### Classes

| [`Adapter`](#arioso.platforms.elevenlabs.adapter.Adapter)(config)   | ElevenLabs Music adapter with OpenAPI-based function generation.   |
|--------------------------------------------------------------------|--------------------------------------------------------------------|

### *class* arioso.platforms.elevenlabs.adapter.Adapter(config)

Bases: `BaseRestAdapter`

ElevenLabs Music adapter with OpenAPI-based function generation.

#### generate(prompt, , duration=30.0, instrumental=False, model='music_v1', output_format='mp3_44100_128', lyrics='', title='', structure=None, watermark=False, seed=None, \*\*kwargs)

Generate music using the ElevenLabs Music API.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Text description of desired music.
  * **duration** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Length in seconds (3-600).
  * **instrumental** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – If True, generate without vocals.
  * **model** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Model ID.
  * **output_format** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Output format string (e.g. ‘mp3_44100_128’).
  * **lyrics** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Lyrics to sing. `[Section]` lines (or blank lines) split them into
    sections; they turn the request into a composition plan.
  * **title** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Song title. Kept on the returned Song only: the API has no title.
  * **structure** ([`list`](https://docs.python.org/3/builtins/stdtypes.html#list)) – Your own composition-plan sections (`music_v1`) or chunks
    (`music_v2*`), sent as given.
  * **watermark** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Apply C2PA content watermark.
  * **seed** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Random seed; only with a composition plan (the API refuses it with
    a plain prompt, so it is dropped there, with a warning).
* **Return type:**
  [`Song`](arioso.base.html.md#arioso.base.Song)
* **Returns:**
  A Song with audio_bytes populated.

### arioso.platforms.elevenlabs.adapter.SECTION_MS *= (3000, 120000)*

ElevenLabs’ limits on a composition plan (POST /v1/music, docs 2026-11).
