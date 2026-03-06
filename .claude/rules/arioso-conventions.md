# Arioso Coding Rules

1. Never import platform dependencies at module level. Use lazy imports inside methods.
2. All public functions must have type hints and Google-style docstrings.
3. Platform configs use Python dicts in `.py` files, never YAML/JSON/TOML.
4. The `AFFORDANCES` dict in `base.py` is the single source of truth for parameter names.
5. Adapters return `Song` objects, never raw API responses.
   Adapters MUST raise on API-level errors (e.g., HTTP 200 with error in body).
   Never silently return a Song with error data buried in metadata.
6. New platforms must have a `config.py` with `PLATFORM_CONFIG`. `adapter.py` is optional for REST APIs.
7. Tests for each platform go in `tests/platforms/test_<name>.py`.
8. No emojis in code or docs.
9. Use `BaseRestAdapter` for REST API platforms that need polling or shared auth logic.
10. Keep the core package dependency-free. Platform deps go in `[project.optional-dependencies]`.
