"""The suite blocks the network and paid-API keys by default (#76)."""

import os
import socket

import pytest


def test_network_is_blocked_by_default():
    with pytest.raises(RuntimeError, match="network access is blocked"):
        socket.create_connection(("example.com", 80))


def test_paid_keys_are_unset_by_default():
    assert "SUNO_API_KEY" not in os.environ
    assert "ELEVENLABS_API_KEY" not in os.environ
