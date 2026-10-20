# Scoring a narration: background music fitted, ducked and synced to speech (research, 2026-10-20)

Scope: instrumental background music (from Suno or another generator) under a spoken narration, here a French poetry audiobook delivered as one audio file per poem with known durations and gaps the producer controls. The goal: music up between poems, far back under speech, and increasingly synced to the speech without becoming song. Status tags: **[verified]** = read on an official page or checked locally on 2026-10-20; **[secondary]** = third-party sources only; **[unverified]** = could not confirm.

## TL;DR

- Suno changed a lot in 2026. On 2026-09-09 it retired all pre-v6 models and replaced them with a v6 family trained on licensed music: v6 and v6-wild for paid users, v6-mini for everyone [1][2][3].
- Suno download caps since 2026-09-03 [10]:
  - Pro: 20 a month.
  - Premier: 60 a month, with no limit inside Suno Studio.
  - Free: "trial" downloads, personal use only.
- Commercial use is granted for songs made and downloaded on a paid plan [10][11]. On 2026-08-06 Suno said it will watermark every generated track [20].
- The Suno features closest to "music around an existing voice" are:
  - **Add Instrumental**: upload a vocal and Suno generates the backing. It launched with v4.5+ in July 2025 [13][14].
  - **Suno Studio** (Premier): a multitrack timeline with BPM control that can generate stems "that flow with your audio" [7][8].
- Suno documents neither feature for spoken word, so test each on one poem first.
- Suno's new **Speech (beta, 2026-10-01)** generates a voice and its soundtrack together. Nothing documents feeding it our own narration, and French support is not documented either [4][5][6].
- For **exact durations**, the best-documented tool is **ElevenLabs Music**. A composition plan holds up to 30 chunks of 3–120 s, each with its own styles, for a total of up to 10 min, and it can inpaint uploaded audio [23][24]. That maps directly onto "one chunk per poem, one chunk per gap".
- The best **open, local** option is **ACE-Step 1.5** (MIT licence, under 4 GB of VRAM claimed) [21][22]. It has:
  - repaint and cover;
  - BPM, key and time-signature settings;
  - durations from 10 s to 10 min;
  - a **Vocal2BGM** mode ("auto-generate accompaniment for vocal tracks"), the open-source counterpart of Add Instrumental. It is also untested on speech.
- Post-production is where sync really happens, and each tool needed is locally or one `pip install` away:
  - ffmpeg 8.0.1 here has `sidechaincompress`, `rubberband` and `atempo` [verified locally][40];
  - `beat_this` for beats and downbeats [41];
  - `allin1` for song sections [42];
  - WhisperX or MFA for French word and phone timing [43][44];
  - Rubber Band or pyrubberband for time-stretching [45].
- A musical idea that removes most of the sync problem is to borrow the Hindustani form [50]. Put an **unmetered, alap-like texture over a drone under the speech**, so there is no rhythm for the speech to clash with. Bring in the **pulse (jor-like) in the gaps between poems**, and sync only the gap music to bars.
- Watermarks:
  - **ElevenLabs does embed an inaudible watermark** in audio it generates. Its Audio Detector checks for it and falls back to the legacy AI Speech Classifier [51][52][53].
  - An older ElevenLabs help article says the watermark is SynthID-based; the current page does not repeat that [54].
  - **Qwen3-TTS and VoxCPM2 document no watermark.** Their READMEs say nothing, and the installed `qwen_tts` and `voxcpm` packages locally contain no watermark code [verified locally][55][56][57].

## 1. Suno in 2026: fitting music to an existing voice and timeline

### 1.1 Relevant releases (all [verified] on Suno's release-notes page [1])

