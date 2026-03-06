# AI music generation tools: a unified API reference for 21 platforms

**The AI music generation landscape in 2026 spans 21+ tools ranging from fully open-source models to closed commercial platforms, yet almost none share a common API surface — making a unified Python façade both desperately needed and surprisingly achievable.** After deep investigation of every tool's endpoints, parameters, and SDKs, a clear pattern emerges: roughly **40 distinct affordances** recur across platforms under different names, and only **4 tools** (ElevenLabs, MusicGen, Stable Audio, Google Lyria) offer first-class, well-documented APIs. The rest require unofficial wrappers, enterprise applications, or reverse-engineered endpoints. This reference maps the full union of capabilities and native parameter names to guide the design of a `Mapping`/`MutableMapping` façade over all backends.

---

## 1. General characteristics comparison

The table below covers the 18 most significant tools (of 21 researched). Three additional tools (Splash Pro, CassetteAI, Musicfy) are covered in the affordance mapping but omitted from this table for space.

| # | Tool | Website | Pricing (from) | Official API | Open-Source | Max Length | Sample Rate | Vocals | Quality Tier |
|---|------|---------|----------------|-------------|-------------|------------|-------------|--------|-------------|
| 1 | **Suno** | suno.com | Free / $10/mo | ❌ (unofficial only) | Bark only (MIT) | ~4 min (extendable) | 44.1 kHz stereo | ✅ Best-in-class | ⭐⭐⭐⭐⭐ |
| 2 | **Udio** | udio.com | Free / $10/mo | ❌ (unofficial only) | ❌ | ~32s (extendable) | 48 kHz stereo | ✅ Strong | ⭐⭐⭐⭐⭐ |
| 3 | **ElevenLabs Music** | elevenlabs.io | $5/mo (credits) | ✅ REST + Python + JS SDK | ❌ (SDK: MIT) | 10 min | 44.1 kHz | ✅ Multi-language | ⭐⭐⭐⭐ |
| 4 | **Stable Audio** | stableaudio.com | Free (Open) / Enterprise (2.5) | ✅ REST + Python | Partial (Open 1.0: Community License; tools: MIT) | 47s (Open) / 3 min (2.5) | 44.1 kHz stereo | ❌ Limited | ⭐⭐⭐⭐ |
| 5 | **MusicGen** | github.com/facebookresearch/audiocraft | Free (self-host) | Python library (no REST) | ✅ Code: MIT; Weights: CC-BY-NC-4.0 | 30s per chunk (extendable) | 32 kHz | ❌ | ⭐⭐⭐⭐ |
| 6 | **Google Lyria 2** | cloud.google.com | Google Cloud pricing | ✅ REST (Vertex AI) | ❌ | 30s fixed | 48 kHz stereo | ❌ (Lyria 3 will) | ⭐⭐⭐⭐ |
| 7 | **Google Lyria RealTime** | ai.google.dev | Free (experimental) | ✅ WebSocket (Gemini API) | ❌ (Magenta RT: open-weight) | Infinite (streaming) | 48 kHz stereo | ❌ | ⭐⭐⭐⭐ |
| 8 | **Riffusion** | riffusion.com | Free beta / $6/mo | Private beta (riff-api) | Hobby: MIT (~3.9k ⭐) | Full songs | 44.1 kHz | ✅ | ⭐⭐⭐⭐ |
| 9 | **YuE** | github.com/multimodal-art-projection/YuE | Free (self-host) / $0.05/s (fal.ai) | Python CLI + fal.ai REST | ✅ Apache 2.0 (~5.9k ⭐) | 5 min | Codec-dependent | ✅ Multilingual | ⭐⭐⭐⭐ |
| 10 | **AIVA** | aiva.ai | Free / €15/mo | ❌ | ❌ | 5.5 min | 48 kHz 16-bit | ❌ | ⭐⭐⭐⭐ (orchestral) |
| 11 | **Mubert** | mubert.com | $14/mo; API: $49/mo | ✅ REST v3 | ❌ | 25 min | 44.1 kHz | ❌ | ⭐⭐⭐ |
| 12 | **Beatoven.ai** | beatoven.ai | $2.50/mo; API: 50 free credits | ✅ REST + Python SDK | ❌ | 15 min (native) / 2.5 min (fal.ai) | 44.1 kHz stereo | ❌ | ⭐⭐⭐ |
| 13 | **Loudly** | loudly.com | Free / $10/mo; API: free tier | ✅ REST | ❌ | 30 min (Pro) | Standard | ❌ | ⭐⭐⭐ |
| 14 | **Soundraw** | soundraw.io | $11/mo; API: enterprise | ✅ REST (B2B) | ❌ | Customizable | Standard | ❌ | ⭐⭐⭐ |
| 15 | **Boomy** | boomy.com | Free / $10/mo; API: enterprise | ✅ Enterprise only | ❌ | Varies | Standard | ✅ (Auto Vocal) | ⭐⭐⭐ |
| 16 | **Jen** | jenmusic.ai | 300 free credits; API: $0.04/track | ✅ REST (self-serve) | ❌ | No stated limit | 48 kHz stereo | ❌ | ⭐⭐⭐⭐ |
| 17 | **Harmonai** | github.com/Harmonai-org/sample-generator | Free | Python (Diffusers) | ✅ MIT (~752 ⭐) | 1–3s (extendable) | Model-dependent (48 kHz) | ❌ | ⭐⭐ (experimental) |
| 18 | **ACE Studio** | acestudio.ai | ~$17/mo | ❌ (DAW plugin only) | ❌ | Unlimited (MIDI-driven) | 44.1/48 kHz | ✅ Primary feature (140+ voices) | ⭐⭐⭐⭐⭐ (vocals) |

