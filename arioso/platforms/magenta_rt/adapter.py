"""Magenta RealTime 2 adapter: offline renders from a worker in magenta-rt's own environment.

The model loads once, in a :class:`~arioso._isolated.Worker` running this platform's
``_driver`` with the runtime's Python (MLX pinned below 0.32, which arioso's environment
need not share). Style comes from the text ``prompt`` or a ``reference_audio`` clip; there
is no tempo control beyond the words, and no seed (the sampler is not seedable).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from arioso._audio import to_audio_ref
from arioso._isolated import Runtime, Worker, song_from_wav
from arioso.platforms.magenta_rt.config import PLATFORM_CONFIG


class Adapter:
    """Local Magenta RealTime 2 (MLX) adapter."""

    def __init__(self, config: dict = None, *, make_worker=Worker):
        self.config = config or PLATFORM_CONFIG
        self.runtime = Runtime(**self.config["runtime"])
        self._make_worker = make_worker
        self._worker = None

    def _magenta_home(self) -> dict:
        """``$MAGENTA_HOME``, else ``<runtime>/home`` when it exists, else magenta-rt's own default."""
        if os.environ.get("MAGENTA_HOME"):
            return {"MAGENTA_HOME": os.environ["MAGENTA_HOME"]}
        home = self.runtime.root() / "home"
        return {"MAGENTA_HOME": str(home)} if home.exists() else {}

    def _ensure_worker(self):
        if self._worker is None:
            env = self._magenta_home()
            self._worker = self._make_worker(
                self.runtime.interpreter(), self.config["driver"], env=env, cwd=self.runtime.workdir()
            )
        return self._worker

    def close(self):
        """Stop the worker (the loaded model is released)."""
        if self._worker is not None:
            self._worker.close()
            self._worker = None

    def generate(
        self,
        prompt: str,
        *,
        duration: float = 10.0,
        model: str = "mrt2_small",
        temperature: float = 1.3,
        top_k: int = 40,
        guidance: float = 3.0,
        reference_audio=None,
        **kwargs,
    ):
        """Render ``duration`` seconds in the style of ``prompt`` (or of ``reference_audio``).

        Args:
            prompt: Style text (genre, instruments, mood; tempo only as words).
            duration: Seconds of audio (25 frames a second).
            model: ``"mrt2_small"`` (real time on M1-class Macs) or ``"mrt2_base"``.
            temperature: Sampling temperature.
            top_k: Top-k sampling.
            guidance: CFG scale on the style embedding.
            reference_audio: A clip whose style replaces the text prompt's.

        Returns:
            A complete Song (48 kHz stereo wav).
        """
        out = Path(tempfile.mkdtemp(prefix="arioso_mrt_")) / "out.wav"
        req = {
            "prompt": prompt, "seconds": float(duration), "size": model,
            "temperature": float(temperature), "top_k": int(top_k), "guidance": float(guidance),
            "out": str(out),
        }
        ref = to_audio_ref(reference_audio) if reference_audio is not None else None
        try:
            if ref is not None:
                req["reference_audio"] = ref.as_path(suffix=".wav")
            result = self._ensure_worker().call(req)
        finally:
            if ref is not None:
                ref.cleanup()
        return song_from_wav(result["out"], platform="magenta_rt", remove=True, metadata={
            "model": model, "temperature": temperature, "top_k": top_k, "guidance": guidance,
            "frames": result["frames"], "seed": None, "style_from_audio": reference_audio is not None,
        })
