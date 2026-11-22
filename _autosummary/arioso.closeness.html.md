# arioso.closeness

Is a take a cover of its source? Lyric recall when there are words, melody rank otherwise.

Measured on the 2026-11-10 folder job (arioso#69, #81): six Suno upload-cover takes of three
home-recorded children’s songs, scored against those three sources and three unrelated songs
by the same family. `arioso.analysis.melody_match()` alone cannot answer “is this take a
cover of that song”: a take’s score against its own source (0.57 to 0.71 on the mix) sits
inside the range of its scores against unrelated songs (up to 0.66), so no fixed threshold
separates them. Two signals did:

- **lyric recall** (the source’s words found, in order, in the take’s words): 0.60 to 0.94
  against the true source, at most 0.15 against any other, for every take with words;
- **melody rank**: for the instrumental takes, the true source had the highest
  `melody_match` of all six songs on the mix (by 0.05 to 0.11), though not in absolute terms.

So [`cover_closeness()`](#arioso.closeness.cover_closeness) reports both and gives a verdict from the one that applies: the
words when the source and the take both have them, else the melody’s rank among
`references` (other songs: the rest of the folder serves), else no verdict (“unclear”).

```pycon
>>> lyric_recall("stinky poo where are you", "oh stinky poo stinky poo where are you now")
1.0
>>> lyric_recall("stinky poo where are you", "climbing up the mountain")
0.0
>>> lyric_recall("", "anything") is None
True
```

### Module Attributes

| [`MIN_WORDS`](#arioso.closeness.MIN_WORDS)       | The fewest words a side must have for its lyric recall to count.                                        |
|------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------|
| [`LYRIC_COVER`](#arioso.closeness.LYRIC_COVER)     | the take sings the source's words (true pairs measured 0.60-0.94).                                      |
| [`LYRIC_UNRELATED`](#arioso.closeness.LYRIC_UNRELATED) | not the source's song (others measured <= 0.15).                                                        |
| [`DFLT_SR`](#arioso.closeness.DFLT_SR)         | The rate audio is read at for the melody comparison.                                                    |
| [`AUTO`](#arioso.closeness.AUTO)            | [`arioso.cover.vocal_lyrics()`](arioso.cover.html.md#arioso.cover.vocal_lyrics). |

### Functions

| [`cover_closeness`](#arioso.closeness.cover_closeness)(source, takes, \*[, ...])   | How close each take is to `source`, and whether it is a cover of it.                        |
|----------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------|
| [`lyric_recall`](#arioso.closeness.lyric_recall)(source_text, take_text)        | The share of the source's words the take sings, in order (`None` when the source has none). |
| [`words`](#arioso.closeness.words)(text)                                 | The words of `text`, lowercased.                                                            |

### arioso.closeness.AUTO *= 'auto'*

[`arioso.cover.vocal_lyrics()`](arioso.cover.html.md#arioso.cover.vocal_lyrics).

* **Type:**
  `transcribe`’s default

### arioso.closeness.DFLT_SR *= 22050*

The rate audio is read at for the melody comparison.

### arioso.closeness.LYRIC_COVER *= 0.4*

the take sings the source’s words (true pairs measured 0.60-0.94).

* **Type:**
  Lyric recall at or above this

### arioso.closeness.LYRIC_UNRELATED *= 0.25*

not the source’s song (others measured <= 0.15).

* **Type:**
  Lyric recall at or below this, with words on both sides

### arioso.closeness.MIN_WORDS *= 12*

The fewest words a side must have for its lyric recall to count.

### arioso.closeness.cover_closeness(source, takes, , references=(), transcribe='auto', source_text=None, melody=None, load=None, min_words=12)

How close each take is to `source`, and whether it is a cover of it.

Matches `cover_folder`’s `assess` keyword: `(source_path, take_paths) -> dict`;
give it references with `functools.partial(cover_closeness, references=[...])`.

* **Parameters:**
  * **source** – The source song’s audio file.
  * **takes** ([`Iterable`](https://docs.python.org/3/library/typing.html#typing.Iterable)) – The takes’ audio files.
  * **references** ([`Iterable`](https://docs.python.org/3/library/typing.html#typing.Iterable)) – Other songs’ audio files, for the melody’s rank (the source itself, if
    listed, is skipped). Without them a take with no words gets no verdict.
  * **transcribe** ([`Union`](https://docs.python.org/3/library/typing.html#typing.Union)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`None`](https://docs.python.org/3/builtins/constants.html#None)]) – `(path) -> text`; the default is [`arioso.cover.vocal_lyrics()`](arioso.cover.html.md#arioso.cover.vocal_lyrics)
    (the vocal stem, transcribed: `pip install arioso[cover]`); `None` skips
    the words.
  * **source_text** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]) – The source’s words, when already known (it is then not transcribed).
  * **melody** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)]) – `(take, source, sr) -> float`, default `arioso.analysis.melody_match()`.
  * **load** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)]) – `(path) -> mono array` at `DFLT_SR`; default `librosa.load`.
  * **min_words** ([`int`](https://docs.python.org/3/builtins/functions.html#int)) – The fewest words each side needs for the words to decide.
* **Returns:**
  name, “source_words”: n, “references”: [names], “takes”: {name:
  {“lyric_recall”, “take_words”, “melody”, “melody_rank”, “verdict”, “why”}}}\`\`.
* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### arioso.closeness.lyric_recall(source_text, take_text)

The share of the source’s words the take sings, in order (`None` when the source has none).

* **Return type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`float`](https://docs.python.org/3/builtins/functions.html#float)]

### arioso.closeness.words(text)

The words of `text`, lowercased.

```pycon
>>> words("Stinky poo, where ARE you? Don't go!")
['stinky', 'poo', 'where', 'are', 'you', "don't", 'go']
```

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)
