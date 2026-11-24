# arioso.platforms.ace_step.config

ACE-Step platform configuration: fal.ai hosted, or ACE-Step 1.5 run locally.

Live docs (verified 2026-10-03): [https://fal.ai/models/fal-ai/ace-step/api](https://fal.ai/models/fal-ai/ace-step/api) and
[https://fal.ai/models/fal-ai/ace-step/audio-to-audio/api](https://fal.ai/models/fal-ai/ace-step/audio-to-audio/api). Local runtime: the
`ACE-Step/ACE-Step-1.5` checkout (MIT code and weights), verified against its
`docs/en/INFERENCE.md` and `acestep.inference.GenerationParams` on 2026-11-10.

### Module Attributes

| [`DFLT_STYLE`](#arioso.platforms.ace_step.config.DFLT_STYLE)   | The style ACE-Step is given when the caller names none (no Styles, no prompt).   |
|---------------------------------------------------------------|----------------------------------------------------------------------------------|

### arioso.platforms.ace_step.config.DFLT_STYLE *= 'melodic, natural instruments, steady groove, warm, balanced mix, well produced'*

The style ACE-Step is given when the caller names none (no Styles, no prompt). It asks
for a well-made recording and names no genre, which is left to the lyrics, the source
audio and ACE-Step’s own planner. A schema shows it as the prompt’s `default`, so a
form can say what an empty field does instead of demanding text.
