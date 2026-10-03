# ACE-Step (fal.ai) reference

Endpoints (verified 2026-10-03): `fal-ai/ace-step` (tags + lyrics to music) and `fal-ai/ace-step/audio-to-audio` (remix or re-lyric an input). Auth: `FAL_KEY`. The result is an audio File (`audio.url`) plus `seed`, `tags`, `lyrics`.

## Parameters

| arioso | native | notes |
|---|---|---|
| `prompt` / `genre` | `tags` | comma-separated style tags; required |
| `lyrics` | `lyrics` | `[inst]` (also sent for empty lyrics or `instrumental=True`) = instrumental |
| `duration` | `duration` | text-to-music only, default 60 s |
| `num_steps` | `number_of_steps` | default 27 |
| `guidance` | `guidance_scale` | default 15 |
| `seed` | `seed` | |
| `audio_input` | `audio_url` | switches to audio-to-audio |
| (adapter kw) `original_tags` | `original_tags` | required by the endpoint; defaults to the new tags |
| (adapter kw) `original_lyrics`, `edit_mode` | same | `edit_mode` is `remix` (default) or `lyrics` |

Native extras passed through: `scheduler` (euler/heun), `guidance_type` (cfg/apg/cfg_star), `granularity_scale`, `guidance_interval`.

## Prompting

Tags, not sentences: `"symphonic, orchestral, film score, heroic fanfare, brass, timpani, march"`. Describe the input honestly in `original_tags` (e.g. `"general midi, synthesized, orchestral"`) so the remix knows what to move away from.
