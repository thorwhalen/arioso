"""Fake platforms for the compare tests; importing this module registers them (no model, no network).

- ``fake_clicks``: a local platform rendering a click track at the BPM written in the prompt
  ("... 120 BPM ...") over an A tone, so tempo checks have something true to find.
- ``fake_hosted``: the same audio declared as a hosted ``rest_api`` platform.
- ``fake_oneshot``: like ``fake_clicks``, but each take runs a short-lived ~200 MB process.
- ``fake_broken``: a local platform whose every call fails.
"""

import re

import numpy as np

from arioso.base import AudioResult, Song
from arioso.registry import register_platform

SAMPLE_RATE = 22050
CALLS = []


def clicks(bpm: float, seconds: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    """A 440 Hz tone with a decaying noise burst on every beat, as (channels, frames) stereo.

    Noise bursts, not smooth pulses: a beat tracker follows onsets, which need broadband energy.
    """
    n = int(seconds * sr)
    t = np.arange(n) / sr
    y = 0.05 * np.sin(2 * np.pi * 440 * t)
    length = int(0.03 * sr)
    noise = np.random.default_rng(0).standard_normal(length)
    click = (
        0.6 * noise / np.abs(noise).max() * np.exp(-np.arange(length) / (0.005 * sr))
    )
    for start in np.arange(0, seconds, 60 / bpm):
        i = int(start * sr)
        y[i : i + len(click)] += click[: n - i]
    return np.stack([y, y]).astype(np.float32)


class _Clicks:
    def generate(self, prompt, *, duration=4.0, seed=None, **kwargs):
        CALLS.append({"prompt": prompt, "duration": duration, "seed": seed, **kwargs})
        m = re.search(r"(\d+)\s*BPM", prompt)
        audio = clicks(float(m.group(1)) if m else 100.0, duration)
        return Song(
            audio=AudioResult(audio_array=audio, sample_rate=SAMPLE_RATE),
            status="complete",
        )


class _OneShot(_Clicks):
    """Each take runs a short-lived process holding ~200 MB, as one-shot runtimes do."""

    def generate(self, prompt, **kwargs):
        import subprocess
        import sys

        code = "b = bytearray(200 * 2**20); b[::4096] = b'x' * len(b[::4096]); import time; time.sleep(0.8)"
        subprocess.run([sys.executable, "-c", code], check=True)
        return super().generate(prompt, **kwargs)


class _Broken:
    def generate(self, prompt, **kwargs):
        raise RuntimeError("model exploded")


def _config(name, access_type="python_lib", commercial_use="yes"):
    return {
        "name": name,
        "access_type": access_type,
        "weights_license": "MIT",
        "commercial_use": commercial_use,
        "supported_affordances": ["prompt", "duration", "seed"],
    }


#: The fake platforms by name: (config, adapter).
PLATFORMS = {
    "fake_clicks": (_config("fake_clicks"), _Clicks()),
    "fake_hosted": (_config("fake_hosted", "rest_api", "provider terms"), _Clicks()),
    "fake_oneshot": (_config("fake_oneshot"), _OneShot()),
    "fake_broken": (_config("fake_broken"), _Broken()),
}


def register():
    """Add the fake platforms to arioso's registry (idempotent)."""
    for name, (config, adapter) in PLATFORMS.items():
        register_platform(name, config, adapter)


def unregister():
    """Take them out again, so other tests see only the real platforms."""
    from arioso.registry import _registry

    for name in PLATFORMS:
        _registry.pop(name, None)


register()  # on import: a child process preloads this module to get them
