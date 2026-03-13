# Udio Platform Reference

Last updated: 2026-03-13

## Overview

[Udio](https://udio.com) is an AI music generation platform known for high-quality vocal generation and
broad genre support. It offers text-to-music generation, custom lyrics, and audio
conditioning. There is no official public API; the arioso adapter relies on the
unofficial [`udio-wrapper`](https://github.com/flowese/UdioWrapper) Python library, which uses cookie-based authentication
obtained from a browser session.

| Item | Link |
|------|------|
| Platform | <https://udio.com> |
| udio-wrapper (PyPI) | `pip install udio-wrapper` |

---

## Prompt Engineering

Udio uses **free-text prompts**, not tag-based inputs. The platform analyzes the full
prompt string to determine style, genre, mood, and production characteristics.

### Recommended prompt structure

Write prompts in roughly this order (not all components are required):

1. **Genre / subgenre:** "90s alternative rock", "trap hip-hop", "baroque chamber music"
2. **Mood / emotion:** "melancholic and introspective", "euphoric", "tense and cinematic"
3. **Instruments / sounds:** "distorted guitars, lo-fi drums, ambient synths"
4. **Vocal style:** "breathy female vocals", "aggressive male rap", "spoken word"
5. **Production quality:** "bedroom pop production", "polished studio sound", "lo-fi tape hiss"

Comma-separated style descriptors work well. Most effective prompts are 1-3 sentences.

### What works well

| Category | Effective vocabulary |
|----------|---------------------|
| Genres | Any standard genre name; era-specific subgenres are especially effective ("1960s psychedelic rock", "80s synthwave", "2020s hyperpop") |
| Moods | The full range of emotional vocabulary |
| Vocals | breathy, nasal, gritty, soaring, husky, sweet, powerful, delicate, raspy |
| Production | lo-fi, hi-fi, compressed, spacious, warm, cold, vintage, modern, crisp, reverb-drenched, dry and intimate |

### Negative prompting (Exclude)

Udio supports excluding unwanted concepts from generation ([Prompt Like a Master](https://help.udio.com/en/articles/10716541-prompt-like-a-master)). Use exclusions to remove
genres, instruments, or production qualities you do not want.

Example exclusion: "autotune, EDM, heavy bass"

(In the udio-wrapper, exclusion support depends on the wrapper version and API surface.)

### Lyrics

- **Auto mode:** Udio generates lyrics from the prompt when no custom lyrics are provided.
- **Manual mode:** Supply your own lyrics via the `lyrics` / `custom_lyrics` parameter.
- **Instrumental:** Include the word "instrumental" in the prompt.

Note: Udio does **not** use structured metatag steering (like `[Verse]`, `[Chorus]`)
as a primary feature. Lyrics are provided as plain text.

### Tips

- Be specific about genre and era -- "1960s psychedelic rock" outperforms just "rock" ([Prompt Like a Master](https://help.udio.com/en/articles/10716541-prompt-like-a-master)).
- Vocal descriptions are very effective -- "raspy baritone", "ethereal soprano" ([MusicSmith guide](https://musicsmith.ai/blog/ai-music-generation-prompts-best-practices)).
- Production terminology is well-understood -- "overdriven", "side-chain compression".
- Do not use artist names (content policy). Instead, describe the stylistic attributes ([name-free gap analysis](https://www.arxiv.org/pdf/2509.00654)).
- Describe musical structure explicitly -- "driving 4-on-the-floor beat", "sparse arrangement with fingerpicked guitar".

### Extension workflow

Udio supports prompt-to-extension: generate a starting clip, then extend it with a new
prompt. When extending, the prompt should describe the **next section** of the song,
not the whole piece.

---

## arioso Adapter Details

### Type

The arioso adapter (`arioso.platforms.udio.adapter.Adapter`) wraps the unofficial
`udio-wrapper` library (`UdioApiWrapper`).

### Authentication

Set the `UDIO_AUTH_COOKIE` environment variable with a valid auth cookie extracted
from your browser after logging into <https://udio.com>. The adapter will raise
`ValueError` if this variable is missing.

### Dependencies

- `udio-wrapper` (required): `pip install udio-wrapper`

### Parameters

| arioso param | Native param | Type | Default | Notes |
|--------------|-------------|------|---------|-------|
| `prompt` | `prompt` | str | (required) | Free-text music description |
| `lyrics` | `custom_lyrics` | str | `""` | Custom lyrics text |
| `seed` | `seed` | int | `-1` | Random seed; -1 for random |
| `audio_input` | `audio_conditioning_path` | str | `""` | Path to conditioning audio file |

### Output

- **Format:** MP3
- **Sample rate:** 48 kHz
- **Returns:** URL string (hosted on Udio's servers)
- Wrapped in `Song` / `AudioResult` dataclasses from `arioso.base`.
- The adapter may return a single `Song` or a list of `Song` objects if the API
  returns multiple results.

### Client lifecycle

The `UdioApiWrapper` client is lazily initialized on the first call to `generate()`.
Subsequent calls reuse the same client instance.

---

## Further Reading

- [Udio platform](https://udio.com) -- web interface for interactive generation.
- [Udio Help Center](https://help.udio.com/) -- official documentation and FAQs.
- [Prompt Like a Master](https://help.udio.com/en/articles/10716541-prompt-like-a-master) -- Udio's official prompt engineering guide.
- [UdioWrapper (GitHub)](https://github.com/flowese/UdioWrapper) -- unofficial Python wrapper source code.
- [udio-wrapper on PyPI](https://pypi.org/project/udio-wrapper/) -- unofficial Python wrapper documentation and source.
- [Scraped prompts analysis](https://arxiv.org/abs/2509.11824) -- analysis of real-world Suno/Udio prompts.
- [aims_prompts](https://github.com/mister-magpie/aims_prompts) -- curated prompt collection for AI music services.
- [OpenMusicPrompt](https://openmusicprompt.com/) -- community prompt sharing platform.
- [MusicSmith guide](https://musicsmith.ai/blog/ai-music-generation-prompts-best-practices) -- best practices for AI music generation prompts.
- [Name-free gap paper](https://www.arxiv.org/pdf/2509.00654) -- study on describing music styles without artist names.
- [awesome-music-prompts](https://github.com/yzfly/awesome-music-prompts) -- curated list of music generation prompt resources.
