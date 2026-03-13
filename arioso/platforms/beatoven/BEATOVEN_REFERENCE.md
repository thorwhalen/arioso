# Beatoven.ai Platform Reference

Last updated: 2026-03-13

## Overview

[Beatoven.ai](https://www.beatoven.ai/) is an ethical AI music generation platform. Its foundation model, "maestro"
(released 2025/2026), was trained on 3 million+ ethically sourced and licensed music and
sound effects tracks. It supports text-to-music, video-to-music, and sound effects
generation.

- Website: https://www.beatoven.ai/
- API page: https://www.beatoven.ai/api
- Developer dashboard: https://sync.beatoven.ai/apiDashboard
- Maestro model blog: https://www.beatoven.ai/blog/introducing-maestro/
- Also available on fal.ai: https://blog.fal.ai/beatoven-ais-maestro-model-is-now-live-on-fal/
- Also available on Make.com for no-code workflows

## Prompt Engineering

### Prompt structure

Beatoven encourages specificity. The recommended prompt structure is:

**context + mood + genre + instrumentation + tempo + emotional progression**

### Good examples

- "Uplifting corporate background music with light acoustic guitar, subtle piano, and
  gentle percussion, moderate tempo, building in energy"
- "Dark ambient soundscape for a horror game, sparse dissonant strings, eerie pads, low
  rumbling bass"

### Creativity parameter

The `guidance` parameter in arioso maps to Beatoven's
"[creativity](https://arxiv.org/abs/2207.12598)" setting (based on classifier-free
guidance):

- **Lower values:** More creative and unexpected results
- **Higher values (default 16):** More literal prompt following

### Negative prompts

Use `negative_prompt` to exclude unwanted elements:

- "no vocals, no heavy drums"

### Looping

The `looping` parameter is unique to Beatoven. Enable it when generating background
music that needs to seamlessly loop (games, apps, ambient environments).

### Refinement steps

The `num_steps` parameter controls quality vs. speed:

- Higher values produce better quality but take longer
- Default of 100 is a good balance

### Output characteristics

Trained on licensed music, so output tends to be "safe" and commercially viable. Best
suited for: corporate videos, podcasts, games, apps, social media content.

### Links

- Maestro model blog: https://www.beatoven.ai/blog/introducing-maestro/
- fal.ai integration: https://blog.fal.ai/beatoven-ais-maestro-model-is-now-live-on-fal/

## API Details

### Connection

- **Type:** REST API (three-step: create, poll, fetch)
- **Base URL:** `https://api.beatoven.ai/api/v1`
- **Auth:** Bearer token via `BEATOVEN_API_KEY` environment variable

### Endpoints

| Method | Path                         | Purpose                        |
|--------|------------------------------|--------------------------------|
| POST   | /tracks                      | Create track, returns track_id |
| GET    | /tracks/{track_id}           | Poll status ("composed" = ready) |
| GET    | /tracks/{track_id}/audio     | Fetch audio URL                |

### Output format

- MP3, 44.1 kHz
- Returns a URL to the generated audio

### Parameters

| Parameter       | Type   | Default | Range / Values       | Description                           |
|-----------------|--------|---------|----------------------|---------------------------------------|
| prompt          | str    | --      | required             | Text description of desired music     |
| duration        | float  | 30      | 5 -- 150 seconds     | Track duration                        |
| negative_prompt | str    | --      | optional             | Elements to avoid in generation       |
| seed            | int    | --      | optional             | Random seed for reproducibility       |
| guidance        | float  | 16      | --                   | Creativity scale (maps to "creativity") |
| num_steps       | int    | 100     | --                   | Refinement steps (quality vs. speed)  |
| looping         | bool   | --      | --                   | Enable loopable audio (ENABLE_LOOPING) |

### Polling behavior

| Parameter            | Default | Description                          |
|----------------------|---------|--------------------------------------|
| wait_for_completion  | --      | Whether to poll until done           |
| poll_interval        | 5s      | Seconds between status checks        |
| timeout              | 300s    | Maximum wait time before giving up   |

## arioso Adapter Notes

The arioso adapter for Beatoven lives in `adapter.py` alongside this file. It wraps the
three-step flow (create track, poll for "composed" status, fetch audio URL) into the
common arioso generation interface.

Duration range is 5--150 seconds, significantly shorter than some other platforms.

## Further Reading

- [Beatoven API docs](https://beatoven.ai/api)
- [Beatoven GitHub SDK](https://github.com/Beatoven/public-api)
- [Beatoven on fal.ai](https://fal.ai/models/fal-ai/beatoven)
