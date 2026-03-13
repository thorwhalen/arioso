# Google DeepMind Lyria 2 Reference

Last updated: 2026-03-13

## Overview

Lyria 2 (`lyria-002`) is [Google DeepMind](https://deepmind.google/)'s high-quality music generation model,
accessed through [Google Cloud Vertex AI](https://cloud.google.com/vertex-ai). It generates fixed **30-second** audio
clips from text prompts. The model builds on DeepMind's Lyria family and uses a
[MuLan](https://arxiv.org/abs/2208.12415)-based text-music alignment encoder.

- **Model ID:** `lyria-002`
- **Platform:** [Google Cloud Vertex AI](https://cloud.google.com/vertex-ai)
- **Output:** WAV, 48 kHz, fixed 30-second duration
- **Vocals:** Not supported -- best used for instrumental music

---

## Prompt Engineering

Lyria 2 responds best to **natural language descriptions**, not tag lists.
Describe the music as if explaining it to a listener
([Google Lyria prompt guide](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/music/music-gen-prompt-guide)).

### Structure and length

- **Medium-length prompts (2--4 sentences)** work best.
- Too short: the model produces generic results.
- Too long: the model may lose coherence or ignore parts.

### Examples

- "A warm, nostalgic folk song with acoustic guitar fingerpicking, soft
  harmonica, and a gentle male vocal humming along"
- "An intense orchestral piece building from a quiet string tremolo to a full
  brass fanfare"

### What works

| Attribute       | Effectiveness | Notes                                                |
|-----------------|---------------|------------------------------------------------------|
| Genre/style     | High          | Standard genre names align well with training data   |
| Instruments     | High          | Common instruments are reliably rendered             |
| Mood/emotion    | High          | Emotional adjectives are well understood             |
| Tempo (words)   | Moderate      | "fast", "slow", "moderate" -- exact BPM less reliable|
| Dynamics         | Moderate      | "quiet", "loud", "building", "fading"               |
| Music theory    | Low           | Specific chord progressions are unreliable           |

### Negative prompts

Negative prompts (`negative_prompt` parameter) are supported and useful for
excluding unwanted elements (e.g., "drums", "vocals", "distortion").

### Important constraints

- Output is always 30 seconds. Prompts should describe what you want within
  that window.
- The text encoder is based on [MuLan](https://arxiv.org/abs/2208.12415) -- vocabulary from MuLan's training data
  works best. Stick to standard genre names, common instruments, and emotional
  adjectives.

---

## API Details

| Field      | Value                                                                                           |
|------------|-------------------------------------------------------------------------------------------------|
| Type       | REST API ([Vertex AI](https://cloud.google.com/vertex-ai))                                      |
| Base URL   | `https://{location}-aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/publishers/google/models/{model}:predict` |
| Auth       | Bearer token via `GOOGLE_CLOUD_API_KEY`; falls back to `google-auth` SDK                        |
| Env vars   | `GOOGLE_CLOUD_PROJECT` (required), `GOOGLE_CLOUD_LOCATION` (default `"us-central1"`)            |
| Output     | WAV bytes (base64-encoded), 48 kHz, fixed 30 s                                                  |

### Parameters

| Parameter        | Type   | Default          | Notes                              |
|------------------|--------|------------------|------------------------------------|
| `prompt`         | str    | (required)       | Text description                   |
| `negative_prompt`| str    | `""`             | Elements to exclude                |
| `seed`           | int    | --               | Random seed for reproducibility    |
| `model`          | str    | `"lyria-002"`    |                                    |
| `batch_size`     | int    | 1                | Maps to `sampleCount`              |

---

## Links and Further Reading

- [Google Cloud Vertex AI](https://cloud.google.com/vertex-ai)
- [Google Lyria prompt guide](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/music/music-gen-prompt-guide)
- [Vertex AI SDK (PyPI)](https://pypi.org/project/google-cloud-aiplatform/)
- [MuLan paper (text encoder basis)](https://arxiv.org/abs/2208.12415)
- [MusicCaps dataset](https://huggingface.co/datasets/google/MusicCaps)
- [LP-MusicCaps dataset](https://huggingface.co/datasets/seungheondoh/LP-MusicCaps-MSD)
- [AudioSet ontology](https://research.google.com/audioset/ontology/index.html)
- [Google AI documentation](https://ai.google.dev/)
- [MusicSmith AI music generation best practices](https://musicsmith.ai/blog/ai-music-generation-prompts-best-practices)
- [awesome-music-prompts](https://github.com/yzfly/awesome-music-prompts)
