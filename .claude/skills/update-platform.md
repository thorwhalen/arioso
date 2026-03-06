# Skill: Update an Existing Platform Adapter

## When to Use
- When a platform adapter is returning errors that suggest the API has changed
- When the user asks to update/refresh a platform
- When adding new features to an existing platform adapter
- Periodically as a maintenance check

## Steps

### 1. Fetch the current live API documentation

This is mandatory before making any changes.

- **Find docs URL**: Check the platform's `config.py` for `website` and `api.base_url`.
  Search for `<platform name> API documentation <current year>`.
- **Fetch docs**: Use WebFetch on the docs URL. Look for `llms.txt`, sitemap,
  or API reference pages. Read the actual endpoint specifications.
- **Look for OpenAPI spec**: Search for `<base_url>/openapi.json`,
  `<base_url>/swagger.json`, or `<platform> openapi spec`.
- **Save updated spec**: Write/update `misc/docs/<name>-api-spec.md` with a
  concise summary of the current API.

### 2. Diff against current implementation

Compare the live docs against:
- `arioso/platforms/<name>/config.py` — parameter names, defaults, enum values
- `arioso/platforms/<name>/adapter.py` — endpoint URLs, payload structure,
  response parsing, required parameters

Look specifically for:
- **Renamed parameters** (e.g., `model_version` -> `model`)
- **Removed/deprecated parameters** (e.g., `wait_audio` no longer exists)
- **New required parameters** (e.g., `callBackUrl` became mandatory)
- **Changed enum values** (e.g., model versions added/removed)
- **Changed response format** (e.g., sync -> async/callback)
- **New endpoints** or endpoint path changes

### 3. Update the adapter

Apply changes to match the live API:
- Update `config.py`: parameter names, choices, defaults, endpoint paths
- Update `adapter.py`: payload construction, response parsing, error detection
- Ensure all error paths raise immediately (never silently return error Songs)
- Update env var defaults if enum values changed

### 4. Update tests

- Fix any tests that assert old parameter names/values
- Add tests for any new behavior (new required params, new error cases)
- Run `pytest` — all tests must pass

### 5. Update local docs

If `misc/docs/<name>-api-spec.md` exists, update it. If not, create it with
a summary of the current API for future reference.

## Common Pitfalls

- **APIs that return HTTP 200 for errors**: Many music APIs (sunoapi, etc.)
  return 200 with `{"code": 400, "msg": "..."}` in the body. Always check
  for this pattern.
- **Parameter name changes**: APIs often rename parameters between versions
  without deprecation notices.
- **Sync-to-async migration**: APIs may switch from synchronous (wait for
  audio) to callback-based (return taskId, POST results to webhook).
- **Stale local docs**: The `misc/docs/` reference document may be outdated.
  Always verify against live docs.
