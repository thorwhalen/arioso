# arioso.platforms.lyria_rt.adapter

Google Lyria RealTime adapter using the google-genai SDK.

### Classes

| [`Adapter`](#arioso.platforms.lyria_rt.adapter.Adapter)(config)   | Lyria RealTime adapter using streaming music sessions.   |
|--------------------------------------------------------------------|----------------------------------------------------------|

### *class* arioso.platforms.lyria_rt.adapter.Adapter(config)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Lyria RealTime adapter using streaming music sessions.

Creates a live music session via the `google-genai` SDK, sends a
prompt, collects PCM audio chunks for a configurable duration, and
returns them as a single `Song`.

#### generate(prompt, , duration=10.0, bpm=None, key=None, energy=None, brightness=None, guidance=4.0, temperature=1.1, top_k=40, seed=None, prompt_weight=None, \*\*kwargs)

Generate music using a Lyria RealTime streaming session.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Text description of desired music.
  * **duration** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Seconds of audio to collect from the stream.
  * **bpm** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Beats per minute (60-200).
  * **key** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Musical scale (e.g. `"C_MAJOR"`).
  * **energy** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Density / energy level (0-1).
  * **brightness** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Spectral brightness (0-1).
  * **guidance** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Guidance strength (0-6).
  * **temperature** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Sampling temperature (0-3).
  * **top_k** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Top-k sampling (1-1000).
  * **seed** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Random seed for reproducibility (0-2.1B).
  * **prompt_weight** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Weight applied to the WeightedPrompt.
* **Return type:**
  [`Song`](arioso.base.html.md#arioso.base.Song)
* **Returns:**
  A Song with PCM audio bytes at 48 kHz.
