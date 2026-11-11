# Suno's generation interface: what a private front end over arioso should copy

Date: 2026-11-11. Suno's UI changes every few weeks, so every UI claim below carries the date of its source. Scope: the Create flow of suno.com only.

## Summary and recommendation

The research could read Suno's own help centre and release notes, plus the API docs, but not the live app (no login). Control names, option order, sliders, model names and upload limits are therefore well sourced. Visual design, the results workspace, the bottom player and the exact copyright-refusal wording are NOT verified from primary sources and are marked as such.

What our UI should copy:

- Two modes, named as Suno names them: Simple (one description box) and Advanced (explicit Lyrics, Styles, Title and a "More Options" block) [1][2]. Our facade already has this split (`customMode`) [6].
- Suno's slider vocabulary and order: Weirdness ("Safe" to "Chaos", 50% as the normal result), Style Influence ("Loose" to "Strong"), and Audio Influence, which appears only when an audio upload is attached [3]. Map them to `weirdnessConstraint`, `styleWeight`, `audioWeight` (each 0 to 1, two decimals) [6].
- The "More Options" order Suno uses today: Exclude styles, Vocal Gender, Duration, Max Mode, Weirdness, Style Influence, Audio Influence, Variety, My Taste [2]. We can expose the first seven (Max Mode and My Taste are Suno-account features with no sunoapi.org parameter that I could verify).
- Audio as a conditional card: an upload control beside the Create button [4] that, once filled, reveals Audio Influence and the Cover and Extend actions. Show the length limit and the refusal state inline.
- One generation produces a pending then streaming then complete lifecycle; sunoapi.org exposes the stages `text`, `first`, `complete` [6], which is enough to show a playable first track before the second finishes.

What our UI should change:

- Do not copy plan-based limits. Suno's help centre says 60 s (free) and 8 min (paid) for uploads [4], while sunoapi.org accepts reference audio of 6 s to 30 min, up to 500 MB [6]. The limit our UI shows must come from the facade, not from Suno's pricing page.
- Do not copy the "Max Mode" and "My Taste" controls; they are account features of suno.com.
- Add what Suno hides: a "will this be refused" pre-flight hint (see the copyright report in this folder), and a plain statement that Audio Influence is a 0 to 1 weight whose effect users report as non-linear (below).
- Keep the Python facade as the single source of truth for ranges and model lists (`config.py` already lists V6, V6_WILD, V6_MINI and the deprecated models) and let the UI read them.

## 1. Create page: modes and controls

Source dating: the Create guide by a third-party Suno educator is dated 11 Sep 2026 [2]; Suno's release notes are dated through 6 Nov 2026 [5]. The guide says Suno may move controls as it rolls out updates [2].

Modes. Simple: describe the result in plain language, with "fast reference doors" labelled Audio, Voice and Image; references can be songs, playlists, uploads, images and video [2]. Advanced: explicit fields in the order audio reference, a Cover workflow, a lyrics area, a Styles area, More Options [2]. A third mode, Sounds, makes one-shot samples and loops with optional BPM and Key (loops launched 27 Jan 2026 for Pro and Premier) [2][5]. I could not verify from primary sources that "Simple" and "Advanced" are still the literal tab labels on the live app; the older help text and our own docs call the second one "Custom" [3][6]. Use "Simple" and "Custom (Advanced)" in labels.

Styles. Free-text field defining genre, production, instrumentation, vocal approach and energy, with style-assist controls and suggested tags beneath it [2]. The exact label of the "enhance" button and the chip behaviour could not be verified.

Lyrics. The web lyrics area was redesigned on 9 Jul 2026 with a "Lyricist" feature that learns from the user's examples, and autosave [5]. Mobile has a lyrics model selector (14 May 2026) [5]. The write / auto-generate / instrumental toggle could not be verified in a dated primary source; sunoapi.org models it as `instrumental` plus `lyrics` or `prompt` [6].

Exclude styles maps to `negativeTags` (up to 1,000 characters on V6) [2][6]. Title maps to `title` (max 80, custom mode only) [6].

Model picker. Top right of Create; options v6 (flagship), v6-wild (more varied), v6-mini (faster, lighter, the only one free users get); all up to 8 minutes per generation; the menu also holds "Create Custom Model" for Pro and Premier [2]. v6 family launched 9 Sep 2026 [5]. Earlier: v5.5 on 26 Mar 2026 (Voices, Custom Models trained from at least 6 tracks, My Taste), v5 on 23 Sep 2025, v4.5 on 1 May 2025, free v4.5-all on 21 Oct 2025 [5].

