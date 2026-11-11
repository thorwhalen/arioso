# Audio-conditioned music backends beyond Suno: what to add, and a shared parameter vocabulary

Date: 2026-11-11. Every API claim carries the date it was read (all 2026-11-11 unless stated). Prices are the provider's list price on that date. Scope: backends that take an uploaded clip and cover, remix, extend, repaint or restyle it, for a web front end that already has keys for Suno (via sunoapi.org) and ElevenLabs.

## Summary and recommendation

**Add ElevenLabs first, because its key already exists, but know what it is.** Its Music API does not take a raw audio upload in the generation call and does not offer cover or remix. Audio enters by `song_id`: an earlier generation stored with `store_for_inpainting`, or a file sent to `POST /v1/music/upload`. A `song_id` plus a time range can then condition a chunk (`conditioning_ref`, with `condition_strength` of low, medium, high or xhigh) or fill a section (`source_from`, "used for inpainting") [1][2][3]. The product help page calls the feature a style reference of about 30 seconds and says it is not a remixing tool [4]. So ElevenLabs gives style-reference and inpainting, not cover. Whether an uploaded `song_id` is accepted by `conditioning_ref` is not stated in the docs [3]; one test call settles it (upload costs the same as a generation, and a detected copyrighted upload still bills half [3]).

**For a true cover/remix with a "how much to keep" dial, a new paid account is needed: fal.ai.** One fal key reaches Stable Audio 2.5 audio-to-audio and inpaint [5][6], ACE-Step audio-to-audio [7], Stable Audio 3 audio-to-audio [8], and ElevenLabs, Mureka and MiniMax through fal as well [9][10]. Arioso already wraps `stable_audio_25` and `ace_step` over fal, including the audio parameters (`arioso/platforms/stable_audio_25/config.py`, `arioso/platforms/ace_step/config.py`), so this is a key and a UI change, not new adapter work. Recommended second backend: **Stable Audio 2.5 on fal** (numeric dial, audio-to-audio and inpaint, 0.2 USD per call [5]). Cheap alternative on the same key: **ACE-Step** (0.0002 USD per generated second [7], so about 0.012 USD for 60 s [estimate], remix and lyric-edit modes, but no numeric dial on the fal v1 endpoint [7]). The decision for the owner is the fal account and its spend, which is a new cost.

Rejected or not available: Udio has no verified official public API [11]; Google Lyria takes text and images only and has no editing or continuation [12]; MiniMax closed its paid music API to new users from 2026-08-20 [13]; Mureka's audio conditioning is documented only by third parties [9].

**Bug found in arioso (inversion).** Arioso defines `audio_input_strength` as "how much reference audio influences output" (higher follows the audio more), and passes it unchanged to Stable Audio 2.5's `strength`, where higher departs more from the audio (`arioso/base.py`, `arioso/platforms/stable_audio_25/config.py` line 99 onward) [5]. A front-end slider wired to the unified name would run backwards on that backend. Fix by inverting in the adapter (`strength = 1 - audio_input_strength`), with a test.

## Per-backend findings

**ElevenLabs Music.** `POST /v1/music` (compose), also stream, compose-detailed, create-composition-plan, video-to-music, upload, stem-separation and finetune endpoints [14]. Models `music_v1`, `music_v2`, `music_v2_5`; v1 is deprecated and removed 2027-01-31 [15]. Length 3 to 600 s in the API reference (3 s to 5 min on the capabilities page; the two pages disagree, so treat 5 min as the safe limit) [1][15]. `prompt` and `composition_plan` are mutually exclusive; `force_instrumental` works only with `prompt`; plan chunks are 3 to 120 s [1]. Audio input as above [1][3]. Upload response returns `song_id`, optionally a composition plan and word timestamps; no file-length limit is stated [3]. Stem separation returns a ZIP, no limits or price stated [16]. Commercial use: "cleared for nearly all commercial uses", plan-dependent [15]. Price per generation: not on the pages read; unverified. Arioso wraps it but exposes no audio parameter (`supported_affordances` has none); it targets `music_v1` by default.

**ElevenLabs Music v2.5 on fal.** Same model behind a different, simpler door: each plan chunk may carry `audio_reference` with `audio_url`, optional `start_ms`/`end_ms` (window at most 30 s) and `strength` low to xhigh; the first chunk matters most. Accepts a public URL or base64 data URI [9]. No price on the page. This avoids the two-step `song_id` flow but needs the fal key.

