# Loudly Platform Reference

Last updated: 2026-03-13

## Overview

[Loudly](https://loudly.com/) is an AI music generation platform with an enterprise API. It uses natural
language processing and deep generative audio models to produce 100% copyright-safe,
royalty-free output with perpetual licenses. The platform includes text-to-music,
parametric generation, stem extraction, and AI playlists, along with a catalog of 3,500
pre-made tracks.

- Website: https://www.loudly.com/
- API page: https://www.loudly.com/music-api
- Knowledge base: https://www.loudly.com/knowledge-base
- Developer docs: https://www.loudly.com/knowledge-base/ai-music-api-developers
- [Loudly developers page](https://loudly.com/developers)
- Output: lossless WAV files, studio quality
- 500+ expert text prompts available, 1000+ pre-set prompts
- 2025 updates: expanded stem-splitter, pay-as-you-go pricing, Healing Frequencies v1.0

## Prompt Engineering

### How prompts work

Loudly uses NLP to parse prompts, extracting tone, mood, and pacing cues. The platform
provides 500+ curated expert prompts as examples and templates.

### Effective prompting strategies

For best results, use a natural language prompt for mood and context, then specify genre,
BPM, and instruments as explicit parameters. The `genre` parameter provides more precise
control than genre terms embedded in the prompt text, because it maps directly to
Loudly's internal genre taxonomy (50+ genres).

**Good examples:**

- "ambient synth track for a sci-fi game"
- "upbeat electronic track with moody synths"

### Combining prompts with parameters

Loudly supports refining results by combining text prompts with structured parameter
controls:

- **genre:** 50+ available genres for precise genre targeting
- **bpm:** Direct tempo control
- **instruments:** Up to 7 instrument names per track
- **energy:** Float 0--1 for direct intensity control
- **structure:** Section-level control for song structure

### Unique: structured generation

Loudly supports section-level structure control, allowing you to define the arrangement
of a track (intro, verse, chorus, bridge, outro, etc.).

### Links

- AI Music Creation Guide: https://www.loudly.com/knowledge-base/ai-music-creation-guide
- Features and Tips: https://www.loudly.com/knowledge-base/loudly-features-and-tips

## API Details

### Connection

- **Type:** REST API
- **Base URL:** `https://api.loudly.com/api`
- **Auth:** Bearer token via `LOUDLY_API_KEY` environment variable

### Endpoints

| Method | Path              | Purpose                        |
|--------|-------------------|--------------------------------|
| POST   | /music/generate   | Initiate generation            |
| GET    | /music/{track_id} | Poll for audio URL             |

### Output format

- MP3, 44.1 kHz
- Returns a URL to the generated audio

### Parameters

| Parameter    | Type        | Default | Range / Values  | Description                         |
|--------------|-------------|---------|-----------------|-------------------------------------|
| prompt       | str         | --      | required        | Text description of desired music   |
| duration     | float       | --      | --              | Track duration in seconds           |
| genre        | str         | --      | 50+ genres      | Genre tag                           |
| bpm          | int         | --      | --              | Tempo (maps to "tempo")             |
| key          | str         | --      | --              | Musical key                         |
| energy       | float       | --      | 0 -- 1          | Energy / intensity level            |
| instruments  | list[str]   | --      | up to 7         | Instrument names                    |
| structure    | list        | --      | --              | Song section structure              |

## arioso Adapter Notes

The arioso adapter for Loudly lives in `adapter.py` alongside this file. It wraps the
two-step flow (initiate generation, poll for audio URL) into the common arioso generation
interface.

Loudly's parametric controls (genre, bpm, key, instruments, structure) offer more
fine-grained musical control than most other platforms in arioso.

## Further Reading

- [Loudly developers](https://loudly.com/developers)
- [MusicSmith AI music generation prompts guide](https://musicsmith.ai/blog/ai-music-generation-prompts-best-practices)
- [AudioSet ontology](https://research.google.com/audioset/ontology/index.html) -- useful context for genre and instrument vocabulary
