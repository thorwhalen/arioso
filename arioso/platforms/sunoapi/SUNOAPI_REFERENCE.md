# Suno API Reference (sunoapi.org)

> Complete REST API reference for [sunoapi.org](https://sunoapi.org/).
> Source documentation: [docs.sunoapi.org](https://docs.sunoapi.org/)

---

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [Base URL](#base-url)
- [AI Model Versions](#ai-model-versions)
- [Common Patterns](#common-patterns)
  - [Task Lifecycle](#task-lifecycle)
  - [Callback (Webhook) System](#callback-webhook-system)
  - [Error Codes](#error-codes)
  - [Data Retention](#data-retention)
- [Endpoints](#endpoints)
  - [Generate Music](#generate-music)
  - [Extend Music](#extend-music)
  - [Upload and Extend Audio](#upload-and-extend-audio)
  - [Upload and Cover Audio](#upload-and-cover-audio)
  - [Generate Mashup](#generate-mashup)
  - [Add Vocals](#add-vocals)
  - [Add Instrumental](#add-instrumental)
  - [Generate Lyrics](#generate-lyrics)
  - [Get Timestamped Lyrics](#get-timestamped-lyrics)
  - [Separate Vocals from Music](#separate-vocals-from-music)
  - [Convert to WAV Format](#convert-to-wav-format)
  - [Boost Music Style](#boost-music-style)
  - [Create Music Video](#create-music-video)
  - [Get Music Generation Details](#get-music-generation-details)
  - [Get Remaining Credits](#get-remaining-credits)

---

## Overview

Suno API provides AI music generation, audio processing, lyrics creation, and video production capabilities via a REST API.

Key features:
- 99.9% uptime guarantee
- 20-second streaming output
- Watermark-free commercial output
- High-concurrency scalable architecture
- Webhook callbacks for async task completion

---

## Authentication

All requests require a Bearer token in the `Authorization` header:

```
Authorization: Bearer YOUR_API_KEY
```

API keys are obtained from the [API Key Management Page](https://sunoapi.org/api-key).

---

## Base URL

```
https://api.sunoapi.org
```

---

## AI Model Versions

| Model | Key Features | Max Duration |
|-------|-------------|--------------|
| `V4` | Enhanced vocals | Up to 4 minutes |
| `V4_5` | Smart prompts | Up to 8 minutes |
| `V4_5PLUS` | Richer tones | Up to 8 minutes |
| `V4_5ALL` | Better song structure | Up to 8 minutes |
| `V5` | Latest cutting-edge model | Up to 8 minutes |

---

## Common Patterns

### Task Lifecycle

Most endpoints are asynchronous. The flow is:

1. **Submit request** -- receive a `taskId` in the response.
2. **Wait for completion** -- either:
   - **Poll** via `GET /api/v1/generate/record-info?taskId=YOUR_TASK_ID` (recommended interval: every 30 seconds).
   - **Receive a webhook callback** at your `callBackUrl`.

### Task Status Values

| Status | Description |
|--------|-------------|
| `PENDING` | Queued for processing |
| `TEXT_SUCCESS` | Lyrics/text generation complete |
| `FIRST_SUCCESS` | First track generated |
| `GENERATING` | Currently being processed |
| `SUCCESS` | Task completed successfully |
| `FAILED` | Task failed |
| `CREATE_TASK_FAILED` | Task creation failed |
| `GENERATE_AUDIO_FAILED` | Audio generation failed |
| `CALLBACK_EXCEPTION` | Callback delivery failed |
| `SENSITIVE_WORD_ERROR` | Content moderation triggered |

### Callback (Webhook) System

When a `callBackUrl` is provided, the API sends POST requests to that URL at up to three stages:

| Callback Type | Description |
|---------------|-------------|
| `text` | Text/lyrics generation complete |
| `first` | First track complete |
| `complete` | All tracks complete |

Standard callback payload structure:

```json
{
  "code": 200,
  "msg": "All generated successfully.",
  "data": {
    "callbackType": "complete",
    "task_id": "2fac****9f72",
    "data": [
      {
        "id": "8551****662c",
        "audio_url": "https://example.cn/****.mp3",
        "source_audio_url": "https://example.cn/****.mp3",
        "stream_audio_url": "https://example.cn/****",
        "source_stream_audio_url": "https://example.cn/****",
        "image_url": "https://example.cn/****.jpeg",
        "source_image_url": "https://example.cn/****.jpeg",
        "prompt": "[Verse] Night city lights shining bright",
        "model_name": "chirp-v3-5",
        "title": "Iron Man",
        "tags": "electrifying, rock",
        "createTime": "2025-01-01 00:00:00",
        "duration": 198.44
      }
    ]
  }
}
```

### Error Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Invalid parameters |
| 401 | Unauthorized access |
| 404 | Invalid request method/path |
| 405 | Rate limit exceeded |
| 409 | Record already exists (WAV/MP4) |
| 413 | Theme or prompt too long |
| 429 | Insufficient credits |
| 430 | Call frequency too high -- retry later |
| 455 | System maintenance |
| 500 | Server error |

Error response format:

```json
{
  "code": 429,
  "msg": "Insufficient credits"
}
```

### Data Retention

- Generated audio files are retained for **15 days** before automatic deletion.
- Generated video files are retained for **15 days**.
- Uploaded files via Base64 upload auto-delete after **3 days**.
- Vocal separation URLs are valid for **14 days**.

### Character Limits by Model

| Parameter | V4 | V4_5 / V4_5PLUS / V5 | V4_5ALL |
|-----------|----|-----------------------|---------|
| `prompt` | 3,000 chars | 5,000 chars | 5,000 chars |
| `style` | 200 chars | 1,000 chars | 1,000 chars |
| `title` | 80 chars | 100 chars | 80 chars |

---

## Endpoints

---

### Generate Music

Create AI-generated music tracks.

**`POST /api/v1/generate`**

#### Request Parameters

| Parameter | Type | Required | Description | Constraints |
|-----------|------|----------|-------------|-------------|
| `prompt` | string | Yes | Text description or lyrics for the music | Max 3,000 chars (V4); 5,000 chars (V4_5+) |
| `model` | string | Yes | AI model version | `V4`, `V4_5`, `V4_5PLUS`, `V4_5ALL`, `V5` |
| `customMode` | boolean | No | Enable custom style/title mode | Default: `false` |
| `instrumental` | boolean | No | Generate instrumental only (no vocals) | Default: `false` |
| `style` | string | Required if `customMode: true` | Music style/genre | Max 200 chars (V4); 1,000 chars (V4_5+) |
| `title` | string | Required if `customMode: true` | Track title | Max 80 chars (V4/V4_5ALL); 100 chars (V4_5/V4_5PLUS/V5) |
| `callBackUrl` | string | No | Webhook URL for completion notification | Valid URL |

#### Example Request (Simple Mode)

```json
{
  "prompt": "A peaceful acoustic guitar melody with soft vocals, folk style",
  "customMode": false,
  "instrumental": false,
  "model": "V4_5ALL",
  "callBackUrl": "https://your-server.com/callback"
}
```

#### Example Request (Custom Mode)

```json
{
  "prompt": "An upbeat electronic dance track with synth leads",
  "customMode": true,
  "style": "Electronic Dance",
  "title": "Digital Dreams",
  "instrumental": false,
  "model": "V4_5"
}
```

#### Success Response

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "taskId": "suno_task_abc123"
  }
}
```

#### Callback Payload

See [Callback System](#callback-webhook-system) for the standard payload format.

---

### Extend Music

Extend or modify an existing music track from a previous generation.

**`POST /api/v1/generate/extend`**

#### Request Parameters

| Parameter | Type | Required | Description | Constraints |
|-----------|------|----------|-------------|-------------|
| `audioId` | string | Yes | Source track ID to extend | UUID from a previous generation |
| `defaultParamFlag` | boolean | Yes | If `true`, use custom params below; if `false`, use source track params | |
| `model` | string | Yes | Must match source audio's model version | `V4`, `V4_5`, `V4_5PLUS`, `V4_5ALL`, `V5` |
| `callBackUrl` | string | Yes | Webhook URL | Valid URL |
| `prompt` | string | When `defaultParamFlag: true` | Lyrics/description for extension | Max 3,000 (V4); 5,000 (V4_5+) |
| `style` | string | When `defaultParamFlag: true` | Music style | Max 200 (V4); 1,000 (V4_5+) |
| `title` | string | When `defaultParamFlag: true` | Track title | Max 80 (V4/V4_5ALL); 100 (V4_5/V4_5PLUS/V5) |
| `continueAt` | number | No | Time point in seconds to begin extension | Must be >0 and < total duration |
| `personaId` | string | No | Persona ID for style | |
| `personaModel` | string | No | Persona type | `style_persona` (default), `voice_persona` |
| `negativeTags` | string | No | Styles to exclude | |
| `vocalGender` | string | No | Vocal gender preference | `m`, `f` |
| `styleWeight` | number | No | Style guidance intensity | 0.00--1.00 |
| `weirdnessConstraint` | number | No | Creative deviation limit | 0.00--1.00 |
| `audioWeight` | number | No | Input audio influence weight | 0.00--1.00 |

#### Example Request

```json
{
  "defaultParamFlag": true,
  "audioId": "e231****-****-****-****-****8cadc7dc",
  "callBackUrl": "https://api.example.com/callback",
  "model": "V4_5ALL",
  "prompt": "Extend the music with more relaxing notes",
  "style": "Classical",
  "title": "Peaceful Piano Extended",
  "continueAt": 60
}
```

#### Success Response

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "taskId": "5c79****be8e"
  }
}
```

#### Callback Payload

See [Callback System](#callback-webhook-system).

---

### Upload and Extend Audio

Upload an external audio file and extend it with AI generation.

**`POST /api/v1/generate/upload-extend`**

#### Request Parameters

| Parameter | Type | Required | Description | Constraints |
|-----------|------|----------|-------------|-------------|
| `uploadUrl` | string | Yes | URL of the audio file to extend | Max 8 min audio; V4_5ALL max 1 min |
| `defaultParamFlag` | boolean | Yes | If `true`, use custom params below | |
| `model` | string | Yes | AI model version | `V4`, `V4_5`, `V4_5PLUS`, `V4_5ALL`, `V5` |
| `callBackUrl` | string | Yes | Webhook URL | Valid URL |
| `instrumental` | boolean | No | Instrumental only | |
| `prompt` | string | When `defaultParamFlag: true` and `instrumental: false` | Lyrics/description | Max 3,000 (V4); 5,000 (V4_5+) |
| `style` | string | When `defaultParamFlag: true` | Music style | Max 200 (V4); 1,000 (V4_5+) |
| `title` | string | When `defaultParamFlag: true` | Track title | Max 80 (V4/V4_5ALL); 100 (V4_5/V4_5PLUS/V5) |
| `continueAt` | number | No | Time in seconds to begin extension | Must be >0 and < uploaded audio duration |
| `personaId` | string | No | Persona ID | |
| `personaModel` | string | No | Persona type | `style_persona`, `voice_persona` |
| `negativeTags` | string | No | Styles to exclude | |
| `vocalGender` | string | No | Vocal gender | `m`, `f` |
| `styleWeight` | number | No | Style guidance intensity | 0.00--1.00 |
| `weirdnessConstraint` | number | No | Creative deviation limit | 0.00--1.00 |
| `audioWeight` | number | No | Input audio influence | 0.00--1.00 |

#### Example Request

```json
{
  "uploadUrl": "https://storage.example.com/my-audio.mp3",
  "defaultParamFlag": true,
  "instrumental": false,
  "prompt": "Continue with an upbeat chorus",
  "style": "Pop Rock",
  "title": "Extended Track",
  "model": "V4_5ALL",
  "callBackUrl": "https://api.example.com/callback",
  "continueAt": 30
}
```

#### Success Response

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "taskId": "5c79****be8e"
  }
}
```

#### Callback Payload

See [Callback System](#callback-webhook-system).

---

### Upload and Cover Audio

Transform an uploaded audio file into a new style while retaining the melody.

**`POST /api/v1/generate/upload-cover`**

#### Request Parameters

| Parameter | Type | Required | Description | Constraints |
|-----------|------|----------|-------------|-------------|
| `uploadUrl` | string | Yes | URL of audio file to cover | Max 8 min audio; V4_5ALL max 1 min |
| `customMode` | boolean | Yes | Enable custom style/title | |
| `instrumental` | boolean | Yes | Instrumental only | |
| `model` | string | Yes | AI model version | `V4`, `V4_5`, `V4_5PLUS`, `V4_5ALL`, `V5` |
| `callBackUrl` | string | Yes | Webhook URL | Valid URL |
| `style` | string | Required if `customMode: true` | Music style | Max 200 (V4); 1,000 (V4_5+) |
| `title` | string | Required if `customMode: true` | Track title | Max 80 (V4/V4_5ALL); 100 (V4_5/V4_5PLUS/V5) |
| `prompt` | string | Required if `customMode: true` and `instrumental: false`; or if `customMode: false` | Lyrics/description | Max 3,000 (V4); 5,000 (V4_5+) when custom; Max 500 when not custom |
| `personaId` | string | No | Persona ID (custom mode only) | |
| `personaModel` | string | No | Persona type | `style_persona` (default), `voice_persona` |
| `negativeTags` | string | No | Styles to exclude | |
| `vocalGender` | string | No | Vocal gender | `m`, `f` |
| `styleWeight` | number | No | Style guidance intensity | 0.00--1.00 |
| `weirdnessConstraint` | number | No | Creative deviation limit | 0.00--1.00 |
| `audioWeight` | number | No | Input audio influence | 0.00--1.00 |

#### Example Request (Custom Mode)

```json
{
  "uploadUrl": "https://storage.example.com/upload",
  "customMode": true,
  "instrumental": false,
  "prompt": "A calm and relaxing piano track with soft melodies",
  "style": "Classical",
  "title": "Peaceful Piano Meditation",
  "model": "V4_5ALL",
  "callBackUrl": "https://api.example.com/callback"
}
```

#### Success Response

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "taskId": "5c79****be8e"
  }
}
```

#### Callback Payload

See [Callback System](#callback-webhook-system).

---

### Generate Mashup

Blend two audio files to create a new track.

**`POST /api/v1/generate/mashup`**

#### Request Parameters

| Parameter | Type | Required | Description | Constraints |
|-----------|------|----------|-------------|-------------|
| `uploadUrlList` | array | Yes | Exactly 2 audio file URLs | Both must be valid URLs |
| `customMode` | boolean | Yes | Enable custom style/title | |
| `model` | string | Yes | AI model version | `V4`, `V4_5`, `V4_5PLUS`, `V4_5ALL`, `V5` |
| `callBackUrl` | string | Yes | Webhook URL | Valid URL |
| `instrumental` | boolean | No | Instrumental only (removes lyrics) | |
| `prompt` | string | When `customMode: true` and `instrumental: false`; or `customMode: false` | Lyrics/description | |
| `style` | string | Required if `customMode: true` | Music style | |
| `title` | string | Required if `customMode: true` | Track title | |
| `vocalGender` | string | No | Vocal gender | `m`, `f` |
| `styleWeight` | number | No | Style guidance intensity | 0.00--1.00 |
| `weirdnessConstraint` | number | No | Creative deviation limit | 0.00--1.00 |
| `audioWeight` | number | No | Input audio influence | 0.00--1.00 |

#### Example Request

```json
{
  "uploadUrlList": [
    "https://storage.example.com/audio1.mp3",
    "https://storage.example.com/audio2.mp3"
  ],
  "customMode": true,
  "instrumental": false,
  "prompt": "[Verse] Blending two worlds together, creating something new",
  "style": "Electronic Pop",
  "title": "Fusion Mashup",
  "model": "V5",
  "vocalGender": "f",
  "styleWeight": 0.7,
  "callBackUrl": "https://api.example.com/callback"
}
```

#### Success Response

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "taskId": "5c79****be8e"
  }
}
```

#### Callback Payload

See [Callback System](#callback-webhook-system).

---

### Add Vocals

Layer AI-generated vocals onto an existing instrumental track.

**`POST /api/v1/generate/add-vocals`**

#### Request Parameters

| Parameter | Type | Required | Description | Constraints |
|-----------|------|----------|-------------|-------------|
| `uploadUrl` | string | Yes | URL of the instrumental audio file | MP3, WAV, or supported formats |
| `prompt` | string | Yes | Desired vocal style and content | Detailed description recommended |
| `title` | string | Yes | Track title | Max 100 chars |
| `style` | string | Yes | Genre and vocal approach | e.g., "Jazz", "Classical", "Pop" |
| `negativeTags` | string | Yes | Styles/traits to exclude | Comma-separated, e.g., "Heavy Metal, Aggressive Vocals" |
| `callBackUrl` | string | Yes | Webhook URL | Valid URL |
| `vocalGender` | string | No | Vocal gender | `m`, `f` |
| `styleWeight` | number | No | Style adherence intensity | 0.00--1.00 |
| `weirdnessConstraint` | number | No | Creativity/novelty control | 0.00--1.00 |
| `audioWeight` | number | No | Audio consistency emphasis | 0.00--1.00 |
| `model` | string | No | Model version | `V4_5PLUS` (default), `V5` |

#### Example Request

```json
{
  "uploadUrl": "https://example.com/instrumental.mp3",
  "prompt": "A calm and relaxing piano track with soothing vocals",
  "title": "Relaxing Piano with Vocals",
  "style": "Jazz",
  "negativeTags": "Heavy Metal, Aggressive Vocals",
  "callBackUrl": "https://api.example.com/callback",
  "vocalGender": "m",
  "styleWeight": 0.61,
  "weirdnessConstraint": 0.72,
  "audioWeight": 0.65,
  "model": "V4_5PLUS"
}
```

#### Success Response

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "taskId": "5c79****be8e"
  }
}
```

#### Callback Payload

See [Callback System](#callback-webhook-system).

---

### Add Instrumental

Generate musical accompaniment for vocal stems or melodies.

**`POST /api/v1/generate/add-instrumental`**

#### Request Parameters

| Parameter | Type | Required | Description | Constraints |
|-----------|------|----------|-------------|-------------|
| `uploadUrl` | string | Yes | URL of the audio file | MP3, WAV, etc. |
| `title` | string | Yes | Track title | Max 100 chars |
| `tags` | string | Yes | Desired style/mood/instruments | e.g., "Relaxing Piano, Ambient" |
| `negativeTags` | string | Yes | Styles/instruments to exclude | e.g., "Heavy Metal, Aggressive Drums" |
| `callBackUrl` | string | Yes | Webhook URL | Valid URL |
| `vocalGender` | string | No | Vocal gender | `m`, `f` |
| `styleWeight` | number | No | Style guidance intensity | 0.00--1.00 |
| `audioWeight` | number | No | Audio consistency | 0.00--1.00 |
| `weirdnessConstraint` | number | No | Creative deviation limit | 0.00--1.00 |
| `model` | string | No | Model version | `V4_5PLUS` (default), `V5` |

> **Note:** This endpoint uses `tags` instead of `style` for genre specification.

#### Example Request

```json
{
  "uploadUrl": "https://example.com/music.mp3",
  "title": "Relaxing Piano",
  "tags": "Relaxing Piano, Ambient, Peaceful",
  "negativeTags": "Heavy Metal, Aggressive Drums",
  "callBackUrl": "https://api.example.com/callback",
  "vocalGender": "m",
  "styleWeight": 0.61,
  "audioWeight": 0.65,
  "weirdnessConstraint": 0.72,
  "model": "V4_5PLUS"
}
```

#### Success Response

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "taskId": "5c79****be8e"
  }
}
```

#### Callback Payload

See [Callback System](#callback-webhook-system).

---

### Generate Lyrics

Create lyrics using AI without generating audio.

**`POST /api/v1/lyrics`**

#### Request Parameters

| Parameter | Type | Required | Description | Constraints |
|-----------|------|----------|-------------|-------------|
| `prompt` | string | Yes | Theme, mood, style, structure description | Max 200 chars |
| `callBackUrl` | string | Yes | Webhook URL | Valid URL |

#### Example Request

```json
{
  "prompt": "A song about peaceful night in the city",
  "callBackUrl": "https://api.example.com/callback"
}
```

#### Success Response

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "taskId": "5c79****be8e"
  }
}
```

#### Callback Payload

```json
{
  "code": 200,
  "msg": "All generated successfully.",
  "data": {
    "callbackType": "complete",
    "taskId": "11dc****8b0f",
    "data": [
      {
        "text": "[Verse]\nLyrics content here...\n[Chorus]\nMore lyrics...",
        "title": "City Nights",
        "status": "complete",
        "errorMessage": ""
      }
    ]
  }
}
```

**Notes:**
- Multiple lyric variations may be returned.
- Generated lyrics can be used as input for the music generation endpoint.
- Results retained for 15 days.

---

### Get Timestamped Lyrics

Retrieve time-synchronized lyrics for a generated track.

**`POST /api/v1/generate/get-timestamped-lyrics`**

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `taskId` | string | Yes | The music generation task ID |
| `audioId` | string | Yes | The specific audio track ID |

#### Example Request

```json
{
  "taskId": "5c79****be8e",
  "audioId": "e231****-****-****-****-****8cadc7dc"
}
```

#### Success Response

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "alignedWords": [
      {
        "word": "[Verse]\nWaggin'",
        "success": true,
        "startS": 1.36,
        "endS": 1.79,
        "palign": 0
      }
    ],
    "waveformData": [0, 1, 0.5, 0.75],
    "hootCer": 0.3803191489361702,
    "isStreamed": false
  }
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `alignedWords` | array | Timestamped lyrics entries |
| `alignedWords[].word` | string | The word or phrase (may include structure markers) |
| `alignedWords[].success` | boolean | Whether alignment was successful |
| `alignedWords[].startS` | number | Start time in seconds |
| `alignedWords[].endS` | number | End time in seconds |
| `alignedWords[].palign` | number | Alignment precision score |
| `waveformData` | array | Audio visualization data points |
| `hootCer` | number | Alignment accuracy score |
| `isStreamed` | boolean | Whether the audio was streamed |

---

### Separate Vocals from Music

Split a track into vocal and instrumental stems.

**`POST /api/v1/vocal-removal/generate`**

#### Request Parameters

| Parameter | Type | Required | Description | Valid Values |
|-----------|------|----------|-------------|--------------|
| `taskId` | string | Yes | Music generation task ID | |
| `audioId` | string | Yes | Specific audio track ID | UUID format |
| `type` | string | Yes | Separation mode | `separate_vocal`, `split_stem` |
| `callBackUrl` | string | Yes | Webhook URL | Valid URL |

#### Separation Modes

| Mode | Description | Credits |
|------|-------------|---------|
| `separate_vocal` | Splits into vocals + instrumental | 10 credits |
| `split_stem` | Splits into up to 12 individual stems | 50 credits |

**`split_stem` returns:** vocals, backing vocals, drums, bass, guitar, keyboard, strings, brass, woodwinds, percussion, synth, FX.

#### Example Request

```json
{
  "taskId": "5c79****be8e",
  "audioId": "e231****-****-****-****-****8cadc7dc",
  "type": "separate_vocal",
  "callBackUrl": "https://api.example.com/callback"
}
```

#### Success Response

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "taskId": "5c79****be8e"
  }
}
```

#### Callback Payload (`separate_vocal`)

```json
{
  "code": 200,
  "msg": "vocal Removal generated successfully.",
  "data": {
    "task_id": "3e63b4cc88d52611159371f6af5571e7",
    "vocal_removal_info": {
      "vocal_url": "https://file.aiquickdraw.com/s/..._Vocals.mp3",
      "instrumental_url": "https://file.aiquickdraw.com/s/..._Instrumental.mp3",
      "origin_url": ""
    }
  }
}
```

**Note:** Separation result URLs are valid for 14 days.

---

### Convert to WAV Format

Convert a generated music track to high-quality WAV format.

**`POST /api/v1/wav/generate`**

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `taskId` | string | Yes | Music generation task ID |
| `audioId` | string | Yes | Specific track ID to convert |
| `callBackUrl` | string | Yes | Webhook URL for download link |

#### Example Request

```json
{
  "taskId": "5c79****be8e",
  "audioId": "e231****-****-****-****-****8cadc7dc",
  "callBackUrl": "https://api.example.com/callback"
}
```

#### Success Response

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "taskId": "5c79****be8e"
  }
}
```

#### Callback Payload

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "audioWavUrl": "https://example.com/s/04e6****e727.wav",
    "task_id": "988e****c8d3"
  }
}
```

**Note:** Error code 409 is returned if a WAV conversion record already exists for the same audio.

---

### Boost Music Style

Enhance and refine a music style description for better generation results.

**`POST /api/v1/style/generate`**

This is a **synchronous** endpoint -- the response contains the result directly (no task/callback pattern).

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `content` | string | Yes | Music style description to enhance |

#### Example Request

```json
{
  "content": "Pop, Mysterious"
}
```

#### Success Response

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "taskId": "string",
    "param": "string",
    "result": "string",
    "creditsConsumed": 0.00,
    "creditsRemaining": 0.00,
    "successFlag": "1",
    "errorCode": 0,
    "errorMessage": "string",
    "createTime": "string"
  }
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `result` | string | The enhanced/boosted style description |
| `creditsConsumed` | number | Credits used for this request |
| `creditsRemaining` | number | Remaining account credits |
| `successFlag` | string | `"1"` for success |
| `errorCode` | number | `0` if no error |
| `errorMessage` | string | Error details if any |

---

### Create Music Video

Generate an MP4 video with visualizations for a generated track.

**`POST /api/v1/mp4/generate`**

#### Request Parameters

| Parameter | Type | Required | Description | Constraints |
|-----------|------|----------|-------------|-------------|
| `taskId` | string | Yes | Music generation task ID | |
| `audioId` | string | Yes | Specific audio track ID | |
| `callBackUrl` | string | Yes | Webhook URL | Valid URL |
| `author` | string | No | Author name displayed in video | Max 50 chars |
| `domainName` | string | No | Domain name displayed in video | Max 50 chars |

#### Example Request

```json
{
  "taskId": "taskId_774b9aa0422f",
  "audioId": "e231****-****-****-****-****8cadc7dc",
  "callBackUrl": "https://api.example.com/callback",
  "author": "Suno Artist",
  "domainName": "music.example.com"
}
```

#### Success Response

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "taskId": "taskId_774b9aa0422f"
  }
}
```

#### Callback Payload

```json
{
  "code": 200,
  "msg": "MP4 generated successfully.",
  "data": {
    "task_id": "taskId_774b9aa0422f",
    "video_url": "https://example.com/videos/video_847715e66259.mp4"
  }
}
```

**Notes:**
- Error code 409 is returned if an MP4 record already exists for the same audio.
- Generated videos are retained for 15 days.

---

### Get Music Generation Details

Retrieve task status, parameters, and results for any generation task.

**`GET /api/v1/generate/record-info`**

#### Request Parameters (Query String)

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `taskId` | string | Yes | The task ID to query |

#### Example Request

```
GET https://api.sunoapi.org/api/v1/generate/record-info?taskId=5c79****be8e
```

#### Success Response

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "taskId": "5c79****be8e",
    "parentMusicId": "",
    "param": "{\"prompt\":\"A calm piano track\",\"style\":\"Classical\",\"title\":\"Peaceful Piano\",\"customMode\":true,\"instrumental\":true,\"model\":\"V4_5ALL\"}",
    "response": {
      "taskId": "5c79****be8e",
      "sunoData": [
        {
          "id": "8551****662c",
          "audioUrl": "https://example.cn/****.mp3",
          "streamAudioUrl": "https://example.cn/****",
          "imageUrl": "https://example.cn/****.jpeg",
          "prompt": "[Verse] lyrics content",
          "modelName": "chirp-v3-5",
          "title": "Track Title",
          "tags": "electrifying, rock",
          "createTime": "2025-01-01 00:00:00",
          "duration": 198.44
        }
      ]
    },
    "status": "SUCCESS",
    "type": "chirp-v3-5",
    "operationType": "generate",
    "errorCode": null,
    "errorMessage": null
  }
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `taskId` | string | Task identifier |
| `parentMusicId` | string | Parent track ID (for extensions/covers) |
| `param` | string | JSON-encoded original request parameters |
| `response.sunoData` | array | Array of generated track objects |
| `response.sunoData[].id` | string | Audio track ID |
| `response.sunoData[].audioUrl` | string | Download URL for the audio |
| `response.sunoData[].streamAudioUrl` | string | Streaming URL |
| `response.sunoData[].imageUrl` | string | Cover art URL |
| `response.sunoData[].prompt` | string | Lyrics/prompt used |
| `response.sunoData[].modelName` | string | Model used |
| `response.sunoData[].title` | string | Track title |
| `response.sunoData[].tags` | string | Genre/style tags |
| `response.sunoData[].createTime` | string | Creation timestamp |
| `response.sunoData[].duration` | number | Duration in seconds |
| `status` | string | Task status (see [Task Status Values](#task-status-values)) |
| `type` | string | Model type identifier |
| `operationType` | string | Operation type (e.g., `generate`) |
| `errorCode` | string/null | Error code if failed |
| `errorMessage` | string/null | Error message if failed |

---

### Get Remaining Credits

Check the available credit balance for your account.

**`GET /api/v1/generate/credit`**

#### Request Parameters

None.

#### Example Request

```
GET https://api.sunoapi.org/api/v1/generate/credit
```

#### Success Response

```json
{
  "code": 200,
  "msg": "success",
  "data": 100
}
```

The `data` field contains the integer credit balance.

---

## Additional Endpoints (from llms.txt)

The following endpoints are referenced in the documentation index but were not all individually documented above. They follow the same authentication and response patterns:

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/generate/replace-section` | Replace a specific time segment within a track |
| `POST /api/v1/generate/persona` | Create a personalized music identity from generated tracks |
| `POST /api/v1/generate/midi` | Convert separated audio tracks into MIDI format |
| `POST /api/v1/generate/music-cover` | Generate personalized cover art images |
| Base64 file upload | Upload temporary files via Base64 encoding (auto-delete after 3 days) |
| File stream upload | Direct stream-based file uploading |
| URL file upload | Upload files from remote URLs |

### Status/Detail Retrieval Endpoints

These follow the same pattern as [Get Music Generation Details](#get-music-generation-details):

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/generate/record-info` | GET | Music generation details |
| `/api/v1/lyrics/record-info` | GET | Lyrics generation details |
| `/api/v1/wav/record-info` | GET | WAV conversion details |
| `/api/v1/vocal-removal/record-info` | GET | Vocal separation details |
| `/api/v1/mp4/record-info` | GET | Music video details |
| `/api/v1/midi/record-info` | GET | MIDI generation details |

All accept `taskId` as a query parameter.

---

## Quick Reference: All Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/generate` | [Generate Music](#generate-music) |
| POST | `/api/v1/generate/extend` | [Extend Music](#extend-music) |
| POST | `/api/v1/generate/upload-extend` | [Upload and Extend Audio](#upload-and-extend-audio) |
| POST | `/api/v1/generate/upload-cover` | [Upload and Cover Audio](#upload-and-cover-audio) |
| POST | `/api/v1/generate/mashup` | [Generate Mashup](#generate-mashup) |
| POST | `/api/v1/generate/add-vocals` | [Add Vocals](#add-vocals) |
| POST | `/api/v1/generate/add-instrumental` | [Add Instrumental](#add-instrumental) |
| POST | `/api/v1/lyrics` | [Generate Lyrics](#generate-lyrics) |
| POST | `/api/v1/generate/get-timestamped-lyrics` | [Get Timestamped Lyrics](#get-timestamped-lyrics) |
| POST | `/api/v1/vocal-removal/generate` | [Separate Vocals from Music](#separate-vocals-from-music) |
| POST | `/api/v1/wav/generate` | [Convert to WAV Format](#convert-to-wav-format) |
| POST | `/api/v1/style/generate` | [Boost Music Style](#boost-music-style) |
| POST | `/api/v1/mp4/generate` | [Create Music Video](#create-music-video) |
| GET | `/api/v1/generate/record-info` | [Get Music Generation Details](#get-music-generation-details) |
| GET | `/api/v1/generate/credit` | [Get Remaining Credits](#get-remaining-credits) |
