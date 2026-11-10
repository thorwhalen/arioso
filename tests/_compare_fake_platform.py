"""Fake platforms for the compare tests (no model, no network); ``register()`` adds them.

Nothing is registered on import: test collection may import this module, and platforms left
in the registry would leak into other tests. A child process gets them with
``preload=["tests._compare_fake_platform:register"]``.

- ``fake_clicks``: a local platform rendering a click track at the BPM written in the prompt
  ("... 120 BPM ...") over an A tone, so tempo checks have something true to find.
- ``fake_hosted``: the same audio declared as a hosted ``rest_api`` platform.
- ``fake_oneshot``: like ``fake_clicks``, but each take runs a short-lived ~200 MB process.
- ``fake_short``: returns 3.5 s whatever it is asked (real time factors divide by what came back).
- ``fake_loud``: peaks at 1.5, over full scale (clipping must be seen).
- ``fake_slow``: sleeps 30 s per call (for timeouts).
- ``fake_batched``: returns ``(1, channels, frames)``.
- ``fake_slow_second``: hangs (with a worker process) on any prompt but the 120 BPM one.
- ``fake_crash_with_worker``: starts a worker process, then the process dies (exit 139).
- ``fake_provider_terms`` / ``fake_fal``: local-looking configs with provider terms / a fal block.
- ``fake_no_access_type``: a plugin config that forgot ``access_type`` (hosted by default).
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


class _Short(_Clicks):
    def generate(self, prompt, **kwargs):
        import time

        time.sleep(0.3)  # long enough that dividing by 4 s instead of 3.5 s shows
        return super().generate(prompt, **dict(kwargs, duration=3.5))


class _Batched(_Clicks):
    def generate(self, prompt, **kwargs):
        song = super().generate(prompt, **kwargs)
        song.audio.audio_array = song.audio.audio_array[None]  # (1, channels, frames)
        return song


class _SlowSecond(_Clicks):
    """Fast for the 120 BPM prompt; for any other, starts a worker process and hangs."""

    def generate(self, prompt, **kwargs):
        import os
        import subprocess
        import sys
        import time

        if "120 BPM" not in prompt:
            from ps.util import NEW_PROCESS_GROUP

            # a session of its own, as ps.isolated starts runtime workers
            worker = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                **NEW_PROCESS_GROUP,
            )
            with open(os.environ["ARIOSO_TEST_PIDFILE"], "w") as f:
                f.write(str(worker.pid))
            time.sleep(60)
        return super().generate(prompt, **kwargs)


class _CrashWithWorker(_Clicks):
    """Starts a worker process, as a runtime does, then dies without any cleanup."""

    def generate(self, prompt, **kwargs):
        import os
        import subprocess
        import sys
        import time

        from ps.util import NEW_PROCESS_GROUP

        worker = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"], **NEW_PROCESS_GROUP
        )
        with open(os.environ["ARIOSO_TEST_PIDFILE"], "w") as f:
            f.write(str(worker.pid))
        time.sleep(1)  # the parent's watch sees it (it reads the tree every 0.25 s)
        os._exit(139)


class _Loud(_Clicks):
    def generate(self, prompt, **kwargs):
        song = super().generate(prompt, **kwargs)
        song.audio.audio_array = song.audio.audio_array * (
            1.5 / np.abs(song.audio.audio_array).max()
        )
        return song


class _Slow(_Clicks):
    def generate(self, prompt, **kwargs):
        import time

        time.sleep(30)
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
    "fake_short": (_config("fake_short"), _Short()),
    "fake_loud": (_config("fake_loud"), _Loud()),
    "fake_slow": (_config("fake_slow"), _Slow()),
    "fake_batched": (_config("fake_batched"), _Batched()),
    "fake_slow_second": (_config("fake_slow_second"), _SlowSecond()),
    "fake_crash_with_worker": (_config("fake_crash_with_worker"), _CrashWithWorker()),
    "fake_provider_terms": (
        _config("fake_provider_terms", "python_lib", "provider terms"),
        _Clicks(),
    ),
    "fake_fal": (dict(_config("fake_fal"), fal={"endpoint": "x"}), _Clicks()),
    "fake_no_access_type": (
        {k: v for k, v in _config("fake_no_access_type").items() if k != "access_type"},
        _Clicks(),
    ),
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


def exit_badly_at_shutdown():
    """Make the process exit with 139 at shutdown, as a native library crashing there does."""
    import atexit
    import os

    atexit.register(os._exit, 139)
