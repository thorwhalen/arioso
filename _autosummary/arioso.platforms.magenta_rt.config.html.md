# arioso.platforms.magenta_rt.config

Magenta RealTime 2 platform configuration (local MLX runtime, Apple Silicon).

`magenta-rt[mlx]` (Apache-2.0 code) with the exported `.mlxfn` models; weights
CC-BY-4.0 (Google claims no rights in generated outputs). `mlx<0.32` is pinned because
MLX 0.32 cannot load the exported functions (magenta/magenta-realtime#103). Verified
against `magenta_rt/mlx/generate.py` of magenta-rt on 2026-11-10. Offline renders only:
the streaming state is not exposed yet.
