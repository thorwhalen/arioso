# Stable Audio 2.5 (fal.ai) reference

Endpoints (verified 2026-10-03): `fal-ai/stable-audio-25/text-to-audio` and `fal-ai/stable-audio-25/audio-to-audio`. Auth: `FAL_KEY`. Calls block (fal queue `subscribe`); the result is an audio File (`audio.url`) plus `seed`.

## Parameters

| arioso | native | notes |
|---|---|---|
| `prompt` | `prompt` | required |
| `duration` | `seconds_total` | max 190; audio-to-audio defaults to the input's length |
| `num_steps` | `num_inference_steps` | default 8 |
| `guidance` | `guidance_scale` | default 1 |
| `seed` | `seed` | |
| `audio_input` | `audio_url` | uploaded to fal storage by arioso; switches to the audio-to-audio endpoint |
| `audio_input_strength` | `strength` | 0-1, default 0.8; lower keeps more of the input |

## Use

`arioso.enhance(audio, prompt, platform="stable_audio_25", strength=s)`.

Measured on a one-minute orchestral recording (chroma DTW cost against the input, 0 = identical pitch content): strength 0.2 gave 0.046, 0.35 gave 0.063, 0.5 gave 0.092. So 0.2-0.35 is "the same piece, subtly changed", and 0.5+ starts to re-imagine it. On a General MIDI render, 0.5-0.7 is the range where the synthetic timbre gives way to a realistic one while the notes survive.

Prompt: a full descriptive sentence works (instrumentation, era, recording space, tempo, mood). No negative prompt on this endpoint.