Duration. A Duration slider arrived on web on 20 Jul 2026 using v5.5 [5]. sunoapi.org: `duration` 10 to 360 s, default 20, only for V5_5 and the V6 family [6]. Note the mismatch: the UI advertises up to 8 minutes, the API caps at 6 minutes.

Vocal Gender maps to `vocalGender` `m` or `f`, and the API says it only raises probability [6]. Variety maps to `variety`, integer 0 to 4, default 1 [6].

Voice and Persona. The Voices button replaced Personas in the Create menu; Style Personas remain inside the Voices menu [7]. Voices: the user records or uploads their own singing (one guide says 30 s to 4 min, unverified) [8]. API: `personaId` plus `personaModel` (`style_persona` default, `voice_persona` for Voice IDs), V5 and later only [6]. Our UI should show one "Voice / Persona" picker and set `personaModel` from the item type.

## 2. The three sliders (most-asked)

Official wording (undated help article): Creative Sliders live in Custom mode. Weirdness runs "Safe" to "Chaos", with 50% the normal result. Style Influence runs "Loose" to "Strong". Audio Influence is a third slider shown only with an audio upload [3]. The help page gives no numeric defaults for the other two and no range for Audio Influence [3].

API mapping [6]: `weirdnessConstraint`, `styleWeight` and `audioWeight`, each 0 to 1 with two decimals, all custom mode only. `audioWeight` is "not supported when there are no vocals" (instrumental). Our UI should therefore disable Audio Influence when Instrumental is on, and say why.

Behaviour caveat: Reddit reports from March 2026 say that at 10% the output still stayed very close to the source, i.e. the slider seems to act higher than labelled [9]. Single-user anecdotes, not confirmed by Suno. Educators suggest starting near the middle (about 50%) and moving gradually [9][10].

## 3. Audio upload and audio-conditioned generation (priority)

What is verified. The Audio Upload button is on the Create page directly next to the Create button; audio can be recorded or added from an existing file, and the upload is saved to the library for reuse [4]. Limits per the help article: Basic 60 s, Pro and Premier 8 min [4]; a 2026 guide notes the pricing page disagrees (it reports 8 min free, 30 min Premier), so treat limits as unstable [11]. Once an upload is attached, Audio Influence appears and is described as an adherence control for how closely the output stays anchored to the source [3][10]. V6 can combine several inputs (songs, playlists, uploads, images, video) in one request [10]. Cover, Extend and Reuse Prompt were rolled out across Suno on 21 May 2025 as "Remix"; the 3 Jun 2025 release added Creative Sliders and 8-minute uploads; Mashup (two songs) and Sample (a section of sound as a starting point) arrived 20 Jan 2026; v5 added remastering with a variation-level control [5]. A "Replace Section" edit exists alongside Extend and Cover [12].

Not verified (no primary source reachable): the exact look of the Audio card, how the Cover versus Extend versus Reference choice is presented after upload, and whether Audio Influence has a default. The Voices upload described as 30 s to 4 min is from a single blog [8].

Copyright refusal UX. Suno screens uploads at upload time [13]. Third-party guides quote two messages, "Copyright detected, please use an original recording" and "Audio quality insufficient", and say original but already-released or fingerprinted material can be flagged; the advice is to stop retrying the same file and contact support with authorship evidence [13][14]. These are secondary sources; the exact in-app wording is unconfirmed. The existing report in this folder covers the detection side. For our UI: show a distinct "refused: rights match" state versus "rejected: quality or format", never auto-retry, and link to authorship guidance.

API side for the same feature: non-custom mode accepts `audioUrls` (6 s to 30 min, up to 500 MB each), `imageUrls` (max 5), `videoUrls` (max 1) and, on V6_WILD only, `midiUrls`; the combined count of style, lyrics and attachments must be at most 10 [6]. arioso also wraps upload-cover and upload-extend [15].

## 4. Results and workspace

Verified: Workspaces were added on 14 Jan 2025, via an option under the Create prompt box, and remixes save to the original song's workspace by default; shareable workspaces came 15 Oct 2026 for paid plans [5].

Not verified from a primary source: two variants per generation, the library list beside the composer, the persistent bottom player, cover art, waveform and version trees. These are widely known behaviours of suno.com but I found no dated source I could open. The sunoapi.org callback gives a three-stage lifecycle (`text`, `first`, `complete`) and carries `stream_audio_url`, so a "plays before finished" state is implementable; the docs do not explain the stream fields further [6]. Recommendation (judgment, not sourced): composer on the left or top, a library list of clips with two sibling variants grouped per generation, a persistent bottom player, and per-clip actions Extend, Cover, Reuse Prompt, Download.

