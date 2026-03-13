# Arioso - Unified AI Music Generation Facade

## Project Purpose

Arioso wraps 14 AI music generation platforms behind a unified Python interface.
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
            <NAME>_REFERENCE.md  # API + prompt engineering reference (for humans & AI agents)
```

### How It Works

1. Each platform lives in `arioso/platforms/<name>/` with a `config.py` exporting
   a `PLATFORM_CONFIG` dict that declares parameter mappings, auth, endpoints, etc.
2. The registry auto-discovers platforms by scanning for these packages.
3. When a platform is first used, its adapter is lazy-loaded.
4. The `translation.py` module handles renaming unified affordance names to native
   platform parameter names, with type coercion.

## CRITICAL: Always Verify Against Live API Docs

Before adding or modifying ANY platform adapter, you MUST fetch and read the
platform's current API documentation. Do NOT rely on local docs in `misc/docs/`
alone — APIs change their parameter names, add required fields, deprecate
endpoints, and switch between sync/async without notice. The live docs are the
single source of truth. See `.claude/skills/add-platform.md` step 1 and
`.claude/skills/update-platform.md` for the full process.

## Adding a New Platform

See `.claude/skills/add-platform.md` for step-by-step instructions.

## Updating an Existing Platform

See `.claude/skills/update-platform.md` for the process.
Use this when an adapter returns unexpected errors or when doing maintenance.

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

`misc/docs/` contains reference documents including a multi-platform overview and
per-platform API spec snapshots (`<name>-api-spec.md`). These are useful as a
starting point but MAY BE OUTDATED. Always verify against live docs before
coding (see "CRITICAL" section above). Each platform also has a
`<platform>/REFERENCE.md` with detailed API and prompt engineering documentation.

## Evolving This File

This CLAUDE.md, along with `.claude/skills/` and `.claude/rules/`, should be
incrementally updated as the project evolves. When you discover better patterns,
fix bugs, or add platforms, update these files to reflect the current state.
The `misc/docs/` folder can also be used to store notes, analysis, or documents
that agents or the user want to reference across sessions.