| Date | Release | Relevance |
|---|---|---|
| 2024-07-23 | Instrumental and vocal stems (V1) | stem export |
| 2024-09-19 | Exclude Styles (beta, Pro/Premier) | negative prompting |
| 2024-10-10 | Replace Section: regenerate a 10–30 s part, including instrumental breaks [12] | local edits |
| 2025-06-03 | Song Editor, up to 12 stems, uploads up to 8 min, creative sliders | upload a whole excerpt |
| 2025-09-25 | Suno Studio (Premier) | timeline DAW |
| 2026-01-27 | Sounds: one-shots and loops at a chosen key and BPM | drone or tanpura-like loops at a fixed key |
| 2026-02-16 | Studio 1.2: warp markers, time signatures, Remove FX, alternates | bar-grid editing |
| 2026-03-26 | v5.5: Voices, Custom Models (at least 6 of your tracks), My Taste | consistent style across 1 h |
| 2026-06-11 | Stems: Advanced Split, Split from Mix, Auto Split | clean instrumental stems |
| 2026-07-20 | **Duration slider** on web (v5.5) | target length |
| 2026-08-13 | Studio 2.0: MIDI, chat bar, effects, wavetable synth, automation (Premier) [8] | volume automation in Suno |
| 2026-09-09 | **v6, v6-wild, v6-mini**: plain-language section edits, lyric edits, mashups; text, audio, image and video inputs [2] | current models |
| 2026-09-17 | Studio: better MIDI transcription, **chat-based stem creation from MIDI** | render a speech melody as an instrument |
| 2026-10-01 | **Speech (beta)** [4] | see 1.4 |
| 2026-10-08 | Studio: better downbeat detection, **clip stretching**, fade curves | fitting clips to the grid |

TechCrunch confirms three points: v6 was trained on licensed data (Warner, BMG, Believe), older models are retired, and v6 and v6-wild are paid only [3].

### 1.2 Feature by feature

- **Instrumental mode.** It has existed since v3 [1]. Whether it behaves the same under v6 is [unverified].
- **Exact duration.** The Duration slider sets a *target* length and was released for v5.5 [1][16].
  - A guide says it does not guarantee ending on the exact second [16] [secondary].
  - Whether the slider carries over to v6 is [unverified]. Third-party coverage says v6 allows up to 8 min per generation [secondary].
  - In practice, generate slightly longer than needed and cut at a bar boundary yourself (see 3.5).
- **Extend** works on clips and on uploads [1][9] [verified].
- **Replace Section** regenerates a 10–30 s window and gives two versions [12] [verified]. v6 adds plain-language section edits [2], which can fix one gap's interlude without regenerating the whole track.
- **Cover** re-styles an existing song or upload [1][9]. It is useful for variants of one interlude that keep the same structure.
- **Uploading audio.** Free accounts can upload up to 60 s; Pro and Premier up to 8 min. Extend and Cover then work on the upload [9] [verified]. The 4.5-minute excerpt fits in one upload. The 1-hour book has to go in pieces, cut at the gaps.
- **Add Instrumental exists.** It launched with v4.5+ (2025-07-17) as the reverse of Add Vocals: "upload voice recordings or vocal stems and add Suno-generated instrumentals underneath" [13] [secondary, consistent across outlets].
  - UI path, per a tutorial: Create → Audio → Upload → trim → track ⋯ menu → Remix/Edit → Add Instrumental [14] [secondary].
  - The words in the upload are transcribed into the lyrics box. An "Audio influence" slider sits under Advanced options, and at 100 % the tutorial author judged the result "not quite there yet" [14] [secondary].
  - **Spoken word:** there is no official statement. The only mention is an API reseller page offering "a short scored bed under a poem, intro or voice-over" with `start_s`/`end_s` limits; it adds that Suno-generated clips are not accepted as input [15] [secondary].
  - **Open questions to test:** whether the output keeps our original voice sample for sample or re-renders it; whether Suno sings the transcribed words; how it handles French; and whether the feature survives under v6, which lists audio as an input [2].
  - **How to test:** run one poem of about 1 min. Split the result into stems and keep the instrumental stem. Lay our original narration back on top, and find any time offset by cross-correlating Suno's vocal stem with our file (`scipy.signal.correlate`).
- **Suno Studio** (Premier) [7] [verified]:
  - a timeline where you can "control BPM, volume, pitch";
  - it starts from any audio, can generate parts "that flow with your audio", and exports stems as audio or MIDI.
  - Studio 2.0 adds automation and uncapped 32-bit/48 kHz stem export [8] [secondary]. The October 2026 update adds downbeat detection and clip stretching [1].
  - This is **Suno's most direct path to accompaniment around our narration**: put the narration on a track, set the BPM and generate instrument stems against it. How it behaves with speech is [unverified].
