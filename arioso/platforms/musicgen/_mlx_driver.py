"""MusicGen on MLX, worker side: runs inside the ``mlx-examples/musicgen`` environment.

Apple's ``ml-explore/mlx-examples`` port (MIT) is a folder of scripts, not a package, so it
runs here, in its own interpreter with that folder as the working directory (its modules,
``musicgen``, ``encodec``, ``t5`` and ``utils``, are top-level names that must not reach
arioso's environment). See the musicgen config's ``mlx_runtime``.

Requests (JSON lines, :func:`arioso._isolated.serve`):

- ``{"op": "load", "model"}`` -> ``{"sample_rate", "frame_rate"}``; loads once per model.
- ``{"op": "text", "model", "prompt", "seconds", "top_k", "temperature", "guidance",
  "seed", "out"}`` -> ``{"out", "frames"}``: ``seconds`` of mono float32 audio saved with
  ``numpy.save`` at ``out``.
"""

from arioso._isolated import serve

#: Codec frames per second of every MusicGen checkpoint (EnCodec 32 kHz, hop 640).
FRAME_RATE = 50
_models = {}


def _model(name):
    if name not in _models:
        import os
        import sys

        # the port's modules sit in the working directory, which is not on sys.path
        # under ``python -P`` / $PYTHONSAFEPATH
        if os.getcwd() not in sys.path:
            sys.path.insert(0, os.getcwd())
        from musicgen import MusicGen

        _models[name] = MusicGen.from_pretrained(name)
    return _models[name]


def handle(req):
    model = _model(req["model"])
    if req["op"] == "load":
        return {"sample_rate": int(model.sampling_rate), "frame_rate": FRAME_RATE}
    if req["op"] != "text":
        raise ValueError(f"unknown op {req['op']!r}")
    import mlx.core as mx
    import numpy as np

    if req.get("seed") is not None:
        mx.random.seed(int(req["seed"]))
    frames = max(1, round(req["seconds"] * FRAME_RATE))
    # undoing the codebook delay pattern costs num_codebooks - 1 of the steps
    audio = model.generate(
        req["prompt"],
        max_steps=frames + model.num_codebooks - 1,
        top_k=int(req["top_k"]),
        temp=float(req["temperature"]),
        guidance_coef=float(req["guidance"]),
    )
    mx.eval(audio)
    hop = int(model.sampling_rate) // FRAME_RATE
    samples = np.asarray(audio, dtype=np.float32).reshape(-1)[: frames * hop]
    np.save(req["out"], samples)
    return {"out": req["out"], "frames": frames}


if __name__ == "__main__":
    serve(handle)
