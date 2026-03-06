# Arioso - Unified AI Music Generation Facade

## Project Purpose

Arioso wraps 21+ AI music generation platforms behind a unified Python interface.
Users generate music via `arioso.generate(prompt, platform="...", **kwargs)`.

## Architecture

```
arioso/
    __init__.py                  # Facade: generate(), list_platforms(), get_platform_info()
    base.py                      # Song, AudioResult dataclasses; AFFORDANCES constant
    registry.py                  # Platform auto-discovery and lazy loading
    translation.py               # Parameter name translation via i2.Ingress
    _util.py                     # Auth helpers, HTTP session factory
    platforms/
        __init__.py              # Auto-discovery hook
        _base_adapter.py         # BaseRestAdapter with common REST patterns
        <name>/                  # One subfolder per platform
            __init__.py
            config.py            # PLATFORM_CONFIG dict (required)
            adapter.py           # Platform-specific code (optional for REST APIs)
```

### How It Works

1. Each platform lives in `arioso/platforms/<name>/` with a `config.py` exporting
   a `PLATFORM_CONFIG` dict that declares parameter mappings, auth, endpoints, etc.
2. The registry auto-discovers platforms by scanning for these packages.
3. When a platform is first used, its adapter is lazy-loaded.
4. The `translation.py` module handles renaming unified affordance names to native
   platform parameter names, with type coercion.

## Adding a New Platform

See the `.claude/skills/add-platform.md` skill for step-by-step instructions.

Quick summary:
1. Create `arioso/platforms/<name>/` directory with `__init__.py`
2. Write `config.py` exporting `PLATFORM_CONFIG` dict (copy from an existing platform)
3. For REST APIs with sufficient config: done (auto-generated adapter)
4. For Python libraries or complex APIs: write `adapter.py` with an `Adapter` class
5. The `Adapter` class must have a `generate(prompt, **kwargs) -> Song` method
6. Add tests in `tests/platforms/test_<name>.py`

## Key Libraries (dependencies used internally)

- **ho**: OpenAPI spec -> Python functions (`route_to_func`, `routes_to_funcs`)
- **ju**: JSON schema parsing, OpenAPI route objects (`Routes`, `Route`)
- **i2**: Signature manipulation (`Sig`), function wrapping (`Wrap`, `Ingress`)

Source locations for reference:
- `/Users/thorwhalen/Dropbox/py/proj/i/ho/ho/base.py`
- `/Users/thorwhalen/Dropbox/py/proj/i/ju/ju/oas.py`
- `/Users/thorwhalen/Dropbox/py/proj/i/i2/i2/wrapper.py`
- `/Users/thorwhalen/Dropbox/py/proj/i/i2/i2/signatures.py`

## Conventions

- Python 3.10+, type hints everywhere
- Google-style docstrings
- Zero required dependencies; platform deps are lazy-imported inside methods
- All platform parameters use unified affordance names (see `AFFORDANCES` in `base.py`)
- No emojis in code or docs
- Tests in `tests/`, examples in `examples/`, scratch in `scrap/`

## Reference Documentation

`misc/docs/` contains the comprehensive 21-platform reference document mapping
all platforms' parameters, SDKs, and capabilities. Agents should consult this
when adding new platforms or understanding parameter mappings.

## Evolving This File

This CLAUDE.md, along with `.claude/skills/` and `.claude/rules/`, should be
incrementally updated as the project evolves. When you discover better patterns,
fix bugs, or add platforms, update these files to reflect the current state.
The `misc/docs/` folder can also be used to store notes, analysis, or documents
that agents or the user want to reference across sessions.
