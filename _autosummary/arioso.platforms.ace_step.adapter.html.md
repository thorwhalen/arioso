# arioso.platforms.ace_step.adapter

ACE-Step adapter: fal.ai’s hosted endpoint, or ACE-Step 1.5 run locally.

`runtime="fal"` (the default) is the config-driven `arioso._fal.FalAdapter` (the
mapping lives in this platform’s `config.py`); `runtime="local"` runs ACE-Step 1.5 in
its own environment (`arioso.platforms.ace_step._local`). `$ARIOSO_ACE_STEP_RUNTIME`
changes the default, e.g. to `local` on a machine with the runtime installed. The module-level `fal_run` /
`fal_upload_audio` are looked up at call time, so tests can patch them here.

### Module Attributes

| [`LOCAL_ONLY`](#arioso.platforms.ace_step.adapter.LOCAL_ONLY)   | Keywords only the local runtime understands (fal's endpoint has no such controls).   |
|---------------------------------------------------------------|--------------------------------------------------------------------------------------|

### Classes

| [`Adapter`](#arioso.platforms.ace_step.adapter.Adapter)([config, local])   | ACE-Step adapter (fal.ai hosted, or local ACE-Step 1.5).   |
|-----------------------------------------------------------------------------|------------------------------------------------------------|

### *class* arioso.platforms.ace_step.adapter.Adapter(config=None, , local=None)

Bases: `FalAdapter`

ACE-Step adapter (fal.ai hosted, or local ACE-Step 1.5).

#### accepted_params()

fal’s keywords plus the local runtime’s own controls and `runtime` itself.

* **Return type:**
  [`frozenset`](https://docs.python.org/3/builtins/stdtypes.html#frozenset)

#### generate(prompt='', , runtime=None, \*\*params)

Generate with fal or locally; see the module docstring for how `runtime` resolves.

#### *property* local *: LocalAceStep*

The local runtime (built on first use; its worker starts on the first call).

### arioso.platforms.ace_step.adapter.LOCAL_ONLY *= ('bpm', 'key', 'model', 'lm_model', 'audio_input_strength', 'reference_audio', 'timesignature')*

Keywords only the local runtime understands (fal’s endpoint has no such controls).
