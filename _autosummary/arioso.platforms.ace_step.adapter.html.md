# arioso.platforms.ace_step.adapter

ACE-Step adapter: a thin shim over the config-driven `arioso._fal.FalAdapter`.

The mapping from unified affordances to fal arguments lives in this platform’s
`config.py` (`PLATFORM_CONFIG["fal"]`); nothing here is platform-specific. The
module-level `fal_run` / `fal_upload_audio` are looked up at call time, so tests
can patch them here.

### Classes

| [`Adapter`](#arioso.platforms.ace_step.adapter.Adapter)([config])   | fal.ai ACE-Step adapter.   |
|----------------------------------------------------------------------|----------------------------|

### *class* arioso.platforms.ace_step.adapter.Adapter(config=None)

Bases: `FalAdapter`

fal.ai ACE-Step adapter.