**Key insight for façade design**: Only **ElevenLabs, Google Lyria, Mubert, Beatoven.ai, Loudly, and Jen** offer self-serve REST APIs. **MusicGen, Stable Audio Open, YuE, and Harmonai** are best wrapped via their Python libraries. **Suno and Udio** require unofficial proxy wrappers (sunoapi.org, gcui-art/suno-api, flowese/UdioWrapper). The remaining tools either have enterprise-only APIs or no programmatic access at all.

---

## 2. Documentation and integration links

| # | Tool | Docs Homepage | OpenAPI Spec | Python SDK / Wrapper | JS/TS SDK | MCP Server(s) |
|---|------|--------------|-------------|---------------------|-----------|---------------|
| 1 | **Suno** | help.suno.com | ❌ (sunoapi.org has OpenAPI-like docs) | `SunoAI` (pip, ~105⭐); gcui-art/suno-api (TS→REST, ~2.5k⭐) | gcui-art/suno-api; hissincn/suno-ai | ✅ sandraschi/suno-mcp; CodeKeanu/suno-mcp; lioensky/MCP-Suno |
| 2 | **Udio** | udio.com/help | ❌ | flowese/UdioWrapper (`pip install udio-wrapper`) | ❌ | ❌ |
| 3 | **ElevenLabs** | elevenlabs.io/docs/overview/capabilities/music | ✅ api.elevenlabs.io/openapi.json | `elevenlabs` (PyPI, official, MIT) | `elevenlabs-js` (official) | ✅ elevenlabs/elevenlabs-mcp (official) |
| 4 | **Stable Audio** | github.com/Stability-AI/stable-audio-tools | ❌ (platform.stability.ai has docs) | `stable_audio_tools` (GitHub); `diffusers` (StableAudioPipeline) | ❌ | ❌ |
| 5 | **MusicGen** | facebookresearch.github.io/audiocraft/ | ❌ | `audiocraft` (PyPI, MIT); `transformers` (MusicgenForConditionalGeneration) | ❌ (HuggingFace Inference API) | ❌ |
| 6 | **Google Lyria 2** | cloud.google.com/vertex-ai/.../generate-music | Via Vertex AI | `google-cloud-aiplatform` | ❌ | ❌ |
| 7 | **Google Lyria RT** | ai.google.dev/gemini-api/docs/music-generation | Via Gemini API | `google-genai` | `@google/genai` | ❌ |
| 8 | **Riffusion** | github.com/riffusion/riffusion-hobby | ❌ | `riffusion` (PyPI); `riff-api` (commercial, 12⭐) | riffusion-app-hobby (Next.js) | ❌ |
| 9 | **YuE** | github.com/multimodal-art-projection/YuE | ❌ | Direct `infer.py`; fal.ai REST; HuggingFace Transformers | ❌ | ❌ |
| 10 | **AIVA** | aiva.ai | ❌ | ❌ | ❌ | ❌ |
| 11 | **Mubert** | mubertmusicapiv3.docs.apiary.io | ❌ (Apiary Blueprint) | MubertAI/Mubert-Text-to-Music (Colab, ~2.7k⭐) | ❌ | ❌ |
| 12 | **Beatoven.ai** | beatoven.ai/api; github.com/Beatoven/public-api (9⭐) | ✅ fal.ai/api/openapi/.../beatoven | Official Python SDK (Beatoven/public-api) | fal.ai `@fal-ai/client` | ❌ |
| 13 | **Loudly** | loudly.com/developers | ❌ | ❌ | code4fukui/loudly-api (JS, 0⭐) | ❌ |
| 14 | **Soundraw** | discover.soundraw.io/api | ❌ (Google Doc) | bilgrami/soundraw (Bash, 2⭐) | ❌ | ✅ yksanjo/soundraw-game-bgm (TS) |
| 15 | **Boomy** | boomycorporation.com | ❌ | ❌ | ❌ | ❌ |
| 16 | **Jen** | api.jenmusic.ai/docs/getting-started | ❌ | ❌ | ❌ | ❌ |
| 17 | **Harmonai** | huggingface.co/docs/diffusers/.../dance_diffusion | ❌ | `diffusers` (DanceDiffusionPipeline) | ❌ | ❌ |
| 18 | **ACE Studio** | support.acestudio.ai | ❌ | ❌ | ❌ | ❌ |

Additional MCP servers discovered that aggregate multiple music tools: **amCharlie/aimusic-mcp-tool** (MusicMCP.AI), **SkyworkAI/Mureka-mcp** (Mureka.ai, ~77⭐), **vapagentmedia/vap-showcase** (Suno V5 + Flux + Veo), and **felores/kie-ai-mcp-server** (Suno V5 + ElevenLabs + more).

