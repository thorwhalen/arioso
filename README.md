# arioso

Unified Python facade for AI music generation.

One interface, many backends. Arioso wraps 14 AI music generation platforms —
from local open-source models to commercial REST APIs — behind a single `generate()` call.

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

14 platforms are included, spanning local models, REST APIs, and SDK-based services:

| Platform | Access | Auth | Install |
|----------|--------|------|---------|
| **MusicGen** | Local (audiocraft/transformers) | None | `pip install arioso[musicgen]` |
| **Stable Audio Open** | Local (diffusers) | None | `pip install arioso[stable-audio]` |
| **Harmonai** | Local (diffusers) | None | `pip install arioso[harmonai]` |
| **Riffusion** | Local (diffusers) | None | `pip install arioso[riffusion]` |
| **ElevenLabs** | REST API | `ELEVENLABS_API_KEY` | `pip install arioso[elevenlabs]` |
| **Suno** (via sunoapi.org) | REST API | `SUNO_API_KEY` | `pip install arioso[sunoapi]` |
| **Google Lyria 2** | REST (Vertex AI) | `GOOGLE_CLOUD_PROJECT` + gcloud auth | `pip install arioso[lyria2]` |
| **Google Lyria RT** | WebSocket (genai SDK) | `GOOGLE_API_KEY` | `pip install arioso[lyria-rt]` |
| **Mubert** | REST API | `MUBERT_PAT` | `pip install arioso[mubert]` |
| **Beatoven.ai** | REST API | `BEATOVEN_API_KEY` | `pip install arioso[beatoven]` |
| **Loudly** | REST API | `LOUDLY_API_KEY` | `pip install arioso[loudly]` |
| **Jen** | REST API | `JEN_API_KEY` | `pip install arioso[jen]` |
| **YuE** | fal.ai / local CLI | `FAL_KEY` | `pip install arioso[yue]` |
| **Udio** | Unofficial wrapper | `UDIO_AUTH_COOKIE` | `pip install arioso[udio]` |

