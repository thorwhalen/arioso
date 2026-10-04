# How music-gen services detect copyrighted uploads (2026-10)

## Summary

Suno does not only match the uploaded *recording*: it recognizes the *composition*. On 2026-10-03, Suno's upload-cover endpoint refused (1) a one-minute excerpt of a commercially released orchestral film main title, and (2) two synthesized General MIDI renders of fan-made MIDI transcriptions of the same piece, instrumental, rendered by fluidsynth with a stock SoundFont. All three failed at poll time with `[413] This audio matches an existing recording in our catalog.` A render shares no audio with any recording, so the match had to come from the music itself: melody, harmony and structure.

That fits what is publicly known. Suno screens uploads with Audible Magic's content identification since October 2024 [1], and Audible Magic sells Version ID, which identifies covers "using melody, harmony, sound and structure" as well as lyrics, across "a different key, a different tempo, different instruments and singers, or no singers at all" [2][3]. Which Audible Magic product Suno runs is not published [1], so "Suno uses Version ID" is an inference from the behaviour, not a documented fact. Suno's second detection partner, Musixmatch Sentinel (August 2026), screens uploads, prompts and outputs, but its cover detection is described as lyric matching [4]. That cannot explain the refusal of an instrumental render, which has no lyrics.

**What to expect (for agents):**

- Covering, extending or remixing a copyrighted piece on Suno will fail, including from a score render, a MIDI file or your own re-performance. The error says "recording", but the match can be at the composition level.
- The refusal arrives at poll time, after the task was accepted (arioso surfaces it as `RuntimeError(... [413] ...)`).
- The fal.ai-hosted models in arioso (`stable_audio_25`, `ace_step`) ran the same original recording without any check on the same day. That is an observation, not a policy guarantee.
- Udio also partnered with Audible Magic, to fingerprint its outputs and check for infringement [5].
- Speed changes or added noise reportedly slip past Suno's filter [6]. Do not do this. It defeats a rights safeguard, and the honest outcome (a refusal) is the useful one to report.

## Body

### Two different problems: recordings and compositions

*Audio fingerprinting* (Content ID, Shazam-style) matches a specific master recording, robust to compression and noise but not to a new performance. *Version identification*, also called *cover song identification* (CSI) in the research literature, matches the underlying work across performances. It uses key-invariant pitch features (chroma), tempo-invariant alignment or learned embeddings. Audible Magic describes needing "deep aspects of the sound that are invariant to differences in master recordings" [2], and its newer Version ID generation uses a neural embedding (VIBE) that places versions of the same work close together "regardless of key, tempo, arrangement, instrumentation, or singer" [3]. Its two patents cover the music-based and lyric-based approaches [7][8].

The academic state of the art is in the same place. ByteCover and CoverHunter learn embeddings over chroma-like inputs and are benchmarked on SHS100K and Da-TACOS [9][10][11]. A synthesized MIDI render keeps exactly what these systems key on: the pitch sequence, the harmony and the form.

### Evidence from our run

| Upload (Suno upload-cover, model V5, instrumental) | Result |
|---|---|
| Original recording, first 60 s | refused, 413 |
| General MIDI render of transcription A (12 parts) | refused, 413 |
| General MIDI render of transcription B (6 parts) | refused, 413 |
| Text prompt only, no audio (character described, no names) | accepted, 2 songs |

The same session measured how closely each render follows the recording with a chroma-DTW cost (`denote.align_audio`): 0.087–0.116, against about 0.16–0.21 for prompt-only pieces in the same style. In other words, the renders carry the original's harmonic and melodic content, which is what a version-identification system detects.

### Open questions

- Whether Suno's threshold catches short quotations or reharmonized variations. Untested.
- Whether a *derivative* far enough from the original (new melody over the same chords) passes. That is a creative and legal question, not a detection one.

## REFERENCES

1. [Suno — Ensuring Content Integrity: Suno Partners with Audible Magic for User Uploads (2024-10-18)](https://about.suno.com/blog/suno-partners-with-audible-magic)
2. [Audible Magic — Identifying cover songs, live performances, AI clones and more (2024-02-07)](https://www.audiblemagic.com/2024/02/07/identifying-cover-songs-live-performances-ai-clones-and-more/)
3. [Audible Magic — Covers and other versions (Version ID, VIBE)](https://www.audiblemagic.com/?p=7190)
4. [Music Business Worldwide — Suno becomes first customer of Musixmatch's Sentinel (2026-08-06)](https://www.musicbusinessworldwide.com/suno-becomes-first-customer-of-musixmatchs-sentinel-which-screens-ai-prompts-and-outputs-for-copyrighted-material/)
5. [Audible Magic — Udio partners with Audible Magic to fingerprint AI-generated tracks](https://www.audiblemagic.com/tag/generative-ai)
6. [AI Musicpreneur — Suno copyright guardrails bypassed (2026)](https://www.aimusicpreneur.com/ai-music-news/suno-copyright-guardrails-bypassed-audacity-2026/)
7. [US 11,294,954 B2 — Music cover identification for search, compliance, and licensing](https://patents.google.com/patent/US11294954)
8. [US 11,816,151 — Music cover identification with lyrics for search, compliance, and licensing](https://patents.justia.com/patent/11816151)
9. [Du et al. — ByteCover: Cover Song Identification via Multi-Loss Training (arXiv 2010.14022)](https://arxiv.org/pdf/2010.14022)
10. [Liu et al. — CoverHunter: Cover Song Identification with Refined Attention and Alignments (arXiv 2306.09025)](https://arxiv.org/pdf/2306.09025)
11. [Yesiler et al. — Da-TACOS: A dataset for cover song identification and understanding (ISMIR 2019)](https://repositori.upf.edu/handle/10230/42771)
