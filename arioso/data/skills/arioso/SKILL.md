---
name: arioso
description: >-
  Generate music with AI using the `arioso` package — one Python interface over
  16 music-generation backends (Suno, ElevenLabs Music, Udio, YuE, ACE-Step, MusicGen,
  Stable Audio, Stable Audio 2.5, Riffusion, Harmonai, Lyria, Mubert, Beatoven,
  Loudly, Jen).
  Use when the user wants to "make a song", "generate music", "write a song
  about X", "turn this poem/text/script into a song", "set these lyrics to
  music", "text to music", "make a theme tune", "I need background music", or
  "a royalty-free instrumental track" — or when they name a platform (Suno,
  ElevenLabs Music, Udio, MusicGen, Stable Audio, Riffusion, Lyria). Covers the
  one-line call, which five backends can actually SING lyrics you wrote (the
  other eleven drop them silently), the Suno customMode title/genre requirement,
  which backends are free versus paid, polling an async job, and writing the
  audio to disk.
metadata:
  audience: users
---

# Making a song with arioso

`arioso` is a facade: one `generate()` call, sixteen backends behind it. It is a
**Python library only — there is no CLI**. Everything below is `import arioso`.

Two questions decide everything else. Answer them before you write any code.

1. **Does it have to sing words the user wrote?** Only **five** of the sixteen
   backends can. Get this wrong and you get a pleasant instrumental and no error.
2. **Are you allowed to spend money?** arioso has **no cost gate, no
   `estimate()`, and no confirmation prompt.** A `generate()` call to a paid
   backend spends the user's credit the moment it runs.

## The shortest thing that works (free, local, instrumental)

```python
import arioso

song = arioso.generate("upbeat jazz piano trio, brushed drums", duration=15)
# platform defaults to "musicgen": runs on this machine, no API key

import soundfile as sf

sf.write("out.wav", song.audio_array, song.sample_rate)
```

Needs `pip install 'arioso[musicgen]'` (pulls torch) and downloads model weights
on the first call. Use this whenever the ask is *background music*, *a bed*, *a
loop*, *an instrumental* — it costs nothing and needs no account.

## Setting words to music

**Only these five platforms accept `lyrics=`:**

| Platform | `platform=` | Key | Sings your words? |
|---|---|---|---|
| Suno (via sunoapi.org) | `"sunoapi"` | `SUNO_API_KEY` | yes — the usual choice |
| ElevenLabs Music | `"elevenlabs"` | `ELEVENLABS_API_KEY` | yes |
| Udio (unofficial wrapper) | `"udio"` | `UDIO_AUTH_COOKIE` | yes |
| YuE (via fal.ai) | `"yue"` | `FAL_KEY` | yes |
| ACE-Step (via fal.ai) | `"ace_step"` | `FAL_KEY` | yes (empty lyrics = instrumental) |

The other eleven — `musicgen`, `stable_audio`, `stable_audio_25`, `harmonai`,
`riffusion`, `lyria2`, `lyria_rt`, `mubert`, `beatoven`, `loudly`, `jen` — **do not**. Every adapter
takes `**kwargs`, so `lyrics=` lands there and is **dropped silently**: no
warning, no error, a normal-looking `Song` with no vocals. (The
`on_unsupported_param: "warn"` in the configs only fires on the config-driven
REST path, and all 16 platforms ship a custom adapter, so nothing reaches it.)

Check rather than remember:

```python
"lyrics" in arioso.get_platform_info("mubert")["supported_affordances"]  # False
```

## MUST: with `lyrics=` on Suno, always pass `title=` and `genre=`

Passing any of `lyrics` / `genre` / `title` flips the Suno adapter into
**customMode**, where the API documents `style` **and** `title` as *required*.
The adapter fills `style` for you (`genre or prompt`) but writes `title` **only
if you passed one**. So `lyrics=` alone produces a request the API rejects.

```python
songs = arioso.generate_many(
    "slow chanson, spare piano, rain",  # becomes `style` if genre is omitted
    platform="sunoapi",
    lyrics=poem_text,
    title="Il pleut",  # REQUIRED in customMode — the adapter will not invent one
    genre="chanson, ambient, french",  # sets `style` explicitly; do this too
    model="V5",
)
```

Three more Suno rules in the same family:

