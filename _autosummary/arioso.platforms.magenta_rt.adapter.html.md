# arioso.platforms.magenta_rt.adapter

Magenta RealTime 2 adapter: offline renders from a worker in magenta-rt’s own environment.

The model loads once, in a `Worker` running this platform’s
`_driver` with the runtime’s Python (MLX pinned below 0.32, which arioso’s environment
need not share). Style comes from the text `prompt` or a `reference_audio` clip; there
is no tempo control beyond the words, and no seed (the sampler is not seedable).

### Classes

| [`Adapter`](#arioso.platforms.magenta_rt.adapter.Adapter)([config, make_worker])   | Local Magenta RealTime 2 (MLX) adapter.   |
|-----------------------------------------------------------------------------------|-------------------------------------------|

### *class* arioso.platforms.magenta_rt.adapter.Adapter(config=None, \*, make_worker=<class 'arioso._isolated.Worker'>)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Local Magenta RealTime 2 (MLX) adapter.

#### close()

Stop the worker (the loaded model is released).

#### generate(prompt, , duration=10.0, model='mrt2_small', temperature=1.3, top_k=40, guidance=3.0, reference_audio=None, \*\*kwargs)

Render `duration` seconds in the style of `prompt` (or of `reference_audio`).

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Style text (genre, instruments, mood; tempo only as words).
  * **duration** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Seconds of audio (25 frames a second).
  * **model** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – `"mrt2_small"` (real time on M1-class Macs) or `"mrt2_base"`.
  * **temperature** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Sampling temperature.
  * **top_k** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Top-k sampling.
  * **guidance** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – CFG scale on the style embedding.
  * **reference_audio** – A clip whose style replaces the text prompt’s.
* **Returns:**
  A complete Song (48 kHz stereo wav).
