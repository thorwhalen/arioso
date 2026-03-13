# Jen Platform Reference

Last updated: 2026-03-13

## Overview

[Jen](https://jenmusic.ai/) is an ethically-trained AI music generation platform by Futureverse, based on the
[JEN-1](https://arxiv.org/abs/2308.04729) architecture: a universal high-fidelity diffusion model that combines autoregressive
and non-autoregressive training (omnidirectional diffusion). It supports text-to-music,
music inpainting, and continuation.

Trained on 40+ fully licensed music catalogs with full commercial rights included.

- Website: https://www.jenmusic.ai/
- API page: https://www.jenmusic.ai/api
- Research: https://www.jenmusic.ai/research
- Paper: "JEN-1: Text-Guided Universal Music Generation" -- https://arxiv.org/abs/2308.04729
- IEEE publication: https://ieeexplore.ieee.org/document/10605479
- Fast generation: 2-minute tracks in under 7 seconds
- No length limits
- Pricing: $0.04 per track (1--60 seconds)

## Prompt Engineering

### Text encoder: [Flan-T5](https://arxiv.org/abs/2210.11416)

JEN-1 uses [Flan-T5](https://arxiv.org/abs/2210.11416) as its text encoder ([T5 base architecture](https://arxiv.org/abs/1910.10683)). Flan-T5 is an instruction-tuned LLM, which means
it understands natural language well. Natural language descriptions work better than tag
lists. Describe the music as you would to a human musician.

### Good examples

- "A smooth jazz piece with a walking bass line, brushed drums, and a mellow saxophone
  melody"
- "High-energy rock anthem with crunchy electric guitars, pounding drums, and soaring
  lead guitar"
- "Gentle acoustic folk song with fingerpicked guitar, harmonica, and soft vocal
  harmonies"

### Instruction-style prompts

Because of the Flan-T5 encoder, instruction-style prompts can work:

- "Create an upbeat track that transitions from verse to chorus"

Longer, more descriptive prompts are handled well. Paraphrasing and different phrasings
of the same concept should produce similar results.

### Music inpainting and continuation

- **Inpainting:** Can edit specific parts of existing audio
- **Continuation:** Use `continue_from` to extend an existing track, providing a new
  prompt describing how the continuation should sound

### Effective vocabulary

Standard genre terms, instrument names, mood descriptors, and production quality terms
all work well. Genre coverage is broad, reflecting the 40+ licensed catalogs used for
training.

### Links

- JEN-1 paper: https://arxiv.org/abs/2308.04729
- IEEE publication: https://ieeexplore.ieee.org/document/10605479

## API Details

### Connection

- **Type:** REST API
- **Base URL:** `https://api.jenmusic.ai/v1`
- **Auth:** Bearer token via `JEN_API_KEY` environment variable
- **Endpoint:** `POST /generate`

### Output format

- MP3 or WAV, 48 kHz
- Returns a URL to the generated audio

### Parameters

| Parameter      | Type   | Default | Range / Values  | Description                              |
|----------------|--------|---------|-----------------|------------------------------------------|
| prompt         | str    | --      | required        | Text description of desired music        |
| duration       | float  | --      | --              | Track duration in seconds                |
| output_format  | str    | "mp3"   | "mp3", "wav"    | Audio output format                      |
| continue_from  | str    | --      | optional        | Track ID or URL to extend from           |

## arioso Adapter Notes

The arioso adapter for Jen lives in `adapter.py` alongside this file. It wraps the
generation endpoint into the common arioso generation interface.

Notable differences from other platforms:

- 48 kHz output (vs. 44.1 kHz for most others)
- No length limits on generation
- Supports continuation from existing tracks via `continue_from`
- No polling step documented -- generation may be synchronous or handled differently

---

## Further Reading

- [Jen API documentation](https://api.jenmusic.ai/docs/getting-started) --
  getting started with the Jen REST API
- [JEN-1: Text-Guided Universal Music Generation](https://arxiv.org/abs/2308.04729) --
  the foundational paper
- [Flan-T5 (Scaling Instruction-Finetuned Language Models)](https://arxiv.org/abs/2210.11416) --
  the text encoder used by JEN-1
- [AudioLDM](https://audioldm.github.io/) --
  a related latent diffusion model for audio generation
- [MusicSmith prompt guide](https://musicsmith.ai/blog/ai-music-generation-prompts-best-practices) --
  best practices for AI music generation prompts
