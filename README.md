# arioso

Unified Python facade for AI music generation.

One interface, many backends. Arioso wraps 16 AI music generation platforms —
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
song.audio.audio_array  # numpy array (for local models)
song.audio.sample_rate  # e.g. 32000

# Use a different platform
song = arioso.generate("epic orchestral soundtrack", platform="elevenlabs", duration=30)
song.audio.audio_bytes  # MP3 bytes
```

## Command line

Installing arioso also installs an `arioso` command (`python -m arioso` does the same).

```
arioso generate "warm lo-fi piano" --platform musicgen --duration 10 -o out.wav
arioso generate "ambient pads" --platform stable_audio --model stabilityai/stable-audio-open-1.0 --seed 7 -o pads.wav
arioso platforms
```

`generate` writes the audio and prints the path it wrote. A waveform from a local model is written as WAV (with `soundfile` when installed, else the standard library's `wave`); encoded audio from a hosted platform keeps its format, and the file's suffix follows it. `--model` and `--seed` are passed on only when given.

`platforms` lists every platform with its access type, weights licence and whether its output may be used commercially (`yes`, `no`, `conditional`, or `provider terms` for hosted models whose service terms decide). The same table is `arioso.platform_table()` in Python, and each platform's `weights_license` and `commercial_use` are in `arioso.get_platform_info(name)`. MusicGen's weights are CC-BY-NC-4.0, so its output is not for commercial use.

Local torch platforms (MusicGen on transformers, Stable Audio Open) run on CUDA, else Apple MPS, else CPU; set `ARIOSO_TORCH_DEVICE` to force one.

### Comparing platforms

`compare` renders the same prompts with several platforms and measures each take:

```
arioso compare stable_audio_3,magenta_rt,ace_step:runtime=local --prompts prompts.json --duration 10
```

A contender is a platform with optional `key=value` options (`musicgen:model=facebook/musicgen-small`). Each one runs in a fresh process, one after the other, so only one model is in memory at a time and its peak memory is its own: on macOS the peak physical footprint, which counts Metal allocations, on Linux the peak resident set, in GB (10^9 bytes), for the process and, sampled while it runs, for the processes it starts (a runtime's worker, or one process per take). Every take becomes one JSON line in `<out_dir>/results.jsonl`: model load plus warm-up time, generation time, real-time factor (generation time over the seconds that came back), peak memory, available memory before the run, the weights licence, and objective checks: peak level and clipping (takes are kept as float WAVs, so a peak over full scale shows), and, when `denote` is installed, the detected tempo against the prompt's `bpm` (half and double time forgiven) and the estimated key against its `key`. A check that cannot run says why under `checks_skipped`. Takes of one run go to `<out_dir>/<run id>/<contender>/<prompt id>.wav` with a page of players beside them (`index.html`), and the command prints a progress line per take, then a summary per contender.

Load times compare like with like only between runtimes of the same kind: a runtime that keeps a worker (Magenta RealTime, ACE-Step) loads once, in the warm-up, while one that starts a process per take (Stable Audio 3) loads in every take, so its load is inside its real-time factor.

Without `--prompts` it uses three built-in prompts (a groove at 100 BPM, an accompaniment in C major, a loop at 85 BPM). A prompts file is a JSON list of `{"id", "text", "bpm", "key", "melody", "duration"}` (only `text` is required; a `melody` path is passed to platforms that take one). Platforms that may call a paid hosted service are refused unless you pass `--allow-hosted`: anything that is not a `python_lib` or `local_runtime`, has provider terms, or takes any credential (even an optional one, as `yue` takes a fal key); `runtime=local` counts as local only on a platform that has a local runtime (`ace_step`). `--min-free-gb` skips a contender when the machine is short of memory.

In Python, `arioso.compare.compare(contenders, prompts)` yields the same records. Its seams are `runner=` (how a contender is run and measured: `in_child_process`, with `python=`, or `in_this_process`), `scorer=` (audio to a dict of checks), `preload=` (modules that register third-party platforms, run here and in each child; `--preload` on the command line) and `timeout=` (seconds before a contender is killed with every process it started; `--timeout`). A killed or crashing contender keeps the takes it finished. Worker memory is sampled every 0.1 s, so it is a lower bound: memory a process takes just before exiting can be missed.

## Enhance existing audio (audio-to-audio)

Beyond text-to-music, arioso can transform audio you already have -- e.g. turn a
plain synthesized/"MIDI" render into something richer, or re-generate music that
follows an input melody. This is the `enhance()` entry point:

```python
import arioso

