# arioso

Unified Python facade for AI music generation.

One interface, many backends. Arioso wraps AI music generation platforms —
MusicGen, ElevenLabs, Suno, and more — behind a single `generate()` call.

## Install

```
pip install arioso
```

## Quick start

```python
import arioso

# Generate music (defaults to MusicGen, runs locally)
song = arioso.generate("upbeat jazz piano")

# The result is a Song object with audio data
song.audio.audio_array   # numpy array (for local models)
song.audio.sample_rate   # e.g. 32000

# Use a different platform
song = arioso.generate("epic orchestral soundtrack", platform="elevenlabs", duration=30)
song.audio.audio_bytes   # MP3 bytes
```

## Platforms

Three platforms are included out of the box:

| Platform | Access | Auth | Install |
|----------|--------|------|---------|
| **MusicGen** | Local Python library | None | `pip install arioso[musicgen]` |
| **ElevenLabs** | REST API | API key (`ELEVENLABS_API_KEY`) | `pip install arioso[elevenlabs]` |
| **Suno** (via sunoapi.org) | REST API | Bearer token (`SUNO_API_KEY`) | `pip install arioso[sunoapi]` |

```python
# See what's available
arioso.list_platforms()
# ['elevenlabs', 'musicgen', 'sunoapi']

# Inspect a platform's configuration
arioso.get_platform_info("musicgen")
```

### MusicGen (local, no API key)

Runs on your machine. Tries `audiocraft` first, falls back to HuggingFace `transformers`.

```python
song = arioso.generate(
    "chill lofi beats",
    platform="musicgen",
    duration=10,
    temperature=0.8,
    guidance=3.0,
    model="facebook/musicgen-small",  # or medium, large, melody
)
```

### ElevenLabs

Needs `ELEVENLABS_API_KEY` environment variable.

```python
song = arioso.generate(
    "dramatic film score",
    platform="elevenlabs",
    duration=60,
    instrumental=True,
    output_format="mp3_44100_128",
)

# With lyrics
song = arioso.generate(
    "pop ballad",
    platform="elevenlabs",
    lyrics="[Verse]\nWalking through the rain\n[Chorus]\nI found my way home",
    title="Coming Home",
)
```

### Suno (via sunoapi.org)

Needs `SUNO_API_KEY` environment variable.

```python
songs = arioso.generate_many(
    "summer reggae vibes",
    platform="sunoapi",
    genre="reggae, tropical",
    instrumental=True,
)
# Suno returns 2 songs per call
for song in songs:
    print(song.title, song.audio_url)
```

## Parameters

All platforms share a common vocabulary of parameter names. Use any that
the platform supports — unsupported ones are warned about and ignored.

```python
song = arioso.generate(
    "ambient soundscape",           # prompt (required)
    platform="musicgen",
    duration=15,                    # seconds
    temperature=1.2,                # sampling randomness
    top_k=250,                      # top-k sampling
    guidance=3.0,                   # classifier-free guidance
    seed=42,                        # reproducibility
)
```

The full set of 40 unified parameter names:

| Parameter | Type | Description |
|-----------|------|-------------|
| `prompt` | str | Text description of desired music |
| `duration` | float | Output length in seconds |
| `lyrics` | str | Custom lyrics text |
| `instrumental` | bool | Force instrumental-only output |
| `genre` | str | Genre tag or category |
| `title` | str | Song title |
| `model` | str | Model version or variant |
| `seed` | int | Random seed for reproducibility |
| `guidance` | float | Classifier-free guidance scale |
| `temperature` | float | Sampling randomness |
| `top_k` | int | Top-k sampling parameter |
| `top_p` | float | Top-p (nucleus) sampling |
| `bpm` | int | Beats per minute |
| `key` | str | Musical key (e.g. "C major") |
| `energy` | float | Energy/intensity level 0-1 |
| `output_format` | str | Desired output format |
| ... | | See `arioso.AFFORDANCES` for all 40 |

Each platform maps these to its native parameter names automatically.
For example, `instrumental=True` becomes `make_instrumental=True` for Suno
and `force_instrumental=True` for ElevenLabs.

## Output

Every call returns a `Song` object:

