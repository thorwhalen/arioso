# arioso.platforms.foundation_1.config

Foundation-1 platform configuration (local, stable-audio-tools in its own environment).

Foundation-1 (`RoyalCities/Foundation-1` on the Hugging Face Hub, ungated) is a fine-tune
of Stable Audio Open 1.0 for structured, tempo- and bar-aware instrument loops and
one-shots: one `model_config.json` (a stable-audio-tools `diffusion_cond` model: oobleck
VAE, T5-base prompt encoder, `seconds_start`/`seconds_total`, DiT; 44.1 kHz stereo, a
20 s window) shared by three checkpoints. Weights: Stability AI Community License (free
for research and non-commercial use, commercial use below US$1M annual revenue). Verified
against the model card, `Master_Tag_Reference.md` and `model_config.json` at the
revision below on 2026-11-10.

stable-audio-tools pins its own torch and Python (`<3.11`), so it runs in an environment
arioso builds once with `uv` (`EnvSpec`, under
`~/.local/share/arioso/envs/foundation-1`; `$ARIOSO_FOUNDATION_1_ENV` names an existing
environment instead); weights go to the Hugging Face cache. torch 2.7 has no Intel macOS
wheels, so on a Mac it needs Apple Silicon.

### Module Attributes

| [`SUPPORTED_BARS`](#arioso.platforms.foundation_1.config.SUPPORTED_BARS)   | bar counts and tempos the loops were trained on.                                                                                                                     |
|-------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`RESOLVED_ON`](#arioso.platforms.foundation_1.config.RESOLVED_ON)      | uv ignores anything published later, so the packages left unpinned below resolve to the same versions on every machine.                                              |
| [`REQUIREMENTS`](#arioso.platforms.foundation_1.config.REQUIREMENTS)     | stable-audio-tools and the packages whose versions decide its behaviour, pinned (the set resolved on RESOLVED_ON); the rest follow from these and `--exclude-newer`. |
| [`T5`](#arioso.platforms.foundation_1.config.T5)               | the worker fetches these files at this revision and points the conditioner at them, so nothing is looked up online once they are cached.                             |

### Functions

| [`env_spec`](#arioso.platforms.foundation_1.config.env_spec)([system])   | The environment for `system` (`platform.system()` by default).   |
|-----------------------------------------------------------------------|------------------------------------------------------------------|

### arioso.platforms.foundation_1.config.REQUIREMENTS *= ('stable-audio-tools==0.0.20', 'torch==2.7.1', 'torchaudio==2.7.1', 'transformers==4.57.1', 'tokenizers==0.22.1', 'huggingface-hub==0.36.0', 'safetensors==0.6.2', 'numpy==1.26.4', 'scipy==1.15.3', 'sentencepiece==0.1.99', 'torchsde==0.2.6', 'soundfile==0.13.1', 'pytorch-lightning==2.5.5', '--exclude-newer=2026-11-10T00:00:00Z')*

stable-audio-tools and the packages whose versions decide its behaviour, pinned (the
set resolved on RESOLVED_ON); the rest follow from these and `--exclude-newer`.

### arioso.platforms.foundation_1.config.RESOLVED_ON *= '2026-11-10'*

uv ignores anything published later, so
the packages left unpinned below resolve to the same versions on every machine.

* **Type:**
  The date the requirements were resolved on

### arioso.platforms.foundation_1.config.SUPPORTED_BARS *= (4, 8)*

bar counts and tempos the loops were trained on.

* **Type:**
  The model card’s prompt grammar

### arioso.platforms.foundation_1.config.T5 *= {'files': ('config.json', 'generation_config.json', 'model.safetensors', 'spiece.model', 'tokenizer.json'), 'repo_id': 'google-t5/t5-base', 'revision': 'a9723ea7f1b39c1eae772870f3b547bf6ef7e6c1'}*

the worker
fetches these files at this revision and points the conditioner at them, so nothing
is looked up online once they are cached.

* **Type:**
  The T5-base text encoder the model’s prompt conditioner loads, pinned

### arioso.platforms.foundation_1.config.env_spec(system=None)

The environment for `system` (`platform.system()` by default).

On Linux uv picks the torch wheel matching the machine’s accelerator (CUDA or CPU)
instead of PyPI’s default CUDA build; macOS wheels carry MPS, there is no index to pick.

* **Return type:**
  `EnvSpec`