- **Stem export.** Up to 12 stems [1]. That Advanced Split is Premier-only with about 100 instrument types is [secondary].
- **BPM.** Studio exposes BPM [7] and Sounds takes a key and BPM [1] [verified]. Whether ordinary song prompts obey a BPM written in the text is not documented [unverified], so always measure the delivered tempo (see 3.2).
- **Style prompt length.** About 1,000 characters on v4.5, v5 and v5.5, and about 200 on v4 and older [17] [secondary]. The v6 limit is [unverified].
- **Exclude Styles** has been official since 2024 [1]. Its v6 behaviour is [unverified]. Suggested exclusions here: vocals, singing, choir, humming, drums.
- **API.** There is no public self-serve API.
  - An invite-only partner program was announced in July 2026 [18].
  - Unofficial wrappers automate the web app and solve captchas, for example `gcui-art/suno-api` [19]. They are fragile and against the spirit of the ToS, so they are not recommended for a production book.

### 1.3 Licensing, downloads, watermark

- **Paid plans:** downloaded songs "remain yours to use commercially or personally" [10]. A subscriber at the time of creation "is considered the owner", and commercial rights survive cancelling [11] [verified].
- **Free plan:** Suno keeps ownership and use is non-commercial [11]. Since 2026-09-03 free accounts get up to 7 lifetime trial downloads, which are not commercial [10].
- **Download caps** (since 2026-09-03, and they apply to old songs too) [10]:
  - Pro: 20 a month.
  - Premier: 60 a month, with no cap in Studio.
  - Extra downloads can be bought.
  - For a 1-hour book with many retries, **Premier plus Studio** is the plan that does not ration exports.
- **Watermark:** every Suno track will carry a watermark and fingerprinting (announced 2026-08-06) [20]. Expect the music bed to be identifiable as Suno output.

### 1.4 Suno Speech (beta)

Speech makes "a speech and its soundtrack together, in one take" [4]. Reported details:

- It has a Simple mode and an Advanced mode where you supply the script, the music can be turned off, and it runs up to about 8 min (The Verge, via [5]).
- Suno itself warns that accents drift and pauses run long [5][6].

Nothing documents uploading our own narration, using a saved Voice, French, or separate voice and music stems [4][6]. Since our narration comes from our own voices, Speech is useful only as a reference for how Suno balances voice and bed.

## 2. Other generators that can follow a voice or a timeline

| Tool | Conditioning | Duration | Licence / access | Fit |
|---|---|---|---|---|
| **ElevenLabs Music** (`music_v2`, `music_v2_5`) | Plan of up to 30 chunks: text, `duration_ms` (3–120 s), up to 50 positive and 50 negative styles (in English), `context_adherence` [23]. Inpainting: `music.upload` your own audio, keep slices of 50 ms or more, or condition on up to 30 s of reference with `condition_strength` [24] | per chunk; 3 s to 10 min in total | Paid plans include a commercial licence, free does not [26]. A film/TV/games carve-out is [secondary] | **Best for music written to our timeline.** Instrumental means a chunk with no lyrics; `force_instrumental` works only with a plain prompt [25] [secondary] |
| **ACE-Step 1.5** | Text2Music, Cover, Repaint, **Vocal2BGM**, reference audio; BPM, key and time-signature settings; LRC timestamps. Lego, Extract and Complete only on the base models [21][22] | 10 s to 10 min | MIT; under 4 GB claimed, XL needs 12 GB or more | **Best open candidate**; untested on speech |
| **Stable Audio 2.5** | text-to-audio, audio-to-audio, **inpainting of your own audio** [27] | up to 190 s [secondary] | licensed training data; API or enterprise | interludes and seams |
| **Stable Audio Open 1.0** | timing conditioning (`seconds_start`, `seconds_total`) [28][29] | up to 47 s | Stability Community Licence | short exact-length interludes, local |
| **MusicGen-melody** | melody via chromagram of a reference [30] | short | weights CC-BY-NC (non-commercial) | prototyping only; speech chroma is weak, so feed it a MIDI rendering instead |
| **Lyria RealTime** (Gemini API) | streamed, steered live by text, `bpm`, `density`, `scale` [39] | open-ended | Google API terms | a steady-BPM bed |
| **Udio** | n/a | n/a | downloads disabled since 2025-10-30; licensed platform in staged rollout [31] | not usable now [secondary] |
| **YuE / YuE2** | text, ABC score or reference recording into music; instrumental via its skill [32] | not stated | code Apache-2.0; weights CC BY-NC, but creators may monetise outputs; needs a 24 GB GPU | heavy, song-oriented |
| **SongBloom** | 10 s prompt plus lyrics, up to 2.5 min [33] | up to 150 s | availability and licence [unverified] | low |
| **SingSong** (Google) | accompaniment from singing [34] | research | no confirmed release | reference |
| **AnyAccomp** | vocals to accompaniment through a quantized melodic bottleneck; checkpoints `amphion/anyaccomp` [35] | research | licence [unverified] | worth one test |
| **Sing-On-Your-Beat** | text-controllable accompaniment for vocals [36] | research | [unverified] | reference |
| **FastSAG** | diffusion accompaniment from vocals | research | release [unverified] | reference |
| **MuseControlLite** | accompaniment conditioned on melody, rhythm and key from a vocal [38] | demo | [unverified] | reference |
| **Anticipatory Music Transformer** | **symbolic (MIDI)** accompaniment and infilling [37] | MIDI | open, with a Colab | for the speech-melody route (3.7) |