```python
song = arioso.generate("jazz piano", platform="musicgen")

song.status           # 'complete'
song.platform         # 'musicgen'
song.title            # ''
song.metadata         # {'model': 'facebook/musicgen-small', ...}

# Audio is in song.audio (an AudioResult)
song.audio.audio_array    # numpy array (local models)
song.audio.audio_bytes    # raw bytes (REST APIs)
song.audio.audio_url      # URL string (Suno)
song.audio.sample_rate    # e.g. 32000
song.audio.format         # 'wav', 'mp3', etc.

# Shortcuts
song.audio_array          # same as song.audio.audio_array
song.audio_bytes          # same as song.audio.audio_bytes
song.sample_rate          # same as song.audio.sample_rate
```

Use `generate_many()` when you want all results (some platforms return multiple):

```python
songs = arioso.generate_many("pop song", platform="sunoapi")
# Returns list[Song]
```

## Adding a new platform

Arioso uses a plugin architecture. Each platform is a subfolder under
`arioso/platforms/` with two files:

```
arioso/platforms/myplatform/
    __init__.py
    config.py        # required: declares PLATFORM_CONFIG
    adapter.py       # optional: custom generation logic
```

### Minimal example (REST API)

For a REST API, you may only need `config.py`:

```python
# arioso/platforms/myplatform/config.py

PLATFORM_CONFIG = {
    "name": "myplatform",
    "display_name": "My Platform",
    "website": "https://myplatform.com",
    "tier": "simple",
    "access_type": "rest_api",

    "auth": {
        "type": "bearer_token",
        "env_var": "MYPLATFORM_API_KEY",
    },

    "param_map": {
        "prompt": {"native_name": "text", "required": True},
        "duration": {"native_name": "length_seconds"},
    },

    "supported_affordances": ["prompt", "duration"],
    "on_unsupported_param": "warn",

    "output": {
        "default_format": "mp3",
        "sample_rate": 44100,
        "returns": "bytes",
    },

    "api": {
        "base_url": "https://api.myplatform.com",
        "generate_endpoint": {"method": "post", "path": "/v1/generate"},
    },
}
```

The platform is auto-discovered on the next `arioso.list_platforms()` call.

### Custom adapter (Python library)

For platforms that are Python libraries rather than REST APIs, add an `adapter.py`:

```python
# arioso/platforms/myplatform/adapter.py

from arioso.base import Song, AudioResult

class Adapter:
    def __init__(self, config):
        self.config = config

    def generate(self, prompt, *, duration=10, **kwargs):
        # Your generation logic here
        from some_library import generate_audio
        audio = generate_audio(prompt, length=duration)

        return Song(
            audio=AudioResult(audio_array=audio, sample_rate=44100, format="wav"),
            platform="myplatform",
            status="complete",
        )
```

### Manual registration

Third-party packages can register platforms at runtime:

```python
from arioso.registry import register_platform

register_platform("custom", my_config_dict, my_adapter_instance)
```

## Architecture

```
arioso/
    __init__.py          # Facade: generate(), list_platforms()
    base.py              # Song, AudioResult, AFFORDANCES (40 unified params)
    registry.py          # Auto-discovery, lazy loading, manual registration
    translation.py       # Parameter renaming & coercion (common -> native)
    _util.py             # Auth helpers, HTTP session factory

    platforms/
        _base_adapter.py # BaseRestAdapter (shared REST infrastructure)
        musicgen/        # Local inference via audiocraft/transformers
        sunoapi/         # REST via sunoapi.org
        elevenlabs/      # REST with OpenAPI spec via ho
```

Key design choices:

- **Zero required dependencies.** The core package imports nothing outside stdlib.
  Platform dependencies are lazy-imported when you first call `generate()`.
- **Config-driven plugins.** Each platform declares a `PLATFORM_CONFIG` dict with
  parameter mappings, auth scheme, endpoints, and output format. Adding a platform
  is mostly configuration.
- **Automatic parameter translation.** The translation layer renames unified
  affordance names to native platform names and applies type coercions
  (e.g. `duration` seconds to `music_length_ms` milliseconds for ElevenLabs).
- **Leverages existing libraries.** Uses
  [ho](https://github.com/i2mint/ho) for OpenAPI-to-Python-function generation,
  [i2](https://github.com/i2mint/i2) for signature manipulation and function wrapping.
