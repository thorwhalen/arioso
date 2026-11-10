"""ACE-Step adapter: fal.ai's hosted endpoint, or ACE-Step 1.5 run locally.

``runtime="fal"`` (the default) is the config-driven :class:`arioso._fal.FalAdapter` (the
mapping lives in this platform's ``config.py``); ``runtime="local"`` runs ACE-Step 1.5 in
its own environment (:mod:`arioso.platforms.ace_step._local`). ``$ARIOSO_ACE_STEP_RUNTIME``
changes the default, e.g. to ``local`` on a machine with the runtime installed. The module-level ``fal_run`` /
``fal_upload_audio`` are looked up at call time, so tests can patch them here.
"""

from __future__ import annotations

import inspect
import os
import warnings

from arioso._fal import FalAdapter, fal_run, fal_upload_audio
from arioso.platforms.ace_step._local import LocalAceStep
from arioso.platforms.ace_step.config import PLATFORM_CONFIG

def _local_only() -> tuple:
    """Keywords the local runtime reads that fal's mapping does not (from the signature)."""
    fal_names = {name for rule in PLATFORM_CONFIG["fal"]["shared"].values() for name in rule.get("from", ())}
    fal_names |= {"prompt", "genre", "instrumental", "duration", "audio_input"}
    params = inspect.signature(LocalAceStep.generate).parameters.values()
    return tuple(p.name for p in params if p.kind is p.KEYWORD_ONLY and p.name not in fal_names)


#: Keywords only the local runtime understands (fal's endpoint has no such controls).
LOCAL_ONLY = _local_only()


class Adapter(FalAdapter):
    """ACE-Step adapter (fal.ai hosted, or local ACE-Step 1.5)."""

    def __init__(self, config: dict = None, *, local=None):
        config = config if config and "fal" in config else PLATFORM_CONFIG
        super().__init__(
            config,
            run=lambda endpoint, arguments: fal_run(endpoint, arguments),
            upload=lambda audio: fal_upload_audio(audio),
        )
        self._local = local

    @property
    def local(self) -> LocalAceStep:
        """The local runtime (built on first use; its worker starts on the first call)."""
        if self._local is None:
            self._local = LocalAceStep(self.config)
        return self._local

    def accepted_params(self) -> frozenset:
        """fal's keywords plus the local runtime's own controls and ``runtime`` itself."""
        return super().accepted_params() | set(LOCAL_ONLY) | {"runtime"}

    def generate(self, prompt: str = "", *, runtime: str = None, **params):
        """Generate with fal or locally; see the module docstring for how ``runtime`` resolves."""
        source = "runtime" if runtime else "$ARIOSO_ACE_STEP_RUNTIME"
        runtime = runtime or os.environ.get("ARIOSO_ACE_STEP_RUNTIME") or "fal"
        if runtime == "local":
            params.pop("fetch", None)
            return self.local.generate(prompt, **params)
        if runtime != "fal":
            raise ValueError(f"ace_step: {source} must be 'fal' or 'local', not {runtime!r}")
        dropped = [k for k in LOCAL_ONLY if params.pop(k, None) is not None]
        if dropped:
            warnings.warn(f"ace_step (fal) has no {', '.join(dropped)} control; ignored "
                          "(runtime='local' supports them)", stacklevel=2)
        return super().generate(prompt, **params)
