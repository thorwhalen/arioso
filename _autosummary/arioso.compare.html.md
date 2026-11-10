# arioso.compare

Compare platforms on the same prompts: time, memory and objective checks, as records.

Choosing a local model is a measurement. [`compare()`](#arioso.compare.compare) renders every prompt with every
contender and yields one flat record per take: wall time (model load plus warm-up, then per
take), real-time factor, peak memory, and objective checks of the audio (detected tempo
against the BPM asked for, estimated key against the key asked for, clipping, level):

```default
import arioso.compare as ac

records = list(ac.compare(["stable_audio_3", "magenta_rt", "ace_step:runtime=local"]))
ac.compare_page(records, "arioso_compare/index.html")
```

or, from the shell:

```default
arioso compare stable_audio_3,magenta_rt,ace_step:runtime=local --prompts prompts.json
```

The records are the single source of truth: they are appended to `<out_dir>/results.jsonl`
as they come, the command prints a summary of them, and [`compare_page()`](#arioso.compare.compare_page) renders them as a
page of players. Each contender runs in a fresh child process (see [`in_child_process()`](#arioso.compare.in_child_process)),
one after the other, so only one model is in memory at a time and each one’s peak memory is
its own.

A **contender** is a platform plus the options it is called with, written
`platform[:key=value[:key=value...]]` (values are read as JSON when they parse, so
`num_steps=8` is an int): `ace_step:runtime=local`, `musicgen:model=facebook/musicgen-small`.

A **prompt** is a dict: `text` (required), `id`, and optionally `bpm`, `key` (`"C
major"`), `melody` (an audio file, passed to platforms that take a melody) and
`duration`. [`DFLT_PROMPTS`](#arioso.compare.DFLT_PROMPTS) is a small set covering a groove, an accompaniment and a
loop.

Hosted platforms cost money per call, so [`compare()`](#arioso.compare.compare) refuses them unless
`allow_hosted=True` ([`is_hosted()`](#arioso.compare.is_hosted) says which those are).

Seams, all keyword arguments: `runner` (how one contender is run and measured:
[`in_child_process()`](#arioso.compare.in_child_process) or [`in_this_process()`](#arioso.compare.in_this_process)), `scorer` (audio to a dict of checks:
[`objective_checks()`](#arioso.compare.objective_checks)), and `min_free_gb` (refuse to start a contender when the machine
has less memory available than that).

### Module Attributes

| [`DFLT_PROMPTS`](#arioso.compare.DFLT_PROMPTS)       | a groove at a tempo, an accompaniment in a key, a loop.                                 |
|---------------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| [`DFLT_WARMUP`](#arioso.compare.DFLT_WARMUP)        | Seconds of audio generated once before the timed takes, so load is not counted in them. |
| [`LOCAL_ACCESS_TYPES`](#arioso.compare.LOCAL_ACCESS_TYPES) | The `access_type` values of platforms that run on this machine.                         |

### Functions

| [`compare`](#arioso.compare.compare)(contenders[, prompts, duration, ...])   | Render every prompt with every contender; yield one record per take.                                                  |
|--------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------|
| [`compare_page`](#arioso.compare.compare_page)(records[, path, title, prompts])   | Write a self-contained HTML page: a summary table, then each prompt's takes as players.                               |
| [`in_child_process`](#arioso.compare.in_child_process)(contender, prompts, \*, ...)   | Run `contender` in a fresh `python -m arioso.compare` process (the default runner).                                   |
| [`in_this_process`](#arioso.compare.in_this_process)(contender, prompts, \*, ...)    | Run `contender` on `prompts` here; one record per prompt, audio under `out_dir`.                                      |
| [`is_hosted`](#arioso.compare.is_hosted)(contender)                            | Whether a contender may call a hosted (paid, per call) service rather than a local model.                             |
| [`key_agreement`](#arioso.compare.key_agreement)(detected, asked)                  | `"exact"`, `"relative"` (C major vs A minor), `"other"`, or `None` if unparsable.                                     |
| [`load_prompts`](#arioso.compare.load_prompts)([source])                          | Prompts from a JSON file (a list of dicts), a list, or [`DFLT_PROMPTS`](#arioso.compare.DFLT_PROMPTS). |
| [`objective_checks`](#arioso.compare.objective_checks)(y, sr, prompt)                 | Checks a listener would otherwise make by ear: level, clipping, tempo, key.                                           |
| [`parse_contenders`](#arioso.compare.parse_contenders)(specs)                         | Contenders from a comma-separated string or an iterable of specs.                                                     |
| [`read_records`](#arioso.compare.read_records)([out_dir])                         | The records in `<out_dir>/results.jsonl`, keeping the latest per (contender, prompt).                                 |
| [`summarize`](#arioso.compare.summarize)(records)                              | One row per contender: takes, failures, median RTF, load, peak memory, check rates.                                   |
| [`summary_lines`](#arioso.compare.summary_lines)(records)                          | [`summarize()`](#arioso.compare.summarize) as aligned text lines, a header first.                   |
| [`tempo_error`](#arioso.compare.tempo_error)(detected, asked)                    | Relative tempo error, forgiving the half/double-time slips beat trackers make.                                        |

### Classes

| [`Contender`](#arioso.compare.Contender)(platform[, options, label])   | A platform and the options it is called with; `label` names it in records.   |
|------------------------------------------------------------------------------------------|------------------------------------------------------------------------------|

### *class* arioso.compare.Contender(platform, options=dict(), label='')

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A platform and the options it is called with; `label` names it in records.

#### *classmethod* parse(spec)

`"ace_step:runtime=local:num_steps=8"` -> `Contender("ace_step", {...})`.

```pycon
>>> Contender.parse("ace_step:runtime=local:num_steps=8").options
{'runtime': 'local', 'num_steps': 8}
```

* **Return type:**
  [`Contender`](#arioso.compare.Contender)

### arioso.compare.DFLT_PROMPTS *= ({'bpm': 100, 'id': 'groove100', 'text': 'funky drum and bass groove at 100 BPM, tight hi-hats, punchy kick, warm electric bass, steady pocket, instrumental'}, {'bpm': 100, 'id': 'accomp', 'key': 'C major', 'text': 'gentle acoustic guitar and soft piano accompaniment, 100 BPM, C major, warm and simple, instrumental'}, {'bpm': 85, 'id': 'loop85', 'text': '4-bar lo-fi hip hop loop, 85 BPM, mellow Rhodes chords, dusty drums, vinyl crackle, seamless loop, instrumental'})*

a groove at a tempo, an accompaniment in a key, a loop.

* **Type:**
  Prompts covering three common asks

### arioso.compare.DFLT_WARMUP *= 2.0*

Seconds of audio generated once before the timed takes, so load is not counted in them.

### arioso.compare.LOCAL_ACCESS_TYPES *= frozenset({'local_runtime', 'python_lib'})*

The `access_type` values of platforms that run on this machine.

### arioso.compare.compare(contenders, prompts=None, \*, duration=10.0, seed=0, out_dir='arioso_compare', warmup=2.0, runner=None, scorer=<function objective_checks>, allow_hosted=False, min_free_gb=None, preload=(), timeout=None, run_id=None)

Render every prompt with every contender; yield one record per take.

* **Parameters:**
  * **contenders** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`Iterable`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterable)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`Contender`](#arioso.compare.Contender)]) – Platform specs (`"ace_step:runtime=local"`, see [`Contender`](#arioso.compare.Contender)),
    comma-separated or as an iterable.
  * **prompts** – A JSON file, a list of prompt dicts, or `None` for [`DFLT_PROMPTS`](#arioso.compare.DFLT_PROMPTS).
  * **duration** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Seconds asked of each take (a prompt’s own `duration` wins).
  * **seed** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`int`](https://docs.python.org/3/builtins/functions.html#int)]) – Passed to platforms that take one (`None`: don’t).
  * **out_dir** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`PathLike`](https://docs.python.org/3/library/os.html#os.PathLike)) – Takes go to `<out_dir>/<run_id>/<contender>/<prompt id>.wav`; records
    are appended to `<out_dir>/results.jsonl` (one file for every run).
  * **warmup** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`float`](https://docs.python.org/3/builtins/functions.html#float)]) – Seconds generated once per contender before the timed takes (`0`/`None`:
    no warm-up, so the first take’s time includes loading the model).
  * **runner** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Callable`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)[[`...`](https://docs.python.org/3/builtins/constants.html#Ellipsis), [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]]]) – Runs one contender: [`in_child_process()`](#arioso.compare.in_child_process) (`None`, the default) or
    [`in_this_process()`](#arioso.compare.in_this_process), or any callable with their signature.
  * **scorer** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Callable`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)[[[`Any`](https://docs.python.org/3/library/typing.html#typing.Any), [`int`](https://docs.python.org/3/builtins/functions.html#int), [`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)], [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]]) – `(audio, sample_rate, prompt) -> dict` merged into each record; `None`
    for no checks.
  * **allow_hosted** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Allow contenders that call paid hosted services ([`is_hosted()`](#arioso.compare.is_hosted)).
  * **min_free_gb** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`float`](https://docs.python.org/3/builtins/functions.html#float)]) – When the machine has less memory available than this before a
    contender starts, record that contender as an error instead of running it.
  * **preload** ([`Iterable`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterable)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]) – Modules (`"module"` or `"module:function"`) that make third-party
    platforms known, run here before anything is checked and passed to a runner
    that takes `preload` (the child process runs them too).
  * **timeout** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`float`](https://docs.python.org/3/builtins/functions.html#float)]) – Seconds a contender may run before it is killed with every process it
    started, passed to a runner that takes `timeout` (the default one does).
  * **run_id** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]) – Names this run in its records and its folder (default: the start time).
* **Yields:**
  *Flat dicts* – `contender`, `platform`, `options`, `prompt`, timings
  (`load_s`, `gen_s`, `rtf`), memory (`peak_memory_gb`,
  `workers_peak_memory_gb`, `available_memory_gb`), `path`, the scorer’s
  checks, `error` when a take failed, and the machine.
* **Return type:**
  [*Iterator*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterator)[[*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)]

### arioso.compare.compare_page(records, path=PosixPath('arioso_compare/index.html'), , title='Music generation compared', prompts=None)

Write a self-contained HTML page: a summary table, then each prompt’s takes as players.

Audio is linked relative to the page, so keep the page beside the takes (the default
`<out_dir>/index.html`) and publish the folder.

* **Return type:**
  [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)

### arioso.compare.in_child_process(contender, prompts, , duration, seed, out_dir, warmup, python=None, preload=(), timeout=None)

Run `contender` in a fresh `python -m arioso.compare` process (the default runner).

A fresh process per contender frees the previous model’s memory before the next loads,
and makes the process’s lifetime peak memory that contender’s own. `python` is the
interpreter (default: this one); `preload` names what the child runs first, to make
third-party platforms known: `"module"` is imported, `"module:function"` is imported
and `function()` called. The child’s output goes to `<out_dir>/<contender>/child.log`.
The child writes each take’s record as soon as it is made, so a child killed after
`timeout` seconds (with every process it started) or exiting non-zero still returns
the takes it finished, each marked with `child_exit`; prompts it never reached get an
`error`. Processes the child started are killed when it ends, however it ends; on
Windows only when it is killed (thorwhalen/ps#25).

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]

### arioso.compare.in_this_process(contender, prompts, , duration, seed, out_dir, warmup, on_record=None)

Run `contender` on `prompts` here; one record per prompt, audio under `out_dir`.

A take that fails becomes a record with an `error` (the others still run); a contender
that fails its warm-up makes every record an error. `peak_memory_gb` is this process’s
lifetime peak, so run each contender in a fresh process ([`in_child_process()`](#arioso.compare.in_child_process)) to
attribute it; `workers_peak_memory_gb` is the peak of the processes it started (a local
runtime’s worker, or one process per take), sampled while it ran (see
`PeakSampler`; here its exit-time floor also covers children of
earlier contenders run in this process). `on_record` is called with each take’s record
as soon as it is made, before the memory figures are added at the end.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]

### arioso.compare.is_hosted(contender)

Whether a contender may call a hosted (paid, per call) service rather than a local model.

Errs on the side of caution. Local means: `access_type` is `python_lib` or
`local_runtime` (a missing one is the translation layer’s `rest_api`), the terms are
not the provider’s, no credential is taken (even an optional one: `yue` calls fal.ai
whenever `FAL_KEY` is set), and no fal model is declared. Anything else is hosted,
unless the contender asks for `runtime="local"` *and* the platform declares a local
runtime (`ace_step`); on any other platform that option is ignored, so it changes
nothing here either.

```pycon
>>> is_hosted("elevenlabs"), is_hosted("stable_audio_3"), is_hosted("ace_step:runtime=local")
(True, False, False)
>>> is_hosted("elevenlabs:runtime=local")
True
```

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### arioso.compare.key_agreement(detected, asked)

`"exact"`, `"relative"` (C major vs A minor), `"other"`, or `None` if unparsable.

```pycon
>>> key_agreement("A minor", "C major"), key_agreement("c major", "C Major")
('relative', 'exact')
```

* **Return type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### arioso.compare.load_prompts(source=None)

Prompts from a JSON file (a list of dicts), a list, or [`DFLT_PROMPTS`](#arioso.compare.DFLT_PROMPTS).

A `melody` path in a file is read relative to that file. Prompts without an `id`
get `p0`, `p1`…

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]

### arioso.compare.objective_checks(y, sr, prompt)

Checks a listener would otherwise make by ear: level, clipping, tempo, key.

Level and clipping need numpy only. Tempo comes from `denote.get_beats` and key from
`denote.get_key` when `denote` provides them; a check that cannot run goes into
`checks_skipped` (check name to reason) instead of failing the take.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### arioso.compare.parse_contenders(specs)

Contenders from a comma-separated string or an iterable of specs.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Contender`](#arioso.compare.Contender)]

### arioso.compare.read_records(out_dir='arioso_compare')

The records in `<out_dir>/results.jsonl`, keeping the latest per (contender, prompt).

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]

### arioso.compare.summarize(records)

One row per contender: takes, failures, median RTF, load, peak memory, check rates.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)]

### arioso.compare.summary_lines(records)

[`summarize()`](#arioso.compare.summarize) as aligned text lines, a header first.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### arioso.compare.tempo_error(detected, asked)

Relative tempo error, forgiving the half/double-time slips beat trackers make.

```pycon
>>> tempo_error(50, 100), tempo_error(110, 100)
(0.0, 0.1)
```

* **Return type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`float`](https://docs.python.org/3/builtins/functions.html#float)]
