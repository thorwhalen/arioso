# arioso.platforms.ace_step.adapter

ACE-Step adapter (fal.ai): text-to-music and audio-to-audio remix.

ACE-Step is steered by comma-separated style *tags*, not a sentence, so the
unified `prompt` (or `genre`) becomes `tags`. Its audio-to-audio endpoint
“remixes” an input toward new tags; it also needs `original_tags` describing
the input, which default to the new tags when not given.

### Classes

| [`Adapter`](#arioso.platforms.ace_step.adapter.Adapter)(config)   | fal.ai ACE-Step adapter.   |
|--------------------------------------------------------------------|----------------------------|

### *class* arioso.platforms.ace_step.adapter.Adapter(config)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

fal.ai ACE-Step adapter.

#### generate(prompt='', , genre='', lyrics='', instrumental=False, duration=60.0, num_steps=27, guidance=15.0, seed=None, audio_input=None, original_tags='', original_lyrics='', edit_mode='remix', fetch=True, \*\*kwargs)

Generate music from tags, or remix `audio_input` toward them.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Style tags (comma-separated works best). `genre` wins
    when both are given.
  * **genre** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Style tags; an alias of `prompt` for this platform.
  * **lyrics** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Lyrics to sing. Empty or `instrumental=True` sends
    `[inst]`, so a remix of a song with vocals comes out
    instrumental unless you pass its lyrics (or new ones).
  * **instrumental** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Force an instrumental (discards `lyrics`).
  * **duration** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Seconds (text-to-music only; a remix keeps the input’s
    length).
  * **num_steps** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – `number_of_steps` (default 27).
  * **guidance** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – `guidance_scale` (default 15).
  * **seed** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Random seed.
  * **audio_input** – Audio to remix (path, bytes, Song, URL, …). When
    given, the audio-to-audio endpoint is used.
  * **original_tags** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Tags describing `audio_input` (defaults to the
    new tags).
  * **original_lyrics** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Lyrics of `audio_input`, if any.
  * **edit_mode** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – `"remix"` (default) or `"lyrics"`.
  * **fetch** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Download the result so `audio_bytes` is populated.
  * **\*\*kwargs** – Native fal arguments in `_NATIVE_EXTRAS`
    (`scheduler`, `guidance_type`, `tag_guidance_scale`, …)
    are passed through; anything else is ignored.
* **Return type:**
  [`Song`](arioso.base.md#arioso.base.Song)
* **Returns:**
  A completed Song.