rendered = (
    ...
)  # a Song, a file path, bytes, an (array, sample_rate) pair, or a numpy waveform

# Audio-to-audio: continue/transform the input (Stable Audio Open, local)
better = arioso.enhance(rendered, "warm analog studio band", platform="stable_audio")

# Subtle variation: low strength keeps the input, high lets the prompt take over
# (Stable Audio 2.5 on fal.ai; needs FAL_KEY)
close = arioso.enhance(
    rendered, "full symphony orchestra", platform="stable_audio_25", strength=0.3
)

# Remix toward style tags (ACE-Step on fal.ai)
remix = arioso.enhance(rendered, "orchestral, film score, brass", platform="ace_step")

# Melody-conditioned: keep the tune, take the style from the prompt (MusicGen-melody)
variation = arioso.enhance(rendered, "energetic EDM", platform="musicgen")

# Discover which platforms accept input audio
arioso.supports_audio_input("stable_audio")  # True
arioso.supports_audio_input("mubert")  # False
```

To *extend* a recording rather than transform it, pass it as `continue_from` to `musicgen`. The last `prompt_seconds` (default 10) of the audio prompt the model, which writes `extend_seconds` (default `duration`) of what comes next, chained over `rounds` calls. The result is the original followed by the continuation; the continuation alone is in `song.metadata["continuation"]`. It runs locally, so it also extends audio that a hosted extend route refuses (Suno's `upload_extend` rejects uploads that match a catalogued composition).

```python
longer = arioso.generate(
    "warm piano trio",
    platform="musicgen",
    model="facebook/musicgen-medium",
    continue_from="take.wav",
    prompt_seconds=10,
    extend_seconds=20,
    rounds=2,
)
```

`enhance(audio, prompt='', *, platform='stable_audio', strength=None, as_='auto')`
routes your audio into the platform's audio-conditioning affordance
(`audio_input`, `melody`, or `reference_audio`) and generates. Input audio is
accepted in any form a `Song`/`AudioResult`/`bytes`/path/`(array, sample_rate)`/
numpy-waveform can take (normalized internally). Note that `stable_audio` via
diffusers uses the input as an initial waveform (continuation/init) and has no
`strength` knob (a value passed there is ignored with a warning); for a
strength-controlled transform use `stable_audio_25`.

## Seeds: a melody over a drone

To make a generator keep a known melody with no harmony (a Suno upload-cover, MusicGen-melody), give it the melody alone over a drone: a cover keeps its source's harmony static, so a source with no harmony gives takes that hold the drone. `arioso.seeds` builds that source from a recording or a score (`pip install 'arioso[seeds]'`; separating a voice from a mix goes through `denote`, which also needs `torch` and `torchaudio`).

```python
from arioso.seeds import melody_contour, melody_over_drone
from arioso.analysis import drone_report, melody_match

contour = melody_contour(
    "song.mid"
)  # one MIDI track's skyline, with glides and vibrato
contour = melody_contour(
    "song.mp3"
)  # or a recording: voice separated, f0 tracked, cleaned
seed, sr = melody_over_drone(
    contour.transposed(-3), "C#"
)  # bowed line over a tanpura on C#

