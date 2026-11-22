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


_PAID_API_KEYS = (
    "SUNO_API_KEY",
    "ELEVENLABS_API_KEY",
    "FAL_KEY",
    "GOOGLE_API_KEY",
    "GOOGLE_CLOUD_API_KEY",
    "BEATOVEN_API_KEY",
    "JEN_API_KEY",
    "LOUDLY_API_KEY",
)


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "network: the test may reach the real network (and spend real money)"
    )


@pytest.fixture(autouse=True)
def _no_network_no_paid_keys(request, monkeypatch):
    """Block outgoing network calls and unset paid-API keys, unless ``@pytest.mark.network``.

    A test once reached sunoapi.org and spent a real generation because the dev
    machine had ``SUNO_API_KEY`` set. Tests that need a key set it themselves with
    ``monkeypatch.setenv``; tests that really want the network opt in with the marker.
    """
    if request.node.get_closest_marker("network"):
        return
    for name in _PAID_API_KEYS:
        monkeypatch.delenv(name, raising=False)

    def _blocked(*args, **kwargs):
        raise RuntimeError(
            "network access is blocked in tests; mark the test with @pytest.mark.network to allow it"
        )

    import socket

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
