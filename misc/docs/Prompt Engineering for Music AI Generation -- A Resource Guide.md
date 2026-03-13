# Prompt Engineering for Music AI Generation: A Resource Guide

**Text prompts are the primary interface for controlling music generation models, yet prompt engineering for music remains a fragmented discipline.** This report compiles **78 resources**—papers, datasets, tools, taxonomies, and guides—that collectively define the state of the art for crafting effective natural language prompts for text-to-music systems. The core finding across sources: effective music prompts combine genre/style, instrumentation, mood, tempo, and production descriptors in layered natural language sentences, and their effectiveness depends heavily on the text encoder architecture (T5, CLAP, FLAN-T5) each model uses. For AI agents and developers building prompt optimization tools, the resources below provide the training data, vocabulary space, evaluation metrics, and empirical findings needed to systematically improve music generation prompts.

## Methodology

Resources were gathered via systematic search across arXiv, Google Scholar, HuggingFace, Kaggle, GitHub, and platform documentation sites. Search queries targeted "text-to-music generation prompt," "music prompt engineering," "music captioning dataset," "audio generation guidance scale," and model-specific documentation for MusicGen, MusicLM, Stable Audio, Suno, Udio, JEN-1, AudioLDM, TANGO, and Riffusion. GitHub was searched for awesome lists and prompt tools. Platform-specific guides were sourced from official documentation and vetted community resources. Each resource was verified for availability and relevance to prompt engineering specifically. Resources are grouped by function: papers on prompt techniques, model architecture papers revealing prompt processing, datasets defining vocabulary space, parameter interaction documentation, vocabulary/taxonomy resources, prompt optimization research, evaluation tools, platform guides, prompt builder tools, and curated collections.

---

## A. Papers directly addressing prompt engineering for music generation

These papers study how prompt design, structure, and content affect music generation output quality and controllability.

**MusiCoT: Chain-of-Musical-Thought Prompting** [1] introduces chain-of-thought prompting for music generation, using CLAP embeddings to create intermediate "musical thoughts" that plan overall structure before generating audio tokens. This structured reasoning approach significantly improves coherence and creativity. **Type:** Paper.

**Advanced Prompt Engineering Techniques for Generative Sound Synthesis Models** [2] directly tests ten specialized prompts across SynthIO, MusicLM, and MusicGen, with three expert composers evaluating outputs on aesthetic quality, spectral consistency, temporal evolution, and prompt coherence. Demonstrates that **prompt specificity critically affects generation effectiveness**. **Type:** Paper.

**Enhancing MusicGen with Prompt Tuning** [3] proposes parameter-efficient prompt tuning for MusicGen, improving CLAP scores by **0.1270** without modifying original model weights. Shows that learned soft prompts outperform handcrafted text for genre-specific generation. **Type:** Paper.

**Long-Form Text-to-Music with Adaptive Prompts (Babel Bardo)** [4] uses LLMs to transform speech transcriptions into music description prompts, comparing four strategies from raw transcription to LLM-refined prompts. Finds that **LLM-refined prompts significantly improve quality** and that consistency across consecutive prompts enhances transition smoothness. **Type:** Paper.

**PAGURI: Creative Interaction with Text-to-Music Models** [5] is a 24-participant user study examining how musicians craft prompts in practice, revealing gaps between user intent and model output and identifying effective prompt-writing behaviors. **Type:** Paper.

**SegTune: Structured Control for Song Generation** [6] introduces hierarchical prompting with global prompts (genre, timbre, emotion) and segment-level prompts (time-varying instrumentation, structure labels). An LLM automatically generates segment-level prompts during a dedicated prompt engineering stage. **Type:** Paper.

**Integrating Text-to-Music Models with Language Models** [7] demonstrates that LLM-generated sequences of structured text prompts controlling musical form (verse, chorus, bridge) enable coherent 2.5-minute compositions, establishing that **prompt sequencing is key to long-form generation**. **Type:** Paper.

**The Name-Free Gap: Policy-Aware Stylistic Control** [8] compares artist-name prompts versus LLM-generated name-free descriptors across five descriptor sets and ten artists. Finds that artist names are the strongest control signal but name-free descriptors (genre, mood, instrumentation, production style) **recover much of this effect**, providing a practical vocabulary framework. **Type:** Paper.

**Instruct-MusicGen** [9] adds instruction-following to MusicGen for editing tasks, showing that imperative prompts ("Add guitar," "Remove drums") are effective for music editing—expanding the prompt vocabulary beyond pure description. **Type:** Paper.

---

## B. Model architecture papers revealing how text prompts are processed

Understanding each model's text encoder reveals which prompt styles work best. Models using CLAP respond to descriptive audio captions; those using T5 or FLAN-T5 handle more natural/instructional language.

**MusicLM** [10] conditions on MuLan text embeddings via a hierarchical sequence-to-sequence approach. Its companion **MusicCaps** dataset (5,521 expert-written captions) defines the gold standard for music prompt vocabulary: genre, tempo, instruments, mood, era. **Type:** Paper.

**MusicGen** [11] uses a **T5 text encoder** with cross-attention conditioning. Larger models (3.3B parameters) follow text prompts more faithfully. Training uses condition merging—combining natural language descriptions with metadata tags—which improves results over descriptions alone. T5 outperformed CLAP on all metrics except CLAP score itself. **Type:** Paper.

