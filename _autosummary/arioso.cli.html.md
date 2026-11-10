# arioso.cli

The functions behind the `arioso` command line.

Plain functions with no CLI library in sight: `arioso.__main__` projects
[`commands`](#arioso.cli.commands) onto a parser with `cw`. Each returns what the command prints.

### Module Attributes

| [`commands`](#arioso.cli.commands)   | The commands of the `arioso` command line (the SSOT its parser is built from).   |
|-------------------------------------------------------------|----------------------------------------------------------------------------------|

### Functions

| [`generate`](#arioso.cli.generate)(prompt, \*[, platform, duration, ...])   | Generate music from a text prompt and write it to a file.                      |
|----------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------|
| [`platforms`](#arioso.cli.platforms)()                                       | List the platforms with their access type, weights licence and commercial use. |

### arioso.cli.commands *= {'generate': <function generate>, 'platforms': <function platforms>}*

The commands of the `arioso` command line (the SSOT its parser is built from).

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
