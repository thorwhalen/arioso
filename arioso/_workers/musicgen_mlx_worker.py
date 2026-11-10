"""MusicGen on MLX, worker side: runs inside the ``mlx-examples/musicgen`` environment.

Apple's ``ml-explore/mlx-examples`` port (MIT) is a folder of scripts, not a package, so it
runs here, in its own interpreter with that folder as the working directory (its modules,
``musicgen``, ``encodec``, ``t5`` and ``utils``, are top-level names that must not reach
arioso's environment). See the musicgen config's ``mlx_runtime``.

``load(model)`` -> the loaded model. ``info(model)`` -> ``{"sample_rate", "frame_rate"}``.
``text(model, *, prompt, seconds, top_k, temperature, guidance, out)`` -> ``{"out",
"frames"}``: ``seconds`` of mono float32 audio saved with ``numpy.save`` at ``out``.
"""

import os
import sys

#: Codec frames per second of every MusicGen checkpoint (EnCodec 32 kHz, hop 640).
FRAME_RATE = 50


def load(model):
    """Load the checkpoint ``model`` with the port found in the working directory."""
    # The port's modules sit in the working directory, which is not on sys.path: a worker
    # takes it off, and so does ``python -P`` / $PYTHONSAFEPATH.
    if os.getcwd() not in sys.path:
        sys.path.insert(0, os.getcwd())
    from musicgen import MusicGen

    return MusicGen.from_pretrained(model)


def info(model):
    """The model's output and codec rates."""
    return {"sample_rate": int(model.sampling_rate), "frame_rate": FRAME_RATE}


def text(model, *, prompt, seconds, top_k, temperature, guidance, out):
    """``seconds`` of audio for ``prompt``, saved at ``out``."""
    import mlx.core as mx
    import numpy as np

    frames = max(1, round(seconds * FRAME_RATE))
    # Undoing the codebook delay pattern costs num_codebooks - 1 steps, and the port's undo
    # leaves its last frame misaligned (codebook 0 at t with the others at t-1..t-3): one
    # step more, and the trim below drops that frame.
    audio = model.generate(
        prompt,
        max_steps=frames + model.num_codebooks,
        top_k=int(top_k),
        temp=float(temperature),
        guidance_coef=float(guidance),
    )
    mx.eval(audio)
    hop = int(model.sampling_rate) // FRAME_RATE
    samples = np.asarray(audio, dtype=np.float32).reshape(-1)[: frames * hop]
    np.save(out, samples)
    return {"out": out, "frames": frames}
