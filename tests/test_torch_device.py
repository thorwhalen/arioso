"""The torch device and dtype every local platform shares (a fake torch; no GPU needed)."""

import sys
import types

import pytest

from arioso._util import torch_device, torch_dtype


def _fake_torch(monkeypatch, *, cuda, mps):
    """A fake torch; ``mps=None`` is a build without the MPS backend."""
    mps_backend = (
        {} if mps is None else {"mps": types.SimpleNamespace(is_available=lambda: mps)}
    )
    torch = types.SimpleNamespace(
        cuda=types.SimpleNamespace(is_available=lambda: cuda),
        backends=types.SimpleNamespace(**mps_backend),
        float16="f16",
        float32="f32",
    )
    monkeypatch.setitem(sys.modules, "torch", torch)


@pytest.mark.parametrize(
    "env, cuda, mps, expected",
    [
        ("forced", True, True, "forced"),  # the variable beats every probe
        (None, True, True, "cuda"),
        (None, False, True, "mps"),
        (None, False, False, "cpu"),
        (None, False, None, "cpu"),  # a torch built without MPS
    ],
)
def test_device_order(monkeypatch, env, cuda, mps, expected):
    monkeypatch.delenv("ARIOSO_TORCH_DEVICE", raising=False)
    if env:
        monkeypatch.setenv("ARIOSO_TORCH_DEVICE", env)
    _fake_torch(monkeypatch, cuda=cuda, mps=mps)
    assert torch_device() == expected


@pytest.mark.parametrize(
    "device, dtype",
    [("cuda", "f16"), ("cuda:1", "f16"), ("mps", "f32"), ("cpu", "f32")],
)
def test_half_precision_only_on_cuda(monkeypatch, device, dtype):
    _fake_torch(monkeypatch, cuda=False, mps=False)
    assert torch_dtype(device) == dtype


def test_musicgen_keeps_its_old_name_for_the_shared_choice():
    from arioso.platforms.musicgen.backends import _device

    assert _device is torch_device