**Noise2Music** [12] uses cascaded diffusion conditioned on text, with **LaMDA (LLM) generating paired text descriptions** for training data. The appendix contains explicit prompt templates showing optimal description structure. **Type:** Paper.

**Stable Audio** [13] uses a CLAP text encoder with cross-attention plus timing embeddings for duration control. The paper documents that **prompts with connector phrases** (e.g., "A man speaking as a crowd laughs") often lose elements—models may omit secondary concepts. **Type:** Paper.

**Stable Audio Open** [14] conditions a DiT on T5-base embeddings via cross-attention, trained on text metadata combining natural language descriptions, titles, and tags. Demonstrates that **multi-source text metadata improves conditioning**. **Type:** Paper.

**JEN-1** [15] uses **FLAN-T5** (instruction-tuned) as text encoder, suggesting that natural, descriptive language works better than keyword-style prompts for this model. Supports text-guided generation, inpainting, and continuation. **Type:** Paper.

**AudioLDM** [16] uses CLAP for text-to-audio generation; during training it conditions on audio embeddings, during inference on text embeddings. Prompts work best when they describe audio properties CLAP has learned. **Type:** Paper.

**AudioLDM 2** [17] unifies speech, music, and sound generation using GPT-2 to translate text into an intermediate "Language of Audio" representation, showing a common prompt-to-audio mapping works across domains. **Type:** Paper.

**TANGO** [18] replaces CLAP with fine-tuned FLAN-T5, achieving comparable results with **63× less training data**. TANGO 2 uses DPO to improve text alignment, creating preference data where "loser" outputs have concepts missing from the prompt. **Type:** Paper.

**YuE** [19] is an open LLaMA2-based model for lyrics-to-song generation (up to 5 minutes), conditioning on structured meta-information (genre tags, emotion, language) plus lyrics via chain-of-thought prompting. **Type:** Paper.

---

## C. Text-audio alignment models defining the prompt embedding space

These models determine how text maps to audio features, directly informing which words and phrases produce the strongest signal in music generation.

**MuLan** [20] is Google's joint music-text embedding model (44M recordings), foundational for MusicLM. Both tag-style and natural language descriptions work, but the model is not publicly available. **Type:** Paper.

**CLAP** [21] (Microsoft) is the dominant contrastive language-audio model used by AudioLDM, Stable Audio, and most evaluation metrics. Understanding CLAP's training distribution reveals which text descriptions best correspond to audio content. **Type:** Paper/Model.

**LAION-CLAP** [22] introduces **keyword-to-caption augmentation**—converting tags into natural language descriptions—demonstrating that natural language captions outperform raw tags for text-audio alignment. **Type:** Paper/Model.

**T-CLAP** [23] addresses CLAP's weakness in temporal information, showing that temporal ordering language ("starts with piano, then drums enter") is **poorly captured** by standard CLAP but can be improved with specialized training. **Type:** Paper.

**CoLLAP** [24] extends CLAP to long-form audio (5+ minutes) and long text descriptions (250+ words), demonstrating that **detailed, structure-aware long descriptions significantly improve retrieval**, suggesting longer prompts are beneficial. **Type:** Paper.

**LP-MusicCaps** [25] uses GPT-3.5 to generate 2.2M captions from tags via four instruction types, providing large-scale evidence that the caption format—combining genre, mood, instruments, tempo, and context—defines effective prompt structure. **Type:** Paper/Dataset.

**Human-CLAP** [26] shows standard CLAPScore has **low correlation with human subjective evaluation** of text-audio relevance, proposing a human-perception-aligned alternative. Critical for developers using CLAP to evaluate prompt quality. **Type:** Paper.

---

## D. How numerical parameters interact with text prompts

The most important parameter across all diffusion-based models is **classifier-free guidance (CFG) scale**, which controls how strongly the model adheres to the text prompt versus generating freely. Higher CFG = stronger prompt adherence but reduced diversity; lower CFG = more creative but weaker alignment [27].

| Model | Default CFG | Text Encoder | Negative Prompts | Key Source |
|-------|------------|-------------|-----------------|-----------|
| MusicGen | 3.0 | T5 | ❌ | [28] |
| Stable Audio Open | 7.0 | T5-base | ✅ | [29] |
| AudioLDM | 2.0–2.5 | CLAP | ❌ | [30] |
| AudioLDM 2 | 3.5 | FLAN-T5 + AudioMAE | ❌ | [17] |
| TANGO | 3.0 | FLAN-T5 | ❌ | [31] |
| JEN-1 | 2.0 | FLAN-T5 | ❌ | [15] |
| Riffusion | 7.0 | CLIP (SD v1.5) | ✅ | [32] |
| ACE-Step | varies | — | ✅ | [33] |
| Google Lyria | — | — | ✅ | [34] |

**MusicGen** [28] exposes `temperature` (default 1.0), `top_k` (default 250), and `top_p` (default 0.0). MusicGen-Style introduces **Double CFG** with independent `cfg_coef` and `cfg_coef_beta` parameters, allowing separate control of text adherence versus style audio adherence. The `eval_q` parameter (1–6) controls quantization of the style conditioner—lower values reduce audio conditioning influence.

