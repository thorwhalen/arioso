# arioso.platforms.sunoapi.adapter

Suno adapter via sunoapi.org REST API.

### Classes

| [`Adapter`](#arioso.platforms.sunoapi.adapter.Adapter)(config, \*[, task_store])   | Adapter for Suno music generation via sunoapi.org.   |
|--------------------------------------------------------------------------------------|------------------------------------------------------|

### *class* arioso.platforms.sunoapi.adapter.Adapter(config, , task_store=None)

Bases: `BaseRestAdapter`

Adapter for Suno music generation via sunoapi.org.

Handles the distinction between simple generation (prompt only)
and custom generation (with lyrics/style via customMode).

The sunoapi.org API is callback-based: it returns a taskId immediately
and POSTs results to your callBackUrl when generation completes.
A no-op placeholder callback URL is used by default, so polling via
`get_status()` (or `wait_for_completion=True`) works out of the box.
Set the SUNO_CALLBACK_URL env var to a real webhook if you want push
notifications.

After calling generate(), use get_status() to poll for results, or
use generate() with wait_for_completion=True to block until audio is ready.

All generation requests and status polls are automatically recorded in a
local task store (`SunoTasks`).  Access it via the `tasks` property:

```default
adapter = Adapter(config)
adapter.tasks                # SunoTasks Mapping
adapter.tasks.last(10)       # last 10 tasks
adapter.tasks.failed()       # all failed tasks
```

#### fetch_audio(song)

Download the audio bytes for a Song that has an audio_url.

* **Parameters:**
  **song** ([`Song`](arioso.base.md#arioso.base.Song)) – A Song object with a populated audio_url.
* **Return type:**
  [`Song`](arioso.base.md#arioso.base.Song)
* **Returns:**
  A new Song with audio_bytes populated.

#### get_status(task_id)

Check the status of a generation task and return updated Songs.

* **Parameters:**
  **task_id** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The taskId returned from generate(), upload_extend(),
  or upload_cover().
* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Song`](arioso.base.md#arioso.base.Song)]
* **Returns:**
  List of Song objects with current status and audio URLs
  (if generation is complete).

#### get_timestamped_lyrics(song_or_task_id, audio_id=None)

Suno’s own alignment of the sung lyric to a finished song.

One entry per sung *word* (Suno’s tokens: space-separated, so a whole
katakana word such as `バカンス` is one entry), in the order sung —
which can differ from the lyric you sent when Suno repeats or drops a
line. Times sit on a coarse (~0.16 s) grid and tend to run late, so
treat them as windows for a finer aligner rather than as onsets.

* **Parameters:**
  * **song_or_task_id** ([`Song`](arioso.base.md#arioso.base.Song) | [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – a completed `Song` from `get_status` /
    `poll_status` (it carries `metadata["task_id"]`), or a taskId.
  * **audio_id** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – the song’s audio id; defaults to `song.id`.
* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)
* **Returns:**
  `{"aligned_words": [...], "hoot_cer": float | None, "raw": dict}`
  where each aligned word is `{"word", "text", "start", "end",
  "line_end", "section", "success"}`: `word` is Suno’s raw token
  (it may carry `[Section]` tags and newlines), `text` the token
  with those removed, `line_end` whether a lyric line ends there,
  `section` the label of a section starting at this word (else
  `None`). Bare section tags are folded onto the next word.
* **Raises:**
  * [**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – the Song is not complete, carries no task_id, or Suno
        has no alignment for it yet.
  * **hoot_cer\` is Suno's character error rate for the alignment** – 

#### *property* tasks

Local task store (`SunoTasks` Mapping) for recorded requests.

#### upload_file(file_path)

Upload a local audio file and return a public URL.

Uses the sunoapi.org file upload API. Uploaded files are temporary
and automatically deleted after 3 days.

* **Parameters:**
  **file_path** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Path to the local audio file.
* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
* **Returns:**
  Public URL of the uploaded file.
