# arioso.platforms.udio.adapter

Udio adapter via udio-wrapper (unofficial).

### Classes

| [`Adapter`](#arioso.platforms.udio.adapter.Adapter)(config)   | Adapter for Udio using the unofficial udio-wrapper package.   |
|--------------------------------------------------------------------|---------------------------------------------------------------|

### *class* arioso.platforms.udio.adapter.Adapter(config)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Adapter for Udio using the unofficial udio-wrapper package.

Requires `pip install udio-wrapper` and a valid auth cookie
set in the UDIO_AUTH_COOKIE environment variable.

#### generate(prompt, , lyrics='', seed=-1, audio_input='', \*\*kwargs)

Generate music via Udio.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Text description of desired music.
  * **lyrics** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Custom lyrics text.
  * **seed** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Random seed (-1 for random).
  * **audio_input** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Path to conditioning audio file.
* **Return type:**
  [`Song`](arioso.base.html.md#arioso.base.Song)
* **Returns:**
  A Song with audio_url populated.