---

## 3. Feature affordance matrix

This table maps each capability to tool support using ✅ (with native parameter name where applicable) or ❌.

### 3a. Input modes and conditioning

| Affordance | Suno | Udio | ElevenLabs | Stable Audio | MusicGen | Lyria 2 | Lyria RT | Riffusion | YuE | Beatoven | Mubert | Loudly | Jen | AIVA |
|-----------|------|------|-----------|-------------|---------|---------|---------|----------|-----|---------|-------|-------|-----|------|
| **Text prompt** | ✅ `prompt` | ✅ `prompt` | ✅ `prompt` | ✅ `prompt` | ✅ `descriptions` | ✅ `prompt` | ✅ `text` | ✅ `prompt` | ✅ `genre_txt` + `lyrics_txt` | ✅ `prompt` | ✅ `prompt` | ✅ `prompt` | ✅ `prompt` | ❌ (parameter-based) |
| **Negative prompt** | ❌ | ❌ | ❌ | ✅ `negative_prompt` | ❌ | ✅ `negative_prompt` | ❌ | ✅ `end.guidance` | ❌ | ✅ `negative_prompt` | ❌ | ❌ | ❌ | ❌ |
| **Custom lyrics** | ✅ `prompt` (custom mode) | ✅ `custom_lyrics` | ✅ `composition_plan.sections[].lyrics` | ❌ | ❌ | ❌ | ❌ | ✅ `lyrics` | ✅ `lyrics_txt` | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Audio input / conditioning** | ✅ (upload reference) | ✅ `audio_conditioning_path` | ❌ | ✅ `init_audio` (2.5 only) | ✅ `melody_wavs` (melody models) | ❌ | ❌ | ✅ `seed_image_id` | ✅ `vocal_track_prompt_path` | ❌ | ❌ | ✅ (clip upload) | ❌ (StyleFilter™ coming) | ✅ (MIDI/audio upload) |
| **Melody conditioning** | ✅ (hum-to-song) | ⚠️ Partial | ❌ | ⚠️ Via audio-to-audio | ✅ `generate_with_chroma()` | ❌ | ❌ | ❌ | ✅ (ICL dual-track) | ❌ | ❌ | ❌ | ❌ | ✅ (MIDI upload) |
| **Style transfer** | ✅ (reference audio) | ✅ (style features) | ❌ | ✅ `strength` (2.5) | ✅ `musicgen-style` model | ❌ | ✅ (weighted prompts) | ✅ (covers) | ✅ (ICL mode) | ❌ | ❌ | ❌ | ❌ (StyleFilter™ coming) | ✅ (Generation Profiles) |

### 3b. Generation controls

