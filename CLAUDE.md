# Arioso - Song Generation Toolkit

## Project Purpose

Arioso is an extensible Python package that aggregates tools for programmatic song
generation. It wraps multiple music generation backends behind a unified interface,
allowing users to swap providers without changing their workflow.

## Architecture

```
arioso/
├── __init__.py          # Package facade - re-exports key classes
├── base.py              # Song dataclass + MusicGenerator protocol
└── (future modules)     # suno.py, elevenlabs.py, musicgen.py, ...
```

### Design Principles

- **Provider-agnostic base**: `base.py` defines the `Song` dataclass and
  `MusicGenerator` protocol that all backends implement. Consumer code depends on
  this protocol, not concrete classes.
- **Lazy imports**: Heavy dependencies are imported inside functions/methods, not at
  module level, so installing `arioso` doesn't require every backend's deps.
- **Extensible via new modules**: Adding a new backend = adding a new module that
  implements `MusicGenerator`.

## Key Conventions

- Python 3.10+, type hints everywhere
- Docstrings: Google style
- Tests in `tests/`, examples in `examples/`, scratch work in `scrap/`
- No emojis in code or docs unless user asks

## History

The `_failed_homegrown_sunoapi` branch contains a failed attempt at direct
cookie-based Suno API access. It was abandoned due to hCaptcha enforcement.
See that branch's README for a detailed post-mortem.

## Next Steps

Implement Suno access via a paid third-party proxy (e.g., sunoapi.org) that
handles auth and CAPTCHA on their end.
