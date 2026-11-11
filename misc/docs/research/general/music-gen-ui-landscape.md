# AI music-generation user interfaces beyond Suno, and visual design for a music-creation web app

Date: 2026-11-11. Research depth: one web-search pass plus a few page fetches; many product details come from third-party guides, not from the products themselves. Every claim is marked with its source, and items that could not be verified are labelled "unverified". Nothing here was observed by using the products directly.

## Summary and recommendation

The products converge on one core idea for audio-conditioned generation: one source clip plus one "how far may the result depart from it" control, plus a text prompt. Udio calls it Variance [1], Stable Audio exposes input-audio strength and prompt strength [4], the Stable Audio API exposes a single `strength` where lower stays closer to the input [5], and Suno-style products use influence sliders (outside this report's scope). The labels disagree and even the direction disagrees between products, so the new app should own one canonical, plain-language control (suggested label "Stay close to original" with an end-labelled slider, "Faithful" to "Reimagined") and let each backend adapter map and invert it. This is the single most valuable design decision for the headline feature.

Recommended shape, as a synthesis (my judgement, not a sourced finding):

- Layout: a two-pane desktop composer (left: source and prompt; right: variants and results), a persistent bottom player, and a single-column stacked version on phones. Not chat-first: chat (Producer.ai [8]) suits one agent backend, but a facade over many backends needs explicit, schema-driven parameter forms.
- Treat "mode" as the primary choice: Create, Cover/Remix, Extend, Inpaint/Replace. Show only the controls the selected backend and mode support, driven by the schema; disable and explain the rest rather than hiding silently.
- Put the source clip in a waveform card with a draggable region (Udio's remix region and inpaint window [1][2]; ElevenLabs section editing [9]) and the strength slider directly beneath it.
- Show lineage: every result records its parent, mode, strength and backend, so Remix, Extend and Cover results form a version tree. No product reviewed shows this well (see section on library patterns), so it is a differentiator.
- wavesurfer.js (BSD-3-Clause [13]) for waveforms and regions; generated gradient cover art from a seed hash (no image generation cost, deterministic, works offline); dark theme with one accent colour.

Biggest caveat: stableaudio.com web-UI details, Mureka web-UI details and Producer.ai status are secondhand or conflicting; verify with a short hands-on session before copying any specific label.

## Product by product

### Udio (observations dated 2025-2026, from help-centre pages)

- Remix: from the Library choose a song and click Remix; the Create window opens with the source track on the left and the Variance slider on the right; the original prompt is prefilled and editable; a lyrics editor is available; for songs of 0:32 or longer an extra Model option under Advanced Controls lets you remix the whole track or one 32-second region [1]. Lower Variance (left) keeps the original structure, higher (right) may sound completely different; changing lyrics may need higher Variance [1]. Rerunning gives a different result each time [1]. A community guide gives the range as 0.1 to 1 [3].
- Own audio: upload supports Remix, Extend (new section before or after) and Inpaint (edit all or part of the upload) [2]; the Remix-from-upload feature is paid-only [2]. Inpaint is done by moving a context window over the region to regenerate [10].
- Styles: one or two audio clips and/or existing Udio songs act as style references; Styles Blending and the Styles Library are desktop-only [6]. A community guide says the similarity slider raises how closely output matches the reference and that Styles replaces the prompt rather than remixing [7].
- Worth copying: the source-left, controls-right remix layout; a prefilled prompt carried over from the parent; one slider with plain end labels. Clumsy: results screen not documented here, the 32-second granularity, paid gating of upload remix (unverified whether still current).

### ElevenLabs Music / ElevenMusic (2025-2026)

- Product page: edit lyrics, add or remove sections, adjust section durations, apply style keywords, or give conversational prompts [11]. A composition plan has global styles, sections with local styles, and lyrics placement; it can be generated from a prompt and edited before composing [12]. The structure differs by model: older examples use `sections` with `duration_ms` and `lines`; examples for `music_v2_5` use an ordered `chunks` array of up to 30 items [12]. Verify against the model you target.
- Composer (reported August 2026 by Digital Music News, third-party): sections can be edited and regenerated without touching the rest; several takes of a section can be compared side by side; per-section style, tempo, energy, instrumentation, key and duration; sections can be swapped, doubled, extended, with an outro added [9]. Music v2 (26 May 2026 per Music Business Worldwide) let users regenerate a selected section [14]. The article does not describe the on-screen layout; unverified.
- Worth copying: the plan as an explicit, inspectable intermediate artifact (an editable list of sections) between prompt and audio; takes grouped under a section for audition. This maps well to a schema-driven form (an array of section objects). Clumsy: model-dependent plan schema forces the facade to normalise.

### Stable Audio / stableaudio.com (2025-2026)

- The user guide describes audio-to-audio as a text prompt plus input audio, adjusted by two sliders, input audio strength and prompt strength, giving minimal to extreme change [4]. Upload limits depend on plan: free tier 3 minutes per month with uploads cropped at 30 seconds; paid tiers 30 to 90 minutes with a 3-minute crop; minimum 1 second [4]. Uploads are stored separately and not used for training [4].
- API side: the ComfyUI node documents `strength` 0.01 to 1.0 (default 1.0) where lower values stay closer to the input, and duration default 190 seconds with input audio 6 to 190 seconds [5]. fal's inpaint endpoint takes a prompt, audio and a mask time window, duration 1 to 190 seconds [15]. Stability's knowledge base suggests 0.85 to 0.95 for more variation and 0.6 to 0.75 for more adherence [16], while another provider describes the opposite direction [16]; this conflict is real and unresolved. The web guide does not mention duration or inpainting controls [4].
- Worth copying: separating "how much of the input to keep" from "how much to follow the text" is the clearest model of the two competing forces. Clumsy: direction of strength inconsistent across surfaces; hard upload crop.

### Riffusion / Producer.ai / Flow Music (status volatile)

- Reported as renamed several times: Riffusion became Producer.ai, was acquired by Google in February 2026, runs on Lyria 3, and the domains now redirect to Google Flow Music [8][17]. Treat as secondhand.
- UI: chat-based agent ("Producer") for edits such as reverb, genre changes, tempo, rewriting a verse; a separate Compose entry point on the right for lyrics or a sound description [8]. Replace/Extend and stem swap are described by reviews, not official docs [8]. Users reported cover failing and library loss during platform transitions (Reddit mirrors, February to April 2026, unverified) [17].
- Worth copying: conversational edit as an optional layer on top of forms (a "tell the agent what to change" box that fills the form). Clumsy: chat hides parameters and makes runs hard to reproduce.

### Mureka

- Third-party guides say a reference track can be picked from the library or uploaded (premium), or a YouTube link pasted, with analysis of genre, rhythm, instrumentation and mood [18]; vocals can be an AI timbre or an uploaded voice sample [18]. API docs (third-party mirror): upload returns a reusable ID for purposes audio, instrumental, melody, reference, remix, vocal, voice; generation takes `reference_id` and `vocal_id`; mp3 and m4a [19]. Rights rules on copyrighted references were not found.
- Worth copying: upload once, get a reusable asset with a role (reference, vocal, melody). That suggests the facade's upload model should be "asset with a role", not "file attached to one run".

### Google: MusicFX, MusicFX DJ, Lyria RealTime

- MusicFX DJ was the first public experiment on Lyria RealTime, built with Google Labs; on-screen knobs can be mapped to a MIDI controller through WebMIDI [20]. The model blends weighted prompts (genres, instruments, moods) and a prompt's weight changes how strongly it affects ongoing output [20][21].
- Config (Gemini API docs): `guidance` 0 to 6 (default 4), `bpm` 60 to 200, `density` 0 to 1, `brightness` 0 to 1, `scale` enum, `mute_bass`, `mute_drums`, `only_bass_and_drums`, `music_generation_mode` (QUALITY, DIVERSITY, VOCALIZATION), `temperature` 0 to 3 (default 1.1), `top_k` 1 to 1000, `seed`; weights are any non-zero value, 1.0 suggested; changing bpm or scale needs a context reset [21]. Open counterpart: Magenta RealTime, steered by text or audio style prompts [22].
- Worth copying: a "weighted prompt stack" control (several text chips, each with a weight knob) is the right widget for real-time and for blending styles; density and brightness are friendly names for abstract params. Clumsy: bpm and scale changes are not instant.

### Sonauto and others

- Sonauto: text or lyrics to song, simple and advanced modes, social hub, v3 Preview up to 4.5 minutes per one aggregator; sources conflict on pricing and version; no official page was found [23].
- Tad AI, Boomy, Soundraw, AIVA, Beatoven: searches returned nothing usable, so no claims are made here. Wubble documents extend and remix with intensity controls (more or less tension, calm to high energy) [24], a useful vocabulary example.

## Comparison table

| Product | Layout | Strength control name | Audio input roles | Section editing | Confidence |
|---|---|---|---|---|---|
| Udio | Create window; source left, slider right | Variance (0.1-1 per community) [1][3] | Remix, Extend, Inpaint, Styles refs [2][6] | Region/context window [1][10] | Medium (help centre) |
| ElevenLabs | Plan/sections editor, Composer [9][12] | none found | not covered here | Per-section regenerate, takes [9] | Medium-low (news) |
| Stable Audio | Prompt plus sliders [4] | Input audio strength, Prompt strength [4]; API `strength` [5] | Audio-to-audio, inpaint (API) [15] | Mask window (API) | Medium; direction conflicts |
| Producer.ai | Chat plus Compose [8] | none | Cover, Extend, Replace, stem swap (reviews) | Highlight and replace | Low (reviews) |
| Mureka | not verified | none found | reference_id, vocal_id [19] | not verified | Low |
| Lyria RealTime / MusicFX DJ | Knobs and prompt weights [20][21] | weight, guidance | text/audio style (Magenta) [22] | n/a (continuous) | High (API docs) |

## Cross-cutting patterns

(a) Composer layout. Udio is a form window with source beside controls [1]; ElevenLabs is a structured plan editor [9][12]; Producer.ai is chat plus a Compose panel [8]; Google DJ is a knob surface [20]. For a facade, a form-first composer with an optional chat helper is the lowest-risk choice (my judgement).

(b) Progressive disclosure. Udio puts Model and region under "Advanced Controls" [1]; Stable Audio keeps two sliders visible [4]; Google exposes expert sampling params (top_k, temperature) only in the API [21]. Suggested tiers (my judgement): prompt and source always visible; strength, duration, seed in a "Tune" row; backend-specific parameters in a collapsible section named after the backend, generated from the schema.

(c) Influence and strength labels. Names seen: Variance [1], input audio strength and prompt strength [4], strength [5], weight and guidance [21], similarity [7]. Directions differ [5][16]. Recommendation: label by outcome, put end-captions on the slider ("Closer to original" to "More different"), show a live one-line explanation, display the backend's native name and value in a tooltip, and store the canonical value with the mapping version.

(d) Pending UX. Not documented in the sources reviewed; unverified for all products. Recommendations (judgement): insert a skeleton card in the library the moment a job is submitted, with the seed-based cover art already visible; poll or stream status; show per-backend expected time; toast and Media Session notification on completion. Real-time products stream audio instead [20].

(e) Library and player. Only Udio's Library-to-Remix entry [1] and ElevenLabs takes-per-section [9] are documented here; no product reviewed shows an explicit version tree (unverified, absence of evidence). Recommendation: group variants under their parent, show lineage chips ("Remix of X, strength 0.3"), and allow compare-A/B. Persistent player: Media Session API can show title and artwork on lock screens, accepts blob or data URL artwork, but iOS lock-screen artwork has been unreliable [25][26].

(f) Mobile. Udio's Styles Blending and Library are desktop-only [6], so mobile parity is a known gap. Recommendation (judgement): bottom sheet for the composer, tab bar of Create / Library / Now Playing, a mini-player above the tab bar expanding to full screen, sliders with large touch targets.

(g) Visual language. I could not retrieve design analyses of the products, so this section is my recommendation, not a finding: near-black surfaces (not pure black), one saturated accent (violet or electric lime) used for primary action, selection and the waveform progress; soft gradients only on cover art and the player backdrop; restrained glass (backdrop blur) for the player bar only; tabular numerals for times; a geometric sans (for example Inter or Geist) plus a monospace for parameters; motion limited to waveform scrub, card appearance and a pulsing skeleton, all disabled under `prefers-reduced-motion`.

## Implementable recommendations for React, Tailwind, shadcn

- Waveform: wavesurfer.js is BSD-3-Clause, has Regions, Timeline and Spectrogram plugins, and v8 is current in its docs [13]. Official React support is not documented on the page I fetched; wrap it in a small hook (unverified whether an official wrapper exists). Alternatives: peaks.js (I believe LGPL-3.0, unverified; check before use) and waveform-playlist (believed MIT, unverified, multitrack focus) [27]. For a library list of many cards, precompute peaks server-side and render a canvas bar from the peaks array instead of instantiating wavesurfer per card.
- Cover-art placeholder: derive a 32-bit hash from the song id or seed (for example with a small FNV or cyrb53 function), pick 3 hues from it, and render 3 to 4 blurred radial-gradient circles in one SVG or CSS `background` with `filter: blur`; same seed, same art, no network. Store the seed with the song so regenerations of art are reproducible. I did not find a library result for this; it is about 30 lines of own code (estimate).
- Sliders and forms: shadcn Slider with end labels; schema-driven forms mapped from each backend's parameter schema, with a `ui:group` hint for the Tune and Advanced tiers.
- Player: one global audio element owned by a store; Media Session metadata with blob-URL artwork rendered from the generated cover [25].
- Terminology: see below; keep the UI vocabulary in one dictionary so a backend rename does not touch components.

## Standard terminology across products

Create or Generate (text to music); Custom or Advanced mode (separate lyrics and style); Style or style prompt; Cover (new rendition, new voice or genre); Remix (variation of an existing track) [1]; Extend (continue past an end, or before a start) [2]; Inpaint or Replace (regenerate a region) [2][8]; Reference or Styles (audio as style guide) [6][19]; Stems (separated or swappable parts) [8]; Composition plan or sections [12]; Variance, strength, weight, guidance, similarity (the influence family) [1][5][7][21]; Seed [21]; Persona or vocal reference [19].

## Not asked but important

- Rights: uploading a file does not clear third-party rights; Stable Audio counts infringing uploads against allowance [4]; Udio advice notes the same [2 context]. A private app should still store a "source provenance" note per upload.
- Platform churn: Producer.ai's renames and reported library loss [8][17] argue for the app keeping its own copy of every generated file and its parameters, not links to backend libraries.
- Upload limits differ widely (30-second crop on Stable Audio free tier [4], 32-second segments in Udio remix [1]); the schema should carry per-backend min and max source length and surface it before upload.
- Strength-direction normalisation and unit tests for each adapter's mapping.
- Accessibility: waveform as an `input range` fallback with keyboard seek; reduced motion.

## Open questions

- What are the actual current labels and layout of stableaudio.com, Mureka and Producer.ai/Flow Music? Needs a hands-on session.
- Which direction does stableaudio.com's prompt strength slider run [4][16]?
- Do any of the products show a lineage tree? Unverified.
- Licences for peaks.js and waveform-playlist [27].
- Whether an official React wrapper for wavesurfer.js exists and is maintained [13].
- Tad AI, Boomy, Soundraw, AIVA, Beatoven were not covered; worth a second pass if a dashboard-style or loop-based model matters.

## REFERENCES

1. [Udio Help: Remixing your music](https://help.udio.com/en/articles/10694179-remixing-your-music)
2. [Udio Help: Create music with your own audio](https://help.udio.com/en/articles/10754328-create-music-with-your-own-audio)
3. [Udio knowledge base (community): Remix](https://succ.gitbook.io/succ-udio-knowledge-base/song-creation/creative-tools/remix)
4. [Stable Audio user guide: audio to audio](https://stableaudio.com/user-guide/audio-to-audio)
5. [ComfyUI docs: Stability Audio to Audio node](https://docs.comfy.org/built-in-nodes/StabilityAudioToAudio.md)
6. [Udio Help: Styles](https://intercom.help/udio-3b94e3c11972/en/articles/11003046-styles)
7. [Udio knowledge base (community): Styles](https://succ.gitbook.io/succ-udio-knowledge-base/song-creation/creative-tools/styles)
8. [Fast.io: Producer AI Review 2026](https://fast.io/resources/producer-ai-review-2026/)
9. [Digital Music News: ElevenMusic Composer section-by-section editor](https://www.digitalmusicnews.com/2026/08/25/elevenmusic-composer-section-by-section-song-editor/)
10. [Tom's Guide: How to extend a song in Udio](https://www.tomsguide.com/how-to-extend-a-song-in-udio)
11. [ElevenLabs docs: Music product](https://elevenlabs.io/docs/eleven-creative/products/music)
12. [ElevenLabs docs: Composition plans](https://elevenlabs.io/docs/eleven-api/guides/how-to/music/composition-plans)
13. [wavesurfer.js repository (BSD-3-Clause)](https://github.com/katspaugh/wavesurfer.js)
14. [Music Business Worldwide: ElevenLabs adds section-by-section editing](https://www.musicbusinessworldwide.com/elevenlabs-adds-section-by-section-song-editing-to-elevenmusic-as-suno-udio-and-google-build-out-rival-tools/)
15. [fal.ai: Stable Audio 2.5 inpaint](https://fal.ai/models/fal-ai/stable-audio-25/inpaint/llms.txt)
16. [Stability AI knowledge base: audio-to-audio strength tuning](https://kb.stability.ai/knowledge-base/audio-to-audio-strength-tuning) (page returned 404 on direct fetch; cited via search snippet, unverified) and [EmpirioLabs: Stable Audio 2.5 API](https://empiriolabs.ai/models/stable-audio-2-5)
17. [Sunowatermark blog: Producer AI is now Google Flow Music](https://sunowatermark.com/blog/producer-ai-review-2026/)
18. [Labellerr: Generating music with Mureka AI](https://www.labellerr.com/blog/mureka-ai/)
19. [WaveSpeed docs: Mureka create upload id](https://wavespeed.ai/docs/docs-api/mureka-ai/mureka-ai-create-upload-id)
20. [Magenta: Lyria RealTime API](https://magenta.tensorflow.org/lyria-realtime)
21. [Google AI Studio docs: Real-time music generation with Lyria RealTime](https://aistudio.google.com/docs/realtime-music-generation)
22. [Magenta RealTime](https://magenta.tensorflow.org/magenta-realtime)
23. [Fitgap: Sonauto AI](https://us.fitgap.com/products/055189/sonauto-ai)
24. [Wubble docs: extend and remix](https://wubble.ai/docs/capabilities/music/extend-remix)
25. [web.dev: Media Session API](https://web.dev/articles/media-session)
26. [WebKit Bugzilla 251782: artwork missing on iOS lock screen](https://bugs.webkit.org/show_bug.cgi?id=251782)
27. [Best-of-web summary: waveform-playlist](https://best-of-web.builder.io/library/naomiaro/waveform-playlist) (licences of peaks.js and waveform-playlist not stated; verify in each repository)
