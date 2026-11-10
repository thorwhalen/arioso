"""ACE-Step 1.5 run locally: a worker in the ACE-Step-1.5 checkout's own environment.

The unified affordances map onto ACE-Step's ``GenerationParams``: ``prompt``/``genre`` is the
caption, ``bpm``/``key`` are explicit controls, ``audio_input`` is the source of a cover
(``audio_input_strength`` its cover strength) and ``reference_audio`` a style reference.
"""

from __future__ import annotations

import tempfile
import warnings

from arioso._audio import to_audio_ref
from arioso._isolated import Runtime, Worker, draw_seed, song_from_wav

#: The checkout's own bundle ships the turbo DiT and the 1.7B LM; other LMs download on use.
DFLT_DIT = "acestep-v15-turbo"
DFLT_LM = "acestep-5Hz-lm-1.7B"


class LocalAceStep:
    """Generate with a local ACE-Step 1.5 worker (started on first use, kept alive)."""

    def __init__(self, config: dict, *, make_worker=Worker):
        self.config = config
        self.runtime = Runtime(**config["runtime"])
        self._make_worker = make_worker
        self._worker = None

    def _ensure_worker(self):
        if self._worker is None:
            self._worker = self._make_worker(
                self.runtime.interpreter(),
                self.config["driver"],
                cwd=self.runtime.workdir(),
            )
        return self._worker

    def close(self):
        """Stop the worker (the loaded models are released)."""
        if self._worker is not None:
            self._worker.close()
            self._worker = None

    def generate(
        self,
        prompt: str = "",
        *,
        genre: str = None,
        lyrics: str = None,
        instrumental: bool = None,
        duration: float = 30.0,
        bpm: int = None,
        key: str = None,
        num_steps: int = 8,
        guidance: float = 7.0,
        seed: int = None,
        model: str = DFLT_DIT,
        lm_model: str = DFLT_LM,
        audio_input=None,
        audio_input_strength: float = 1.0,
        reference_audio=None,
        timesignature: str = None,
        **fal_only,
    ):
        if fal_only:
            warnings.warn(
                f"ace_step (local) has no {', '.join(sorted(fal_only))} control; ignored "
                "(those are fal.ai endpoint options)",
                stacklevel=3,
            )
        caption = (
            genre or prompt
        )  # the same precedence as the fal mapping (tags: genre, else prompt)
        if not caption:
            raise ValueError("ace_step requires a style prompt (prompt or genre)")
        if instrumental is None:
            instrumental = not lyrics
        seed = draw_seed() if seed is None else int(seed)
        req = {
            "caption": caption,
            "lyrics": "[Instrumental]" if instrumental else lyrics,
            "instrumental": bool(instrumental),
            "seconds": float(duration),
            "bpm": bpm,
            "key": key,
            "timesignature": timesignature,
            "steps": int(num_steps),
            "guidance": float(guidance),
            "seed": seed,
            "dit": model,
            "lm": lm_model,
            "out_dir": tempfile.mkdtemp(prefix="arioso_ace_"),
        }
        refs = []
        try:
            if audio_input is not None:
                refs.append(to_audio_ref(audio_input))
                req.update(
                    task_type="cover",
                    src_audio=refs[-1].as_path(suffix=".wav"),
                    cover_strength=float(audio_input_strength),
                )
            if reference_audio is not None:
                refs.append(to_audio_ref(reference_audio))
                req["reference_audio"] = refs[-1].as_path(suffix=".wav")
            result = self._ensure_worker().call(req)
        finally:
            for ref in refs:
                ref.cleanup()
        meta = {
            "runtime": "local",
            "seed": seed,
            "model": model,
            "lm_model": lm_model,
            "bpm": bpm,
            "key": key,
            "num_steps": num_steps,
            "audio_to_audio": audio_input is not None,
            "ace_step": result.get("params", {}),
        }
        return song_from_wav(
            result["out"], platform="ace_step", metadata=meta, remove=True
        )