## 3. Post-production techniques and tools

### 3.1 Ducking

**Zero-code option: ffmpeg `sidechaincompress`.** Its options are threshold, ratio, attack, release, makeup, knee and level_sc [40] [verified present here].

```bash
ffmpeg -i music.wav -i narration.wav -filter_complex \
 "[1:a]asplit=2[key][voice];[0:a][key]sidechaincompress=threshold=0.02:ratio=10:attack=60:release=1200[bed];\
  [bed][voice]amix=inputs=2:duration=longest:normalize=0[out]" -map "[out]" mix.wav
```

- It reacts only after speech starts, and it pumps on short pauses inside lines.
- Lookahead trick: delay the music and the voice by about 150 ms with `adelay`, but not the sidechain input, so the compressor sees each phrase early.

**Recommended: a gain envelope built from a speech map.**

- Poem boundaries are already known. Add pauses inside poems from Silero VAD or WhisperX.
- Merge pauses shorter than about 1.5–2 s so the music does not swell on every comma.
- Starting values: about −18 to −22 dB under speech, 0 dB in gaps, a ramp down of 0.5–1 s *before* each poem starts and a ramp up of 1–2 s after it ends. These are a practitioner starting point, not a sourced standard; tune by ear.
- Apply it with numpy and soundfile, or with ffmpeg `volume` evaluated per frame [40].
- Make each gap swell land on a downbeat. That is the first real sync.

### 3.2 Beats, downbeats and sections of the music

- **beat_this** (ISMIR 2024, MIT) [41] is the first choice. It finds beats and downbeats; CLI `beat_this f -o out.beats`, Python `File2Beats`.
- **allin1** (MIT) [42] gives BPM, beats, downbeats, the position in the bar, and labelled sections (intro, verse, chorus, break, inst, solo, outro) as JSON. It needs NATTEN, madmom installed from git, and Demucs separation.
- Fallbacks:
  - madmom, which also serves as beat_this's optional DBN step [41]; install it from git;
  - `librosa.beat.beat_track`, which gives tempo and beats but no downbeats;
  - Suno Studio's own downbeat detection [1].

### 3.3 Word and syllable timing in French

- **WhisperX** [43] gives word-level timestamps. Its default French alignment model is `VOXPOPULI_ASR_BASE_10K_FR` [verified in source]. Since we have the text, align against the known poem rather than transcribing.
- **Montreal Forced Aligner** [44] gives phone-level timing with the `french_mfa` dictionary v3.0.0 (about 105k words, CC BY 4.0) and its matching acoustic model. Vowel phones mark the syllable nuclei.
- **Where French stress falls.** Prominence lands on the last full syllable of each rhythmic group, which is lengthened and usually carries a pitch change [48]. In an alexandrine the fixed accents fall on syllable 6 (the césure) and syllable 12 (the rhyme) [48]. These are the syllables to place on beats.

### 3.4 Time-stretching without changing pitch

