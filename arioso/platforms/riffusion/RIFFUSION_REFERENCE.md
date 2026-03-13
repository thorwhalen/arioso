# Riffusion Reference

Last updated: 2026-03-13

## Overview

Riffusion generates music through a distinctive two-stage pipeline: it uses a fine-tuned
[Stable Diffusion](https://github.com/CompVis/stable-diffusion) v1.5 model to produce spectrogram images from text prompts, then converts
those spectrograms back to audio via inverse Short-Time Fourier Transform ([Griffin-Lim
algorithm](https://en.wikipedia.org/wiki/Griffin-Lim_algorithm)).

This spectrogram-based approach gives Riffusion strong harmonic/tonal fidelity but less
precise rhythmic timing compared to waveform-based models. It can generate short clips in
near-real-time and supports smooth interpolation between two prompts for style transitions.

- Website: <https://www.riffusion.com/>
- GitHub (hobby): <https://github.com/riffusion/riffusion-hobby>
- HuggingFace model: <https://huggingface.co/riffusion/riffusion-model-v1>
- Wikipedia: <https://en.wikipedia.org/wiki/Riffusion>

---

## Prompt Engineering

Because Riffusion is built on Stable Diffusion, its prompt engineering follows image-generation
conventions adapted to spectrogram captions. Keep prompts short and descriptive -- 5 to 15
words is ideal.

### Prompt Format

The optimal structure is: **genre + key instruments + mood/energy**.

**Good prompts:**

- `jazz saxophone solo, smooth, mellow`
- `heavy metal guitar riff, distorted, aggressive`
- `classical piano sonata, elegant, flowing`
- `EDM drop with heavy bass and synths`
- `acoustic folk guitar fingerpicking, warm, intimate`

### Negative Prompts

Negative prompts are supported and effective for steering output away from unwanted elements:

- `vocals, singing, speech` -- for instrumental-only output
- `noise, distortion` -- for cleaner results
- `drums, percussion` -- to exclude specific instruments

### Guidance Scale

The `guidance` parameter controls how literally the model follows the prompt:

| Range | Behavior |
|-------|----------|
| 3--5 | More ambient, creative, loosely interpreted |
| 7 | Default -- good balance of fidelity and variety |
| 10--15 | Very literal adherence to prompt; may introduce artifacts |

### What Works Well

- **Genre terms:** jazz, rock, classical, electronic, ambient, folk, blues, metal, pop.
- **Music theory terms:** "minor key", "major chord", "pentatonic" -- moderately effective.
- **Instrument names:** saxophone, piano, guitar, synth, drums, violin, etc.
- **Mood/texture descriptors:** smooth, aggressive, dreamy, dark, bright, warm.

### Characteristics and Limitations

- Output length is typically 5--10 seconds. Best suited for loops, samples, or short passages.
- Strong at tonal and harmonic content due to the spectrogram representation.
- Less precise with rhythm and timing than waveform-based models (MusicGen, Dance Diffusion).
- Can produce "impossible" sounds that no acoustic instrument could make -- useful for
  experimental work.
- **Interpolation:** two prompts can be blended for smooth style transitions.

---

## arioso Adapter Details

| Property | Value |
|----------|-------|
| Type | Python library (dual backend) |
| Dependencies | `diffusers`, `torch`, `scipy`, `numpy`, `Pillow` |
| Authentication | None |
| Output format | WAV, 44.1 kHz, numpy array |

### Backends

The adapter supports two backends:

1. **riffusion library** -- the full spectrogram-to-audio pipeline (preferred when installed).
2. **diffusers fallback** -- Stable Diffusion image generation + inverse STFT via Griffin-Lim.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | `str` | (required) | Text description of the desired music. |
| `negative_prompt` | `str` | `""` | Elements to exclude from the output. |
| `seed` | `int` | (random) | Random seed for reproducibility. |
| `guidance` | `float` | `7.0` | [Classifier-free guidance](https://arxiv.org/abs/2207.12598) scale. |
| `num_steps` | `int` | `50` | Number of diffusion inference steps. |
| `audio_input_strength` | `float` | `0.75` | Denoising strength (0.0--1.0). Lower values preserve more of any input audio; higher values allow more creative deviation. |

---

## How It Works (Technical Summary)

1. **Text encoding:** The prompt is encoded using [CLIP](https://arxiv.org/abs/2103.00020) (same as Stable Diffusion).
2. **Spectrogram generation:** The diffusion model denoises a latent into a spectrogram image.
3. **Audio reconstruction:** The spectrogram image is converted to audio using the inverse
   Short-Time Fourier Transform (Griffin-Lim algorithm).

This pipeline means the model's "understanding" of music is mediated by its visual
representation as a spectrogram. Harmonic structure (vertical patterns in a spectrogram) is
well-captured; precise temporal/rhythmic structure (horizontal patterns) is less reliable.

---

## Further Reading

- [Riffusion GitHub (hobby)](https://github.com/riffusion/riffusion-hobby) --
  open-source codebase for local experimentation
- [Riffusion website](https://www.riffusion.com/) --
  interactive demo and technical explanation
- [Stable Diffusion](https://github.com/CompVis/stable-diffusion) --
  the base model architecture
- [Stable Diffusion paper (Rombach et al., 2022)](https://arxiv.org/abs/2112.10752) --
  latent diffusion models
- [Griffin-Lim algorithm](https://en.wikipedia.org/wiki/Griffin-Lim_algorithm) --
  phase reconstruction from spectrograms
- [awesome-music-prompts](https://github.com/yzfly/awesome-music-prompts) --
  curated prompt examples for music generation models
- [OpenVINO Riffusion tutorial](https://docs.openvino.ai/2024/notebooks/riffusion-text-to-music-with-output.html) --
  text-to-music with code examples
- [HuggingFace model card](https://huggingface.co/riffusion/riffusion-model-v1)
- [Wikipedia overview](https://en.wikipedia.org/wiki/Riffusion)
