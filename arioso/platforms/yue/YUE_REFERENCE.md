# YuE Platform Reference

Last updated: 2026-03-13

## Overview

[YuE](https://github.com/multimodal-art-projection/YuE) is an open foundation model for full-song music generation, developed by HKUST / M-A-P
(multimodal-art-projection) with support from moonshot.ai, ByteDance, 01.ai, and Geely.
It generates complete songs with vocals and accompaniment from genre tags and lyrics
(lyrics2song). Output can last several minutes and spans diverse genres, languages
(English, Mandarin, Cantonese, Japanese, Korean), and vocal techniques.

The model uses a two-stage pipeline:
- **Stage 1** -- A [LLaMA-2](https://arxiv.org/abs/2307.09288)-based LLM generates musical structure and composition tokens.
- **Stage 2** -- An [EnCodec](https://github.com/facebookresearch/encodec)-based audio codec model renders those tokens into waveform audio.

| Item | Link |
|------|------|
| Paper | [YuE: Scaling Open Foundation Models for Long-Form Music Generation](https://arxiv.org/abs/2503.08638) (March 2025) |
| GitHub | <https://github.com/multimodal-art-projection/YuE> |
| Project page | <https://map-yue.github.io/> |
| GPU-poor variant | <https://github.com/deepbeepmeep/YuEGP> |

---

## Prompt Engineering

YuE takes **two separate text inputs**. Getting both right is critical to output quality.

### 1. Genre Tags (`prompt` / `genre_txt`)

Genre tags are **space-separated descriptor words**, not free-form prose. Five component
categories should ideally all be present:

| Component | Examples |
|-----------|----------|
| Genre | pop, rock, jazz, electronic, hip-hop, R&B, folk, classical, metal, ambient |
| Instrument | acoustic, electronic, guitar, piano, synth, strings |
| Mood | uplifting, melancholic, dark, energetic, calm, aggressive, romantic |
| Gender | male, female |
| Timbre | bright, warm, airy, deep, husky, smooth, raspy |

**Example tags:**

```
inspiring female uplifting pop airy vocal electronic bright vocal
```

```
dark male aggressive rock heavy guitar distorted vocal
```

The model accepts open vocabulary but the authors provide a list of the **top 200 most
commonly used tags**. Using tags from that list produces the most stable results.

Language-specific tags: use `Mandarin` or `Cantonese` to distinguish Chinese language
variants.

### 2. Lyrics (`lyrics` / `lyrics_txt`)

Structure lyrics with section labels and double-newline separators:

```
[verse]
Walking down the street at night
Stars above are shining bright

[chorus]
We are the dreamers of tomorrow
Living through the joy and sorrow

[verse]
Morning comes with golden light
Everything will be alright

[chorus]
We are the dreamers of tomorrow
Living through the joy and sorrow
```

Rules and tips:
- Supported section labels: `[verse]`, `[chorus]`, `[bridge]`, `[outro]`.
- Start with `[verse]` or `[chorus]` -- do **not** start with `[intro]`.
- Each section maps to approximately one generation segment (~30 seconds).
- Avoid packing too many words into a single section.
- Use `[Instrumental]` for non-vocal sections.

### In-Context Learning (ICL)

Dual-track ICL mode -- providing both a vocal and instrumental reference audio clip --
produces the best results. Guidelines:
- Use ~30-second reference audio segments.
- Chorus sections from reference tracks tend to yield better results than verses.

---

## arioso Adapter Details

### Type and backends

The arioso adapter (`arioso.platforms.yue.adapter.Adapter`) supports two backends:

| Backend | When selected | Dependency |
|---------|---------------|------------|
| **[fal.ai](https://fal.ai/models/fal-ai/yue)** (hosted API) | `FAL_KEY` environment variable is set | `fal_client` (`pip install fal-client`) |
| **Local CLI** (subprocess) | `FAL_KEY` is not set | `infer.py` from the YuE repo on PATH |

Backend resolution happens automatically at generation time.

### Authentication

- **fal.ai backend:** Set the `FAL_KEY` environment variable with your fal.ai API key.
- **Local backend:** No auth needed, but requires the YuE repository and its dependencies.

### Parameters

| arioso param | Native param | Type | Default | Notes |
|--------------|-------------|------|---------|-------|
| `prompt` | `genre_txt` | str | (required) | Genre/style tag string |
| `lyrics` | `lyrics_txt` | str | `""` | Structured lyrics text |
| `duration` | `run_n_segments` | float | `30.0` | Seconds; converted to segments via `max(1, round(duration / 30))` |
| `model` | `stage1_model` | str | `"m-a-p/YuE-s1-7B-anneal-en-cot"` | Stage-1 model identifier |
| `batch_size` | `stage2_batch_size` | int | `4` | Stage-2 batch size |
| `max_tokens` | `max_new_tokens` | int | `3000` | Maximum new tokens |
| `repetition_penalty` | `repetition_penalty` | float | `1.1` | Token repetition penalty |
| `audio_input` | `vocal_track_prompt_path` | str | `""` | Path to vocal track prompt file for ICL |

### Output

- **Format:** WAV
- **Sample rate:** Codec-dependent (not fixed)
- **Returns:** `bytes` (local backend) or URL string (fal.ai backend)
- Wrapped in `Song` / `AudioResult` dataclasses from `arioso.base`.

### Duration mapping

Each generation segment produces approximately 30 seconds of audio.
Total duration = `run_n_segments * ~30s`. The adapter converts the `duration` parameter
(in seconds) to a segment count automatically.

---

## Further Reading

- [YuE paper (arXiv)](https://arxiv.org/html/2503.08638v1) -- full model architecture, training details, and evaluation.
- [YuE GitHub repository](https://github.com/multimodal-art-projection/YuE) -- model weights, inference scripts, and tag lists.
- [YuE project page](https://map-yue.github.io/) -- audio samples and demos.
- [YuE GPU-poor variant](https://github.com/deepbeepmeep/YuEGP) -- optimized for lower-VRAM setups.
- [fal.ai YuE endpoint](https://fal.ai/models/fal-ai/yue) -- hosted inference API documentation.
- [LLaMA 2 paper](https://arxiv.org/abs/2307.09288) -- foundation LLM architecture used by YuE's Stage 1.
- [EnCodec](https://github.com/facebookresearch/encodec) -- audio codec used by YuE's Stage 2.
