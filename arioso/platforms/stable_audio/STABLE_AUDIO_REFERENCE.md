# Stable Audio Open Platform Reference

Last updated: 2026-03-13

## Overview

Stable Audio Open is [Stability AI](https://stability.ai/)'s open-source latent diffusion
model for audio generation. It uses a diffusion transformer (DiT) architecture with
**timing conditioning**, allowing explicit control over output duration. Text conditioning
uses a hybrid [T5](https://arxiv.org/abs/1910.10683) +
[CLAP](https://arxiv.org/abs/2206.04769) encoder.

The model was trained on open datasets including the
[Free Music Archive (FMA)](https://github.com/mdeff/fma) and
[FSD50K](https://zenodo.org/record/4060432).

- **Paper (architecture):** Evans et al., "Fast Timing-Conditioned Latent Audio Diffusion" (2024) -- <https://arxiv.org/abs/2402.04825>
- **Paper (open weights):** Evans et al., "Stable Audio Open" (2024) -- <https://arxiv.org/abs/2407.14358>
- **HuggingFace:** [stabilityai/stable-audio-open-1.0](https://huggingface.co/stabilityai/stable-audio-open-1.0)
- **Training data:** [FMA (Free Music Archive)](https://github.com/mdeff/fma), FSD50K, and other open datasets
- **Commercial version:** Stable Audio 2.5 (not open-source, available via stability.ai)

---

## Prompt Engineering

Stable Audio Open uses a **[T5](https://arxiv.org/abs/1910.10683) +
[CLAP](https://arxiv.org/abs/2206.04769) hybrid text encoder**, giving it both
natural language understanding (T5) and audio-semantic alignment
([CLAP](https://huggingface.co/laion/clap-htsat-unfused) — Contrastive Language-Audio
Pretraining). This combination makes it responsive to both descriptive text and
audio-specific terminology.

### Prompt anatomy

Structure prompts with these components:

    Genre, Sub-genre, Instruments, Mood/Vibe, BPM, Production style

Examples:
- *"Ambient electronic track, soft pads, reverb-heavy, slow tempo at 70 BPM, dreamy and atmospheric"*
- *"High-energy drum and bass, fast breakbeats, heavy sub-bass, dark and aggressive, 174 BPM"*

### BPM in prompts

Because of the timing conditioning architecture, **specifying BPM in the prompt is
effective** and more reliable than vague tempo descriptions. Include it explicitly
(e.g., "120 BPM") when tempo matters.

### Negative prompts

Negative prompts (`negative_prompt` parameter) are effective for excluding unwanted
elements:

- To ensure instrumental output: `"vocals, singing, speech"`
- To avoid specific instruments: `"drums, percussion"`
- To control production: `"distortion, noise, lo-fi"`

### Stem / instrument isolation

Use explicit isolation language in prompts:

- `"isolated drum track"`
- `"solo piano, no accompaniment"`
- `"solo acoustic guitar"`

The keyword **`solo`** is particularly effective for instrument isolation.

### Section descriptions

Structural descriptions can influence output: *"starting with a gentle intro, building
to a powerful chorus"*

### Guidance scale ([classifier-free guidance](https://arxiv.org/abs/2207.12598))

| Range | Behavior |
|-------|----------|
| 3-5   | More creative, ambient, loosely interpreted results |
| 7     | Default -- good balance of quality and prompt adherence |
| 9-12  | Very literal prompt following; can introduce harshness/artifacts at extremes |

More specific prompts produce good results at lower guidance; vague prompts benefit from
higher guidance values.

### Duration: parameter vs. prompt text

The `duration` parameter controls timing architecturally and is **more reliable** than
describing length in the prompt text. Always set duration via the parameter.

### Effective vocabulary

**Genres** (well-represented in [FMA](https://github.com/mdeff/fma) training data — 106K tracks,
[161-genre hierarchy](https://github.com/mdeff/fma#data)): Electronic, Rock, Folk, Hip-Hop,
Classical, Jazz, Pop, Ambient, Experimental

**Instruments:** guitar, piano, drums, bass, synth, strings, brass, woodwinds, percussion

**Mood terms:** dark, bright, melancholic, uplifting, aggressive, calm, eerie, nostalgic,
euphoric

**Production terms:** "lo-fi", "vinyl crackle", "warm analog", "crisp digital",
"studio quality", "live recording feel"

### Open model limitations

The open model (1.0) has a narrower training set than the commercial Stable Audio 2.5,
which means less genre coverage and potentially lower fidelity for underrepresented
styles.

### Further reading

- [Stable Audio 2.5 Prompt Guide](https://stability.ai/learning-hub/stable-audio-25-prompt-guide) — official prompt engineering guide with four building blocks and era references
- [On Prompting Stable Audio](https://www.jordipons.me/on-prompting-stable-audio/) — expert blog by Jordi Pons (Stability AI researcher): genre → instruments → mood → BPM
- [CLAP model](https://huggingface.co/laion/clap-htsat-unfused) — the text-audio encoder; understanding its training distribution reveals which descriptions work best
- [LAION-CLAP](https://github.com/LAION-AI/CLAP) — keyword-to-caption augmentation showing natural language captions outperform raw tags
- [T-CLAP](https://arxiv.org/abs/2404.17806) — temporal-enhanced CLAP; shows temporal ordering language ("starts with piano, then drums enter") is poorly captured by standard CLAP
- [FMA dataset](https://github.com/mdeff/fma) — 106K tracks with 161-genre hierarchy; defines the vocabulary space for genre terms
- [HuggingFace Diffusers StableAudioPipeline](https://huggingface.co/docs/diffusers/api/pipelines/stable_audio) — API documentation for the inference backend
- [awesome-music-prompts](https://github.com/yzfly/awesome-music-prompts) — curated prompt examples including Stable Audio

---

## arioso Adapter Details

### Type

Python library -- local inference via HuggingFace Diffusers (no external API calls).

### Dependencies

- `diffusers`
- `torch`
- `transformers`

### Authentication

None required.

### Output format

- Format: WAV
- Sample rate: 44.1 kHz
- Data type: numpy array

### Parameters

| Parameter              | Type   | Default                                  | Description |
|------------------------|--------|------------------------------------------|-------------|
| `prompt`               | str    | (required)                               | Text description of desired audio |
| `negative_prompt`      | str    | `None`                                   | Text describing elements to avoid |
| `duration`             | float  | 10.0                                     | Duration in seconds |
| `num_steps`            | int    | 200                                      | Number of diffusion inference steps |
| `guidance`             | float  | 7.0                                      | Classifier-free guidance scale |
| `seed`                 | int    | `None`                                   | Random seed for reproducibility |
| `batch_size`           | int    | 1                                        | Number of samples to generate |
| `sampler`              | str    | `"dpmpp-3m-sde"`                         | Diffusion sampler type |
| `audio_input`          | --     | `None`                                   | Audio conditioning input |
| `audio_input_strength` | float  | `None`                                   | Denoising strength for audio conditioning |

### Model

`stabilityai/stable-audio-open-1.0`

### Notes on `num_steps`

| Steps   | Behavior |
|---------|----------|
| 50-100  | Faster generation, lower quality |
| 200     | Default, good quality |
| 200+    | Marginal improvement, significantly slower |

---

## References

[1] Evans, Z., Parker, J. D., Carr, C. J., Zukowski, Z., Taylor, J., & Pons, J. (2024). [Fast Timing-Conditioned Latent Audio Diffusion](https://arxiv.org/abs/2402.04825). arXiv:2402.04825.

[2] Evans, Z., Parker, J. D., Carr, C. J., Zukowski, Z., Taylor, J., & Pons, J. (2024). [Stable Audio Open](https://arxiv.org/abs/2407.14358). arXiv:2407.14358.