**Stable Audio 2.5 (fal).** `fal-ai/stable-audio-25/audio-to-audio`: `prompt`, `audio_url`, `strength` (default 0.8, range 0.01 to 1; 0 returns the input, 1 behaves as no audio), `total_seconds` (1 to 190, defaults to input length), `guidance_scale` (1), `num_inference_steps` (8), `seed` [5][17]. `fal-ai/stable-audio-25/inpaint`: `audio_url`, `mask_start` (30), `mask_end` (190), `seconds_total`, units not stated on the page [6]. Price 0.2 USD per audio on fal [17]. Direct Stability API lists 8 credits per call for text, audio-to-audio and inpaint, at 0.01 USD per credit, so 0.08 USD [18]; its parameter names for these endpoints could not be read (the reference page was not retrievable), so they are unverified. Max input length not stated. Licence not stated on the fal pages; arioso's config records "proprietary / provider terms".

**Stable Audio 3 (fal).** `init_noise_level` default 0.9, range 0 to 1 (1 replaces the source entirely, 0.1 stays close), `duration` 1 to 380 s, price 0.0417 USD per audio for Medium [8]. Same inverted sense as 2.5. Arioso has only a local MLX wrapper (`stable_audio_3`), not a fal one; licence is the Stability Community License per that config. Newer and cheaper than 2.5 on fal, worth a test.

**ACE-Step (fal).** `fal-ai/ace-step/audio-to-audio`: `audio_url`, `original_tags`, `tags`, `edit_mode` (`remix` default, or `lyrics`), `original_lyrics`, `lyrics`, guidance and scheduler options; no `ref_audio_strength`, no length limit or range stated [7]. Price 0.0002 USD per generated second [19]. Self-hosted ACE-Step 1.5 is richer: `task_type` of text2music, cover, repaint, lego, extract, complete; `audio_cover_strength` 0.0 to 1.0 (default 1.0, lower for style transfer); `repainting_start`/`repainting_end` in seconds (-1 means end); reference and source audio fields [20]. Parameter names differ per host (DeepInfra has a separate `repaint_strength`, 0 aggressive to 1 conservative; Runware uses `strength`) [20]. Licence per arioso config: Apache-2.0 for v1 on fal, MIT for 1.5, commercial yes. Arioso already exposes `audio_input`, `reference_audio`, `audio_input_strength`, `edit_mode` and `original_*` (the last two as adapter params), but the strength and reference audio apply to the local runtime only; the fal adapter drops them.

**Suno via sunoapi.org (baseline).** `upload-and-cover-audio`: `uploadUrl` or `taskId`+`audioId`, `audioWeight`, `styleWeight`, `weirdnessConstraint` (each 0 to 1, two decimals), `variety` 0 to 4, `duration` 10 to 360 s on V6 models, `vocalGender`, `negativeTags`, `personaId`; uploads up to 8 minutes [21]. Sibling endpoints: cover, extend, upload-extend, add vocals, add instrumental, vocal separation [22]. Credit costs are not published on the pages read.

**MusicGen-melody.** Replicate `meta/musicgen` (default `model_version` `melody`, 1.5B) costs about 0.042 USD per run; weights are CC-BY-NC 4.0, so no commercial use [23]. Continuation parameters (`continuation`, `continuation_start`, `continuation_end`) appear in third-party version schemas but were not visible on the model page [24]. No fal endpoint found [24]. Arioso wraps it locally only, same licence problem. Not suitable for a public paid app.

**Mureka.** Official docs list lyrics-to-song, prompt-to-song, extend-song and recognize-song [25], but the reference-audio parameters were not retrievable from the official site. Via fal v9.5: `reference_id` (from upload with purpose reference), `vocal_id` (from voice clone), `melody_id` (cannot be combined with prompt, reference or vocal), `duration` 120 to 300 s; 0.15 USD per song with lyrics, 0.50 without [26]. Third-party sources give 15 to 30 s for the voice-clone sample [9]. Not wrapped by arioso. Strong for vocals; no strength dial documented.

**MiniMax Music.** `POST /v1/music_generation`; `music-cover` takes `audio_url` or `audio_base64` (6 s to 6 min, 50 MB, mp3/wav/flac), prompt 10 to 300 characters, optional lyrics (else ASR), or a two-step `cover_feature_id` valid 24 h [13]. From 2026-08-20 the paid API is closed to new users [13]. Not wrapped. Drop.

**Google Lyria 3 / 3.5.** Gemini API, text plus up to 10 images; clip model fixed 30 s; "single-turn", no iterative editing; no audio input [12]. A third-party report of Lyria 3.5 dated 2026-09-04 was not confirmed in primary docs. Arioso wraps Lyria 2 and a RealTime variant; neither fits.

**Udio.** No verified official public API; aggregators resell unofficial access [11]. Exclude.

**Sonauto v2 (fal).** 0.075 USD per generation; a review page states no inpainting or remixing [27]. Exclude for this feature.

