# arioso.tools

High-level tools for common arioso workflows (submit, poll, download).

### Functions

| [`download_songs`](#arioso.tools.download_songs)(songs, target_folder, \*[, ...])   | Download completed songs to *target_folder*.                         |
|----------------------------------------------------------------------------------------------------|----------------------------------------------------------------------|
| [`ensure_adapter`](#arioso.tools.ensure_adapter)([adapter])                         | Return a ready-to-use platform adapter.                              |
| [`extract_style`](#arioso.tools.extract_style)(filename)                           | Parse style from a filename like `barry_{key}_{bpm}bpm_{Style}.wav`. |
| [`poll_status`](#arioso.tools.poll_status)(task_id, \*[, poll_interval, ...])    | Poll until a task completes.                                         |
| [`safe_name`](#arioso.tools.safe_name)(text)                                   | Convert arbitrary text to a filesystem-safe string.                  |
| [`submit_cover`](#arioso.tools.submit_cover)(source_path, \*[, style, ...])       | Submit an upload-cover job.                                          |
| [`wav_to_mp3`](#arioso.tools.wav_to_mp3)(wav_path, \*[, max_duration])          | Convert wav to a trimmed mp3.                                        |

### arioso.tools.download_songs(songs, target_folder, , name_prefix='cover', adapter=None)

Download completed songs to *target_folder*. Returns list of saved paths.

### arioso.tools.ensure_adapter(adapter='sunoapi')

Return a ready-to-use platform adapter.

`adapter` can be:

- An existing adapter instance — returned as-is.
- A platform config dict — instantiated via its `Adapter` class.
- A string that is a valid platform name (e.g. `"sunoapi"`) — loaded
  from the arioso registry.
- `None` — falls back to `DFLT_PLATFORM`.

Raises `ValueError` for unrecognised inputs.

### arioso.tools.extract_style(filename)

Parse style from a filename like `barry_{key}_{bpm}bpm_{Style}.wav`.

### arioso.tools.poll_status(task_id, , poll_interval=15, timeout=600, adapter=None)

Poll until a task completes. Returns list of completed Song objects.

### arioso.tools.safe_name(text)

Convert arbitrary text to a filesystem-safe string.

### arioso.tools.submit_cover(source_path, \*, style='', prompt='', instrumental=True, model='V5', audio_weight=0.5, style_weight=0.5, source_prep=functools.partial(<function wav_to_mp3>, max_duration=480), adapter='sunoapi')

Submit an upload-cover job. Returns `(task_id, source_path)`.

* **Parameters:**
  * **source_path** – Path to source audio file.
  * **source_prep** – Callable `(path) -> path` to prepare the source file
    before upload (e.g. convert wav to mp3).  Defaults to
    [`wav_to_mp3()`](#arioso.tools.wav_to_mp3) (trimmed to *max_duration*).
  * **adapter** – Platform adapter, config dict, platform name, or `None`.

The caller is responsible for cleaning up *source_path* when done.

### arioso.tools.wav_to_mp3(wav_path, , max_duration=480)

Convert wav to a trimmed mp3. Returns path to a temp mp3 file.

The caller is responsible for deleting the temp file when done.
