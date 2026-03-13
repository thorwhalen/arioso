Let me think through the categories systematically, then hunt for concrete data sources for each.Here's my proposed taxonomy of `(identifier, prompt_text)` categories, each with the rationale for why a mapping is needed and concrete sources an extraction agent can work from.

---

## 1. **Artists** → sonic style descriptions
**Why a mapping?** Platform policies block artist names; models trained on CLAP/MuLan may not have learned artist–sound associations.

**Sources:**
- [OpenMusic.ai — 100 Artist-Inspired Prompts](https://www.openmusic.ai/docs/song-prompt/100-artist-style-music-prompts) — clean code-block format, extraction-ready
- [Travis Nicholson — Complete List of Prompts & Styles for Suno](https://travisnicholson.medium.com/complete-list-of-prompts-styles-for-suno-ai-music-2024-33ecee85f180) — hundreds of `Artist: tag, tag, tag` pairs
- [Woke Waves — 150 Artist-Inspired Styles](https://www.wokewaves.com/posts/150-artist-styles-suno-ai) — same structure
- [MakeSong.com — Top 100 Artist Prompts](https://www.makesong.com/song-prompt/artist-music-prompts) — artist + tag-string pairs
- The Name-Free Gap paper's **GPT prompt template** + their released data on [HuggingFace](https://huggingface.co/datasets/ArtisticStyling/music-style-control-data) — the most principled approach, reproducible for any artist
- **Tools** (for on-demand generation): [Word Studio Music Style Prompt Generator](https://word.studio/tool/music-style-prompt-generator/), [Music Prompter GPT](https://www.yeschat.ai/gpts-2OToXVvX2g-Music-Prompter), [HowToPromptSuno generator](https://howtopromptsuno.com/)

---

## 2. **Emotions / Moods** → sonic-only descriptors
**Why a mapping?** Emotion words like "nostalgic" or "anxious" aren't in CLAP's training vocabulary as sonic descriptors. The mapping needs to translate affect terms into purely acoustic language (tempo range, dynamics, harmonic qualities, timbre characteristics) without baking in genre or instrument choices.

**Sources for emotion taxonomies:**
- [awesome-MER (GitHub)](https://github.com/AMAAI-Lab/awesome-MER) — master list of every MER dataset, including tag vocabularies
- [datasets_emotion (GitHub)](https://github.com/juansgomez87/datasets_emotion) — curated list of 30+ emotion datasets with annotation schemes
- **MTG-Jamendo Dataset** (in your project knowledge) — 56 mood/theme tags crowdsourced from listeners; available as structured CSV on [GitHub](https://github.com/MTG/mtg-jamendo-dataset)
- **GEMS (Geneva Emotional Music Scales)** — 45 emotion terms grouped into 9 categories (amazement, solemnity, tenderness, nostalgia, calmness, power, joyful activation, tension, sadness) — the academic gold standard
- **Russell's Circumplex Model** quadrants (high/low valence × high/low arousal) — used by DEAM, EMOPIA, AMG1608 datasets
- **MuSe dataset** ([Kaggle](https://www.kaggle.com/datasets/cakiki/muse-the-musical-sentiment-dataset)) — 90K songs with valence/arousal/dominance scores derived from Last.fm mood tags mapped via Warriner's affective word norms
- **Warriner et al. (2013)** — affective norms for 13,915 English lemmas with valence/arousal/dominance scores; the bridge between arbitrary emotion words and dimensional scores that can be translated to sonic descriptors

---

## 3. **Decades / Eras** → production & sonic signatures
**Why a mapping?** "1980s" to a model might mean anything. But the *sonic signature* of a decade — the recording technology, dominant production techniques, frequency characteristics — is very specific and describable in acoustic terms (e.g., gated reverb drums, analog warmth, tape hiss, brick-wall limiting).

**Sources:**
- [HowToPromptSuno.com — Style Prompts](https://howtopromptsuno.com/genres/style-prompts) — era-tagged prompt descriptions
- [Travis Nicholson's "100+ Suno AI Prompts by the Decade"](https://travisnicholson.medium.com/complete-list-of-prompts-styles-for-suno-ai-music-2024-33ecee85f180) — downloadable deck
- The **MusicCaps aspect_list** field often includes era descriptors — extract from [google/MusicCaps on HuggingFace](https://huggingface.co/datasets/google/MusicCaps)
- [ConceptCaps on HuggingFace](https://huggingface.co/datasets/bsienkiewicz/ConceptCaps) — 200-tag taxonomy derived from MusicCaps, includes era/production style tags

---

## 4. **Production Techniques / Aesthetics** → sonic descriptions
**Why a mapping?** Terms like "lo-fi," "tape saturation," "sidechain pumping," or "brick-wall limiting" are producer jargon that models may half-understand. The mapping translates each into a pure sonic description of what it *sounds like* (not how it's achieved).

**Sources:**
- [iZotope Mixing Glossary](https://www.izotope.com/en/learn/a-glossary-of-common-and-confusing-mixing-terms) — definitions framed in sonic terms (e.g., "muddy," "presence," "punchiness")
- [EDMProd Electronic Music Production Glossary](https://www.edmprod.com/electronic-music-production-glossary/) — 500+ terms with sonic descriptions
- [Sonic Atlas — Music Production Terms](https://sonicatlas.co/music-production-terms/)
- [Loopcloud Glossary](https://www.loopcloud.com/cloud/blog/5262-Musical-Terms-Every-Producer-Should-Know-Loopcloud-Glossary)
- [Silverplatter Audio — Sound Designer's Glossary](https://silverplatteraudio.com/pages/glossary) — particularly good on *how effects sound* rather than how they work
- The **MusicBench dataset** on [HuggingFace](https://huggingface.co/datasets/amaai-lab/MusicBench) — 52K audio-text pairs with control sentences describing chords, beats, tempo, key — very structured

---

## 5. **Vocal Descriptors** → sonic descriptions
**Why a mapping?** Users want "a voice like ___" but that's blocked. And terms like "belting," "head voice," "growl," or "melismatic" are technical singing vocabulary the model didn't learn. The mapping translates vocal technique terms into acoustic descriptions (pitch range, breathiness, resonance, dynamics).

**Sources:**
- **Text Mining Pitchfork Reviews for Descriptors of Vocal Sounds** (in your project knowledge) — NLP-extracted vocabulary of vocal descriptors (breathy, nasal, gritty, soaring, etc.) with frequency statistics from thousands of reviews
- The **Suno Tags Complete Reference** (in your project knowledge) — has a dedicated section on voice/vocal tags
- The **ElevenLabs Music Prompt Guide** (in your project knowledge) — vocal style descriptors and the `solo` keyword for vocal isolation
- [HowToPromptSuno — vocal tags](https://howtopromptsuno.com/making-music) — practical vocal prompt language

---

## 6. **Use-Case / Context / Scene** → sonic descriptions
**Why a mapping?** Users think in terms of *function* — "coffee shop background," "workout mix," "horror movie chase scene," "meditation." These are natural-language scene descriptors that need translation into pure musical attributes. This is essentially the "intent → sound" bridge.

**Sources:**
- **MusicSmith's AI Music Prompts Guide** (in your project knowledge) — explicit examples of intent-based prompts ("ad for a sneaker brand," "D&D background music")
- [Envato Elements — AI Music Prompts Guide](https://elements.envato.com/learn/ai-music-prompts) — prompts organized by use-case (lifestyle content, corporate, cinematic)
- [Soundverse — Best Prompts for Music Generator AI](https://www.soundverse.ai/blog/article/best-prompts-for-music-generator-ai) — scene-oriented prompt templates
- **AudioCaps** on [HuggingFace](https://huggingface.co/datasets/d0rj/audiocaps) — 57K audio-caption pairs, many describing *scenes* (crowded café, rainy street, etc.)

---

## 7. **Music Theory Terms** → sonic descriptions
**Why a mapping?** "Dorian mode," "tritone substitution," "polyrhythm," or "Neapolitan chord" are precise musical concepts that models may not reliably produce from the term alone (as the paper *Do Music Generation Models Encode Music Theory?* in your project knowledge investigates). The mapping translates theory jargon into sonic/feel descriptions.

**Sources:**
- **Do Music Generation Models Encode Music Theory** (in your project knowledge) — tests which theory concepts models actually encode
- **MusicBench** on [HuggingFace](https://huggingface.co/datasets/amaai-lab/MusicBench) — includes `prompt_ch` (chord sequences), `prompt_key` (musical key), `prompt_bpm` (tempo) as structured control sentences
- Standard music theory references (e.g., modes, scales, cadences) need to be paired with "sounds like" descriptions rather than formal definitions

---

## 8. **Sub-Genres** → sonic descriptions
**Why a mapping?** Models may know "electronic" but not "vaporwave" or "witch house" or "future funk." Micro-genres are poorly represented in training data. The mapping expands a sub-genre tag into its defining sonic attributes.

**Sources:**
- [Every Noise at Once](https://everynoise.com/) — Spotify's genre taxonomy (~6,000 micro-genres) with audio samples; the taxonomy itself is extractable
- **FMA dataset** (in your project knowledge) — 161-genre taxonomy from the Free Music Archive
- **MTG-Jamendo** (in your project knowledge) — 87 genre tags
- [HowToPromptSuno — genre style prompts](https://howtopromptsuno.com/genres/style-prompts) — sub-genre → prompt descriptor pairs
- **ConceptCaps** on [HuggingFace](https://huggingface.co/datasets/bsienkiewicz/ConceptCaps) — 200-tag taxonomy with explicit genre category

---

## 9. **Instrument Timbres / Synth Patches** → sonic descriptions
**Why a mapping?** "Juno pad," "Moog bass," "Rhodes," "TB-303 acid line" — these are shorthand for very specific timbres that are blocked (brand names) or simply unknown to the model. The mapping decomposes the shorthand into acoustic descriptors (warm analog, detuned, filter-swept, etc.).

**Sources:**
- **MusicCaps aspect_list** on [HuggingFace](https://huggingface.co/datasets/google/MusicCaps) — instrument descriptors like "reverberated guitar," "tinny wide hi hats," "sustained pulsating synth lead"
- **LP-MusicCaps** on HuggingFace ([MSD](https://huggingface.co/datasets/seungheondoh/LP-MusicCaps-MSD), [MTT](https://huggingface.co/datasets/seungheondoh/LP-MusicCaps-MTT), [MC](https://huggingface.co/datasets/seungheondoh/LP-MusicCaps-MC)) — 2.2M tag-to-caption pairs including instrument descriptors
- **Stable Audio prompt guides** (in your project knowledge) — explicitly recommend adjective + instrument pairs ("reverberated guitar," "swelling strings")

---

## 10. **Cultural / Regional Styles** → sonic descriptions
**Why a mapping?** "Bollywood," "Afrobeats," "Nordic noir soundtrack," "Okinawan folk" — these are cultural signifiers that collapse a complex sonic profile into one or two words. Some are well-represented in training data; many are not. And some carry the same name-restriction issues as artists (e.g., "Nollywood soundtrack style").

**Sources:**
- **MusicCaps** and **LP-MusicCaps** contain regional music descriptions
- **AudioSet ontology** — includes cultural music categories; the label set is [publicly available](https://research.google.com/audioset/ontology/index.html)
- **FMA** (in your project knowledge) — includes international genre tags

---

## Summary Table for the Extraction Agent

| # | Category | Identifier Example | Prompt Text Example | Best Extraction Sources |
|---|---|---|---|---|
| 1 | Artist | `billie_eilish` | `close-mic lead timbre, sparse percussion, intimate mix space` | OpenMusic.ai list, Name-Free Gap HF data, Travis Nicholson list |
| 2 | Emotion/Mood | `nostalgic` | `slow tempo, warm midrange, soft dynamics, sustained reverb tails, gentle melodic contour` | GEMS-45, MTG-Jamendo 56 mood tags, Warriner norms, MuSe dataset |
| 3 | Decade/Era | `1980s` | `gated reverb drums, bright analog synths, chorus-drenched guitar, punchy snare, wide stereo mix` | HowToPromptSuno decade packs, MusicCaps aspect_list |
| 4 | Production FX | `tape_saturation` | `warm harmonic distortion, gentle high-frequency rolloff, subtle compression, analog character` | iZotope glossary, Silverplatter glossary, MusicBench control sentences |
| 5 | Vocal Style | `belting` | `loud, sustained, open chest resonance, high intensity, bright formant emphasis` | Pitchfork vocal descriptors (project KB), Suno voice tags |
| 6 | Use-Case/Scene | `chase_scene` | `fast tempo, driving percussion, staccato strings, rising tension, dissonant accents` | MusicSmith guide, AudioCaps dataset |
| 7 | Music Theory | `dorian_mode` | `minor tonality with a raised sixth, jazz-inflected, bittersweet quality, natural minor with a bright twist` | MusicBench structured prompts, Do Models Encode Music Theory (project KB) |
| 8 | Sub-Genre | `vaporwave` | `slowed-down samples, heavy reverb, lo-fi aesthetic, detuned synths, 80s commercial music texture` | Every Noise at Once, FMA taxonomy, ConceptCaps |
| 9 | Instrument/Patch | `moog_bass` | `deep analog sub-bass, warm sawtooth, slight filter sweep, round attack, rich low harmonics` | MusicCaps aspect_list, LP-MusicCaps 2.2M pairs |
| 10 | Cultural/Region | `afrobeats` | `syncopated percussion, call-response vocal pattern, log drum texture, mid-tempo groove, bright horn stabs` | AudioSet ontology, MusicCaps, FMA |

The datasets on HuggingFace (MusicCaps, LP-MusicCaps, ConceptCaps, MusicBench, AudioCaps) are the most extraction-friendly — they're already in Parquet/JSON with structured columns your agent can directly `datasets.load_dataset()` on.

# Extras on (artist, prompt) pairs


I extracted a lot from the Name-Free Gap paper. Let me now search the platform guides for related content.Now let me search the web for community resources — lists, tools, and databases of artist-to-description mappings.Now I have a thorough picture. Here's what the research and community landscape looks like:


## The Concept and Its Names

The core technique — describing an artist's sonic identity through musical attributes rather than their name — goes by several names depending on context:

**In academic research**, the most precise term is the **"name-free gap"**, coined by Nagarajan et al. (2025) in your project knowledge [1]. They define it formally as the controllability difference between artist-name prompts and policy-compliant descriptors. Their method uses an LLM (GPT-5) to decompose an artist's style into sets of **"style tokens"** — short 2–4 word descriptors covering three axes: (i) lead timbre/texture, (ii) instrumentation/timbre, and (iii) mix/space or rhythm/harmony. For example, Billie Eilish becomes `"close-mic lead timbre, sparse percussion, intimate mix space"` appended to a neutral baseline like `"a moody contemporary pop track with subtle electronic textures."` Their key finding: these name-free descriptors recover *much* of the stylistic steering effect of using the artist name directly, though a measurable gap remains.

**In the practitioner/community space**, the same idea is called variously: **"artist-inspired style prompts"**, **"style descriptions"**, **"artist style decomposition"**, or simply **"artist-to-tag mapping."** The Suno and Udio communities use it heavily because Suno blocks artist/band names due to copyright restrictions, so users rely on style-tag correlations instead. The MusicSmith guide in your knowledge base puts it concisely: to avoid unintended stylistic copying, skip specific artist names and prefer genre/era descriptors.

---

## Resources: Artist → Description Lists

### Static Lookup Lists

These pair artist names with copy-paste prompt descriptions:

1. **OpenMusic.ai — 100 Artist-Inspired AI Music Prompts** ([link](https://www.openmusic.ai/docs/song-prompt/100-artist-style-music-prompts)). Each entry includes the artist's name for reference, followed by a clean, artist-name-free style prompt in a code block, crafted for creative and commercial use.

2. **Travis Nicholson — Complete List of Prompts & Styles for Suno AI** ([Medium](https://travisnicholson.medium.com/complete-list-of-prompts-styles-for-suno-ai-music-2024-33ecee85f180)). Hundreds of artists mapped to tag-style descriptions like "Bon Iver: Indie Folk, Ethereal, Intimate, male vocals". He also sells expanded packs with 2,000+ entries.

3. **Scribd — 150 Artist Styles to Shape Your Suno AI Songs** ([link](https://www.scribd.com/document/852563402/150-Artist-Styles-to-Shape-Your-Suno-AI-Songs)). Each artist is accompanied by a brief description highlighting their musical style and vocal characteristics.

4. **Woke Waves — 150 Artist-Inspired Styles for Suno AI** ([link](https://www.wokewaves.com/posts/150-artist-styles-suno-ai)). Entries span pop, jazz, rock, and more, each mapping an artist to a style descriptor string.

5. **Dezomind — 200+ Rock & Metal Prompt Pack** ([Gumroad](https://dezomind.gumroad.com/l/ghcqnkm)). 206 copy-paste style prompts modeled after specific guitar tones, vocal styles, and drum patterns of rock/metal/punk bands (paid).

### Interactive Tools (Artist → Prompt Generators)

6. **Word Studio — Music Style Prompt Generator** ([link](https://word.studio/tool/music-style-prompt-generator/)). You type an artist, album, or mood, and the tool crafts a structured music style prompt — describing instrumentation, rhythm, production style, and emotional tone — without naming the artist. Lets you choose short/medium/long output.

7. **Music Prompter (GPT-4o)** ([YesChat](https://www.yeschat.ai/gpts-2OToXVvX2g-Music-Prompter)). A specialized GPT designed to describe the instrumental style of music artists without referencing lyrics, voice, or the artists' names directly, encapsulating the essence through beat, rhythm, instruments, and mood.

8. **HowToPromptSuno.com — Suno Prompt Generator** ([link](https://howtopromptsuno.com/)). You type an artist, album, genre, or song and get an accurate inspired description for use in music prompt generators. Also has a curated artist-style lookup.

9. **SunoPrompt.com** ([link](https://sunoprompt.com)). An AI that takes your idea and generates precise Suno song prompts with lyric structure, genre tags, and style descriptors.

### The Research Paper's Own Method (DIY via LLM)

The Name-Free Gap paper [1] provides a **reproducible GPT prompt template** for generating style tokens for *any* artist. Their released code and data are at:
- **Code:** [github.com/artisticstyles/artisticstyles-neurips](https://github.com/artisticstyles/artisticstyles-neurips) 
- **Demo + generated clips:** [artisticstyles.github.io/music-style-control-demo](https://artisticstyles.github.io/music-style-control-demo/)
- **Data (manifests, embeddings):** [HuggingFace dataset](https://huggingface.co/datasets/ArtisticStyling/music-style-control-data)

Their template (from the paper's Appendix D.2) asks the LLM to produce a neutral baseline sentence + 5 sets of 3 short "style tokens" per artist, constrained to be lowercase ASCII, no proper nouns, no artist names, covering timbre, instrumentation, and mix/rhythm. This is the most principled and reproducible approach — you can run it for any artist you want.

---

## REFERENCES

[1] Nagarajan, A. et al., "The Name-Free Gap: Policy-Aware Stylistic Control in Music Generation" (2025). [arXiv:2509.00654](https://arxiv.org/abs/2509.00654). Also in your project knowledge as `The_NameFree_Gap__PolicyAware_Stylistic_Control_in_Music_Generation_2025.pdf`.

[2] OpenMusic.ai, "100 Artist-Inspired AI Music Prompts." [openmusic.ai](https://www.openmusic.ai/docs/song-prompt/100-artist-style-music-prompts)

[3] Nicholson, T., "Complete List of Prompts & Styles for Suno AI Music (2026)." [Medium](https://travisnicholson.medium.com/complete-list-of-prompts-styles-for-suno-ai-music-2024-33ecee85f180)

[4] Word Studio, "Music Style Prompt Generator." [word.studio](https://word.studio/tool/music-style-prompt-generator/)

[5] "Music Prompter" (GPT-4o tool). [yeschat.ai](https://www.yeschat.ai/gpts-2OToXVvX2g-Music-Prompter)

[6] HowToPromptSuno.com, "Suno Prompt Generator." [howtopromptsuno.com](https://howtopromptsuno.com/)

[7] MusicSmith, "AI Music Prompts Guide 2026." [musicsmith.ai](https://musicsmith.ai/blog/ai-music-generation-prompts-best-practices). Also in project knowledge as `AI_Music_Generation_Prompts_Best_Practices__MusicSmith_-_2025_.md`.