- **`instrumental=True` discards `lyrics`.** The adapter only sends lyrics
  `if not instrumental`. Never pass both.
- **Length caps depend on the model, and the default model is `V4`** — the
  tightest one. Lyrics: 3,000 chars on V4, 5,000 on everything later. Style:
  200 on V4, 1,000 later. Title: 80 on V4 and `V4_5ALL`, 100 on
  `V4_5`/`V4_5PLUS`/`V5`. Pass `model="V5"` (or set `SUNO_DEFAULT_MODEL`) for a
  long poem. Valid values: `V4`, `V4_5`, `V4_5ALL`, `V4_5PLUS`, `V5`.
- **A rejected lyric fails at poll time, not call time** — `get_status` raises
  `RuntimeError` with `SENSITIVE_WORD_ERROR` once the job has run.

## Suno is asynchronous — you get two pending songs, not audio

`generate_many` returns immediately with **two** `Song`s, `status="pending"`,
carrying only a task id. Nothing is downloaded yet.

Simplest: let the adapter block for you.

```python
songs = arioso.generate_many(
    "chanson, spare piano",
    platform="sunoapi",
    lyrics=poem_text,
    title="Il pleut",
    genre="chanson",
    model="V5",
    wait_for_completion=True,
    timeout=600,  # default is 300s; Suno often needs more
)
```

Or poll yourself, which is what you want if you need to report progress:

```python
from arioso.tools import poll_status, download_songs

pending = arioso.generate_many(...)  # as above, without wait_for_completion
task_id = pending[0].id

done = poll_status(task_id, adapter="sunoapi", poll_interval=15, timeout=900)
paths = download_songs(done, "out/", name_prefix="il_pleut", adapter="sunoapi")
```

`arioso.check_status(song)` is the single-shot version (it returns a **list**).
`poll_status` loops until every song reads `complete` and raises `TimeoutError`
otherwise.

## Getting audio onto disk — there is no `song.save()`

What you get back differs per backend. Look at the field that is populated.

| Backends | `Song` field | How to write it |
|---|---|---|
| `sunoapi`, `udio`, `mubert`, `beatoven`, `loudly`, `jen` | `audio_url` | `arioso.fetch_audio(song)` first, then write `.audio_bytes` |
| `elevenlabs`, `lyria2`, `lyria_rt`, `yue`, `stable_audio_25`, `ace_step` | `audio_bytes` | write the bytes directly |
| `musicgen`, `stable_audio`, `riffusion`, `harmonai` | `audio_array` | `soundfile.write(path, arr, song.sample_rate)` |

```python
song = arioso.fetch_audio(song)  # url -> bytes (no-op cost, but it downloads)
with open("song.mp3", "wb") as f:
    f.write(song.audio_bytes)
```

`fetch_audio` raises `ValueError` if `audio_url` is still empty — that means the
job is not finished, so poll first.

## Free versus paid — say so before you spend

| Free (local inference, no key, no account) | Paid / metered (needs a key) |
|---|---|
| `musicgen`, `stable_audio`, `riffusion`, `harmonai` | `sunoapi`, `elevenlabs`, `udio`, `yue`, `stable_audio_25`, `ace_step`, `lyria2`, `lyria_rt`, `mubert`, `beatoven`, `loudly`, `jen` |

The free four need a heavy install (`torch`, `diffusers`/`audiocraft`) and real
CPU/GPU time, but cost nothing and send nothing anywhere.

**Because arioso has no cost gate, the gate is you.** Before the first call to a
paid backend, tell the user which platform you are about to use, that it draws
on their account, and that Suno returns **two** songs per call — then get
agreement. Suno via sunoapi.org is credit-based on top of a subscription;
arioso cannot quote a per-call price, so do not invent one.

Never retry a failed paid call blind. A `generate` that reached the API has
already consumed credit even if polling later fails; re-check with
`check_status(song)` before generating again.

## Writing the prompt

The prompt is the *style*, not the story: instrumentation, tempo feel, era,
production, vocal type. Keep the narrative in `lyrics`.

arioso ships a ledger of sonic descriptions you can look up by name, so you can
describe an artist's sound without naming them (many services reject that):

```python
from arioso.named_prompts import named_prompts, search

named_prompts.artists["billie_eilish"]  # a prompt-safe description of the sound
search("jazz")  # across artists / moods / genres / instruments / decades / vocals
```

