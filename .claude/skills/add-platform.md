# Skill: Add a New Platform to Arioso

## When to Use
When the user asks to add support for a new AI music generation platform.

## Steps

### 1. Fetch and verify the live API documentation

This is the MOST IMPORTANT step. Do NOT rely on cached/local docs alone.

- **Search for official docs**: Use WebSearch to find the platform's current API
  documentation page.
- **Fetch the docs**: Use WebFetch to read the actual endpoint specifications.
  Look for an `llms.txt` or sitemap to discover all doc pages.
- **Look for an OpenAPI spec**: Many APIs publish one. Search for
  `<platform> openapi.json` or `<platform> swagger`. If found, fetch it and
  save it to `misc/docs/<name>-openapi.json` for reference.
- **Extract the ground truth**: From the live docs, record:
  - Endpoint URL(s) and HTTP method(s)
  - All parameter names, types, required vs optional
  - Valid enum values (model versions, formats, etc.)
  - Authentication method and header names
  - Response format (sync bytes, async callback, taskId polling, etc.)
  - Any required parameters that might not be obvious (callback URLs, etc.)
- **Save a snapshot**: Write a concise summary of the API spec to
  `misc/docs/<name>-api-spec.md` so future sessions have a reference point
  and can diff against it.

Do NOT proceed to implementation until this step is complete. The most common
failure mode is coding against stale or assumed API specs.

### 2. Cross-check with local reference docs

Check `misc/docs/` for any existing documentation about this platform.
If `misc/docs/AI music generation tools - a unified API reference for 21 platforms.md`
covers this platform, compare it against the live docs fetched in step 1.
Note any discrepancies — the live docs are authoritative.

### 3. Determine access type
   - `rest_api`: Platform has a REST API (self-serve or unofficial)
   - `python_lib`: Platform is a Python library for local inference
   - `unofficial_wrapper`: Platform requires a third-party wrapper

### 4. Identify supported affordances
Check which of the 40 affordances in `arioso/base.py:AFFORDANCES` the platform
supports. Map each to the platform's **actual** native parameter name (from step 1).

### 5. Create the platform directory
   ```
   arioso/platforms/<name>/
       __init__.py
       config.py
       adapter.py  (if needed)
   ```

### 6. Write `config.py` with `PLATFORM_CONFIG` dict

Include `choices` for any enum parameters (model versions, formats, etc.)
and `default_env_var` for configurable defaults.

```python
PLATFORM_CONFIG = {
    "name": "<name>",
    "display_name": "<Human Name>",
    "website": "https://...",
    "tier": "simple|structured|low_level",
    "access_type": "rest_api|python_lib|unofficial_wrapper",
    "auth": {
        "type": "api_key|bearer_token|none",
        "env_var": "<ENV_VAR_NAME>",
    },
    "param_map": {
        "prompt": {"native_name": "<native>", "required": True},
        "model": {
            "native_name": "<native>",
            "native_default": "<default>",
            "choices": ["..."],  # valid enum values from the live docs
            "default_env_var": "<PLATFORM>_DEFAULT_MODEL",
        },
        # ... one entry per supported affordance
    },
    "supported_affordances": ["prompt", ...],
    "on_unsupported_param": "warn",
    "output": {
        "default_format": "mp3|wav",
        "sample_rate": 44100,
        "returns": "bytes|url|array",
    },
    "api": {  # for REST platforms only
        "base_url": "https://...",
        "generate_endpoint": {"method": "post", "path": "/..."},
    },
}
```

### 7. Write `adapter.py` if needed
   - For `python_lib`: Must have an `Adapter` class with `generate(prompt, **kwargs) -> Song`
   - For `rest_api` without OpenAPI spec: Extend `BaseRestAdapter`
   - For `rest_api` with OpenAPI spec: Can use `ho.route_to_func` (see elevenlabs adapter)
   - **Error handling**: The adapter MUST detect API-level errors (e.g., HTTP 200
     with error in response body) and raise immediately. Never silently return a
     Song with error data buried in metadata.
   - **Defaults**: Use env vars for configurable defaults (model, callback URLs, etc.)
     following the pattern `<PLATFORM>_DEFAULT_<PARAM>`.

### 8. Write `__init__.py`
```python
"""<Platform> platform for arioso."""
from arioso.platforms.<name>.config import PLATFORM_CONFIG
platform_config = PLATFORM_CONFIG
```

### 9. Add tests in `tests/platforms/test_<name>.py`

Include tests for:
- Config structure and values
- Successful generation (mocked)
- API error detection and raising
- Default parameter population
- Required parameter validation

### 10. Add optional deps in `pyproject.toml`

### 11. Verify
Run `pytest` and test that `arioso.list_platforms()` includes the new platform.