**Stable Audio** [29] supports negative prompts (recommended: "low quality, average quality"), timing conditioning (`audio_start_in_s`, `audio_end_in_s`), and audio-to-audio via `initial_audio_waveforms`. Multiple waveforms can be generated per prompt with automatic scoring for adherence.

**TANGO** [31] provides the clearest empirical ablation: CFG 1 (no guidance) performs poorly; CFG 2.5–3 is optimal for FAD; CFG 5 improves FD/KL but degrades FAD. This pattern—**optimal CFG varies by metric and model**—is universal.

**Suno** [35] abstracts most parameters but exposes an "Exclude" field for negative prompting, `styleWeight` (0–1) for style adherence, and boolean `instrumental` mode.

**AudioLDM** [30] provides explicit audio-to-audio control via `transfer_strength` (0–1): 0 preserves original audio, 1 fully transforms to match the text prompt.

**Prompt-Aware Classifier-Free Guidance** [36] demonstrates that a fixed CFG scale is suboptimal across diverse prompts and trains a lightweight predictor to select prompt-dependent guidance scales adaptively. Tested on AudioLDM2 with consistent improvements over vanilla CFG.

**ACE-Step** [33] offers the most granular parameter control: independent `guidance_scale_text` and `guidance_scale_lyric`, `guidance_interval` (controlling when during denoising guidance is applied), and `guidance_interval_decay` for linear decay.

---

## E. Music captioning datasets defining the vocabulary space

These datasets trained the captioning and generation models, making their vocabulary the "language" these systems understand best.

