# arioso.platforms.foundation_1.adapter

Foundation-1 adapter: stable-audio-tools in its own environment, one worker per adapter.

The model loads once, in a `Worker` running
`arioso/_workers/foundation_1_worker.py` with the Python of the `foundation-1`
environment, which `ensure_env()` builds on first use (pinned
stable-audio-tools, torch 2.7). `make_worker=` and `ensure_env=` are the seams.

Foundation-1 reads a tag prompt: instrument family and sub-family, timbre, notation and FX
tags, then `"<N> Bars, <BPM> BPM, <key>"` (see [`build_prompt()`](#arioso.platforms.foundation_1.adapter.build_prompt)). arioso’s `bpm`
and `key` become those tags; a loop’s length follows from its bars and tempo, so with a
tempo the clip is exactly `bars` bars of 4/4 (`bars=` 4 or 8, else the count nearest
to `duration`). Without one, `duration` is the clip length (a one-shot or free clip).

### Module Attributes

| [`BEATS_PER_BAR`](#arioso.platforms.foundation_1.adapter.BEATS_PER_BAR)     | Beats in a bar (the loops are 4/4).                                                                                                         |
|--------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------|
| [`WINDOW_SECONDS`](#arioso.platforms.foundation_1.adapter.WINDOW_SECONDS)    | Seconds of audio the model renders at most (its 882000-sample window at 44.1 kHz).                                                          |
| [`DFLT_SAMPLER`](#arioso.platforms.foundation_1.adapter.DFLT_SAMPLER)      | stable-audio-tools' sampler and noise schedule used for Stable Audio Open 1.0.                                                              |
| [`WORKER_ENV`](#arioso.platforms.foundation_1.adapter.WORKER_ENV)        | MPS falls back to the CPU for an operator it lacks.                                                                                         |
| [`TARGET_NOTE_TAG`](#arioso.platforms.foundation_1.adapter.TARGET_NOTE_TAG)   | The tag before a one-shot's pitch, and the keybeds checkpoint's single-note prefix (`keybed_training_strategy.md` in the model repository). |
| [`DFLT_NOTE_SECONDS`](#arioso.platforms.foundation_1.adapter.DFLT_NOTE_SECONDS) | A one-shot's length when no duration is given (the keybed notes were trained at 3 s).                                                       |

### Functions

| [`build_prompt`](#arioso.platforms.foundation_1.adapter.build_prompt)(prompt, \*[, bpm, key, bars, ...])   | The tag prompt, the clip's seconds and the timing it used, from arioso's controls.    |
|----------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------|
| [`cached_weights`](#arioso.platforms.foundation_1.adapter.cached_weights)([model, config])                   | The local path of `model`'s checkpoint in the Hugging Face cache, or None if absent.  |
| [`hf_hub_cache`](#arioso.platforms.foundation_1.adapter.hf_hub_cache)()                                    | The Hugging Face hub cache: `$HF_HUB_CACHE`, else `$HF_HOME/hub`, else the default.   |
| [`normalize_key`](#arioso.platforms.foundation_1.adapter.normalize_key)(key)                                | A key as Foundation-1's tags spell it: `"Am"` -> `"A minor"`, `"f#"` -> `"F# major"`. |
| [`normalize_note`](#arioso.platforms.foundation_1.adapter.normalize_note)(note)                              | A pitch as the tags spell it (`"c#3"` -> `"C#3"`); a ValueError if it is not one.     |
| [`parse_key`](#arioso.platforms.foundation_1.adapter.parse_key)(key)                                    | `(spelling, pitch_class, mode)` of a key, or None if `key` is not one.                |

### Classes

| [`Adapter`](#arioso.platforms.foundation_1.adapter.Adapter)([config, make_worker, ensure_env, ...])   | Local Foundation-1 adapter (stable-audio-tools, MPS / CUDA / CPU).   |
|----------------------------------------------------------------------------------------------------|----------------------------------------------------------------------|

### *class* arioso.platforms.foundation_1.adapter.Adapter(config=None, \*, make_worker=<class 'ps.isolated.Worker'>, ensure_env=<function ensure_env>, is_supported=<function \_is_supported>)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Local Foundation-1 adapter (stable-audio-tools, MPS / CUDA / CPU).

#### close()

Stop the worker (the loaded model is released).

#### generate(prompt, , duration=None, bpm=None, key=None, bars=None, note=None, model='foundation-1', num_steps=100, guidance=7.0, seed=None, negative_prompt=None, sampler='dpmpp-3m-sde', device=None, \*\*kwargs)

Render a loop or a one-shot for the tag prompt `prompt`.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Foundation-1 tags, e.g. `"Synth Lead, Warm, Arp, Medium Reverb"`
    (instrument, timbre, notation, FX; see the model card). Passed through,
    with the bar, tempo and key tags appended when given as arguments.
  * **duration** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Seconds; without a tempo, the clip length (default 10), with one,
    only the hint for the bar count.
  * **bpm** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Tempo, appended as `"<bpm> BPM"` (trained on 100-150, see the config).
  * **key** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Key, appended as e.g. `"E minor"` (`"Em"` and `"E minor"` both work).
  * **bars** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – 4 or 8, with a tempo: the loop is exactly that many 4/4 bars.
  * **note** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – A one-shot’s pitch (`"C3"`), appended as `"Target Note, C3"`; with
    `model="1.2-keybeds"` the prompt takes that checkpoint’s single-note
    form (`"Keybed, Timbre Profile, ..."`). Default length 3 s.
  * **model** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – `"foundation-1"` (loops), `"1.2-samples"` (loops and one-shots) or
    `"1.2-keybeds"` (pitch-consistent one-shots).
  * **num_steps** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Sampler steps.
  * **guidance** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – CFG scale.
  * **seed** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Seed; a fresh one is drawn and recorded when None.
  * **negative_prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – What to steer away from.
  * **sampler** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – stable-audio-tools sampler type.
  * **device** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – `"mps"`, `"cuda"` or `"cpu"`; default: the best available.
* **Returns:**
  A complete Song (44.1 kHz stereo wav), the prompt sent in its metadata.

### arioso.platforms.foundation_1.adapter.BEATS_PER_BAR *= 4*

Beats in a bar (the loops are 4/4).

### arioso.platforms.foundation_1.adapter.DFLT_NOTE_SECONDS *= 3.0*

A one-shot’s length when no duration is given (the keybed notes were trained at 3 s).

### arioso.platforms.foundation_1.adapter.DFLT_SAMPLER *= 'dpmpp-3m-sde'*

stable-audio-tools’ sampler and noise schedule used for Stable Audio Open 1.0.

### arioso.platforms.foundation_1.adapter.TARGET_NOTE_TAG *= 'Target Note'*

The tag before a one-shot’s pitch, and the keybeds checkpoint’s single-note prefix
(`keybed_training_strategy.md` in the model repository).

### arioso.platforms.foundation_1.adapter.WINDOW_SECONDS *= 20.0*

Seconds of audio the model renders at most (its 882000-sample window at 44.1 kHz).

### arioso.platforms.foundation_1.adapter.WORKER_ENV *= {'PYTORCH_ENABLE_MPS_FALLBACK': '1', 'TOKENIZERS_PARALLELISM': 'false'}*

MPS falls back to the CPU for an operator it lacks.

* **Type:**
  Variables for the worker

### arioso.platforms.foundation_1.adapter.build_prompt(prompt, , bpm=None, key=None, bars=None, duration=None, note=None, keybed=False, supported_bars=(4, 8))

The tag prompt, the clip’s seconds and the timing it used, from arioso’s controls.

Tags already in `prompt` are read and must agree with the arguments (`"140 BPM"`
with `bpm=120` is an error; keys compare by pitch class and mode, so `"Cb major"`
agrees with `"B major"`); a short key tag (`"Am"`) is spelt out. Missing tags go
in the model card’s order, `..., 8 Bars, 140 BPM, E minor`: bars before the tempo
(also when only the tempo was in the prompt), the key last.

With a tempo (`bpm` or a `BPM` tag) the clip is `bars` bars of 4/4: `bars`,
else a `Bars` tag, else the supported count nearest to `duration * bpm / 240` (4
without a duration); a `duration` more than a bar away from that warns. Without a
tempo the clip is `duration` seconds (default 10).

`note` makes a one-shot at that pitch: `"Target Note, <note>"` is appended (no
tempo or bars then; default length 3 s; a key goes before it; a `Target Note` already
in the prompt is read like the other tags), and with `keybed=True` (the keybeds
checkpoint) the prompt starts with its single-note prefix `"Keybed, Timbre Profile"`.

```pycon
>>> build_prompt("Synth Lead, Warm, Arp", bpm=140, key="Em", duration=12)
('Synth Lead, Warm, Arp, 8 Bars, 140 BPM, E minor', 13.714285714285714, {'bpm': 140, 'bars': 8, 'key': 'E minor', 'note': None})
>>> build_prompt("Grand Piano, Bright", note="c3", keybed=True)[:2]
('Keybed, Timbre Profile, Grand Piano, Bright, Target Note, C3', 3.0)
```

* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`float`](https://docs.python.org/3/builtins/functions.html#float), [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]

### arioso.platforms.foundation_1.adapter.cached_weights(model='foundation-1', , config=None)

The local path of `model`’s checkpoint in the Hugging Face cache, or None if absent.

Looks at the pinned revision only (no network, no huggingface_hub import).

### arioso.platforms.foundation_1.adapter.hf_hub_cache()

The Hugging Face hub cache: `$HF_HUB_CACHE`, else `$HF_HOME/hub`, else the default.

* **Return type:**
  [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)

### arioso.platforms.foundation_1.adapter.normalize_key(key)

A key as Foundation-1’s tags spell it: `"Am"` -> `"A minor"`, `"f#"` -> `"F# major"`.

Anything that is not a key comes back stripped, unchanged.

```pycon
>>> normalize_key("Am"), normalize_key("C# minor"), normalize_key("eb")
('A minor', 'C# minor', 'Eb major')
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### arioso.platforms.foundation_1.adapter.normalize_note(note)

A pitch as the tags spell it (`"c#3"` -> `"C#3"`); a ValueError if it is not one.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### arioso.platforms.foundation_1.adapter.parse_key(key)

`(spelling, pitch_class, mode)` of a key, or None if `key` is not one.

The spelling is the tags’ (`"A minor"`); the pitch class compares enharmonics.

```pycon
>>> parse_key("Am"), parse_key("f# major"), parse_key("Bell")
(('A minor', 9, 'minor'), ('F# major', 6, 'major'), None)
```