- **Rubber Band** is available as an ffmpeg filter (`tempo`, `pitch`, `formant`, `transients`…) [40] [verified present here] and in Python as `pyrubberband.time_stretch(y, sr, rate)` [45].
- **ffmpeg `atempo`** accepts 0.5–100, but above 2× it skips samples [40].
- Rule of thumb (practitioner guidance, not a published threshold):
  - stretch the music by up to ±3–5 %;
  - stretch the speech by 3 % at most;
  - otherwise edit the pauses between lines.

### 3.5 Cutting music at bars and choosing gaps that land on phrases

- **Bar length:** `B = 60 · beats_per_bar / BPM`. At 72 BPM in 4/4, a bar lasts 3.33 s and a 4-bar phrase 13.3 s.
- **Cuts:** cut only at downbeats, preferably at allin1 section boundaries. Join with an equal-power crossfade of about one beat (`acrossfade=c1=qsin:c2=qsin`) [40], at the same position in the bar on both sides.
- **Gap planner.** Choosing the gaps is a small deterministic optimisation over the list of poems:
  1. Fix a minimum silence `g_min` (e.g. 2.5 s) and a lead-in `pre` of about one beat.
  2. Let poem *i* end at `e_i`, and let `P` be the list of phrase-start downbeats in the music.
  3. Start the next poem at `s_{i+1} = min{p ∈ P : p − pre ≥ e_i + g_min}`.
  4. If that gap is too long, snap to the next bar instead of the next phrase, or stretch the music there by a few percent.

### 3.6 Spoken word over a beat, and tempo from speech rate

- Analysis of rap "flow" names three metrical levers [47]:
  - where accented (and rhyming) syllables fall against the beat;
  - how many syllables fall on each beat;
  - whether units of syntax line up with bars.
- For gentle poetry: put line starts on downbeats and group-final stressed syllables on beats, and leave everything else free.
- Read French prose runs at about **7.2 syllables a second** [46]. Slow poetry will be well below that, so measure ours. Two ways to turn that into a tempo:
  - one stress per beat: `BPM = 60 / mean interval between stresses` (stresses 0.8 s apart give 75 BPM);
  - from the syllable rate: `BPM = 60 · syllable_rate / syllables_per_beat` (4.5 syllables a second at 3 per beat gives 90 BPM).
- For an alexandrine of about 3.3 s, one line per 4/4 bar at 72 BPM puts the césure on beat 3 and the rhyme on the next downbeat.
- Always check the tempo that comes back with beat_this and correct it with rubberband.

### 3.7 "Inching towards spoken word" without singing

- **Use the form.** In a Hindustani performance, the alap has no meter and is played over a tanpura drone; the jor adds a pulse without a rhythmic cycle (tala); the jhala is the fast climax [50]. Mapped onto the book:
  - under speech: an alap-like texture, for example "unmetered alap, cello and alto flute over a sustained drone, no percussion";
  - in the gaps: a jor-like pulse, for example "gentle pulse, pizzicato strings, frame drum, 72 BPM";
  - at the end of a section: jhala-like energy.
- **Speech-melody doubling**, as in Steve Reich's *Different Trains*, where instruments play transcribed speech contours alongside or after the recording [49]:
  1. Extract the pitch contour of a line (pyin or CREPE).
  2. Quantise it to the raga's scale and write it out as MIDI.
  3. Have a solo instrument echo it in the gap *after* the line.
  4. Render with FluidSynth and an orchestral soundfont, or with Suno Studio's stem-from-MIDI [1] [untested]. The Anticipatory Music Transformer can add accompaniment to that line [37].
- **Key:** put the drone's tonic near the narrator's median pitch, or a fifth below. This is a design idea, not an attested practice [unverified].

## 4. Recommended pipeline, from simplest to most synced

1. **Level 0: duck and swell.**
   - Generate one long instrumental in Suno: v6, instrumental, the BPM in the prompt, and vocals, singing and drums excluded.
   - Join the poems with fixed gaps.
   - Apply the gain envelope from 3.1.
   - Tools: Suno, numpy or ffmpeg, Silero VAD or WhisperX.
2. **Level 1: musical seams.**
   - Find beats and sections with beat_this and allin1.
   - Start swells on downbeats.
   - Cut the music to length at bars or section boundaries with a one-beat crossfade.
