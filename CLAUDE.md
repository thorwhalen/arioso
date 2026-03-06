# Arioso - Song Generation Toolkit

## Project Purpose

Arioso is an extensible Python package that aggregates tools for programmatic song
generation. It wraps multiple music generation backends behind a unified interface,
allowing users to swap providers without changing their workflow.

## Architecture

```
arioso/
├── __init__.py          # Package facade - re-exports key classes
├── base.py              # Abstract base classes and shared types
├── suno.py              # Suno API client (unofficial, cookie-based + commercial proxy)
├── _util.py             # Internal utilities (config loading, etc.)
└── (future modules)     # elevenlabs.py, musicgen.py, udio.py, ...
```

### Design Principles

- **Provider-agnostic base**: `base.py` defines the `MusicGenerator` protocol that all
  backends implement. Consumer code should depend on this protocol, not concrete classes.
- **Lazy imports**: Heavy dependencies are imported inside functions/methods, not at
  module level, so installing `arioso` doesn't require every backend's deps.
- **Config via environment**: Credentials go in env vars or a `.env` file. The
  `arioso/_util.py` module handles loading. Never hardcode secrets.
- **Extensible via new modules**: Adding a new backend = adding a new module that
  implements `MusicGenerator`. No central registry needed.

## Key Conventions

- Python 3.10+, type hints everywhere
- Use `requests` for HTTP (not `httpx`, not `aiohttp` — keep sync-first, simple)
- Docstrings: Google style
- Tests in `tests/`, examples in `examples/`, scratch work in `scrap/`
- No emojis in code or docs unless user asks

## Suno Backend Details

The Suno module supports two modes:

1. **Cookie-based (direct)**: Uses extracted browser cookies to authenticate with
   Suno's Clerk.dev backend. Requires `SUNO_COOKIE` env var. Fragile but free
   (beyond the Suno subscription). Needs cookie refresh every ~7 days.

2. **Commercial proxy**: Uses third-party API proxies (sunoapi.org, MusicAPI.ai,
   CometAPI, etc.). Requires `SUNO_API_KEY` and `SUNO_API_BASE` env vars.
   More reliable but costs per generation.

## Environment Variables

| Variable | Used By | Description |
|----------|---------|-------------|
| `SUNO_COOKIE` | suno.py (cookie mode) | Browser cookie from suno.com |
| `SUNO_API_KEY` | suno.py (proxy mode) | API key for commercial proxy |
| `SUNO_API_BASE` | suno.py (proxy mode) | Base URL of commercial proxy |
| `TWOCAPTCHA_KEY` | suno.py (cookie mode) | 2Captcha key for CAPTCHA solving |

## Running Tests

```bash
pip install -e ".[dev]"
pytest
```