## 5. Visual design language

Not verified. No source describing colours, typography, density, motion or mobile layout was found. Suno's mobile Create has its own parity work (Vocal Gender and prompt memory on 14 May 2026, share-sheet attach from Voice Memos on 4 Jun 2026) [5], so mobile Create is a first-class layout. Recommendation (estimate): dark theme by default, one accent colour, large touch targets, sliders as full-width rows, collapsible "More Options".

## 6. Terminology to reuse

Create, Simple, Custom or Advanced, Lyrics, Styles, Exclude styles, Title, Weirdness, Style Influence, Audio Influence, Variety, Vocal Gender, Duration, Voices, Personas (Style Persona), Custom Model, Sounds (One-Shot, Loop), Cover, Extend, Remix, Reuse Prompt, Replace Section, Mashup, Sample, Workspace, Library, Studio [2][5][7][12].

## 7. Other things worth knowing

- Model churn: v4.5 (May 2025), v5 (Sep 2025), v5.5 (Mar 2026), v6 (Sep 2026) [5]. Our model list must come from config, not code.
- Suno MCP (beta, 28 Oct 2026) lets agents create songs from a voice memo or loop [5]; worth watching as a competing surface.
- Credit cost is shown in the app for Max Mode [2]; our UI has no equivalent unless sunoapi.org credits are surfaced.

## Open questions

1. Exact in-app copyright-refusal copy and whether refusal happens at upload or at generation: needs a logged-in session or a screen recording.
2. Whether the live app still labels the modes Simple and Advanced, and where Lyrics write / auto / instrumental sit.
3. Defaults of Style Influence and Audio Influence in the UI, and whether Audio Influence is truly non-linear [9].
4. Upload limits per plan today (the help page and pricing page disagree) [4][11].
5. Visual design details and the two-variants and bottom-player behaviour: need screenshots; all unverified here.

## REFERENCES

[1] Suno. Introducing v5 (help article, URL returned 404 on 2026-11-11, not used for claims). [help.suno.com/en/articles/8105153](https://help.suno.com/en/articles/8105153)
[2] Jack Righteous. Inside Suno V6: Create Explained (11 Sep 2026, updated Sep 2026; third party). [link](https://jackrighteous.com/blogs/guides-using-suno-ai-music-creation/inside-suno-v6-create-simple-advanced-sounds-guide)
[3] Suno Help Center. How to Use: Creative Sliders (undated). [link](https://help.suno.com/en/articles/6141377)
[4] Suno Help Center. How to Use: Audio Uploads (undated). [link](https://help.suno.com/en/articles/6141569)
[5] Suno. What's New (release notes, to 6 Nov 2026). [link](https://suno.com/release-notes)
[6] sunoapi.org. Generate Music API (docs read 2026-11-11). [link](https://docs.sunoapi.org/suno-api/generate-music)
[7] Suno Help Center. Voices FAQ. [link](https://help.suno.com/en/articles/11362433)
[8] aimusicpreneur. Voices and Personas article (third party, date unknown). [link](https://www.aimusicpreneur.com/?p=15078)
[9] Reddit r/SunoAI snapshots via a mirror (Mar 2026; anecdotal). [link](https://reddit.sentinel-team.org/posts/1scy3ov/snapshots/2026-04-09T19%3A10%3A59.878122Z)
[10] Jack Righteous. Inside Suno V6: Audio Uploads and References Explained (11 Sep 2026). [link](https://jackrighteous.com/blogs/guides-using-suno-ai-music-creation/inside-suno-v6-audio-uploads-references-guide)
[11] Jack Righteous. Suno Blocked My Own Song: Copyright Flags and Upload Fixes (2026). [link](https://jackrighteous.com/blogs/ai-music-distribution-guide/suno-blocked-my-own-song-copyright-upload-errors)
[12] Jack Righteous. Suno Create Page Guide 2026 (29 Jul 2025, updated Sep 2026). [link](https://jackrighteous.com/de-us/blogs/guides-using-suno-ai-music-creation/suno-ai-v4-5-plus-create-page-guide)
[13] Why Suno Blocks Your Cover Upload: Copyright Screening in 2026 (third party). [link](https://sunowatermark.com/blog/suno-cover-upload-blocked/)
[14] Jack Righteous, as [11]: error message wording and support advice.
[15] arioso, `arioso/platforms/sunoapi/config.py` and `SUNOAPI_REFERENCE.md` (this repo).
