# ElevenLabs Music Generation API Reference

Last updated: 2026-03-13

## Overview

[ElevenLabs](https://elevenlabs.io/) Music Generation API uses model `music_v1` to produce music from text
prompts. ElevenLabs is known primarily for voice synthesis and TTS, and has
expanded into music generation with structured composition support, lyrics, and
C2PA watermarking.

- **Website:** https://elevenlabs.io/music
- **API docs:** https://elevenlabs.io/docs/api-reference/music/create-music
- **Duration range:** 3--600 seconds
- **Output:** MP3, 44.1 kHz

---

## Prompt Engineering

Prompts follow a **layered structure**, with the most important descriptors first
([ElevenLabs prompt guide](https://fal.ai/learn/biz/eleven-music-prompt-guide),
[MusicSmith best practices](https://musicsmith.ai/blog/ai-music-generation-prompts-best-practices)):

1. **Genre and mood** -- "Upbeat indie pop, cheerful and nostalgic"
2. **Instrumentation** -- "with jangly electric guitars, driving drums, and
   bright synth pads"
3. **Technical specs** -- "120 BPM, in G major, 4/4 time signature"

### Tips

- The keyword `solo` is powerful for instrument isolation: "solo piano",
  "solo acoustic guitar".
- Section-by-section descriptions work well when using the `composition_plan`
  structure.
- Lyrics: provide lyrics text and the model will attempt to sing them.
- BPM in the prompt text is understood and roughly followed.
- Key/scale specifications have moderate effect.
- Time signatures can be specified, but complex meters (5/4, 7/8) are less
  reliable.
- For instrumental tracks: set `instrumental=True` **and** include
  "instrumental" in the prompt for best results. Negative phrasing like
  "no vocals" is less reliable than the flag.
- Longer durations (>60 s) benefit from a `composition_plan` with explicit
  sections.

### Vocabulary that works well

| Category     | Examples                                                                  |
|--------------|---------------------------------------------------------------------------|
| Genres       | pop, rock, jazz, classical, electronic, ambient, R&B, hip-hop, folk, country, metal, funk |
| Moods        | upbeat, melancholic, energetic, calm, dramatic, mysterious, romantic, aggressive |
| Instruments  | guitar, piano, drums, bass, synthesizer, strings, brass, woodwinds, percussion, organ |
| Production   | clean, distorted, reverb-heavy, compressed, spacious, intimate, lo-fi, hi-fi, vinyl crackle, studio quality, warm analog |

---

## API Details

| Field         | Value                                       |
|---------------|---------------------------------------------|
| Type          | [REST API](https://elevenlabs.io/docs/overview/capabilities/music) |
| Base URL      | `https://api.elevenlabs.io`                 |
| Endpoint      | `POST /v1/music`                            |
| Auth          | API key via `ELEVENLABS_API_KEY` env var, sent as header `xi-api-key` |
| Output format | MP3 bytes, 44.1 kHz                         |

### Parameters

| Parameter       | Type   | Default            | Notes                                           |
|-----------------|--------|--------------------|-------------------------------------------------|
| `prompt`        | str    | (required)         | Text description of the desired music            |
| `duration`      | float  | 30.0               | Range 3--600 s. Maps to `music_length_ms`        |
| `instrumental`  | bool   | --                 | Maps to `force_instrumental`                     |
| `model`         | str    | `"music_v1"`       |                                                  |
| `output_format` | str    | `"mp3_44100_128"`  | 21 format variants available                     |
| `lyrics`        | str    | --                 | Builds `composition_plan.sections`               |
| `title`         | str    | --                 | Sets `composition_plan.title`                    |
| `structure`     | list   | --                 | Sets `composition_plan.sections`                 |
| `watermark`     | bool   | --                 | C2PA watermark via `sign_with_c2pa`              |
| `seed`          | int    | --                 | Random seed (streaming endpoint only)            |

---

## Links and Further Reading

- [ElevenLabs Music docs](https://elevenlabs.io/docs/overview/capabilities/music)
- [API Reference](https://elevenlabs.io/docs/api-reference)
- [Music creation endpoint](https://elevenlabs.io/docs/api-reference/music/create-music)
- [ElevenLabs Music home](https://elevenlabs.io/music)
- [OpenAPI spec](https://api.elevenlabs.io/openapi.json)
- [ElevenLabs Python SDK (PyPI)](https://pypi.org/project/elevenlabs/)
- [ElevenLabs MCP server](https://github.com/elevenlabs/elevenlabs-mcp)
- [ElevenLabs prompt guide (fal.ai)](https://fal.ai/learn/biz/eleven-music-prompt-guide)
- [MusicSmith AI music generation best practices](https://musicsmith.ai/blog/ai-music-generation-prompts-best-practices)
- [awesome-music-prompts](https://github.com/yzfly/awesome-music-prompts)
