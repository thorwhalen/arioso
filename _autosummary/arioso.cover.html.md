# arioso.cover

Cover every song in a folder: lyrics, one cover call per song, every take saved, resumable.

[`cover_folder()`](#arioso.cover.cover_folder) is the loop around one-song `generate(audio_input=...)` that a folder
job needs. Per source file it:

1. skips the song when the folder’s manifest already records it as done or refused;
2. reuses the cover task the manifest recorded for it, when a run stopped between
   submitting and saving (so a crash or a re-run never pays twice), or else
3. transcribes its lyrics (`transcribe`, default [`vocal_lyrics()`](#arioso.cover.vocal_lyrics): the vocal stem
   from `denote.separate`, transcribed by `scribed`; only for a platform that takes
   lyrics), so the cover keeps the words; no words heard makes it instrumental; and
   submits one cover, recording the task id in the manifest before waiting for it;
4. waits for it and saves every take as `<stem> (<platform> N).<ext>` in `dst`;
5. records the outcome in the manifest (`dst/covers.jsonl`, JSON lines, the last line
   of a song wins): `done`, `refused` (a [`CatalogMatchError`](arioso.base.html.md#arioso.base.CatalogMatchError),
   final) or `error` (tried again on the next run: by reusing its task once, then by
   submitting anew).

```pycon
>>> from arioso.base import AudioResult, Song
>>> import tempfile, pathlib
>>> src, dst = pathlib.Path(tempfile.mkdtemp()), pathlib.Path(tempfile.mkdtemp())
>>> _ = (src / "Lullaby.wav").write_bytes(b"RIFF")
>>> def fake(prompt, **kw):  # a platform that answers at once, with two takes
...     return [Song(id=f"t{i}", status="complete", platform="fake",
...                  audio=AudioResult(audio_bytes=b"ID3", format="mp3")) for i in (1, 2)]
>>> [r["outcome"] for r in cover_folder(src, dst, platform="fake", generate=fake,
...                                     transcribe=lambda p: "hush now")]
['done']
>>> sorted(p.name for p in dst.iterdir())
['Lullaby (fake 1).mp3', 'Lullaby (fake 2).mp3', 'covers.jsonl']
>>> cover_folder(src, dst, platform="fake", generate=fake, transcribe=None)  # resumed
[]
```

### Module Attributes

| [`AUDIO_EXTENSIONS`](#arioso.cover.AUDIO_EXTENSIONS)   | The audio files [`cover_folder()`](#arioso.cover.cover_folder) picks up from the source folder.   |
|---------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|
| [`DFLT_MANIFEST`](#arioso.cover.DFLT_MANIFEST)      | The manifest's file name, inside the target folder.                                                                |
| [`FINAL_OUTCOMES`](#arioso.cover.FINAL_OUTCOMES)     | Outcomes that end a song's job; `error` is tried again on the next run.                                            |
| [`DFLT_STRENGTH`](#arioso.cover.DFLT_STRENGTH)      | a folder cover is meant to keep each song (the #69 run used 0.9).                                                  |
| [`DFLT_POLL_INTERVAL`](#arioso.cover.DFLT_POLL_INTERVAL) | seconds between status checks, and the most to wait.                                                               |
| [`DFLT_TIMEOUT`](#arioso.cover.DFLT_TIMEOUT)       | seconds between status checks, and the most to wait.                                                               |
| [`AUTO`](#arioso.cover.AUTO)               | [`vocal_lyrics()`](#arioso.cover.vocal_lyrics) when the platform takes lyrics, else none.         |

### Functions

| [`cover_folder`](#arioso.cover.cover_folder)(src, dst, \*[, platform, ...])     | Cover every audio file in `src` with `platform`, takes saved in `dst`.          |
|--------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| [`cover_params`](#arioso.cover.cover_params)(path, \*, lyrics, style, strength) | The cover call's keyword arguments for one song (unified names).                |
| [`read_manifest`](#arioso.cover.read_manifest)(path)                             | The last record of each song in a manifest (JSON lines), by source file name.   |
| [`save_takes`](#arioso.cover.save_takes)(songs, folder, stem, \*, platform)   | Write each take as `<stem> (<platform> N).<ext>`; returns their file names.     |
| [`vocal_lyrics`](#arioso.cover.vocal_lyrics)(path, \*[, separate, transcribe])  | The words sung in `path`: its vocal stem (`denote.separate`), transcribed.      |
| [`wait_for_songs`](#arioso.cover.wait_for_songs)(songs, \*[, poll_interval, ...]) | `songs` once all complete, polled with `check` (default `arioso.check_status`). |

### arioso.cover.AUDIO_EXTENSIONS *= ('.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg', '.aiff', '.aif')*

The audio files [`cover_folder()`](#arioso.cover.cover_folder) picks up from the source folder.

### arioso.cover.AUTO *= 'auto'*

[`vocal_lyrics()`](#arioso.cover.vocal_lyrics) when the platform takes lyrics, else none.

* **Type:**
  `transcribe`’s default

### arioso.cover.DFLT_MANIFEST *= 'covers.jsonl'*

The manifest’s file name, inside the target folder.

### arioso.cover.DFLT_POLL_INTERVAL *= 15.0*

seconds between status checks, and the most to wait.

* **Type:**
  Waiting for a hosted cover

### arioso.cover.DFLT_STRENGTH *= 0.9*

a
folder cover is meant to keep each song (the #69 run used 0.9).

* **Type:**
  How much the source shapes the cover. Higher than `tools.DFLT_AUDIO_WEIGHT` (0.5)

### arioso.cover.DFLT_TIMEOUT *= 1200.0*

seconds between status checks, and the most to wait.

* **Type:**
  Waiting for a hosted cover

### arioso.cover.FINAL_OUTCOMES *= ('done', 'refused')*

Outcomes that end a song’s job; `error` is tried again on the next run.

### arioso.cover.cover_folder(src, dst, \*, platform='sunoapi', audio_input_strength=0.9, transcribe='auto', style=None, only=None, params=<function cover_params>, generate=None, wait=<function wait_for_songs>, manifest='covers.jsonl', extensions=('.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg', '.aiff', '.aif'), \*\*generate_kwargs)

Cover every audio file in `src` with `platform`, takes saved in `dst`.

Returns the records written this run (one per song attempted; songs the manifest
already holds as done or refused are skipped). See the module docstring.

* **Parameters:**
  * **src** – The folder of source songs (files with one of `extensions`).
  * **dst** – The folder for the takes and the manifest (created if missing).
  * **platform** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – An arioso platform that takes `audio_input`.
  * **audio_input_strength** ([`float`](https://docs.python.org/3/builtins/functions.html#float)) – How much the source shapes the cover, 0-1.
  * **transcribe** ([`Union`](https://docs.python.org/3/library/typing.html#typing.Union)[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable), [`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`None`](https://docs.python.org/3/builtins/constants.html#None)]) – `(path) -> lyrics`; `""` makes the cover instrumental, `None`
    sends no lyrics. The default uses [`vocal_lyrics()`](#arioso.cover.vocal_lyrics) when `platform`
    takes lyrics, and none otherwise.
  * **style** ([`Union`](https://docs.python.org/3/library/typing.html#typing.Union)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable), [`None`](https://docs.python.org/3/builtins/constants.html#None)]) – The style for every song, or `(path) -> style`; `None` sends none.
  * **only** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Iterable`](https://docs.python.org/3/library/typing.html#typing.Iterable)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]]) – Source stems to cover (default every file).
  * **params** ([`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)) – `(path, *, lyrics, style, strength) -> kwargs` for the cover call
    (default [`cover_params()`](#arioso.cover.cover_params)); parameters `platform` does not take are
    dropped.
  * **generate** ([`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)) – `(prompt, **kwargs) -> list[Song]`; default `arioso.generate_many`.
  * **wait** ([`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)) – `(songs) -> songs`, all complete (default [`wait_for_songs()`](#arioso.cover.wait_for_songs)).
  * **manifest** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The manifest’s name in `dst`.
  * **\*\*generate_kwargs** – Passed to every cover call (`model`, `vocal_gender`, …).
* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)

### arioso.cover.cover_params(path, , lyrics, style, strength)

The cover call’s keyword arguments for one song (unified names).

`lyrics=""` (no words heard) asks for an instrumental; `None` sends nothing.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### arioso.cover.read_manifest(path)

The last record of each song in a manifest (JSON lines), by source file name.

A line that does not parse (a run killed mid-write) is skipped.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### arioso.cover.save_takes(songs, folder, stem, , platform)

Write each take as `<stem> (<platform> N).<ext>`; returns their file names.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)

### arioso.cover.vocal_lyrics(path, , separate=None, transcribe=None, \*\*transcribe_kwargs)

The words sung in `path`: its vocal stem (`denote.separate`), transcribed.

One line per transcript segment; `""` when no words are heard. `separate` and
`transcribe` default to `denote.separate` and `scribed.transcribe` (both
imported only here; `pip install arioso[cover]`); `transcribe_kwargs` go to the
transcriber (`backend`, `model`, `language`, …).

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### arioso.cover.wait_for_songs(songs, , poll_interval=15.0, timeout=1200.0, check=None)

`songs` once all complete, polled with `check` (default `arioso.check_status`).

Songs already complete (a local platform) come back at once. Raises `TimeoutError`
past `timeout`, and `RuntimeError` on a song in error.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)
