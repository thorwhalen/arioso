# MusicGen Platform Reference

Last updated: 2026-03-13

## Overview

MusicGen is Meta/Facebook's open-source text-to-music model, part of the
[AudioCraft](https://github.com/facebookresearch/audiocraft) framework. It uses a
single-stage transformer language model operating over audio tokens
([EnCodec](https://github.com/facebookresearch/encodec)), conditioned
on text via a [T5 encoder](https://arxiv.org/abs/1910.10683). The `musicgen-melody` variant additionally supports melody
conditioning from audio input.

- **Paper:** Copet et al., "Simple and Controllable Music Generation" (2023) -- <https://arxiv.org/abs/2306.05284>
- **GitHub:** <https://github.com/facebookresearch/audiocraft>
- **HuggingFace models:**
  - [facebook/musicgen-small](https://huggingface.co/facebook/musicgen-small) (300M params)
  - [facebook/musicgen-medium](https://huggingface.co/facebook/musicgen-medium) (1.5B params)
  - [facebook/musicgen-large](https://huggingface.co/facebook/musicgen-large) (3.3B params)
  - [facebook/musicgen-melody](https://huggingface.co/facebook/musicgen-melody) (1.5B, melody-conditioned)

---

## Prompt Engineering

MusicGen uses a **[T5 text encoder](https://arxiv.org/abs/1910.10683)** for conditioning
(via cross-attention over T5 embeddings — see [Section 3.2 of the MusicGen paper](https://arxiv.org/abs/2306.05284)),
so it responds well to natural language descriptions rather than structured tags.

### Prompt structure

Use 1-3 concise sentences following this pattern:

    Genre + Instrumentation + Mood + Tempo description

Example: *"80s pop track with driving drums and synth pads, energetic and uplifting"*

### What works well

These vocabulary categories align with the [MusicCaps](https://huggingface.co/datasets/google/MusicCaps)
caption style that MusicGen was trained on (5,521 expert-written captions covering
genre, instruments, mood, and tempo — see [LP-MusicCaps](https://huggingface.co/datasets/seungheondoh/LP-MusicCaps-MSD) for a 2.2M GPT-expanded version):

- **Genre terms:** rock, jazz, classical, ambient, electronic, hip-hop, folk, pop, metal, lo-fi
- **Instrument names:** piano, guitar, drums, bass, synth, strings, brass, flute, violin, saxophone
- **Mood adjectives:** calm, energetic, melancholic, uplifting, dark, bright, dreamy, aggressive, nostalgic
- **Tempo descriptions:** "fast", "slow", "moderate tempo" — understood but less precise than explicit parameters

### What does NOT work well

- Specific chord progressions (e.g., "Cmaj7 - Dm7 - G7")
- Exact note sequences or melodies described in text
- Highly technical music theory terminology
- Very long or multi-part structural descriptions

### Guidance ([classifier-free guidance](https://arxiv.org/abs/2207.12598) / `cfg_coef`)

Controls how literally the model follows the prompt (see also
[prompt-aware CFG](https://arxiv.org/abs/2509.22728) for adaptive guidance):

| Range | Behavior |
|-------|----------|
| 1-2   | Very creative, may deviate significantly from prompt |
| 3-4   | Good balance between prompt adherence and quality (default: 3.0) |
| 5-8   | Very literal prompt following, may reduce audio quality at extremes |

### Temperature

Controls randomness in generation:

- **Lower values** (e.g., 0.5): More deterministic, consistent output
- **Default** (1.0): Standard variability
- **Higher values** (e.g., 1.5): More varied, potentially less coherent

### Melody conditioning ([musicgen-melody](https://huggingface.co/facebook/musicgen-melody) only)

The `musicgen-melody` variant accepts audio input as a melody reference via
chromagram extraction (`generate_with_chroma()`), allowing the model to generate
music that follows a given melodic contour while applying the style described in
the text prompt. See [AudioCraft melody docs](https://github.com/facebookresearch/audiocraft/blob/main/docs/MUSICGEN.md#melody-conditioning).

### Extending generations

MusicGen supports `extend_stride` for generating pieces longer than the base window by
iteratively extending the output.

### Background

The model was trained on captions from the [MusicCaps dataset](https://huggingface.co/datasets/google/MusicCaps),
which uses descriptive natural language written by expert musicians. Prompts that
resemble these caption styles tend to produce the best results. Text adherence is
strongest for genre, instruments, and general mood; weaker for specific harmonic
or melodic content [1]. A [user study on prompting music models](https://arxiv.org/html/2407.04333v2)
(PAGURI) found that musicians often struggle to translate intent into effective
prompts, suggesting that iterative generation (multiple attempts with the same
prompt) is more effective than prompt rewriting.

### Further reading

- [AudioCraft MusicGen docs](https://github.com/facebookresearch/audiocraft/blob/main/docs/MUSICGEN.md) — official documentation for all MusicGen variants
- [MusicGen-Style](https://arxiv.org/html/2407.12563v1) — adds a discrete bottleneck for audio style conditioning/transfer
- [AudioCraft metrics documentation](https://github.com/facebookresearch/audiocraft/blob/main/docs/METRICS.md) — FAD, KLD, CLAP score, and chroma similarity evaluation
- [Instruct-MusicGen](https://arxiv.org/html/2405.18386v3) — instruction-tuned MusicGen for editing tasks ("Add guitar", "Remove drums")
- [Enhancing MusicGen with Prompt Tuning](https://www.mdpi.com/2076-3417/15/15/8504) — learned soft prompts improve CLAP score by 0.1270
- [HuggingFace Transformers MusicGen](https://huggingface.co/docs/transformers/model_doc/musicgen) — alternative inference backend (used by arioso as fallback)
- [MusicCaps dataset](https://huggingface.co/datasets/google/MusicCaps) — the 5,521-caption dataset that defines MusicGen's prompt vocabulary
- [awesome-music-prompts](https://github.com/yzfly/awesome-music-prompts) — curated prompt examples for MusicGen and other models

---

## arioso Adapter Details

### Type

Python library -- local inference (no external API calls).

### Dependencies

- Primary: `audiocraft` (Meta's library)
- Fallback: `transformers` (HuggingFace)
- Required: `torch`

The adapter uses a **dual backend** strategy: it tries `audiocraft` first and falls back
to `transformers` if `audiocraft` is not installed.

### Authentication

None required.

### Output format

- Format: WAV
- Sample rate: 32 kHz
- Data type: numpy array

### Parameters

| Parameter     | Type   | Default                      | Description |
|---------------|--------|------------------------------|-------------|
| `prompt`      | str    | (required)                   | Text description of desired music |
| `duration`    | float  | 8.0                          | Duration in seconds |
| `temperature` | float  | 1.0                          | Sampling temperature (randomness) |
| `top_k`       | int    | 250                          | Top-k sampling |
| `top_p`       | float  | 0.0                          | Nucleus sampling threshold (0 = disabled) |
| `guidance`    | float  | 3.0                          | Classifier-free guidance scale |
| `model`       | str    | `"facebook/musicgen-small"`  | Model variant: small / medium / large / melody |

---

## References

[1] Copet, J., Kreuk, F., Gat, I., Remez, T., Kant, D., Synnaeve, G., Adi, Y., & Defossez, A. (2023). [Simple and Controllable Music Generation](https://arxiv.org/abs/2306.05284). arXiv:2306.05284.
