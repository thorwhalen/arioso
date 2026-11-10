"""Stable Audio 3 adapter: Stability's pure-MLX build, run as one process per take.

The MLX build is a script in the ``Stability-AI/stable-audio-3`` checkout with its own
virtualenv (see the config's ``runtime``), so each call runs ``scripts/sa3_mlx.py`` there
(the small model loads in about a second, so a persistent worker would buy little) and
reads back the wav it wrote. A seed is always passed and recorded (a fresh one when none
is given). ``runner=`` is the process seam.
"""

from __future__ import annotations

import platform
import re
import tempfile
from pathlib import Path

from arioso._audio import to_audio_ref
from arioso._isolated import Runner, Runtime, draw_seed, run_process, song_from_wav
from arioso.platforms.stable_audio_3.config import PLATFORM_CONFIG

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _is_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


class Adapter:
    """Local Stable Audio 3 (MLX) adapter."""

    def __init__(self, config: dict = None, *, runner: Runner = run_process, is_supported=_is_apple_silicon):
        self.config = config or PLATFORM_CONFIG
        self.runtime = Runtime(**self.config["runtime"])
        self._run = runner
        self._is_supported = is_supported

    def _command(self, prompt, out, *, model, seconds, steps, guidance, seed,
                 negative_prompt, init_audio, strength, inpaint_range):
        try:
            dit, decoder = self.config["models"][model]
        except KeyError:
            raise ValueError(f"stable_audio_3: unknown model {model!r}; one of {sorted(self.config['models'])}")
        cmd = [self.runtime.interpreter(), "scripts/sa3_mlx.py", "--prompt", prompt,
               "--dit", dit, "--decoder", decoder, "--seconds", seconds, "--steps", steps,
               "--cfg", guidance, "--seed", seed, "--out", out]
        if negative_prompt:
            cmd += ["--negative-prompt", negative_prompt]
        if init_audio is not None:
            cmd += ["--init-audio", init_audio, "--init-noise-level", strength]
            if inpaint_range is not None:
                start, end = inpaint_range
                cmd += ["--inpaint-range", f"{start},{end}"]
        elif inpaint_range is not None:
            raise ValueError("stable_audio_3: inpaint_range needs audio_input (the audio to inpaint into)")
        return cmd

    def generate(
        self,
        prompt: str,
        *,
        duration: float = 10.0,
        model: str = "sm-music",
        num_steps: int = 8,
        guidance: float = 1.0,
        seed: int = None,
        negative_prompt: str = None,
        audio_input=None,
        audio_input_strength: float = 0.7,
        inpaint_range=None,
        timeout: float = None,
        **kwargs,
    ):
        """Generate ``duration`` seconds for ``prompt``.

        Args:
            prompt: Text description (tempo and key only through the text, e.g. "100 BPM").
            duration: Seconds of audio (trimmed exactly).
            model: ``"sm-music"`` (fast), ``"sm-sfx"`` (sound effects) or ``"medium"``.
            num_steps: Sampler steps (the models are distilled for 8).
            guidance: CFG scale; 1.0 (the default) runs no unconditional branch, so a
                ``negative_prompt`` acts only above 1.
            seed: Seed; a fresh one is drawn and recorded when None.
            negative_prompt: What to steer away from (needs ``guidance`` above 1).
            audio_input: Audio to vary (audio-to-audio) or, with ``inpaint_range``, to inpaint.
            audio_input_strength: Noise level 0-1 applied to ``audio_input`` (higher = freer).
            inpaint_range: ``(start, end)`` seconds of ``audio_input`` to regenerate.
            timeout: Seconds before the process is killed.

        Returns:
            A complete Song (wav bytes, array when soundfile is installed, metadata).
        """
        if not self._is_supported():
            raise RuntimeError("stable_audio_3 runs on Apple Silicon only (MLX)")
        seed = draw_seed() if seed is None else int(seed)
        work = Path(tempfile.mkdtemp(prefix="arioso_sa3_"))
        out = work / "out.wav"
        init_path = None
        if audio_input is not None:
            init_path = to_audio_ref(audio_input).as_path(suffix=".wav")
        cmd = self._command(prompt, out, model=model, seconds=float(duration), steps=int(num_steps),
                            guidance=float(guidance), seed=seed, negative_prompt=negative_prompt,
                            init_audio=init_path, strength=float(audio_input_strength),
                            inpaint_range=inpaint_range)
        code, log = self._run(cmd, cwd=self.runtime.workdir(), env=None, timeout=timeout)
        if code or not out.exists():
            tail = _ANSI.sub("", log)[-2000:]
            raise RuntimeError(f"stable_audio_3 failed (exit {code}):\n{tail}")
        return song_from_wav(out, platform="stable_audio_3", metadata={
            "seed": seed, "model": model, "num_steps": num_steps, "guidance": guidance,
            "audio_to_audio": audio_input is not None, "inpaint_range": inpaint_range,
        })