```python
# See what's available
arioso.list_platforms()
# ['beatoven', 'elevenlabs', 'harmonai', 'jen', 'loudly', 'lyria2', ...]

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

## Platforms Without Public APIs

The following platforms were considered during the design of arioso's unified
parameter vocabulary and affordance system, but do not have public APIs (nor a
reliable third-party API wrapper). They are listed here for completeness.

| Platform | Website | What It Does | Affordances Considered |
|----------|---------|-------------|----------------------|
| **AIVA** | [aiva.ai](https://aiva.ai) | Orchestral AI composition. Desktop/web DAW with 250+ style presets, direct BPM/key/instrument control. | genre, bpm, key, instruments, duration |
| **ACE Studio** | [acestudio.ai](https://acestudio.ai) | AI vocal synthesis DAW plugin. 140+ voice models for singing voice generation. | voice_id, lyrics, instruments |
| **Boomy** | [boomy.com](https://boomy.com) | AI song creation with Auto Vocal and streaming platform distribution. Enterprise-only API. | prompt, voice_id, instrumental |
| **Soundraw** | [soundraw.io](https://soundraw.io) | AI music generation for content creators. Enterprise B2B API only ($11/mo consumer web app). | genre, duration, energy |
| **CassetteAI** | [cassetteai.com](https://cassetteai.com) | Prompt-based music generation. Web-only, no known API. | prompt, duration |
| **Musicfy** | [musicfy.lol](https://musicfy.lol) | AI music generation with voice cloning and pitch shifting. Web-only, no known API. | prompt, voice_id, pitch_shift |

## Research & Background

Arioso's design is informed by extensive research into the AI music generation
landscape. Two reference documents in [`misc/docs/`](misc/docs/) provide the
full background:

### Platform comparison and API landscape

[**AI Music Generation Tools: A Unified API Reference for 21 Platforms**](misc/docs/AI%20music%20generation%20tools%20-%20a%20unified%20API%20reference%20for%2021%20platforms.md)
maps the full union of capabilities across every tool we investigated. Highlights:

- [General characteristics comparison](misc/docs/AI%20music%20generation%20tools%20-%20a%20unified%20API%20reference%20for%2021%20platforms.md#1-general-characteristics-comparison) —
  pricing, API availability, max length, sample rate, vocal support, and quality tier for 18 tools
- [Documentation and integration links](misc/docs/AI%20music%20generation%20tools%20-%20a%20unified%20API%20reference%20for%2021%20platforms.md#2-documentation-and-integration-links) —
  docs URLs, OpenAPI specs, Python/JS SDKs, and MCP servers per platform
- [Feature affordance matrix](misc/docs/AI%20music%20generation%20tools%20-%20a%20unified%20API%20reference%20for%2021%20platforms.md#3-feature-affordance-matrix) —
  which platforms support text prompts, negative prompts, lyrics, audio conditioning, melody conditioning, duration, BPM, key, genre tags, energy, instruments, and more
- [Unified affordance mapping](misc/docs/AI%20music%20generation%20tools%20-%20a%20unified%20API%20reference%20for%2021%20platforms.md#4-unified-affordance-mapping-for-façade-design) —
  the 40 common parameter names that arioso exposes, with native parameter names per platform
- [Complete API parameter catalogs](misc/docs/AI%20music%20generation%20tools%20-%20a%20unified%20API%20reference%20for%2021%20platforms.md#5-complete-api-parameter-catalogs-for-key-tools) —
  full endpoint and parameter documentation for Suno, ElevenLabs, MusicGen, Lyria RealTime, Stable Audio Open, and YuE

### Prompt engineering across platforms

[**Prompt Engineering for Music AI Generation: A Resource Guide**](misc/docs/Prompt%20Engineering%20for%20Music%20AI%20Generation%20--%20A%20Resource%20Guide.md)
compiles 78 resources (papers, datasets, tools, taxonomies, and guides) covering
how to write effective prompts for text-to-music systems. Key sections:

- [Papers on prompt engineering techniques](misc/docs/Prompt%20Engineering%20for%20Music%20AI%20Generation%20--%20A%20Resource%20Guide.md#a-papers-directly-addressing-prompt-engineering-for-music-generation) —
  chain-of-thought prompting, prompt tuning, user studies, and structured prompting strategies
- [Model architecture and text encoders](misc/docs/Prompt%20Engineering%20for%20Music%20AI%20Generation%20--%20A%20Resource%20Guide.md#b-model-architecture-papers-revealing-how-text-prompts-are-processed) —
  how T5, CLAP, FLAN-T5, and MuLan encoders determine which prompt styles work best
- [Text-audio alignment models](misc/docs/Prompt%20Engineering%20for%20Music%20AI%20Generation%20--%20A%20Resource%20Guide.md#c-text-audio-alignment-models-defining-the-prompt-embedding-space) —
  CLAP, MuLan, LAION-CLAP, and how they shape the vocabulary space
- [CFG and parameter interactions](misc/docs/Prompt%20Engineering%20for%20Music%20AI%20Generation%20--%20A%20Resource%20Guide.md#d-how-numerical-parameters-interact-with-text-prompts) —
  how guidance scale, temperature, and other parameters interact with text prompts
- [Captioning datasets defining vocabulary](misc/docs/Prompt%20Engineering%20for%20Music%20AI%20Generation%20--%20A%20Resource%20Guide.md#e-music-captioning-datasets-defining-the-vocabulary-space) —
  MusicCaps, LP-MusicCaps, MusicBench, and 11 other datasets that trained these models
- [Vocabulary and taxonomy resources](misc/docs/Prompt%20Engineering%20for%20Music%20AI%20Generation%20--%20A%20Resource%20Guide.md#f-vocabulary-taxonomy-and-terminology-resources) —
  AudioSet ontology, Music Ontology, Cyanite AI taxonomy
- [Platform-specific prompt guides](misc/docs/Prompt%20Engineering%20for%20Music%20AI%20Generation%20--%20A%20Resource%20Guide.md#i-platform-specific-prompt-guides-and-prompt-builder-tools) —
  official and community guides for Stable Audio, Udio, Lyria, Suno, ElevenLabs, and more

Each platform also has a `<PLATFORM>_REFERENCE.md` in its directory under
`arioso/platforms/` with platform-specific prompt engineering guidance, API
details, and links to further reading.

## Architecture

```
arioso/
    __init__.py          # Facade: generate(), list_platforms()
    base.py              # Song, AudioResult, AFFORDANCES (40 unified params)
    registry.py          # Auto-discovery, lazy loading, manual registration
    translation.py       # Parameter renaming & coercion (common -> native)
    _util.py             # Auth helpers, HTTP session factory

    platforms/
        _base_adapter.py   # BaseRestAdapter (shared REST infrastructure)
        musicgen/          # Local inference via audiocraft/transformers
        stable_audio/      # Local inference via diffusers
        harmonai/          # Unconditional generation via Dance Diffusion
        riffusion/         # Spectrogram-based via diffusers
        elevenlabs/        # REST with OpenAPI spec via ho
        sunoapi/           # REST via sunoapi.org
        lyria2/            # Google Vertex AI REST
        lyria_rt/          # Google Lyria RealTime WebSocket
        mubert/            # Mubert REST API
        beatoven/          # Beatoven.ai REST API
        loudly/            # Loudly REST API
        jen/               # Jen REST API
        yue/               # YuE via fal.ai or local CLI
        udio/              # Udio via unofficial wrapper
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
