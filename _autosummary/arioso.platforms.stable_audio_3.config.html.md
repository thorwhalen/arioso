# arioso.platforms.stable_audio_3.config

Stable Audio 3 platform configuration (local MLX runtime, Apple Silicon).

Stability ships the MLX build as `optimized/mlx` in `Stability-AI/stable-audio-3` (MIT
code), a script with its own small virtualenv; weights come on first use from Stability’s
ungated `stabilityai/stable-audio-3-optimized` (Stability AI Community License, plus the
Gemma terms for the T5Gemma text encoder). Verified against the checkout’s
`scripts/sa3_mlx.py` and the model card on 2026-11-10.
