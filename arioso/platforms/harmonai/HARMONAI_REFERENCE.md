# Harmonai / Dance Diffusion Reference

Last updated: 2026-03-13

## Overview

[Dance Diffusion](https://huggingface.co/docs/diffusers/api/pipelines/dance_diffusion) is an open-source, [diffusion](https://arxiv.org/abs/2006.11239)-based audio generation model developed by the
[Harmonai](https://github.com/Harmonai-org/sample-generator) community under Stability AI. Unlike most music generation systems, it operates
directly on raw audio waveforms rather than MIDI, spectrograms, or text tokens.

**Critical fact: This is an unconditional model. It does not accept text prompts.**

Generation is controlled entirely by seed selection, inference step count, and the choice of
pre-trained model checkpoint. Each checkpoint encodes a particular musical style derived from
its training data.

Initial models generate 1--3 seconds of audio. The system also supports audio interpolation
between two tracks and style transfer / regeneration.

- GitHub: <https://github.com/Harmonai-org/sample-generator>
- HuggingFace model (jmann-small): <https://huggingface.co/harmonai/jmann-small-190k-steps>
- HuggingFace diffusers docs: <https://huggingface.co/docs/diffusers/api/pipelines/dance_diffusion>
- Replicate API: <https://replicate.com/harmonai/dance-diffusion>

---

## Prompt Engineering

There is no prompt engineering for Dance Diffusion. The model has **no text conditioning
whatsoever**. If a text prompt is supplied through the arioso adapter, it is ignored and a
warning is emitted.

Generation is shaped by three levers only:

| Lever | Effect |
|-------|--------|
| **seed** | Different seeds produce different outputs. This is the primary way to explore the output space. |
| **num_steps** | More diffusion steps yield higher-quality audio, with diminishing returns past ~100 steps. |
| **Model checkpoint** | The pre-trained model determines the musical style. For example, `jmann-small-190k-steps` tends toward electronic/ambient textures. |

### When to use Dance Diffusion

- Generating short audio samples and loops for electronic music production.
- Audio interpolation between two existing clips.
- Style transfer / regeneration of existing audio.
- Experimental and generative audio art.

### When to use something else

If you need text-conditioned music generation, use one of the following instead:

- **MusicGen** (Meta) -- text-to-music, multiple model sizes.
- **Stable Audio** (Stability AI) -- text-to-music with timing control.
- **Riffusion** -- text-to-spectrogram-to-audio via Stable Diffusion.

---

## arioso Adapter Details

| Property | Value |
|----------|-------|
| Type | Python library (local inference via [diffusers](https://huggingface.co/docs/diffusers/)) |
| Dependencies | `diffusers`, `torch` |
| Authentication | None |
| Default model | `harmonai/jmann-small-190k-steps` |
| Output format | WAV, 48 kHz, numpy array |

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | `str` | `""` | **Ignored.** A warning is emitted if a non-empty value is provided. |
| `num_steps` | `int` | `100` | Number of diffusion inference steps. |
| `seed` | `int` | (random) | Random seed for reproducibility. |
| `batch_size` | `int` | `1` | Number of audio clips to generate in one call. |

---

## Available Pre-trained Models

Models are hosted on HuggingFace under the `harmonai` organization. Each model has different
musical characteristics determined by its training data. Browse available checkpoints at:

<https://huggingface.co/harmonai>

---

## Further Reading

- [DanceDiffusionPipeline documentation](https://huggingface.co/docs/diffusers/api/pipelines/dance_diffusion) --
  diffusers API reference for Dance Diffusion
- [HuggingFace diffusers library](https://huggingface.co/docs/diffusers/) --
  the inference framework used by the arioso adapter
- [Harmonai / sample-generator](https://github.com/Harmonai-org/sample-generator) --
  community project and source code
- [Denoising Diffusion Probabilistic Models (DDPM)](https://arxiv.org/abs/2006.11239) --
  the foundational technique behind Dance Diffusion
- [DiffWave](https://arxiv.org/abs/2009.09761) -- diffusion models for raw audio