## Cross-backend vocabulary

Direction column: "up = follows audio more" or "up = departs more". Unified names are arioso's (`arioso/base.py`); `audio_input_strength` must be defined once as 0 = ignore the audio, 1 = follow it, and every adapter converts.

| Unified name | Suno (sunoapi) | ElevenLabs (official / fal) | Stable Audio 2.5 (fal) | Stable Audio 3 (fal) | ACE-Step (fal v1 / self-hosted 1.5) | Mureka (fal) |
|---|---|---|---|---|---|---|
| `audio_input` | `uploadUrl` (or `taskId`+`audioId`), up to 8 min | `song_id` via `/v1/music/upload` / `audio_reference.audio_url` | `audio_url` | `audio_url` | `audio_url` / `src_audio` | `reference_id` (upload) |
| `audio_input_strength` | `audioWeight` 0 to 1, up = follows more | `condition_strength` low/medium/high/xhigh, up = follows more / `strength` same enum | `strength` 0.01 to 1, up = departs MORE (invert) | `init_noise_level` 0 to 1, up = departs MORE (invert) | none on fal v1 / `audio_cover_strength` 0 to 1, up = follows more | none documented |
| `reference_audio` (style only) | not separate | `conditioning_ref` or `audio_reference`, about 30 s | not available | not available | `reference_audio` (1.5 only) | `reference_id`, `vocal_id` (voice), `melody_id` (tune) |
| `melody` | not available | not available | not available | not available | not available | `melody_id` (exclusive of prompt) |
| `continue_from` / `continue_at` | `/extend`, `/upload-extend`; `continueAt` | not available (v2 plan chunks can append) | not available | not available | `complete` task (1.5) | extend-song endpoint |
| `mask_start` / `mask_end` | not available (add-vocals, add-instrumental instead) | `source_from` with `song_id` + `range`, in `music_v1` plans | `mask_start`/`mask_end`, units unstated | not found | `repainting_start`/`repainting_end` s, -1 = end (1.5) | not available |
| `style_weight` | `styleWeight` 0 to 1 | `context_adherence` low/medium/high (per chunk; text, not audio) | `guidance_scale` | `guidance_scale` | `guidance_scale`, `tag_guidance_scale` | none |
| `duration` | `duration` 10 to 360 s (V6) | `music_length_ms` 3000 to 600000 (prompt mode) | `total_seconds` 1 to 190 | `duration` 1 to 380 | by source length | `duration` 120 to 300 |

Operations supported (yes, partial, no):

| Operation | Suno | ElevenLabs | Stable Audio 2.5 | ACE-Step (fal) | Mureka |
|---|---|---|---|---|---|
| Cover / restyle | yes | partial (style reference only) | yes (remix at chosen strength) | yes (`remix`) | partial (reference) |
| Extend / continue | yes | partial | no | partial (1.5 only) | yes |
| Inpaint / repaint | no | yes (v1 sections) | yes | partial (1.5 only) | no |
| Melody follow | no | no | no | no | yes (`melody_id`) |
| Style reference | partial | yes | no | partial (1.5 only) | yes |
| Lyric edit on existing audio | no | no | no | yes (`edit_mode=lyrics`) | no |

## Standard terminology

