# Mubert Platform Reference

Last updated: 2026-03-13

## Overview

[Mubert](https://mubert.com/) is an AI music generation platform with a unique approach: it uses real
musician-created loops and samples that are combined and arranged by AI. It is NOT a
neural audio synthesis model. The AI maps text prompts to tag vectors (see
[API docs](https://mubertmusicapiv3.docs.apiary.io/) for details on the tag-vector
matching approach), selects matching loops from a library of human-created sounds, and
arranges them into tracks.

All sounds in Mubert's library are created by human musicians and sound designers.

- Website: https://landing.mubert.com/
- Text-to-music: https://mubert.com/render/text-to-music
- API v3 docs: https://mubertmusicapiv3.docs.apiary.io/
- GitHub notebook: https://github.com/MubertAI/Mubert-Text-to-Music

## Prompt Engineering

### How prompts work internally

The prompt is encoded to a latent space vector via a transformer. This vector is compared
against Mubert's library of tag vectors. The closest matching tags are selected and sent
to the API to arrange corresponding loops. This means prompts are converted to TAGS
internally -- they are not used for neural synthesis.

### Effective prompting strategies

Because the system resolves prompts to tags, descriptions of mood, genre, and energy map
well to Mubert's internal tag system. Short to medium prompts work best; the transformer
encoding loses specificity with very long prompts. Musical specifics (BPM, key) should
be implied through genre and mood rather than stated explicitly.

**Good examples:**

- "calm ambient music for meditation"
- "upbeat electronic dance music"
- "chill lofi hip hop beats to study to"
- "dramatic cinematic orchestral trailer music"

**Genre terms that map well:** ambient, electronic, hip-hop, pop, rock, classical, jazz,
chill, lofi, cinematic.

**Mood terms:** calm, energetic, dark, uplifting, romantic, tense, peaceful, aggressive.

### Energy parameter mapping

The `energy` parameter (float, 0-1) is mapped to intensity levels:

- 0 -- 0.33: "low" intensity
- 0.34 -- 0.66: "medium" intensity
- 0.67 -- 1.0: "high" intensity

### Output characteristics

Since Mubert uses real musician-created loops, output quality is consistently high but
variety is limited to their sample library. Each generation produces a unique combination
and never repeats the same arrangement.

### Links

- Mubert Text-to-Music notebook: https://github.com/MubertAI/Mubert-Text-to-Music
- Mubert API docs: https://mubertmusicapiv3.docs.apiary.io/

## API Details

### Connection

- **Type:** REST API (two-step polling)
- **Base URL:** `https://api-b2b.mubert.com/v2`
- **Auth:** Personal Access Token (PAT) via `MUBERT_PAT` environment variable
- **Endpoint:** `POST /RecordTrackTTM` (initiate + poll)

### Output format

- MP3 or WAV, 44.1 kHz
- Returns a URL to the generated audio

### Parameters

| Parameter       | Type   | Default | Range / Values       | Description                        |
|-----------------|--------|---------|----------------------|------------------------------------|
| prompt          | str    | --      | required             | Text description of desired music  |
| duration        | float  | 30      | 15 -- 1500 seconds   | Track duration                     |
| output_format   | str    | "mp3"   | "wav", "mp3"         | Audio output format                |
| bitrate         | int    | 320     | 128, 320             | Audio bitrate (kbps)               |
| energy          | float  | --      | 0 -- 1               | Mapped to intensity (low/med/high) |

### Polling behavior

| Parameter            | Default | Description                          |
|----------------------|---------|--------------------------------------|
| wait_for_completion  | --      | Whether to poll until done           |
| poll_interval        | 5s      | Seconds between status checks        |
| timeout              | 300s    | Maximum wait time before giving up   |

## arioso Adapter Notes

The arioso adapter for Mubert lives in `adapter.py` alongside this file. It wraps the
two-step polling flow (initiate generation, then poll until the track URL is available)
into the common arioso generation interface.

Duration supports very long tracks -- up to 25 minutes (1500 seconds).

## Further Reading

- [Mubert API v3 documentation](https://mubertmusicapiv3.docs.apiary.io/)
- [Mubert Text-to-Music Colab notebook](https://github.com/MubertAI/Mubert-Text-to-Music)
- [MTG-Jamendo dataset](https://github.com/MTG/mtg-jamendo-dataset) -- relevant tag taxonomy for understanding Mubert's tag system
