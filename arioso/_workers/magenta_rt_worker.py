"""Magenta RealTime 2 worker: runs inside the magenta-rt environment (see the platform config).

``load()`` -> a cache of models, one per size, loaded on first use and kept.
``render(models, *, prompt | reference_audio, seconds, size, temperature, top_k, guidance,
out)`` -> ``{"out", "sample_rate", "frames"}``: one offline render written to ``out``; the
sampling settings are passed with each render.
"""

FRAME_RATE = 25


def load():
    """The state: a cache of loaded models, by size."""
    return {}


def _model(models, size):
    if size not in models:
        from magenta_rt import MagentaRT2StdMlxfn

        models[size] = MagentaRT2StdMlxfn(size=size)
    return models[size]


def render(
    models,
    *,
    seconds,
    size,
    temperature,
    top_k,
    guidance,
    out,
    prompt=None,
    reference_audio=None,
):
    """Render ``seconds`` in the style of ``prompt`` (or of ``reference_audio``) to ``out``."""
    from magenta_rt import audio
    from magenta_rt.config import MUSICCOCA

    mrt = _model(models, size)
    style = audio.Waveform.from_file(reference_audio) if reference_audio else prompt
    emb = mrt.embed_style(style, use_mapper=True)
    frames = max(1, round(seconds * FRAME_RATE))
    wav, _state = mrt.generate(
        conditioning={MUSICCOCA.key: emb},
        cfg_scales={"musiccoca": guidance, "notes": 1.0, "drums": 1.0},
        temperature=temperature,
        top_k=top_k,
        frames=frames,
    )
    wav.write(out)
    return {"out": out, "sample_rate": wav.sample_rate, "frames": frames}
