"""Magenta RealTime 2 worker: runs inside the magenta-rt environment (see the config).

One request is one offline render: ``{"prompt" | "reference_audio", "seconds", "size",
"temperature", "top_k", "guidance", "out"}`` -> ``{"out", "sample_rate", "frames"}``.
One model stays loaded per size; the sampling settings are passed with each render.
"""

from arioso._isolated import serve

FRAME_RATE = 25
_models = {}


def _model(size):
    if size not in _models:
        from magenta_rt import MagentaRT2StdMlxfn

        _models[size] = MagentaRT2StdMlxfn(size=size)
    return _models[size]


def handle(req):
    from magenta_rt import audio
    from magenta_rt.config import MUSICCOCA

    mrt = _model(req["size"])
    if req.get("reference_audio"):
        style = audio.Waveform.from_file(req["reference_audio"])
    else:
        style = req["prompt"]
    emb = mrt.embed_style(style, use_mapper=True)
    frames = max(1, round(req["seconds"] * FRAME_RATE))
    wav, _state = mrt.generate(
        conditioning={MUSICCOCA.key: emb},
        cfg_scales={"musiccoca": req["guidance"], "notes": 1.0, "drums": 1.0},
        temperature=req["temperature"],
        top_k=req["top_k"],
        frames=frames,
    )
    wav.write(req["out"])
    return {"out": req["out"], "sample_rate": wav.sample_rate, "frames": frames}


if __name__ == "__main__":
    serve(handle)
