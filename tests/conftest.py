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


@pytest.fixture(autouse=True)
def _suno_tasks_in_tmp(monkeypatch, tmp_path):
    """Keep tests' Suno task records out of the user's ``~/.local/share/arioso``.

    The sunoapi adapter tests mock the HTTP calls but recorded their fake tasks
    (``t1``, ``cover-task``) in the real task store, among real generations.
    """
    from arioso.platforms.sunoapi import task_store

    def tmp_dir(*, ensure_exists=True):
        folder = tmp_path / "suno_tasks"
        if ensure_exists:
            folder.mkdir(parents=True, exist_ok=True)
        return folder

    monkeypatch.setattr(task_store, "_default_data_dir", tmp_dir)
