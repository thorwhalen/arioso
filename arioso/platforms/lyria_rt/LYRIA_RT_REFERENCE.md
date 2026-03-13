# Google Lyria RealTime Reference

Last updated: 2026-03-13

## Overview

[Lyria RealTime](https://ai.google.dev/gemini-api/docs/music-generation) (`lyria-realtime-exp`) is [Google](https://ai.google.dev/)'s real-time streaming music
generation model. Unlike Lyria 2, it produces a continuous PCM audio stream via
WebSocket sessions, allowing live parameter changes (BPM, key, energy,
brightness) during generation. It is accessed through the [`google-genai`](https://pypi.org/project/google-genai/) Python
SDK.

- **Model ID:** `models/lyria-realtime-exp`
- **SDK:** [`google-genai`](https://pypi.org/project/google-genai/) (async streaming)
- **Output:** PCM audio, 48 kHz, 16-bit mono
- **Best for:** Background music, interactive experiences, live performances,
  gaming

---

## Prompt Engineering

Lyria RealTime differs from Lyria 2 because it has **explicit parameter
controls** for musical specifics. Prompts can therefore be simpler -- they
describe the style and genre, while parameters handle BPM, key, energy, and
brightness ([Google Lyria prompt guide](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/music/music-gen-prompt-guide)).

### Prompt guidelines

- Keep prompts **short (1--2 sentences)**. Describe a continuous mood or style,
  not a composition arc.
- Standard genre terms and mood adjectives work best.
- When BPM or key is specified both in the prompt text and as a parameter, **the
  parameter takes precedence**.

### Examples

| Prompt                   | Parameters                                          |
|--------------------------|-----------------------------------------------------|
| "upbeat jazz"            | `bpm=140, key="Bb_MAJOR", energy=0.7`               |
| "ambient electronic"     | `bpm=80, key="D_MINOR", energy=0.3, brightness=0.4` |
| "driving rock"           | `bpm=130, key="E_MINOR", energy=0.9, brightness=0.8`|

### Parameter semantics

| Parameter     | Range   | Effect                                                    |
|---------------|---------|-----------------------------------------------------------|
| `energy`      | 0--1    | Density of musical events. 0 = sparse, 1 = dense.        |
| `brightness`  | 0--1    | High-frequency content. 0 = dark/warm, 1 = bright/crisp. |
| `guidance`    | 0--6    | 0--2: loose/creative. 3--4: balanced (default). 5--6: strict prompt following. Related to [classifier-free guidance](https://arxiv.org/abs/2207.12598). |
| `temperature` | 0--3    | 0.5--0.8: predictable. 1.0--1.5: good variety (default range). 2.0--3.0: very creative, potentially chaotic. |

---

## API Details

| Field         | Value                                              |
|---------------|----------------------------------------------------|
| Type          | Python library (async streaming via [`google-genai`](https://pypi.org/project/google-genai/)) |
| Auth          | API key via `GOOGLE_API_KEY` env var                |
| Model         | `models/lyria-realtime-exp`                         |
| Output        | PCM bytes, 48 kHz, 16-bit mono                      |

### Parameters

| Parameter       | Type   | Default  | Notes                                          |
|-----------------|--------|----------|-------------------------------------------------|
| `prompt`        | str    | (required)| Style/genre description                        |
| `duration`      | float  | 10.0     | Seconds of audio to collect                     |
| `bpm`           | int    | --       | Range 60--200                                   |
| `key`           | str    | --       | Enum, 24 options (see below)                    |
| `energy`        | float  | --       | Range 0--1                                      |
| `brightness`    | float  | --       | Range 0--1                                      |
| `guidance`      | float  | 4.0      | Range 0--6                                      |
| `temperature`   | float  | 1.1      | Range 0--3                                      |
| `top_k`         | int    | 40       | Range 1--1000                                   |
| `seed`          | int    | --       | Range 0--2,147,483,647                          |
| `prompt_weight`  | float  | --       | Weight for `WeightedPrompt`                     |

### Key enum values

C_MAJOR, C_MINOR, C#_MAJOR, C#_MINOR, D_MAJOR, D_MINOR, D#_MAJOR, D#_MINOR,
E_MAJOR, E_MINOR, F_MAJOR, F_MINOR, F#_MAJOR, F#_MINOR, G_MAJOR, G_MINOR,
G#_MAJOR, G#_MINOR, A_MAJOR, A_MINOR, A#_MAJOR, A#_MINOR, B_MAJOR, B_MINOR

---

## Links and Further Reading

- [Lyria RealTime docs (Gemini API)](https://ai.google.dev/gemini-api/docs/music-generation)
- [Google Lyria prompt guide](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/music/music-gen-prompt-guide)
- [`google-genai` SDK (PyPI)](https://pypi.org/project/google-genai/)
- [Google AI Studio (Lyria RealTime access)](https://aistudio.google.com/)
- [Google Cloud Vertex AI](https://cloud.google.com/vertex-ai)
- [Classifier-free guidance paper](https://arxiv.org/abs/2207.12598)
- [MusicSmith AI music generation best practices](https://musicsmith.ai/blog/ai-music-generation-prompts-best-practices)
- [awesome-music-prompts](https://github.com/yzfly/awesome-music-prompts)