| Dataset | Size | Caption Type | Vocabulary | URL |
|---------|------|-------------|-----------|-----|
| MusicCaps [37] | 5,521 clips | Human expert (10 musicians) | Genre, instruments, mood, tempo, vocals, quality | [HuggingFace](https://huggingface.co/datasets/google/MusicCaps) |
| LP-MusicCaps-MSD [25] | 2.2M captions / 0.5M audio | GPT-3.5 from tags | Genre, mood, instruments, tempo, atmosphere | [HuggingFace](https://huggingface.co/datasets/seungheondoh/LP-MusicCaps-MSD) |
| MusicBench [38] | 52,768 pairs | Enhanced + ChatGPT | Chords, beats, tempo, key, genre, mood | [HuggingFace](https://huggingface.co/datasets/amaai-lab/MusicBench) |
| Song Describer [39] | 1,100 captions / 706 tracks | Human crowdsourced | Free-form (genre, mood, instruments, texture) | [HuggingFace](https://huggingface.co/datasets/renumics/song-describer-dataset) |
| MUCaps [40] | 21,966 files | MU-LLaMA generated | Tempo, rhythm, mood, genre, instruments | [HuggingFace](https://huggingface.co/datasets/M2UGen/MUCaps) |
| MidiCaps [41] | 168,385 MIDI files | Claude 3 + MIR | Tempo, key, time signature, instruments, chords | [HuggingFace](https://huggingface.co/datasets/amaai-lab/MidiCaps) |
| JamendoMaxCaps [42] | 362K+ tracks | Qwen2-Audio | Genre, BPM, key, mood, instruments | [HuggingFace](https://huggingface.co/datasets/amaai-lab/JamendoMaxCaps) |
| ConceptCaps [43] | 21,000 triplets | VAE + Llama 3.1 pipeline | 200 attributes across Genre, Mood, Instruments, Tempo | [HuggingFace](https://huggingface.co/datasets/bsienkiewicz/ConceptCaps) |
| AudioCaps [44] | ~57,000 clips | Human annotated | Environmental, speech, music — free-form | [HuggingFace](https://huggingface.co/datasets/d0rj/audiocaps) |
| WavCaps [45] | ~400,000 clips | ChatGPT processed | Broad audio descriptions | [HuggingFace](https://huggingface.co/datasets/cvssp/WavCaps) |
| AudioSetCaps [46] | 6.1M captions | LALM-generated | Speech, music genre, instruments, fine-grained audio | [HuggingFace](https://huggingface.co/datasets/baijs/AudioSetCaps) |
| LAION-Audio-630K [47] | 633,526 pairs | Web-harvested | Diverse audio descriptions | [GitHub](https://github.com/LAION-AI/audio-dataset) |
| AIME [48] | 6,500 tracks (12 models) | Prompt-output pairs | MTG-Jamendo tags as prompts | [HuggingFace](https://huggingface.co/datasets/disco-eth/AIME) |
| WikiMT-X [49] | 1,000 triplets | Multi-perspective text | 8 genre classes, multi-language descriptions | [HuggingFace](https://huggingface.co/datasets/sander-wood/wikimt-x) |
| MMTrail-20M [50] | 2M+ clips | Multi-modal captions | Instruments, tempo, arrangement, mood, genre | [HuggingFace](https://huggingface.co/datasets/litwell/MMTrail-20M) |

Additional tagging datasets providing structured vocabulary: **MTG-Jamendo** [51] (55K tracks, 195 tags across 87 genre / 40 instrument / 56 mood categories; [GitHub](https://github.com/MTG/mtg-jamendo-dataset)), **MagnaTagATune** [52] (25K clips, 188 tags), **FMA** [53] (106K tracks, 161-genre hierarchy; [GitHub](https://github.com/mdeff/fma)), **MusicNet** [54] (330 classical recordings with note annotations; [Kaggle](https://www.kaggle.com/datasets/imsparsh/musicnet-dataset)), and **AudioSet** [55] (2M+ clips, 632 classes; [Website](https://research.google.com/audioset/)).

**SunoCaps** [56] provides 256 prompt-output pairs with expert annotations for prompt alignment and discrete emotion annotations, using MusicCaps descriptions as prompts for Suno. A research dataset of **100K+ scraped Suno/Udio prompts** [57] analyzes user prompting patterns, genre/mood qualifiers, and structural tags ([GitHub](https://github.com/mister-magpie/aims_prompts)).

---

## F. Vocabulary, taxonomy, and terminology resources

The core vocabulary dimensions for music prompts, synthesized across all datasets and guides, are: **genre/sub-genre, era/decade, mood/emotion, energy/dynamics, instrumentation, tempo/BPM, texture/production, vocal characteristics, song structure, musical key/harmony, rhythm/groove, and spatial/quality descriptors.**

**Google AudioSet Ontology** [55] provides 632 hierarchical audio classes including extensive music branches (instruments, genres, concepts, moods). This is the academic standard used across most audio AI research. Available at the [AudioSet ontology page](https://research.google.com/audioset/ontology/index.html) and [GitHub](https://github.com/audioset/ontology).

**Music Ontology Specification** [58] is a Semantic Web vocabulary with 54 classes and 153 properties for music metadata, linking to MusicBrainz instrument taxonomy and DBPedia genres. Available at [musicontology.com](http://musicontology.com/specification/).

**Cyanite AI Tagging Taxonomy** [59] is the dominant commercial taxonomy (45M+ songs tagged, 150+ companies). It classifies genre (15 top-level with sub-genres), mood (13+ simple labels plus advanced), instrumentation (9 categories), BPM, key, energy, valence-arousal, and voice characteristics, all with numerical confidence scores (0–1). Documentation at [api-docs.cyanite.ai](https://api-docs.cyanite.ai/docs/audio-analysis-v6-classifier/).

**Annotator Subjectivity in MusicCaps** [60] provides quantitative analysis of tag category frequency distributions across different annotators, revealing how vocabulary choices vary for the same music.

**Text Mining Pitchfork Reviews** [61] applies NLP to 24,169 music reviews using Phillip Tagg's Sound Descriptor Words taxonomy, tallying vocal-related sound descriptors by genre—a practical methodology for vocabulary frequency analysis.

---

## G. Prompt optimization and automated prompt engineering

**Two-LLM Prompt Optimization Pipeline** [62] (Atassi, 2024) is the most directly applicable framework: a Music Prompt LLM generates prompts for MusicGen, while a Prompt Optimization LLM (GPT-4) iteratively refines instructions using exploration/exploitation phases scored by human MOS. **Type:** Paper.

**Make-An-Audio: Pseudo Prompt Enhancement** [63] uses a "distill-then-reprogram" approach—auto-captioning models generate descriptions for unlabeled audio, then template-based reprogramming creates enriched training prompts. **Type:** Paper.

**Structured Prompting Strategies for Audio** [64] systematically compares prompt strategies for AudioGen and Stable Audio Open, using GPT-4 to identify five key sound attributes (pitch, pattern, intensity, acoustics, location) for structured expansion. Task-specific structured prompts significantly outperform basic prompts. **Type:** Paper.

**DRAGON: Distributional Rewards for Music Diffusion** [65] optimizes music generation using 20 reward functions including CLAP score, achieving **81.45% average win rate**. Shows that optimizing CLAP score improves both text-audio alignment and quality, and that LLM-generated prompts (without paired audio) improve generation. **Type:** Paper.

**Audio Conditioning via Discrete Bottleneck Features** [66] implements **textual inversion for MusicGen**—optimizing pseudo-word embeddings in the text conditioning space to match target audio style. Computationally expensive but demonstrates gradient-based prompt optimization is feasible. **Type:** Paper.

**LAION-CLAP Keyword-to-Caption Augmentation** [22] uses T5 to convert audio tags/keywords into descriptive captions, enriching short labels into full sentences—directly applicable to prompt expansion. **Type:** Paper/Model.

**Rethinking Music Captioning with Music Metadata LLMs** [67] shows that prompt engineering in the metadata-to-caption conversion stage improves captioning performance by **20%+** without retraining, demonstrating that caption/prompt style significantly affects model performance. **Type:** Paper.

For **music understanding models** useful for reverse prompt engineering (audio → caption → refined prompt): **MU-LLaMA** [68] (MERT encoder + LLaMA-2; [GitHub](https://github.com/shansongliu/MU-LLaMA)), **Qwen2-Audio** [69] (state-of-the-art on MusicCaps captioning; [GitHub](https://github.com/QwenLM/Qwen2-Audio)), and **SALMONN** [70] (dual Whisper + BEATS encoder with Vicuna LLM).

---

## H. Evaluation metrics and benchmarks for prompt-audio alignment

**CLAP Score** is the most practical automated metric, computing cosine similarity between CLAP text and audio embeddings. CLAP models trained on music data best approximate human preferences [71]. **FAD (Fréchet Audio Distance)** measures distributional distance using various embeddings (VGGish, CLAP, PANN, EnCodec, MERT), with **FAD-CLAP-MA** showing best correlation with human quality perception [71]. Other metrics include **KLD** (Kullback-Leibler Divergence over classifier probabilities), **MuLan Cycle Consistency**, and newer **KAD/MAD** metrics that outperform FAD on human correlation [72].

The **AIME benchmark** [48] provides 6,000 songs across 12 models with 15,600 human comparisons, finding Suno ranked highest for both quality and text adherence.

Implementation toolkits: **AudioCraft Metrics** [73] ([GitHub](https://github.com/facebookresearch/audiocraft/blob/main/docs/METRICS.md)) implements FAD, KLD, CLAP score, and chroma similarity. **audioldm_eval** [74] ([GitHub](https://github.com/haoheliu/audioldm_eval)) supports FAD, KL, PSNR, SSIM with multiple backbones. **fadtk** [75] adapts per-song FAD for individual sample quality estimation.

---

## I. Platform-specific prompt guides and prompt builder tools

The best practical guides document optimal prompt structure as: **genre/style → mood/emotion → instrumentation (with adjectives) → tempo/BPM → production characteristics**.

| Resource | Type | Platform | Key Feature | URL |
|----------|------|----------|------------|-----|
| Stable Audio 2.5 Prompt Guide [76] | Official guide | Stable Audio | Four building blocks + era references | [stability.ai](https://stability.ai/learning-hub/stable-audio-25-prompt-guide) |
| "On Prompting Stable Audio" (Jordi Pons) [77] | Expert blog | Stable Audio | Researcher tips: genre→instruments→mood→BPM | [jordipons.me](https://www.jordipons.me/on-prompting-stable-audio/) |
| Udio "Prompt Like a Master" [78] | Official guide | Udio | Tag suggestions, vocal effect tags | [help.udio.com](https://help.udio.com/en/articles/10716541-prompt-like-a-master) |
| Google Lyria Prompt Guide [34] | Official guide | Lyria/Vertex AI | Genre, era, tempo, instruments, vocals | [cloud.google.com](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/music/music-gen-prompt-guide) |
| ACE-Step Prompt Guide [79] | Platform guide | ACE-Step | 100+ genres, 3–7 tag structure | [ambienceai.com](https://www.ambienceai.com/tutorials/ace-step-music-prompting-guide) |
| ElevenLabs Music Guide [80] | Guide | ElevenLabs | Layered approach, negative prompting | [fal.ai](https://fal.ai/learn/biz/eleven-music-prompt-guide) |
| MusicSmith Prompt Guide [81] | Cross-platform guide | Multi | 20+ examples with audio, cross-model comparison | [musicsmith.ai](https://musicsmith.ai/blog/ai-music-generation-prompts-best-practices) |
| Musci.io Suno Tags [82] | Tag encyclopedia | Suno | Most comprehensive tag reference (all categories) | [musci.io](https://musci.io/blog/suno-tags) |
| SunoMetaTagCreator [83] | Interactive tool | Suno | 1000+ tags, drag-and-drop builder | [sunometatagcreator.com](https://sunometatagcreator.com/metatags-guide) |
| HookGenius Suno Tags [84] | Tag reference | Suno | 300+ searchable, copy-ready tags | [hookgenius.app](https://hookgenius.app/learn/suno-style-tags-guide/) |

Prompt builder tools for automated expansion: **OpenMusicPrompt** [85] converts short ideas into detailed prompts for Suno/Udio/Stable Audio and offers reference-track-to-prompt conversion ([openmusicprompt.com](https://openmusicprompt.com/)). **Word Studio Music Style Generator** [86] translates artist/mood references into structured prompts ([word.studio](https://word.studio/tool/music-style-prompt-generator/)). **JustBuildThings Audio Analyzer** [87] generates platform-specific prompts from uploaded audio ([justbuildthings.com](https://justbuildthings.com/ai-audio-analysis/ai-music-prompt-generator)). **Tad AI** [88] integrates ChatGPT prompt generation with their Skymusic 2.0 model ([tad.ai](https://tad.ai/)).

---

## J. Awesome lists and curated collections

- **awesome-music-prompts** [89] — Prompt examples for MusicLM/Stable Audio plus a GPT-based prompt generator system prompt. [GitHub](https://github.com/yzfly/awesome-music-prompts)
- **awesome-ai-music-generation** [90] — Compilation of AI music tools, papers, and frameworks. [GitHub](https://github.com/Curated-Awesome-Lists/awesome-ai-music-generation)
- **awesome-music-informatics** [91] — Courses, tutorials, datasets, and sub-lists for MIR. [GitHub](https://github.com/yamathcy/awesome-music-informatics)
- **awesome-deep-learning-music** [92] — 167+ papers organized by task (34), dataset (55), and architecture (30). [GitHub](https://github.com/ybayle/awesome-deep-learning-music)
- **DeepLearningMusicGeneration** [93] — Models, datasets, and evaluations for music generation. [GitHub](https://github.com/carlosholivan/DeepLearningMusicGeneration)
- **audio-ai-timeline** [94] — Chronological timeline of audio AI developments. [GitHub](https://github.com/archinetai/audio-ai-timeline)

---

## K. Surveys providing comprehensive landscape context

**Foundation Models for Music: A Survey** [95] is a 100+ page review covering pre-training paradigms, architectures, tokenization, and controllability, with extensive coverage of how different text conditioning approaches process prompts. **A Survey on Music Generation** [96] reviews input modalities (text, image, video) and how conditioning signals guide generation. **A Survey on Evaluation Metrics for Music Generation** [72] covers all metrics including a dedicated section on "Adherence to Textual Prompts Evaluation." **Do Music Generation Models Encode Music Theory?** [97] probes whether MusicGen and Jukebox encode tempo, pitch, chords, and scales internally—finding these concepts are detectable, implying that **music-theory-specific language in prompts can influence generation**. **Discovering Interpretable Concepts in MusicGen** [98] uses sparse autoencoders to find that models encode more musical structure than text prompts can access alone.

---

## Conclusion: what prompt authors and optimization systems need to know

Six principles emerge from the collective evidence. First, **prompt structure should mirror training caption format**: genre/style first, then instrumentation with adjectives, mood, tempo/BPM, and production characteristics—this order reflects how MusicCaps and LP-MusicCaps captions are structured, and these datasets trained most major models. Second, **the text encoder determines prompt style**: T5-based models (MusicGen, Stable Audio Open) handle natural descriptive language well; FLAN-T5 models (JEN-1, TANGO) prefer instructional language; CLAP-based models respond to audio-descriptive captions. Third, **temporal ordering within single prompts is unreliable** [23]—use segmented/sequential prompts for structural control [6][7]. Fourth, **CFG scale is prompt-dependent**, not model-dependent—a fixed value is suboptimal across diverse prompts [36], creating an opportunity for adaptive prompt-aware guidance. Fifth, **LLM-mediated prompt expansion consistently improves output quality** [4][62][64], making automated prompt refinement the lowest-hanging fruit for tooling. Sixth, **CLAP score is the most practical proxy for prompt-audio alignment** but correlates imperfectly with human judgment [26]—developers should combine it with FAD-CLAP-MA and human evaluation where possible.

The most significant gap in the literature: no comprehensive statistical analysis exists of which specific words and terms produce the best results across platforms. The scraped Suno/Udio prompt dataset [57] and MusicCaps vocabulary analysis [60] provide starting points, but systematic prompt-effectiveness scoring across models remains an open research problem and a high-value opportunity for tool builders.

---

## REFERENCES

[1] Lam, M.W.Y. et al. "MusiCoT: Analyzable Chain-of-Musical-Thought Prompting for High-Fidelity Music Generation." arXiv, 2025. https://arxiv.org/abs/2503.19611

[2] "Advanced Prompt Engineering Techniques for Generative Sound Synthesis Models." ACM UMAP Adjunct Proceedings, 2025. https://dl.acm.org/doi/10.1145/3708319.3733669

[3] "Enhancing MusicGen with Prompt Tuning." Applied Sciences 15(15), 2025. https://www.mdpi.com/2076-3417/15/15/8504

[4] Marra, F. et al. "Long-Form Text-to-Music Generation with Adaptive Prompts." arXiv, 2024. https://arxiv.org/abs/2411.03948

[5] "PAGURI: A User Experience Study of Creative Interaction with Text-to-Music Models." arXiv, 2024. https://arxiv.org/html/2407.04333v2

[6] "SegTune: Structured and Fine-Grained Control for Song Generation." arXiv, 2025. https://arxiv.org/pdf/2510.18416

[7] Atassi, L. "Integrating Text-to-Music Models with Language Models." arXiv, 2024. https://arxiv.org/abs/2410.00344

[8] "The Name-Free Gap: Policy-Aware Stylistic Control in Music Generation." arXiv, 2025. https://www.arxiv.org/pdf/2509.00654

[9] Zhang, Y. et al. "Instruct-MusicGen: Unlocking Text-to-Music Editing via Instruction Tuning." arXiv, 2024. https://arxiv.org/html/2405.18386v3

[10] Agostinelli, A. et al. "MusicLM: Generating Music From Text." arXiv/ICML, 2023. https://arxiv.org/abs/2301.11325

[11] Copet, J. et al. "Simple and Controllable Music Generation (MusicGen)." arXiv/NeurIPS, 2023. https://arxiv.org/pdf/2306.05284

[12] Huang, Q. et al. "Noise2Music: Text-conditioned Music Generation with Diffusion Models." arXiv/ICML, 2023. https://arxiv.org/abs/2302.03917

[13] Evans, Z. et al. "Fast Timing-Conditioned Latent Audio Diffusion (Stable Audio)." arXiv/ICML, 2024. https://arxiv.org/abs/2402.04825

[14] Evans, Z. et al. "Stable Audio Open." arXiv, 2024. https://arxiv.org/html/2407.14358v1

[15] Li, P. et al. "JEN-1: Text-Guided Universal Music Generation." arXiv, 2023. https://arxiv.org/abs/2308.04729

[16] Liu, H. et al. "AudioLDM: Text-to-Audio Generation with Latent Diffusion Models." arXiv/ICML, 2023. https://audioldm.github.io/

[17] Liu, H. et al. "AudioLDM 2: Learning Holistic Audio Generation." arXiv/IEEE TASLP, 2024. https://arxiv.org/pdf/2308.05734

[18] Ghosal, D. et al. "TANGO: Text-to-Audio Generation using Instruction-Tuned LLM and Latent Diffusion." arXiv, 2023. https://github.com/declare-lab/tango

[19] "YuE: Scaling Open Foundation Models for Long-Form Music Generation." arXiv, 2025. https://arxiv.org/html/2503.08638v1

[20] Huang, Q. et al. "MuLan: A Joint Embedding of Music Audio and Natural Language." ISMIR, 2022. https://arxiv.org/abs/2208.12415

[21] Elizalde, B. et al. "CLAP: Learning Audio Concepts From Natural Language Supervision." ICASSP, 2023. https://arxiv.org/abs/2206.04769

[22] Wu, Y. et al. "Large-Scale Contrastive Language-Audio Pretraining (LAION-CLAP)." ICASSP, 2023. https://github.com/LAION-AI/CLAP

[23] Yuan, Y. et al. "T-CLAP: Temporal-Enhanced Contrastive Language-Audio Pretraining." arXiv, 2024. https://arxiv.org/abs/2404.17806

[24] Wu, J. et al. "CoLLAP: Contrastive Long-form Language-Audio Pretraining." arXiv, 2024. https://arxiv.org/abs/2410.02271

[25] Doh, S. et al. "LP-MusicCaps: LLM-Based Pseudo Music Captioning." ISMIR, 2023. https://arxiv.org/abs/2307.16372

[26] Takano, T. et al. "Human-CLAP: Human-perception-based Contrastive Language-Audio Pretraining." arXiv, 2025. https://arxiv.org/abs/2506.23553

[27] Ho, J. & Salimans, T. "Classifier-Free Diffusion Guidance." arXiv, 2022. https://arxiv.org/abs/2207.12598

[28] Meta AudioCraft/MusicGen Documentation. https://github.com/facebookresearch/audiocraft

[29] Stable Audio Open Model Card. https://huggingface.co/stabilityai/stable-audio-open-1.0

[30] Liu, H. AudioLDM GitHub. https://github.com/haoheliu/AudioLDM

[31] TANGO Paper. OpenReview, 2023. https://openreview.net/pdf?id=1Sn2WqLku1e

[32] Riffusion Model. https://github.com/riffusion/riffusion-hobby

[33] ACE-Step Documentation. https://deepwiki.com/ace-step/ACE-Step/4.4-input-parameters-and-configuration

[34] Google Lyria/Vertex AI Music Prompt Guide. https://docs.cloud.google.com/vertex-ai/generative-ai/docs/music/music-gen-prompt-guide

[35] Suno Help Center. https://help.suno.com/en/articles/3161921

[36] "Prompt-Aware Classifier-Free Guidance." arXiv, 2025. https://arxiv.org/abs/2509.22728

[37] Google MusicCaps Dataset. https://huggingface.co/datasets/google/MusicCaps

[38] MusicBench Dataset. https://huggingface.co/datasets/amaai-lab/MusicBench

[39] Song Describer Dataset. https://huggingface.co/datasets/renumics/song-describer-dataset

[40] MUCaps Dataset. https://huggingface.co/datasets/M2UGen/MUCaps

[41] MidiCaps Dataset. https://huggingface.co/datasets/amaai-lab/MidiCaps

[42] JamendoMaxCaps Dataset. https://huggingface.co/datasets/amaai-lab/JamendoMaxCaps

[43] ConceptCaps Dataset. https://huggingface.co/datasets/bsienkiewicz/ConceptCaps

[44] AudioCaps Dataset. https://huggingface.co/datasets/d0rj/audiocaps

[45] WavCaps Dataset. https://huggingface.co/datasets/cvssp/WavCaps

[46] AudioSetCaps Dataset. https://huggingface.co/datasets/baijs/AudioSetCaps

[47] LAION-Audio-630K. https://github.com/LAION-AI/audio-dataset

[48] AIME Benchmark Dataset. https://huggingface.co/datasets/disco-eth/AIME

[49] WikiMT-X Dataset. https://huggingface.co/datasets/sander-wood/wikimt-x

[50] MMTrail-20M Dataset. https://huggingface.co/datasets/litwell/MMTrail-20M

[51] MTG-Jamendo Dataset. https://github.com/MTG/mtg-jamendo-dataset

[52] MagnaTagATune Dataset. https://paperswithcode.com/dataset/magnatagatune

[53] FMA Dataset. https://github.com/mdeff/fma

[54] MusicNet Dataset. https://www.kaggle.com/datasets/imsparsh/musicnet-dataset

[55] Google AudioSet & Ontology. https://research.google.com/audioset/ontology/index.html

[56] SunoCaps Dataset. https://www.sciencedirect.com/science/article/pii/S2352340924007078

[57] Suno/Udio Prompt Analysis. arXiv, 2024. https://arxiv.org/abs/2509.11824 / https://github.com/mister-magpie/aims_prompts

[58] Music Ontology Specification. http://musicontology.com/specification/

[59] Cyanite AI Tagging API. https://api-docs.cyanite.ai/docs/audio-analysis-v6-classifier/

[60] "Annotator Subjectivity in the MusicCaps Dataset." CEUR, 2023. https://ceur-ws.org/Vol-3528/paper6.pdf

[61] "Text Mining Pitchfork Reviews for Descriptors of Vocal Sounds." Temple University, 2024. https://sites.temple.edu/tudsc/2024/05/09/text-mining-pitchfork-music-reviews-for-descriptors-of-vocal-sounds/

[62] Atassi, L. "Large Language Models: From Notes to Musical Form." arXiv, 2024. https://arxiv.org/pdf/2404.11976

[63] Huang, R. et al. "Make-An-Audio: Text-To-Audio Generation with Prompt-Enhanced Diffusion Models." arXiv/ICML, 2023. https://arxiv.org/abs/2301.12661

[64] "Prompting Strategies in Audio Generations for Improving Sound Classification." arXiv, 2025. https://arxiv.org/pdf/2504.03329

[65] Bai, Y. et al. "DRAGON: Distributional Rewards Optimize Diffusion Generative Models." arXiv, 2025. https://arxiv.org/abs/2504.15217

[66] "Audio Conditioning for Music Generation via Discrete Bottleneck Features." arXiv, 2024. https://arxiv.org/html/2407.12563v1

[67] "Rethinking Music Captioning with Music Metadata LLMs." arXiv, 2026. https://arxiv.org/html/2602.03023

[68] Liu, S. et al. "MU-LLaMA: Music Understanding LLaMA." arXiv/ICASSP, 2024. https://github.com/shansongliu/MU-LLaMA

[69] Qwen2-Audio. Alibaba, 2024. https://github.com/QwenLM/Qwen2-Audio

[70] Tang, C. et al. "SALMONN." arXiv, 2023. https://www.arxiv.org/pdf/2409.09601

[71] Grötschla, F. et al. "Benchmarking Music Generation Models and Metrics." ICASSP, 2025. https://arxiv.org/abs/2506.19085

[72] Kader, F.B. & Karmaker, S. "A Survey on Evaluation Metrics for Music Generation." arXiv, 2025. https://arxiv.org/html/2509.00051v1

[73] AudioCraft Metrics Documentation. https://github.com/facebookresearch/audiocraft/blob/main/docs/METRICS.md

[74] audioldm_eval Library. https://github.com/haoheliu/audioldm_eval

[75] Gui, A. et al. "Adapting Frechet Audio Distance for Generative Music Evaluation." arXiv, 2024. https://arxiv.org/html/2311.01616v2

[76] Stability AI. "Stable Audio 2.5 Prompt Guide." https://stability.ai/learning-hub/stable-audio-25-prompt-guide

[77] Pons, J. "On Prompting Stable Audio." https://www.jordipons.me/on-prompting-stable-audio/

[78] Udio. "Prompt Like a Master." https://help.udio.com/en/articles/10716541-prompt-like-a-master

[79] Ambience AI. "ACE-Step Music Prompting Guide." https://www.ambienceai.com/tutorials/ace-step-music-prompting-guide

[80] fal.ai. "ElevenLabs Music Prompt Guide." https://fal.ai/learn/biz/eleven-music-prompt-guide

[81] MusicSmith. "AI Music Generation Prompts Best Practices." https://musicsmith.ai/blog/ai-music-generation-prompts-best-practices

[82] Musci.io. "Suno Tags Complete Reference." https://musci.io/blog/suno-tags

[83] Suno Meta Tag Creator. https://sunometatagcreator.com/metatags-guide

[84] HookGenius. "Suno Style Tags Guide." https://hookgenius.app/learn/suno-style-tags-guide/

[85] OpenMusicPrompt. https://openmusicprompt.com/

[86] Word Studio Music Style Prompt Generator. https://word.studio/tool/music-style-prompt-generator/

[87] JustBuildThings AI Music Prompt Generator. https://justbuildthings.com/ai-audio-analysis/ai-music-prompt-generator

[88] Tad AI. https://tad.ai/

[89] yzfly. "awesome-music-prompts." GitHub. https://github.com/yzfly/awesome-music-prompts

[90] "awesome-ai-music-generation." GitHub. https://github.com/Curated-Awesome-Lists/awesome-ai-music-generation

[91] yamathcy. "awesome-music-informatics." GitHub. https://github.com/yamathcy/awesome-music-informatics

[92] ybayle. "awesome-deep-learning-music." GitHub. https://github.com/ybayle/awesome-deep-learning-music

[93] carlosholivan. "DeepLearningMusicGeneration." GitHub. https://github.com/carlosholivan/DeepLearningMusicGeneration

[94] archinetai. "audio-ai-timeline." GitHub. https://github.com/archinetai/audio-ai-timeline

[95] Ma, Y. et al. "Foundation Models for Music: A Survey." arXiv, 2024. https://arxiv.org/abs/2408.14340

[96] "A Survey on Music Generation from Single-Modal, Cross-Modal and Multi-Modal Perspectives." arXiv, 2025. https://arxiv.org/html/2504.00837v2

[97] Wei, M. et al. "Do Music Generation Models Encode Music Theory?" ISMIR, 2024. https://arxiv.org/abs/2410.00872

[98] Singh, N. et al. "Discovering and Steering Interpretable Concepts in Large Generative Music Models." arXiv, 2025. https://arxiv.org/abs/2505.18186