Research and tool vocabulary for these operations: audio-to-audio or "init audio" (diffusion started from a noised source, as in Stable Audio's `init_noise_level`; strength here is the noise level, hence the inversion) [8]; cover or "restyle" (new arrangement, same song); continuation or "outpainting"; inpainting or "repaint" (regenerate a masked span); melody conditioning (chroma-based, MusicGen); style or timbre reference (audio prompt that is not reproduced). The fal pages use "audio-to-audio", ElevenLabs uses "audio reference" and "inpainting" [4][5][14].

## Things not asked that matter

1. Copyright: ElevenLabs screens every upload and bills half on a hit [3]; Suno-class uploads and Stable Audio inputs carry the same user-risk. Arioso already has a refusal exception for catalogued input (`arioso/base.py`); the UI needs the same message path for every backend. See `misc/docs/research/general/music-gen-upload-copyright-detection.md`.
2. Input must be a public URL on fal and sunoapi; a VPS needs to upload to a temporary public store (arioso's adapters do this) and delete afterwards.
3. Output URL lifetimes are short (MiniMax 24 h; Stability results 24 h) [13][28]; copy audio to local storage on completion.
4. Mixed units (seconds, milliseconds, enums): the UI should speak seconds and 0 to 1 and let adapters convert.
5. The Stability and fal price gap for the same model (0.08 vs 0.20 USD) [17][18] means a direct Stability key is cheaper at volume, but its audio-to-audio parameters were not verified and arioso wraps only the fal route.

## Open questions

1. Does ElevenLabs accept an uploaded `song_id` in `conditioning_ref`, and what is its real price per generation? Needs one live test call.
2. Direct Stability API parameter names and licence terms for Stable Audio 2.5 (reference page was not retrievable on 2026-11-11).
3. Units and valid range of `mask_start`/`mask_end` on fal Stable Audio 2.5 inpaint.
4. Mureka official reference-audio parameters, max lengths and price; Suno credit costs per cover/extend.
5. Whether fal ACE-Step v2 or an ACE-Step 1.5 host offers `audio_cover_strength` at a price that suits the app.
6. Owner decision: approve a fal account and a monthly spend cap.

## REFERENCES

1. [ElevenLabs, Compose music (API reference)](https://elevenlabs.io/docs/api-reference/music/compose)
2. [ElevenLabs, Compose music with details](https://elevenlabs.io/docs/api-reference/music/compose-detailed.md)
3. [ElevenLabs, Upload Music](https://elevenlabs.io/docs/api-reference/music/upload.md)
4. [ElevenLabs help centre, What is Audio Reference](https://elevenlabs.io/docs/help-center/product/core-capabilities/music/what-is-audio-reference.md)
5. [fal.ai, Stable Audio 2.5 audio-to-audio API](https://fal.ai/models/fal-ai/stable-audio-25/audio-to-audio/api)
6. [fal.ai, Stable Audio 2.5 inpaint API](https://fal.ai/models/fal-ai/stable-audio-25/inpaint/api)
7. [fal.ai, ACE-Step audio-to-audio API](https://fal.ai/models/fal-ai/ace-step/audio-to-audio/api)
8. [fal.ai, Stable Audio 3 Medium audio-to-audio](https://fal.ai/models/fal-ai/stable-audio-3/medium/audio-to-audio/llms.txt)
9. [fal.ai, ElevenLabs Music v2.5 API](https://fal.ai/models/elevenlabs/music/v2.5/api); Mureka vocal and reference notes: [EachLabs Mureka vocal clone](https://www.eachlabs.ai/mureka/mureka/mureka-vocal-clone)
10. [fal.ai, MiniMax Music v2.5](https://fal.ai/models/fal-ai/minimax-music/v2.5/api)
11. [APIFRAME, AI music API pricing 2026 (Udio status; secondary source)](https://apiframe.ai/blog/ai-music-api-pricing-2026)
12. [Google, Generate music with Lyria 3](https://aistudio.google.com/docs/music-generation)
13. [MiniMax, Music generation API](https://platform.minimax.io/docs/api-reference/music-generation.md)
14. [ElevenLabs, Music API index](https://elevenlabs.io/docs/api-reference/music/llms.txt)
15. [ElevenLabs, Eleven Music overview](https://elevenlabs.io/docs/overview/capabilities/music)
16. [ElevenLabs, Stem separation](https://elevenlabs.io/docs/api-reference/music/separate-stems.md)
17. [fal.ai, Stable Audio 2.5 audio-to-audio (llms.txt, price and ranges)](https://fal.ai/models/fal-ai/stable-audio-25/audio-to-audio/llms.txt)
18. [Stability AI, API pricing](https://docs.stability.ai/pricing.md)
19. [fal.ai, ACE-Step audio-to-audio (pricing)](https://fal.ai/models/fal-ai/ace-step/audio-to-audio)
20. [ACE-Step 1.5 API documentation (community mirror)](https://huggingface.co/spaces/mcuo/Ace-Step-v1.5/blob/main/docs/en/API.md); [Runware ACE-Step schema](https://runware.ai/docs/models/ace-step-v1-5-xl-base/schema.json)
21. [sunoapi.org, Upload and cover audio](https://docs.sunoapi.org/suno-api/upload-and-cover-audio)
22. [sunoapi.org documentation index](https://docs.sunoapi.org/)
23. [Replicate, meta/musicgen](https://replicate.com/meta/musicgen)
24. [Replicate, meta/musicgen version schemas (third-party versions, continuation fields)](https://replicate.com/meta/musicgen/versions/7a76a8258b23fae65c5a22debb8841d1d7e816b75c2f24218cd2bd8573787906/api)
25. [Mureka platform documentation](https://platform.mureka.ai/docs/)
26. [fal.ai, Mureka 9.5 song generation](https://fal.ai/models/mureka/v9.5/generate/song/llms.txt)
27. [fal.ai, Sonauto v2 (listing and comparison)](https://fal.ai/models/sonauto/v2/extend)
28. [Stability AI, API reference (async results kept 24 h)](https://docs.stability.ai/api-reference)