| Affordance | Suno | Udio | ElevenLabs | Stable Audio | MusicGen | Lyria 2 | Lyria RT | Riffusion | YuE | Beatoven | Mubert | Loudly | Jen | AIVA |
|-----------|------|------|-----------|-------------|---------|---------|---------|----------|-----|---------|-------|-------|-----|------|
| **Duration** | ❌ (auto) | ❌ (auto ~32s) | ✅ `music_length_ms` (3k–600k) | ✅ `audio_end_in_s` | ✅ `duration` (set_generation_params) | ❌ (fixed 30s) | ✅ (continuous stream) | ❌ (fixed ~5s clips) | ✅ `run_n_segments` | ✅ `duration` (5–150s) | ✅ `duration` (15–1500s) | ✅ `duration` | ✅ `duration` | ✅ (editor) |
| **BPM / tempo** | ⚠️ Via prompt text | ⚠️ Via prompt | ⚠️ Via prompt | ⚠️ Via prompt text | ⚠️ Via prompt text | ⚠️ Via prompt | ✅ `bpm` (60–200) | ❌ | ❌ (TODO) | ⚠️ Via descriptive words | ❌ | ✅ `tempo`/`bpm` | ⚠️ Via prompt | ✅ Direct parameter |
| **Musical key / scale** | ⚠️ Via prompt | ⚠️ Via prompt | ⚠️ Via prompt | ⚠️ Via prompt | ⚠️ Via prompt | ⚠️ Via prompt | ✅ `scale` (enum) | ❌ | ❌ | ❌ | ❌ | ✅ `key` | ⚠️ Via prompt | ✅ Direct parameter |
| **Genre / style tags** | ✅ `tags` | ⚠️ Via prompt | ⚠️ Via prompt | ⚠️ Via prompt | ⚠️ Via `descriptions` | ⚠️ Via prompt | ⚠️ Via `text` | ✅ `prompt_1` | ✅ `genre_txt` | ⚠️ Via prompt | ✅ `playlist_index` (150+ channels) | ✅ `genre` (50+ options) | ⚠️ Via prompt | ✅ 250+ style presets |
| **Energy / intensity** | ⚠️ Via tags | ⚠️ Via prompt | ⚠️ Via prompt | ❌ | ❌ | ❌ | ✅ `density` (0–1) | ❌ | ❌ | ❌ | ✅ `intensity` (low/medium/high) | ✅ `energy` | ❌ | ❌ |
| **Brightness** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `brightness` (0–1) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Instrument selection** | ⚠️ Via tags | ⚠️ Via prompt | ⚠️ Via prompt | ⚠️ Via prompt | ⚠️ Via prompt | ⚠️ Via prompt | ✅ (instrument group silencing) | ⚠️ Via prompt | ❌ | ⚠️ Via prompt | ❌ | ✅ `instruments` (up to 7) | ⚠️ Via prompt | ✅ Instrument selection |
| **Instrumental only** | ✅ `make_instrumental` | ✅ (toggle) | ✅ `force_instrumental` | ✅ (default) | ✅ (default) | ✅ (only mode) | ✅ (only mode) | ✅ `instrumental` | ⚠️ (see issue #18) | ✅ (default) | ✅ (only mode) | ✅ (default) | ✅ (primary mode) | ✅ (only mode) |
| **Song title** | ✅ `title` | ❌ | ✅ `composition_plan.title` | ❌ | ❌ | ❌ | ❌ | ✅ `title` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Song structure** | ⚠️ Via lyrics tags | ⚠️ Via extend/sessions | ✅ `composition_plan.sections[]` | ❌ | ❌ | ❌ | ❌ | ✅ `prompt_1_start`/`_end` | ✅ `[verse]`/`[chorus]` tags | ❌ | ❌ | ✅ `structure` | ✅ STRUCTUR3™ | ❌ |

### 3c. Model and sampling parameters

| Affordance | Suno | Udio | ElevenLabs | Stable Audio (Open) | MusicGen | Lyria 2 | Lyria RT | Riffusion (hobby) | Beatoven | CassetteAI | Harmonai |
|-----------|------|------|-----------|-------------------|---------|---------|---------|------------------|---------|-----------|---------|
| **Model version** | ✅ `mv` (chirp-v2→v5) | ❌ | ✅ `model_id` (music_v1) | N/A (single model) | ✅ Model variant selection | ✅ `lyria-002` | ✅ `lyria-realtime-exp` | ✅ `model` (FUZZ 0.8→2.0) | ❌ | ❌ | ❌ |
| **Seed** | ❌ | ✅ `seed` | ✅ `seed` (stream only) | ✅ `generator` | ❌ | ✅ `seed` | ✅ `seed` (0–2.1B) | ✅ `start.seed` / `end.seed` | ✅ `seed` | ❌ | ✅ `generator` |
| **Guidance / CFG** | ❌ | ❌ | ❌ | ✅ `cfg_scale` (default 7) | ✅ `cfg_coef` (default 3.0) | ❌ | ✅ `guidance` (0–6, default 4) | ✅ `start.guidance` (default 7) | ✅ `creativity` (default 16) | ❌ | ❌ |
| **Temperature** | ❌ | ❌ | ❌ | ❌ | ✅ `temperature` (default 1.0) | ❌ | ✅ `temperature` (0–3, default 1.1) | ❌ | ❌ | ❌ | ❌ |
| **Top-k** | ❌ | ❌ | ❌ | ❌ | ✅ `top_k` (default 250) | ❌ | ✅ `top_k` (1–1000, default 40) | ❌ | ❌ | ❌ | ❌ |
| **Top-p** | ❌ | ❌ | ❌ | ❌ | ✅ `top_p` (default 0) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Inference steps** | ❌ | ❌ | ❌ | ✅ `num_inference_steps` (default 200) | ❌ | ❌ | ❌ | ✅ `num_inference_steps` (default 50) | ✅ `refinement` (default 100) | ❌ | ✅ `num_inference_steps` (default 100) |
| **Denoising strength** | ❌ | ❌ | ❌ | ✅ `strength` (0–1, for audio-to-audio) | ❌ | ❌ | ❌ | ✅ `start.denoising` (default 0.75) | ❌ | ❌ | ❌ |
| **Sampler type** | ❌ | ❌ | ❌ | ✅ `sampler_type` (dpmpp-3m-sde) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Batch size** | ❌ | ❌ | ❌ | ✅ `num_waveforms_per_prompt` | ✅ `batch_size` (via descriptions list) | ✅ `sample_count` | ❌ | ❌ | ❌ | ❌ | ✅ `batch_size` |

### 3d. Post-generation and output

| Affordance | Suno | Udio | ElevenLabs | Stable Audio | MusicGen | Lyria 2 | Riffusion | YuE | Beatoven | Mubert | Loudly | Jen |
|-----------|------|------|-----------|-------------|---------|---------|----------|-----|---------|-------|-------|-----|
| **Extend / continue** | ✅ `continue_clip_id` + `continue_at` | ✅ `extend()` | ✅ (section editing) | ✅ (inpainting) | ✅ `extend_stride` | ❌ | ✅ `transform:"extend"` + `extend_after_seconds` | ✅ (incremental segments) | ❌ | ✅ (streaming) | ⚠️ | ✅ Extend endpoint |
| **Inpainting** | ✅ (Studio) | ✅ (inpainting tool) | ✅ (Enterprise, `store_for_inpainting`) | ✅ `mask_start` + `mask_end` (2.5) | ❌ | ❌ | ✅ `transform:"replace"` | ❌ | ❌ | ❌ | ❌ | ✅ R3FILL™ |
| **Stem separation** | ✅ (up to 12 stems) | ✅ (4 stems) | ❌ | ❌ | ✅ (stem models) | ❌ | ✅ | ✅ (native dual-track) | ✅ `stems_url` | ⚠️ Partial | ✅ | ✅ |
| **Remix / cover** | ✅ | ✅ (remix tool) | ✅ (edit sections) | ❌ | ❌ | ❌ | ✅ `transform:"cover"` | ✅ (ICL) | ❌ | ✅ | ✅ | ❌ |
| **Output format** | MP3, WAV, MIDI, Video | MP3, WAV, Stems | MP3, PCM (21 variants) | WAV | WAV | WAV (base64) | M4A (320kbps) | WAV (vocal + instrumental + mix) | MP3, WAV, AAC | MP3, WAV | MP3, WAV | MP3, WAV |
| **Streaming output** | ❌ | ❌ | ✅ `/v1/music/stream` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ WebRTC + HTTP | ❌ | ⚠️ Near-RT |
| **Real-time generation** | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ (AI Radio) | ⚠️ (~7s for 2min) |
| **Commercial use** | ✅ (Pro/Premier) | ⚠️ (user doesn't own post-UMG settlement) | ✅ (most; Enterprise for film/TV) | Community License (<$1M free) | ❌ (CC-BY-NC-4.0 weights) | Google Cloud ToS | Experimental ToS | ✅ (paid plans) | ✅ Apache 2.0 | ✅ (paid plans, non-exclusive) | ✅ (paid plans) | ✅ (all output) |
| **Output format param** | ❌ | ❌ | ✅ `output_format` (21 enum values) | ❌ (WAV only) | ❌ (WAV via `audio_write`) | ❌ (WAV only) | ❌ | ❌ | ❌ | ✅ `format` (wav/mp3) | ❌ | ✅ `format` (mp3/wav) |
| **Bitrate control** | ❌ | ❌ | ✅ (via output_format enum) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `bitrate` (128/320) | ❌ | ❌ |
| **C2PA / watermark** | ❌ | ❌ | ✅ `sign_with_c2pa` | ❌ | ❌ | ✅ SynthID (auto) | ✅ SynthID (auto) | ❌ | ❌ | ❌ | ❌ | ✅ JENUINE™ (blockchain) |

---

## 4. Unified affordance mapping for façade design

This is the **union of all parameters** across all 21 tools, normalized to common names. Each row represents one affordance that the Python façade should expose. The `Common Name` is the suggested key for the `Mapping` interface.

| # | Common Name | Type | Description | Tools Supporting (native param) |
|---|------------|------|-------------|-------------------------------|
| 1 | `prompt` | str | Text description of desired music | Suno (`prompt`), Udio (`prompt`), ElevenLabs (`prompt`), Stable Audio (`prompt`), MusicGen (`descriptions`), Lyria 2 (`instances[].prompt`), Lyria RT (`text`), Riffusion (`prompt`/`prompt_1`), YuE (`genre_txt`), Beatoven (`prompt`), Mubert (`prompt`), Loudly (`prompt`), Jen (`prompt`), CassetteAI (`prompt`), Musicfy (`prompt`) |
| 2 | `negative_prompt` | str | Elements to avoid in generation | Stable Audio (`negative_prompt`), Lyria 2 (`negative_prompt`), Beatoven (`negative_prompt`), Riffusion-hobby (`end.prompt` used as contrast) |
| 3 | `lyrics` | str | Custom lyrics text | Suno (`prompt` in custom mode), Udio (`custom_lyrics`), ElevenLabs (`composition_plan.sections[].lyrics`), Riffusion (`lyrics`), YuE (`lyrics_txt`) |
| 4 | `duration` | float | Output length in seconds | ElevenLabs (`music_length_ms`÷1000), Stable Audio (`audio_end_in_s`), MusicGen (`duration`), Beatoven (`duration`), Mubert (`duration`), Loudly (`duration`), Jen (`duration`), CassetteAI (`duration`), YuE (`run_n_segments`×segment_length) |
| 5 | `bpm` | int | Beats per minute | Lyria RT (`bpm`, 60–200), Loudly (`tempo`/`bpm`), AIVA (direct param), Mubert (library filter `bpm`) |
| 6 | `key` | str | Musical key (e.g., "C major") | Lyria RT (`scale`, enum), Loudly (`key`), AIVA (direct param) |
| 7 | `genre` | str | Genre tag or category | Suno (`tags`), YuE (`genre_txt`), Loudly (`genre`), Soundraw (`genre`), Mubert (`playlist_index`), AIVA (250+ presets) |
| 8 | `energy` | float∣str | Energy/intensity level (0–1 or enum) | Mubert (`intensity`: low/medium/high), Loudly (`energy`), Lyria RT (`density`: 0–1), Soundraw (`energy`) |
| 9 | `brightness` | float | Spectral brightness (0–1) | Lyria RT (`brightness`, 0–1) |
| 10 | `instruments` | list[str] | Instrument selection or silencing | Loudly (`instruments`, up to 7), AIVA (instrument selection), Lyria RT (instrument group controls), ACE Studio (MIDI instrument assignment) |
| 11 | `instrumental` | bool | Force instrumental-only output | Suno (`make_instrumental`), ElevenLabs (`force_instrumental`), Riffusion (`instrumental`), YuE (flag) |
| 12 | `title` | str | Song title | Suno (`title`), ElevenLabs (`composition_plan.title`), Riffusion (`title`) |
| 13 | `structure` | list[dict] | Song section structure | ElevenLabs (`composition_plan.sections[]`), Loudly (`structure`), YuE (`[verse]`/`[chorus]` tags), Riffusion (`prompt_N_start`/`_end`) |
| 14 | `audio_input` | bytes∣str | Reference audio for conditioning | Udio (`audio_conditioning_path`), Stable Audio (`init_audio`), MusicGen (`melody_wavs`+`melody_sample_rate`), Riffusion-hobby (`seed_image_id`), YuE (`vocal_track_prompt_path`+`instrumental_track_prompt_path`), AIVA (upload), Loudly (clip upload) |
| 15 | `audio_input_strength` | float | How much the reference audio influences output (0–1) | Stable Audio 2.5 (`strength`), Riffusion-hobby (`start.denoising`) |
| 16 | `continue_from` | str | ID/URL of track to extend | Suno (`continue_clip_id`), Udio (`audio_conditioning_song_id`), Riffusion (`transform:"extend"`), Jen (Extend endpoint) |
| 17 | `continue_at` | float | Timestamp (seconds) to continue from | Suno (`continue_at`), Riffusion (`extend_after_seconds`) |
| 18 | `mask_start` | float | Inpainting region start (seconds or fraction) | Stable Audio 2.5 (`mask_start`), Riffusion (`prompt_1_start` as %), Jen (R3FILL™) |
| 19 | `mask_end` | float | Inpainting region end | Stable Audio 2.5 (`mask_end`), Riffusion (`prompt_1_end` as %) |
| 20 | `model` | str | Model version / variant | Suno (`mv`: chirp-v2→v5), ElevenLabs (`model_id`: music_v1), MusicGen (model name selection), Riffusion (`model`: FUZZ 0.8→2.0), Lyria 2 (`lyria-002`), Lyria RT (`lyria-realtime-exp`) |
| 21 | `seed` | int | Random seed for reproducibility | Udio (`seed`), ElevenLabs (`seed`), Lyria 2 (`seed`), Lyria RT (`seed`), Riffusion (`start.seed`/`end.seed`), Beatoven (`seed`), Harmonai (`generator`), Stable Audio (`generator`) |
| 22 | `guidance` | float | Classifier-free guidance scale | Stable Audio (`cfg_scale`, default 7), MusicGen (`cfg_coef`, default 3), Lyria RT (`guidance`, 0–6), Riffusion-hobby (`start.guidance`, default 7), Beatoven (`creativity`, default 16) |
| 23 | `temperature` | float | Sampling randomness | MusicGen (`temperature`, default 1.0), Lyria RT (`temperature`, 0–3, default 1.1) |
| 24 | `top_k` | int | Top-k sampling parameter | MusicGen (`top_k`, default 250), Lyria RT (`top_k`, 1–1000, default 40) |
| 25 | `top_p` | float | Top-p (nucleus) sampling | MusicGen (`top_p`, default 0) |
| 26 | `num_steps` | int | Number of inference/diffusion steps | Stable Audio (`num_inference_steps`, default 200), Riffusion-hobby (`num_inference_steps`, default 50), Beatoven (`refinement`, default 100), Harmonai (`num_inference_steps`, default 100) |
| 27 | `sampler` | str | Sampling algorithm for diffusion | Stable Audio (`sampler_type`, default "dpmpp-3m-sde") |
| 28 | `batch_size` | int | Number of outputs per request | Stable Audio (`num_waveforms_per_prompt`), MusicGen (len of `descriptions` list), Lyria 2 (`sample_count`), Harmonai (`batch_size`), YuE (`stage2_batch_size`) |
| 29 | `output_format` | str | Desired output format | ElevenLabs (`output_format`, 21 enum values), Mubert (`format`: wav/mp3), Jen (`format`: mp3/wav) |
| 30 | `bitrate` | int | Audio bitrate (kbps) | Mubert (`bitrate`: 128/320), ElevenLabs (via `output_format` enum) |
| 31 | `prompt_weight` | float | Strength of prompt adherence | Riffusion (`prompt_1_strength`, 20–100), Lyria RT (`weight` on WeightedPrompt) |
| 32 | `interpolation_alpha` | float | Blend between two prompts | Riffusion-hobby (`alpha`, 0–1) |
| 33 | `wait_for_completion` | bool | Block until audio is ready | Suno (`wait_audio`), ElevenLabs (sync endpoints), Beatoven (polling pattern) |
| 34 | `voice_id` | str | AI singer/voice model selection | Musicfy (`voice_id`), ACE Studio (140+ voice models), Boomy (Auto Vocal) |
| 35 | `pitch_shift` | int | Pitch adjustment in semitones | Musicfy (`pitch_shift`, -12 to 12), Udio (v1.5 pitch control) |
| 36 | `watermark` | bool | Apply content authenticity watermark | ElevenLabs (`sign_with_c2pa`), Google Lyria (SynthID, always on), Jen (JENUINE™, always on) |
| 37 | `extend_stride` | float | Overlap stride for extended generation | MusicGen (`extend_stride`, default 18s) |
| 38 | `max_tokens` | int | Max generated tokens (LLM-based models) | YuE (`max_new_tokens`, default 3000) |
| 39 | `repetition_penalty` | float | Penalize repeated patterns | YuE (`repetition_penalty`) |
| 40 | `looping` | bool | Generate loopable audio | Beatoven (`ENABLE_LOOPING`), Mubert (streaming mode) |

---

## 5. Complete API parameter catalogs for key tools

### Suno (via gcui-art/suno-api and sunoapi.org)

The most popular Suno wrapper, gcui-art/suno-api (~2,500 ⭐, LGPL-3.0), exposes these endpoints: `/api/generate`, `/api/custom_generate`, `/api/extend_audio`, `/api/generate_lyrics`, `/api/concat`, and an OpenAI-compatible `/v1/chat/completions`. The commercial proxy at **sunoapi.org** (base URL: `https://api.sunoapi.org`) supports all Suno models V3.5 through V5 and adds endpoints for stem separation, MIDI extraction, cover generation, mashups, and music video creation — over **20 endpoints total**. Authentication uses Bearer tokens. The Python SDK `SunoAI` (pip install) wraps the core `generate()` method with parameters `prompt`, `is_custom`, `tags`, `title`, `make_instrumental`, `wait_audio`, and `model_version`.

### ElevenLabs (`POST /v1/music`)

The best-documented music API in this landscape. The official Python SDK method `client.music.compose()` accepts `prompt` (≤4,100 chars), `composition_plan` (sections with style/lyrics/duration_ms), `music_length_ms` (3,000–600,000), `model_id` ("music_v1"), `force_instrumental`, `respect_sections_durations`, `store_for_inpainting` (Enterprise), `sign_with_c2pa`, and `output_format` (21 format variants like `mp3_44100_128`). The streaming endpoint `/v1/music/stream` adds a `seed` parameter and caps duration at 300,000ms. A full **OpenAPI spec is available** at `https://api.elevenlabs.io/openapi.json`.

### MusicGen (`audiocraft.models.MusicGen`)

The `set_generation_params()` method accepts `use_sampling` (bool, True), `top_k` (250), `top_p` (0.0), `temperature` (1.0), `duration` (30.0), `cfg_coef` (3.0), `cfg_coef_beta` (None), `two_step_cfg` (False), and `extend_stride` (18). The melody variants add `generate_with_chroma(descriptions, melody_wavs, melody_sample_rate)`. The style variant adds `set_style_conditioner_params(eval_q=3, excerpt_length=3.0, ds_factor=None, encodec_n_q=None)`. **13 model variants** span 300M to 3.3B parameters, with mono/stereo/melody/style/stem configurations. All models output at **32 kHz** and use the EnCodec tokenizer.

### Google Lyria RealTime (WebSocket API)

The most parameter-rich real-time API. Connects via WebSocket to `wss://generativelanguage.googleapis.com/ws/...BidiGenerateMusic`. Supports `WeightedPrompt` objects (text + weight), and `MusicGenerationConfig` with `guidance` (0–6, default 4), `bpm` (60–200), `density` (0–1), `brightness` (0–1), `scale` (enum of all major/minor keys), `temperature` (0–3, default 1.1), `top_k` (1–1000, default 40), and `seed` (0–2.1B). Session controls include play, pause, reset_context, and per-instrument-group silencing. Outputs continuous **48 kHz stereo 16-bit PCM** in 2-second chunks. Available via `google-genai` Python SDK and `@google/genai` JS SDK.

### Stable Audio Open (via HuggingFace Diffusers)

`StableAudioPipeline.__call__()` accepts `prompt`, `negative_prompt`, `num_inference_steps` (default 200), `audio_end_in_s` (default 10.0), `num_waveforms_per_prompt` (default 1), and `generator`. The lower-level `generate_diffusion_cond()` adds `cfg_scale` (default 7), `sigma_min`/`sigma_max`, `sampler_type`, and `conditioning` dicts with `seconds_start`/`seconds_total`. Output is **44.1 kHz stereo WAV**, max **47 seconds**. Stable Audio 2.5 (commercial, via platform.stability.ai) adds `init_audio`, `strength`, `mask_start`, and `mask_end` for audio-to-audio and inpainting.

### YuE (via `infer.py`)

Command-line parameters: `--stage1_model`, `--stage2_model`, `--genre_txt`, `--lyrics_txt`, `--run_n_segments`, `--stage2_batch_size`, `--max_new_tokens` (default 3000), `--repetition_penalty`, `--output_dir`, `--cuda_idx`, `--use_dual_tracks_prompt`, `--vocal_track_prompt_path`, `--instrumental_track_prompt_path`, `--prompt_start_time`, `--prompt_end_time`. Generates **separate vocal and instrumental tracks** natively. The lyrics file uses structural tags (`[verse]`, `[chorus]`, `[outro]`). Also available on fal.ai at $0.05/second.

---

## 6. Façade design implications

The unified affordance mapping reveals **three tiers of API complexity** that the `MutableMapping` façade must accommodate. The first tier comprises prompt-and-duration tools (CassetteAI, Musicfy, Loudly) that accept essentially two parameters. The second tier includes structured-generation tools (ElevenLabs, Suno, Udio, Riffusion, Jen) with 5–15 parameters covering lyrics, style tags, continuation, and model selection. The third tier encompasses low-level research models (MusicGen, Stable Audio, Harmonai, Lyria RT) that expose 10–20 sampling and diffusion parameters.

A practical façade should expose a `generate(**kwargs)` method where the kwargs map to the 40 common affordances listed above. The backend adapter for each tool translates common names to native parameter names — for instance, `instrumental=True` becomes `make_instrumental=True` for Suno, `force_instrumental=True` for ElevenLabs, and is a no-op for tools like MusicGen that are instrumental by default. Parameters unsupported by a given backend either raise `NotImplementedError` or are silently dropped, configurable via a `strict` flag.

**Authentication patterns** vary significantly: ElevenLabs and Lyria use API keys, Suno/Udio unofficial wrappers use browser cookies, MusicGen/Stable Audio Open/YuE/Harmonai need no auth (local inference), and Mubert uses a two-level customer-id + access-token system. The façade should abstract this via a `credentials` mapping per backend.

**Output normalization** is equally important. Suno returns MP3 URLs, ElevenLabs streams MP3/PCM bytes, MusicGen returns PyTorch tensors, Stable Audio returns NumPy arrays via Diffusers, Google Lyria returns base64-encoded WAV or raw PCM chunks, and Riffusion returns base64 M4A. A consistent output type — either `AudioSegment`, a `(numpy.ndarray, sample_rate)` tuple, or a file path — should be enforced by the façade layer.

For tools lacking official APIs, the façade should support **pluggable backends**: `SunoBackend` wrapping sunoapi.org or gcui-art/suno-api, `UdioBackend` wrapping flowese/UdioWrapper, `MusicGenBackend` wrapping `audiocraft` directly, and so on. The `Mapping` pattern fits naturally: keys are affordance names, values are the current configuration, and iteration yields `(affordance_name, native_parameter_name)` pairs for introspection.

### Recommended backend priority for the façade

Based on API maturity, documentation quality, and Python ecosystem support:

- **Tier 1 (production-ready):** ElevenLabs (best docs, official SDK, OpenAPI spec), Google Lyria 2 (official SDK, GA), MusicGen (mature Python lib, 22.8k⭐), Beatoven.ai (official SDK, fal.ai integration)
- **Tier 2 (usable with caveats):** Suno (via sunoapi.org or gcui-art, TOS gray area), Stable Audio Open (via diffusers), YuE (Apache 2.0, active development), Mubert (REST API, enterprise pricing), Loudly (REST API, free tier)
- **Tier 3 (limited/experimental):** Udio (single unofficial wrapper, TOS gray area), Riffusion (private beta API), Jen (self-serve but sparse docs), Harmonai (experimental quality)
- **Tier 4 (no programmatic access):** AIVA, ACE Studio, Boomy (consumer only), Soundraw (enterprise only)

---

## Conclusion

The AI music generation API landscape is remarkably fragmented. Of **21 tools investigated**, only **6 offer genuinely self-serve REST APIs** (ElevenLabs, Google Lyria, Mubert, Beatoven.ai, Loudly, Jen), and only **ElevenLabs publishes a downloadable OpenAPI specification**. The open-source models — MusicGen (22.8k⭐), YuE (5.9k⭐), Stable Audio Open (3.6k⭐), and Riffusion-hobby (3.9k⭐) — provide the richest parameter surfaces but require local GPU infrastructure. The market leaders Suno and Udio remain API-less officially, forcing reliance on community wrappers operating in legal gray areas.

The **40 unified affordances** identified here form a practical vocabulary for the façade's `Mapping` interface. The most universally supported parameters are `prompt` (15/21 tools), `instrumental` (14/21), and `duration` (10/21). The most differentiating parameters are `brightness` and `density` (Lyria RT only), `composition_plan` (ElevenLabs only), and dual-track vocal/instrumental output (YuE only). **Google's Lyria RealTime** stands out as the only tool offering true real-time streaming with direct BPM, key, density, and brightness controls — making it the closest to the gesture-controlled sound system use case. **MusicGen's melody conditioning** and **YuE's lyrics-to-full-song with ICL style transfer** represent two other unique capabilities worth prioritizing in the façade.

For MCP integration, **8 music generation MCP servers** were found — primarily for Suno (3 servers) and ElevenLabs (1 official). The ElevenLabs MCP server (elevenlabs/elevenlabs-mcp) is the only official, maintained option. The Mureka MCP server (SkyworkAI/Mureka-mcp, 77⭐) provides an alternative backend not covered in the main tool list. A façade-aware MCP server that routes through the unified `Mapping` interface to any backend would fill a significant gap in the ecosystem.