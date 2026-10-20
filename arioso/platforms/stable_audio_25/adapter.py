"""Stable Audio 2.5 adapter: a thin shim over the config-driven :class:`arioso._fal.FalAdapter`.

The mapping from unified affordances to fal arguments lives in this platform's
``config.py`` (``PLATFORM_CONFIG["fal"]``); nothing here is platform-specific. The
module-level ``fal_run`` / ``fal_upload_audio`` are looked up at call time, so tests
can patch them here.
"""

from __future__ import annotations

from arioso._fal import FalAdapter, fal_run, fal_upload_audio
from arioso.platforms.stable_audio_25.config import PLATFORM_CONFIG


class Adapter(FalAdapter):
    """fal.ai Stable Audio 2.5 adapter."""

    def __init__(self, config: dict = None):
        super().__init__(
            config if config and "fal" in config else PLATFORM_CONFIG,
            run=lambda endpoint, arguments: fal_run(endpoint, arguments),
            upload=lambda audio: fal_upload_audio(audio),
        )
