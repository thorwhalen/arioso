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
  **song** ([`Song`](arioso.base.html.md#arioso.base.Song)) – A Song object with a populated audio_url.
* **Return type:**
  [`Song`](arioso.base.html.md#arioso.base.Song)
* **Returns:**
  A new Song with audio_bytes populated.

#### get_status(task_id)

Check the status of a generation task and return updated Songs.

* **Parameters:**
  **task_id** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – The taskId returned from generate(), upload_extend(),
  or upload_cover().
* **Return type:**
  [`list`](https://docs.python.org/3/library/stdtypes.html#list)[[`Song`](arioso.base.html.md#arioso.base.Song)]
* **Returns:**
  List of Song objects with current status and audio URLs
  (if generation is complete).

#### *property* tasks

Local task store (`SunoTasks` Mapping) for recorded requests.

#### upload_file(file_path)

Upload a local audio file and return a public URL.

Uses the sunoapi.org file upload API. Uploaded files are temporary
and automatically deleted after 3 days.

* **Parameters:**
  **file_path** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Path to the local audio file.
* **Return type:**
  [`str`](https://docs.python.org/3/library/stdtypes.html#str)
* **Returns:**
  Public URL of the uploaded file.
