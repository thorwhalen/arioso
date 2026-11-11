# arioso.cli

The functions behind the `arioso` command line.

Plain functions with no CLI library in sight: `arioso.__main__` projects
[`commands`](#arioso.cli.commands) onto a parser with `cw`. Each returns what the command prints.

### Module Attributes

| [`commands`](#arioso.cli.commands)   | The commands of the `arioso` command line (the SSOT its parser is built from).   |
|-------------------------------------------------------------|----------------------------------------------------------------------------------|

### Functions

| [`compare`](#arioso.cli.compare)(contenders, \*[, prompts, duration, ...])   | Render the same prompts with several platforms; time, measure and check each take.   |
|------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------|
| [`generate`](#arioso.cli.generate)(prompt, \*[, platform, duration, ...])     | Generate music from a text prompt and write it to a file.                            |
| [`platforms`](#arioso.cli.platforms)()                                         | List the platforms with their access type, weights licence and commercial use.       |
| [`schema`](#arioso.cli.schema)(platform, \*[, indent])                      | Print the JSON Schema of the parameters a platform accepts.                          |

### arioso.cli.commands *= {'compare': <function compare>, 'generate': <function generate>, 'platforms': <function platforms>, 'schema': <function schema>}*

The commands of the `arioso` command line (the SSOT its parser is built from).

### arioso.cli.compare(contenders, , prompts=None, duration=10.0, seed=0, out_dir='arioso_compare', warmup=2.0, allow_hosted=False, min_free_gb=None, timeout=None, preload=None, no_page=False)

Render the same prompts with several platforms; time, measure and check each take.

Each contender runs in its own process, one after the other, with one progress line per
take on stderr. Takes go to `<out_dir>/<run>/<contender>/`, one JSON line per take to
`<out_dir>/results.jsonl`.

* **Parameters:**
  * **contenders** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Comma-separated platforms, each optionally with options:
    `stable_audio_3,magenta_rt,ace_step:runtime=local`.
  * **prompts** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – A JSON file holding a list of prompts (`text`, and optionally `id`,
    `bpm`, `key`, `melody`, `duration`); default: three built-in prompts.
  * **duration** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Seconds asked of each take.
  * **seed** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Random seed, on platforms that take one.
  * **out_dir** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Where takes, records and the page go.
  * **warmup** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Seconds generated once per contender before the timed takes (0: none).
  * **allow_hosted** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Allow platforms that call a paid hosted service.
  * **min_free_gb** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Skip a contender when less memory than this is available.
  * **timeout** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Seconds a contender may run before it is killed (with its workers).
  * **preload** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Comma-separated modules (`module` or `module:function`) that
    register third-party platforms.
  * **no_page** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Do not write `<out_dir>/<run>/index.html` (a page of players).
* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]
* **Returns:**
  A summary table, one line per contender, then the paths written.
* **Raises:**
  [**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – When every take failed (the command exits 1).

### arioso.cli.generate(prompt, , platform='musicgen', duration=None, output='out.wav', model=None, seed=None)

Generate music from a text prompt and write it to a file.

* **Parameters:**
  * **prompt** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Text description of the music.
  * **platform** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The platform to generate with (see `arioso platforms`).
  * **duration** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – Length in seconds (default: the platform’s own).
  * **output** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Where to write the audio. A waveform is written as WAV and
    encoded audio from a hosted platform keeps its own format; either
    way the suffix follows the format.
  * **model** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The platform’s model or checkpoint, when it offers a choice.
  * **seed** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – Random seed, on platforms that take one.
* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
* **Returns:**
  The path written.

### arioso.cli.platforms()

List the platforms with their access type, weights licence and commercial use.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]
* **Returns:**
  The table’s lines, a header first.

### arioso.cli.schema(platform, , indent=2)

Print the JSON Schema of the parameters a platform accepts.

Common parameters (shared names across platforms) are marked
`"x-arioso": {"group": "common"}`; the platform’s own extras `"extra"`.
A web form, an agent tool or a validator can be generated from it.

* **Parameters:**
  * **platform** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The platform (see `arioso platforms`).
  * **indent** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – JSON indentation (0: one line).
* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
* **Returns:**
  The schema as JSON.