Categories: `artists`, `decades`, `genres`, `instruments`, `moods`,
`production`, `scenes`, `vocals`. Add your own with
`arioso.named_prompts.add_prompt(...)`; user entries overlay the shipped ones.

## Picking a platform when it is not obvious

```python
arioso.list_platforms()
arioso.get_platform_info("elevenlabs")  # auth, supported_affordances, output
arioso.supports_audio_input("stable_audio")  # can it take audio IN? -> True
```

| The ask | Use |
|---|---|
| A full song that sings the user's words | `sunoapi` (paid) |
| Same, but one synchronous call returning bytes | `elevenlabs` (paid) |
| Background bed / loop / instrumental, free | `musicgen` |
| Free, texture / sound-design rather than a tune | `stable_audio` |
| Transform audio the user already has | `arioso.enhance(audio, prompt)` — see below |
| The same piece, subtly changed (a strength knob) | `enhance(..., platform="stable_audio_25", strength=0.2-0.5)` (paid, fal) |
| Remix existing audio toward style tags | `enhance(..., platform="ace_step")` (paid, fal) |

`arioso.enhance(audio, "warm analog studio band")` routes existing audio into
whichever conditioning affordance the platform has (`audio_input` / `melody` /
`reference_audio`). It accepts a `Song`, bytes, a path, an `(array, rate)` pair
or a waveform. Only some platforms take input audio — check
`supports_audio_input` first.

Audio-in platforms: `stable_audio` (local, no strength knob), `stable_audio_25`
(fal; `strength` 0-1, lower keeps more of the input), `ace_step` (fal remix),
`musicgen` (melody only, local, 30 s max), `sunoapi` (`upload_cover` /
`upload_extend`), `yue` (vocal prompt), `udio`.

**Suno refuses copyrighted material on upload**, and not only the recording:
an upload-cover of a synthesized render of a copyrighted *score* fails too,
with `[413] This audio matches an existing recording in our catalog.` at poll
time. Suno matches the *composition* (melody, harmony, structure), not just the
recording, so no re-render or re-performance gets through. The fal-hosted
platforms did not check (2026-10). Why, and what to expect: [research note](https://github.com/thorwhalen/arioso/blob/main/misc/docs/research/general/music-gen-upload-copyright-detection.md).

## Three levels of control

```python
arioso.generate("jazz", platform="sunoapi")  # 1. facade, unified names
arioso.services.sunoapi.native_generate(...)  # 2. the adapter's own signature
arioso.services.sunoapi.upload_file(path)  # 3. platform-only methods
```

Level 2 and 3 exist for the things the unified vocabulary does not cover —
Suno's `upload_extend` / `upload_cover`, its local task store
(`arioso.services.sunoapi.adapter.tasks.last(10)`), and so on.

## When it goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| Song has no vocals though you passed `lyrics` | the platform is not one of the four | check `supported_affordances`; switch to `sunoapi` |
| Suno rejects the request outright | customMode with no `title` | always pass `title=` alongside `lyrics=` |
| Lyrics ignored on Suno specifically | `instrumental=True` was also passed | drop `instrumental` |
| Long poem truncated | default model is `V4` (3,000 chars) | `model="V5"` |
| `ValueError: ... has no audio_url` | job not finished | `poll_status` / `check_status` before `fetch_audio` |
| `TimeoutError` after 300s | Suno is slower than the default | raise `timeout=` (600–900) |
| `RuntimeError ... SENSITIVE_WORD_ERROR` | the lyric or style tripped a filter | reword and regenerate; that attempt still cost credit |
| `song.audio_bytes` is `None` on a local model | local models return arrays | use `song.audio_array` + `soundfile.write` |

## Rules you must not break

- **Never call a paid backend without saying so first.** Nothing in arioso will
  stop you, and one call to Suno bills for two songs.
- **Never assume `lyrics=` was honoured.** It is silent when unsupported. Check
  `supported_affordances`, or check the audio.
- **Never pass `lyrics` without `title` on Suno**, and never with
  `instrumental=True`.
- **Never install every extra.** `import arioso` is light; each platform's deps
  are an extra (`pip install 'arioso[sunoapi]'`, `'arioso[musicgen]'`, ...) and
  lazy-imported at first use.
