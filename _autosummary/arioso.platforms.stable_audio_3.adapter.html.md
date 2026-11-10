# arioso.platforms.stable_audio_3.adapter

Stable Audio 3 adapter: Stability’s pure-MLX build, run as one process per take.

The MLX build is a script in the `Stability-AI/stable-audio-3` checkout with its own
virtualenv (see the config’s `runtime`), so each call runs `scripts/sa3_mlx.py` there
(the small model loads in about a second, so a persistent worker would buy little) and
reads back the wav it wrote. A seed is always passed and recorded (a fresh one when none
is given). `runner=` is the process seam.

### Module Attributes

| [`DFLT_A2A_NOISE`](#arioso.platforms.stable_audio_3.adapter.DFLT_A2A_NOISE)   | Noise level for audio-to-audio when none is given; inpainting starts from pure noise (1.0).   |
|-------------------------------------------------------------------|-----------------------------------------------------------------------------------------------|

### Classes

| [`Adapter`](#arioso.platforms.stable_audio_3.adapter.Adapter)([config, runner, is_supported])   | Local Stable Audio 3 (MLX) adapter.   |
|--------------------------------------------------------------------------------------------|---------------------------------------|

### *class* arioso.platforms.stable_audio_3.adapter.Adapter(config=None, \*, runner=<function run_process>, is_supported=<function is_apple_silicon>)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Local Stable Audio 3 (MLX) adapter.

#### generate(prompt, , duration=10.0, model='sm-music', num_steps=8, guidance=1.0, seed=None, negative_prompt=None, audio_input=None, audio_input_strength=None, inpaint_range=None, timeout=None, \*\*kwargs)

Generate `duration` seconds for `prompt`.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Text description (tempo and key only through the text, e.g. “100 BPM”).
  * **duration** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Seconds of audio (trimmed exactly).
  * **model** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – `"sm-music"` (fast), `"sm-sfx"` (sound effects) or `"medium"`.
  * **num_steps** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Sampler steps (the models are distilled for 8).
  * **guidance** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – CFG scale; 1.0 (the default) runs no unconditional branch, so a
    `negative_prompt` acts only above 1.
  * **seed** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Seed; a fresh one is drawn and recorded when None.
  * **negative_prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – What to steer away from (needs `guidance` above 1).
  * **audio_input** – Audio to vary (audio-to-audio) or, with `inpaint_range`, to inpaint.
  * **audio_input_strength** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Noise level 0-1 applied to `audio_input` (higher = freer);
    default 0.7 for a variation, 1.0 for inpainting (which starts from noise).
  * **inpaint_range** – `(start, end)` seconds of `audio_input` to regenerate.
  * **timeout** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Seconds before the process is killed.
* **Returns:**
  A complete Song (wav bytes, array when soundfile is installed, metadata).

### arioso.platforms.stable_audio_3.adapter.DFLT_A2A_NOISE *= 0.7*

Noise level for audio-to-audio when none is given; inpainting starts from pure noise (1.0).
