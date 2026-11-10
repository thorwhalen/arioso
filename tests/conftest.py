"""Shared test setup: keep the machine's own MusicGen runtime and backend choice out of tests.

On a Mac with the MLX runtime installed (or ``$ARIOSO_MUSICGEN_BACKEND`` set), the default
MusicGen backend selection would start a real worker and load a real model. Tests that want
MLX opt back in by pointing the runtime variable at a fake runtime.
"""

import pytest


@pytest.fixture(autouse=True)
def _no_local_musicgen_runtime(monkeypatch, tmp_path_factory):
    monkeypatch.delenv("ARIOSO_MUSICGEN_BACKEND", raising=False)
    missing = tmp_path_factory.getbasetemp() / "no-mlx-examples-runtime"
    monkeypatch.setenv("ARIOSO_MLX_EXAMPLES_DIR", str(missing))