3. **Level 2: music-aware gaps.**
   - Run the gap planner from 3.5.
   - Stretch the music by up to 3–5 % where needed.
   - Regenerate an individual interlude with Suno section edits or Replace Section [2][12], ElevenLabs inpainting [24] or ACE-Step repaint [21].
4. **Level 3: music composed to the timeline.**
   - Measure the stress interval and syllable rate with MFA or WhisperX, and work out a BPM (3.6).
   - Option (a), **ElevenLabs composition plan:** one sparse, alap-like chunk per poem (`duration_ms` = the poem's length) and one pulsed chunk per gap. That means about 6–7 plans of up to 10 min for the 1-hour book [23].
   - Option (b), **Suno:** generate at that BPM over a drone made with Suno Sounds at the same key and BPM [1], and make the gap interludes separately at the same key and BPM.
5. **Level 4: speech snapped to bars.**
   - Adjust only the pauses between lines, with at most a 3 % formant-preserving stretch of the speech.
   - Aim for line starts on downbeats and césure and rhyme syllables on beats.
   - Check by ear. Poetry tolerates far less quantising than rap.
6. **Level 5: accompaniment generated from the narration.**
   - Feed the narration to one of: (a) **Suno Studio** [7]; (b) **Suno Add Instrumental** with influence at 60–100 % [13][14]; (c) **ACE-Step Vocal2BGM**, locally [21].
   - Keep only the instrumental stem, lay our original narration back on top, and duck as in level 0.
   - Add speech-melody echoes in the gaps (3.7).
   - All three are untested on spoken French, so try one poem with each first.

**For the 4.5-minute excerpt:** do levels 0–2 now, since everything they need is on the server, and run a one-poem trial of each level-5 option. **For the 1-hour book:** level 3 (a) or (b) gives the most control per euro, given Suno's download caps [10].

## 5. Watermarks in generated speech

- **ElevenLabs embeds an inaudible audio watermark** [verified].
  - "ElevenLabs embeds watermarks into audio we generate" [51]. It is hidden "at frequencies that are masked by the existing audio", and ElevenLabs claims no loss of quality and no added latency [51].
  - The Audio Detector (free, sign-in required) checks for the watermark first and falls back to the legacy AI Speech Classifier [52]. That classifier only works on older ElevenLabs TTS models.
  - Only audio generated after watermarking was introduced carries the mark; no start date is given [52]. Third-party models served through ElevenLabs are generally not watermarked [53]. "No other platforms can currently detect ElevenLabs watermarks" [51].
  - SynthID: an older ElevenLabs help article describes a Google partnership to embed SynthID [54], but the current page at that address no longer names it [secondary].
  - C2PA: the official pages read today do not mention it [unverified].
  - So ElevenLabs uses both: an embedded watermark first, and a classifier as the fallback.
- **Qwen3-TTS: no documented watermark** [verified]. The GitHub README and HF model card do not mention a watermark, Perth, AudioSeal or provenance [55]. The installed `qwen_tts` package (in the voxy `qwen3tts` environment) contains no watermark code.
- **VoxCPM2: no documented watermark** [verified]. Its "Risks and Limitations" section forbids impersonation and "strongly recommend[s] clearly marking any AI-generated content", but describes no built-in mark; the licence is Apache-2.0 [56][57]. The installed `voxcpm` package contains no watermark code.
- Suno's planned watermark [20] means the music bed will probably be identifiable even where the voice is not.

## How arioso maps to this

- Exact-length sections: ElevenLabs Music's composition plan, reached through `arioso.generate(..., platform="elevenlabs", structure=[...])` (each section a dict passed into `composition_plan.sections`; check the live API for the per-section duration field before relying on it).
- Accompaniment from an existing recording: `arioso.enhance(audio, prompt)` on the audio-in platforms (`ace_step`, `stable_audio_25`, `sunoapi` upload-cover/extend). Suno's Add Instrumental and ACE-Step's Vocal2BGM are not exposed yet.
- Ducking, beat-aware cutting and gap planning are post-production, outside arioso today (ffmpeg, beat_this, allin1, WhisperX/MFA, Rubber Band).

## REFERENCES

1. Suno. [Release notes](https://suno.com/release-notes) (accessed 2026-10-20).
2. Suno. [Introducing v6](https://suno.com/release-notes/introducing-v6). 2026-09-09.
3. TechCrunch. [Suno replaces its AI models with one trained on licensed music](https://techcrunch.com/2026/09/09/suno-replaces-its-ai-models-with-a-new-one-trained-on-licensed-music-as-copyright-suits-pile-up/). 2026-09-09.
4. Suno. [Introducing Speech (beta)](https://www.suno.com/release-notes/introducing-speech-beta). 2026-10-01.
5. Kryden. [Suno Speech adds a soundtrack to your words](https://kryden.ai/news/suno-speech-background-music-review). 2026-10.
6. AIReiter. [Suno Speech beta guide](https://aireiter.com/blog/suno-speech-beta-guide). 2026-10.
7. Suno. [Introducing Suno Studio](https://suno.com/release-notes/introducing-suno-studio). 2025-09-25.
8. Dubspot. [Suno Studio 2.0](https://blog.dubspot.com/suno-studio-2-0). 2026-08.
9. Suno Help. [How to use: Audio Uploads](https://help.suno.com/en/articles/6141569).
10. Suno. [An update to our downloads policy and Terms of Service](https://suno.com/blog/suno-updates-tos). 2026.
11. Suno Help. [Does Suno own the music I make?](https://help.suno.com/en/articles/2416769)
12. Suno. [Replace Section](https://suno.com/release-notes/replace-section). 2024-10-10.
13. RouteNote. [Suno users can now generate music around their own vocals](https://routenote.com/blog/?p=105322); [CometAPI: Suno v4.5+](https://www.cometapi.com/suno-releases-v4-5/). 2025-07.
14. Lilys.ai. [Add instrumentals to vocals in Suno](https://lilys.ai/en/notes/suno-ai-20251031/add-instrumental-to-vocals-suno-ai). 2025-10-31.
15. Unifically. [Suno Add Instrumental (API wrapper)](https://unifically.com/es/models/suno-add-instrumental).
16. Jack Righteous. [Suno v5.5 Duration slider guide](https://jackrighteous.com/blogs/guides-using-suno-ai-music-creation/suno-duration-slider-control-song-length-in-v5-5). 2026-07.
17. HookGenius. [Suno character limits](https://hookgenius.app/fr/learn/suno-character-limits/).
18. Digital Music News. [Suno is opening an API partner program](https://www.digitalmusicnews.com/2026/07/03/suno-is-opening-an-api-partner-program/). 2026-07-03.
19. gcui-art. [suno-api (unofficial)](https://github.com/gcui-art/suno-api).
20. TechCrunch. [Suno says it will start watermarking songs](https://techcrunch.com/2026/08/06/amid-legal-battles-suno-says-it-will-start-watermarking-songs/). 2026-08-06.
21. ACE-Step. [ACE-Step 1.5 (GitHub)](https://github.com/ace-step/ACE-Step-1.5).
22. ACE-Step. [Ace-Step1.5 model card](https://huggingface.co/ACE-Step/Ace-Step1.5).
23. ElevenLabs. [Music: composition plans](https://elevenlabs.io/docs/eleven-api/guides/how-to/music/composition-plans).
24. ElevenLabs. [Music: inpainting](https://elevenlabs.io/docs/eleven-api/guides/how-to/music/inpainting).
25. ElevenLabs. [API reference: compose](https://elevenlabs.io/docs/api-reference/music/compose).
26. ElevenLabs Help. [Can I publish the content I generate?](https://help.elevenlabs.io/hc/en-us/articles/13313564601361)
27. Stability AI. [Stable Audio 2.5](https://stability.ai/news/stability-ai-introduces-stable-audio-25-the-first-audio-model-built-for-enterprise-sound-production-at-scale). 2025-09.
28. Stability AI. [stable-audio-open-1.0](https://huggingface.co/stabilityai/stable-audio-open-1.0).
29. Stability AI. [Stable Audio: timing-conditioned latent audio diffusion](https://stability.ai/research/stable-audio-efficient-timing-latent-diffusion).
30. Meta. [facebook/musicgen-melody](https://huggingface.co/facebook/musicgen-melody).
31. Music Business Worldwide. [Universal settles Udio lawsuit](https://www.musicbusinessworldwide.com/universal-music-settles-udio-lawsuit-strikes-deal-for-licensed-ai-music-platform). 2025-10.
32. M-A-P. [YuE (GitHub)](https://github.com/multimodal-art-projection/YuE).
33. [SongBloom](https://nips.cc/virtual/2025/poster/119028). NeurIPS 2025.
34. Donahue et al. [SingSong](https://ar5iv.labs.arxiv.org/html/2301.12662). 2023.
35. [AnyAccomp](https://arxiv.org/abs/2509.14052). 2025.
36. [Sing-On-Your-Beat](https://arxiv.org/html/2411.01661v2). 2024.
37. Thickstun et al. [Anticipatory Music Transformer](https://crfm.stanford.edu/2023/06/16/anticipatory-music-transformer.html). 2023.
38. [MuseControlLite singing accompaniment demo](https://neurips.cc/virtual/2025/loc/san-diego/123747). NeurIPS 2025.
39. Google. [Lyria RealTime](https://ai.google.dev/gemini-api/docs/realtime-music-generation).
40. FFmpeg. [Filters documentation](https://ffmpeg.org/ffmpeg-filters.html).
41. Foscarin, Schlüter, Widmer. [beat_this](https://github.com/CPJKU/beat_this). ISMIR 2024.
42. [all-in-one (allin1)](https://github.com/mir-aidj/all-in-one).
43. Bain et al. [WhisperX](https://github.com/m-bain/whisperX).
44. MFA. [French MFA dictionary v3.0.0](https://mfa-models.readthedocs.io/en/latest/dictionary/French/French%20MFA%20dictionary%20v3_0_0.html).
45. [pyrubberband](https://pyrubberband.readthedocs.io/); [Rubber Band](https://breakfastquay.com/rubberband/).
46. Pellegrino, Coupé, Marsico. [A cross-language perspective on speech information rate](https://www.cambridge.org/core/journals/language/article/abs/crosslanguage-perspective-on-speech-information-rate/73064B3F77E7CE81C42CAB29B4393F80). *Language* 87(3), 2011.
47. Adams. [On the metrical techniques of flow in rap music](https://mtosmt.org/issues/mto.09.15.5/mto.09.15.5.adams.php). *MTO* 15(5), 2009.
48. [French poetry (Wikipedia)](https://en.wikipedia.org/wiki/French_poetry); [French accentual groups (Springer)](https://www.doi.org/10.1007/978-1-349-12670-5_10); [Universalis: Vers](https://www.universalis.fr/encyclopedie/vers/).
49. Steve Reich. [Different Trains](https://stevereich.com/composition/different-trains/).
50. [Alap (Wikipedia)](https://en.wikipedia.org/wiki/Alap); [Darbar: alap, jor, jhalla](https://www.darbar.org/article/performance-format-for-hindustani-instrumental-music-alap-jor-and-jhalla).
51. ElevenLabs. [What is watermarking](https://elevenlabs.io/docs/help-center/legal/audio-detector/what-is-watermarking-and-why-is-eleven-labs-using-it); [Can I hear the watermark?](https://elevenlabs.io/docs/help-center/legal/audio-detector/can-i-hear-the-watermark); [Will watermarks cause flagging?](https://elevenlabs.io/docs/help-center/legal/audio-detector/will-watermarks-cause-my-content-to-be-flagged-downranked-or-demonetized-on-you-tube-or-other-platforms)
52. ElevenLabs. [Classifier vs Audio Detector](https://elevenlabs.io/docs/help-center/legal/audio-detector/what-is-the-difference-between-the-eleven-labs-ai-speech-classifier-and-the-new-audio-detector-tool); [Audio detector](https://elevenlabs.io/docs/eleven-creative/audio-tools/audio-detector).
53. ElevenLabs. [Third-party models watermarked?](https://elevenlabs.io/docs/help-center/legal/audio-detector/is-content-generated-by-third-party-models-available-through-eleven-labs-watermarked)
54. ElevenLabs Help (older). [What is SynthID and why is ElevenLabs using it](https://help.elevenlabs.io/hc/en-us/articles/48099338486801-What-is-SynthID-and-why-is-ElevenLabs-using-it).
55. Qwen. [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS); [model card](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base).
56. OpenBMB. [VoxCPM, "Risks and Limitations"](https://github.com/OpenBMB/VoxCPM).
57. OpenBMB. [VoxCPM2 model card](https://huggingface.co/openbmb/VoxCPM2).