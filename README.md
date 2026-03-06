# arioso

Make tunes.

---

## This branch: `_failed_homegrown_sunoapi`

This branch documents an attempt to build a direct, cookie-based Python client
for Suno's private API. The approach ultimately failed due to Suno's aggressive
hCaptcha enforcement. Below is a full account of what was tried, what worked,
what didn't, and where we left off.

### Goal

Build `arioso.suno.SunoCookieClient` — a Python class that authenticates with
Suno's internal API using browser cookies, and can generate music (including
"cover" generation from uploaded audio files) without any third-party proxy
service.

### What succeeded

1. **Cookie extraction from Chrome** (`arioso._util.get_suno_cookie_from_browser`):
   Using `browser-cookie3`, we can programmatically extract Suno cookies from
   Chrome's cookie store. Safari is sandboxed on macOS and requires Full Disk
   Access; Chrome works out of the box (after a one-time Keychain approval).

2. **Clerk authentication flow**: Suno uses Clerk.dev for auth. We successfully:
   - Extracted the Clerk session ID from the cookie via
     `GET https://clerk.suno.com/v1/client?_clerk_js_version=4.73.2`
   - Refreshed JWT tokens via
     `POST https://clerk.suno.com/v1/client/sessions/{sid}/tokens`
   - Both `clerk.suno.com` and `auth.suno.com` work as base URLs.

3. **Read-only API endpoints work**: With a valid JWT, these endpoints respond
   correctly on `https://studio-api.prod.suno.com`:
   - `GET /api/feed/?page=0` — returns the user's song history
   - `GET /api/feed/?ids={id1},{id2}` — returns specific songs by ID
   - `GET /api/uploads/audio/{id}/` — returns upload processing status

4. **Audio upload to Suno's S3**: The full upload flow works:
   - `POST /api/uploads/audio/` with `{"extension": "wav"}` returns a presigned
     S3 URL and fields.
   - Upload the file to `https://suno-uploads.s3.amazonaws.com/` via multipart POST
     using the returned fields.
   - `POST /api/uploads/audio/{id}/upload-finish/` with
     `{"upload_type": "file_upload", "upload_filename": "name.wav"}` confirms the
     upload. (**Note**: the payload must be flat — not nested under a `spec` key,
     despite what the Pydantic validation error path suggests.)
   - Polling `GET /api/uploads/audio/{id}/` returns `{"status": "complete"}` with
     a `title`, `image_url`, and `has_vocal` flag.

5. **API endpoint discovery**: The old `studio-api.suno.ai` hostname has been
   suspended ("This service has been suspended by its owner"). The live endpoint
   is `studio-api.prod.suno.com`.

### What failed

**Generation and cover endpoints are blocked by mandatory hCaptcha.**

- `POST /api/generate/v2/` returns `{"detail": "Token validation failed."}`.
- This is **not** a payload format error — the payload schema is accepted.
  Suno simply requires a valid solved hCaptcha token in the `"token"` field of
  every generation request.
- The same applies to `/api/generate/v2-web/`.

### What we tried to fix it

1. **2Captcha integration**: We implemented `_solve_captcha()` which submits the
   hCaptcha challenge to 2Captcha's API (sitekey `d65453de-3f1a-4aac-9366-a0f06e52b2ce`,
   page URL `https://suno.com/create`), polls for the human-solved token, and
   passes it in the `"token"` field. This was implemented but **not tested** —
   we decided to abandon the approach before spending money on 2Captcha credits.

2. **Research into why token solving may not work**: According to multiple sources
   (gcui-art/suno-api issues #198, #211), even valid 2Captcha-solved tokens may
   be rejected because hCaptcha validates behavioral signals (mouse paths, click
   timing) beyond just the token. The gcui-art project switched to a
   Playwright-based approach that launches a real browser, triggers the challenge
   visually, screenshots it, sends it to 2Captcha's coordinate-solving API, and
   clicks the results — producing tokens with realistic behavioral data. Songs
   generated with API-only tokens reportedly get watermarked with "This is a
   fake app" lyrics.

### Payload format reference (for future reference)

**Generation (description mode):**
```json
{
  "gpt_description_prompt": "a dreamy pop song about summer love",
  "prompt": "",
  "mv": "chirp-crow",
  "make_instrumental": false,
  "generation_type": "TEXT",
  "token": "<solved_hcaptcha_token>"
}
```

**Generation (custom mode with lyrics):**
```json
{
  "prompt": "[Verse]\nWalking down...\n[Chorus]\nHey world...",
  "tags": "electronic hip hop",
  "title": "Lost in the Shuffle",
  "mv": "chirp-crow",
  "make_instrumental": false,
  "generation_type": "TEXT",
  "token": "<solved_hcaptcha_token>"
}
```

**Cover (from uploaded audio):**
```json
{
  "task": "cover",
  "cover_clip_id": "<uuid_from_upload>",
  "mv": "chirp-crow",
  "generation_type": "TEXT",
  "make_instrumental": true,
  "tags": "Jazz, Piano, Drums",
  "title": "My Cover",
  "prompt": "",
  "token": "<solved_hcaptcha_token>",
  "metadata": {
    "create_mode": "custom",
    "control_sliders": {
      "style_weight": 0.8,
      "weirdness_constraint": 0.2
    },
    "can_control_sliders": ["style_weight", "weirdness_constraint"]
  }
}
```

**Model versions:**
- `chirp-crow` = v5 (current as of March 2026)
- `chirp-bluejay` = v4.5
- `chirp-v3-5` = v3.5

### Where we left off

The client can authenticate, read feeds, and upload audio. Generation is blocked
by hCaptcha. The 2Captcha integration is coded but untested, and likely
insufficient without full browser automation (Playwright).

### Decision

Rather than maintaining a fragile reverse-engineering setup that requires:
- Weekly cookie re-extraction
- A paid CAPTCHA-solving service ($2.99/1,000 solves)
- Possible Playwright browser automation
- Constant maintenance as Suno changes endpoints

...we're switching to a **paid third-party API proxy** (e.g., sunoapi.org) that
handles all of this on their end. If Suno ever offers an official API, we'll
switch to that.