drone_report(take, sr, sa="C#").holds()  # does a take hold the drone?
melody_match(take, seed, sr)  # does it keep the tune? (~0.9 vs ~0.45 for another song)
```

Every step is a seam: `audio_contour(..., separator=, f0_tracker=)`, `melody_over_drone(..., drone=, timbre=)`. A low (male) line is lifted by octaves above the drone's register (`floor_midi`), where it would otherwise fail `drone_report`.

A real tanpura sounds less synthetic than `tanpura()`: pass a recording as `drone=` (or `drone=recorded_drone(y, sr)`). It is retuned to Sa by varispeed (up to `max_shift`, 2 semitones by default) and looped with crossfades. A CC0 one to start from: ["Tanpura in E"](https://freesound.org/s/148850/) on Freesound.

For a source in a generator's own phrasing, `musicgen_variation(voice, "C#", prompt="slow sarangi", transpose=..., slow=1.2)` runs MusicGen-melody on the voice over the drone, high-passes its take below the drone's band, and puts the drone back underneath.

## Platforms

16 platforms are included, spanning local models, REST APIs, and SDK-based services:

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
| **Stable Audio 2.5** | fal.ai | `FAL_KEY` | `pip install arioso[stable-audio-25]` |
| **ACE-Step** | fal.ai, or local ACE-Step 1.5 (`runtime="local"`) | `FAL_KEY` (fal only) | `pip install arioso[ace-step]` |
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

### Local models in their own environments (Stable Audio 3, Magenta RealTime 2, ACE-Step 1.5)

Some local models pin library versions (MLX, torch) that cannot share an environment with each other, so arioso runs them in their own: each platform names a runtime directory and the commands that install it, and a missing one raises `RuntimeNotInstalled` with those commands. Runtimes live under `~/.local/share/arioso/runtimes/<name>` unless `$ARIOSO_RUNTIMES_DIR` or the platform's own variable (`$ARIOSO_SA3_DIR`, `$ARIOSO_MAGENTA_RT_DIR`, `$ARIOSO_ACE_STEP_DIR`) points elsewhere. Magenta RealTime and ACE-Step keep one worker process alive, so the model loads once per session.

```python
import arioso

# Stable Audio 3 (Stability's MLX build, Apple Silicon): model="sm-music" (default), "sm-sfx" or "medium"
song = arioso.generate(
    "lo-fi hip hop loop, 85 BPM, mellow Rhodes",
    platform="stable_audio_3",
    duration=11.29,
    seed=1,
)

# Magenta RealTime 2 (MLX, Apple Silicon): style from text or from a reference clip
song = arioso.generate("funky drum and bass groove", platform="magenta_rt", duration=10)

# ACE-Step 1.5 run locally (fal.ai stays the default; $ARIOSO_ACE_STEP_RUNTIME=local changes it): explicit BPM and key
song = arioso.generate(
    "acoustic guitar and soft piano",
    platform="ace_step",
    runtime="local",
    bpm=100,
    key="C Major",
    duration=30,
)
```

| platform | weights licence | commercial use |
|---|---|---|
| `stable_audio_3` | Stability AI Community License (+ Gemma terms for its text encoder) | free under US$1M annual revenue |
| `magenta_rt` | CC-BY-4.0 | yes, with attribution |
| `ace_step` (local) | MIT | yes |

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
    "ambient soundscape",  # prompt (required)
    platform="musicgen",
    duration=15,  # seconds
    temperature=1.2,  # sampling randomness
    top_k=250,  # top-k sampling
    guidance=3.0,  # classifier-free guidance
    seed=42,  # reproducibility
)
```

The full set of unified parameter names (42):

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

song.status  # 'complete'
song.platform  # 'musicgen'
song.title  # ''
song.metadata  # {'model': 'facebook/musicgen-small', ...}

# Audio is in song.audio (an AudioResult)
song.audio.audio_array  # numpy array (local models)
song.audio.audio_bytes  # raw bytes (REST APIs)
song.audio.audio_url  # URL string (Suno)
song.audio.sample_rate  # e.g. 32000
song.audio.format  # 'wav', 'mp3', etc.

# Shortcuts
song.audio_array  # same as song.audio.audio_array
song.audio_bytes  # same as song.audio.audio_bytes
song.sample_rate  # same as song.audio.sample_rate
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
    base.py              # Song, AudioResult, AFFORDANCES (42 unified params)
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
        stable_audio_25/   # Stable Audio 2.5 via fal.ai (audio-to-audio with strength)
        ace_step/          # ACE-Step via fal.ai (tags -> music, audio remix)
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
  (e.g. `duration` seconds to `music_length_ms` milliseconds for ElevenLabs)
  for platforms served by the config-generated REST adapter. A platform with its
  own `adapter.py` takes unified names directly, on every path
  (`arioso.generate` and `arioso.services.<platform>.generate` alike).
- **Leverages existing libraries.** Uses
  [ho](https://github.com/i2mint/ho) for OpenAPI-to-Python-function generation,
  [i2](https://github.com/i2mint/i2) for signature manipulation and function wrapping.
