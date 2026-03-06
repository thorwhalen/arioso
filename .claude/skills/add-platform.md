# Skill: Add a New Platform to Arioso

## When to Use
When the user asks to add support for a new AI music generation platform.

## Steps

1. **Research the platform**: Check `misc/docs/AI music generation tools - a unified API reference for 21 platforms.md` for existing documentation. If the platform isn't there, research its API docs, SDK, or wrapper libraries.

2. **Determine access type**:
   - `rest_api`: Platform has a REST API (self-serve or unofficial)
   - `python_lib`: Platform is a Python library for local inference
   - `unofficial_wrapper`: Platform requires a third-party wrapper

3. **Identify supported affordances**: Check which of the 40 affordances in `arioso/base.py:AFFORDANCES` the platform supports. Map each to the platform's native parameter name.

4. **Create the platform directory**:
   ```
   arioso/platforms/<name>/
       __init__.py
       config.py
       adapter.py  (if needed)
   ```

5. **Write `config.py`** with `PLATFORM_CONFIG` dict. Use this template:
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

6. **Write `adapter.py`** if needed:
   - For `python_lib`: Must have an `Adapter` class with `generate(prompt, **kwargs) -> Song`
   - For `rest_api` without OpenAPI spec: Extend `BaseRestAdapter`
   - For `rest_api` with OpenAPI spec: Can use `ho.route_to_func` (see elevenlabs adapter)

7. **Write `__init__.py`**:
   ```python
   """<Platform> platform for arioso."""
   from arioso.platforms.<name>.config import PLATFORM_CONFIG
   platform_config = PLATFORM_CONFIG
   ```

8. **Add tests** in `tests/platforms/test_<name>.py`

9. **Add optional deps** in `pyproject.toml` under `[project.optional-dependencies]`

10. **Verify**: Run `pytest` and test that `arioso.list_platforms()` includes the new platform
