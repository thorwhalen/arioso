"""Foundation-1 worker: runs inside the ``foundation-1`` environment (stable-audio-tools).

``load(device=None)`` -> the state: the torch device (``"mps"``, ``"cuda"`` or ``"cpu"``;
the best available when None) and the one checkpoint loaded so far (a new checkpoint
replaces it, so at most one ~5 GB model is held).

``render(state, *, repo_id, revision, config_file, checkpoint, t5, prompt, seconds, steps,
cfg_scale, seed, sampler, sigma_min, sigma_max, out, negative_prompt=None)`` ->
``{"out", "sample_rate", "seconds", "device"}``: one take, peak-normalised, written as a
16-bit wav at ``out``. Weights come from the Hugging Face cache at pinned revisions
(downloaded on first use, read from the cache with no network call after): the checkpoint,
and the T5-base files (``t5``: ``repo_id``, ``revision``, ``files``), which the prompt
conditioner is pointed at (its ``model_path``) instead of looking ``t5-base`` up online.
The model is conditioned on whole seconds (``seconds_total``), as it was trained, and the
audio is trimmed to the exact ``seconds``.

Sampling is plain classifier-free guidance (``apg_scale=0``), as Stable Audio Open 1.0 and
the Foundation-1 tools sample. stable-audio-tools' adaptive projected guidance (its
default) projects in float64, which Apple's MPS backend lacks; plain CFG never leaves
float32, so the model runs on MPS whole. ``PYTORCH_ENABLE_MPS_FALLBACK=1`` (set by arioso)
lets any operator MPS does not have run on the CPU instead of failing.
"""

import json
import os


def load(device=None):
    """Pick the device; the model loads on the first render (it depends on the checkpoint)."""
    import torch

    if device is None:
        if torch.cuda.is_available():
            device = "cuda"
        elif torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"
    return {"device": device, "loaded": None, "model": None, "model_config": None}


def _fetch(repo_id, filename, revision):
    """The cached file at ``revision``, else downloaded (no network call when it is cached)."""
    from huggingface_hub import hf_hub_download

    try:
        return hf_hub_download(
            repo_id, filename, revision=revision, local_files_only=True
        )
    except Exception:  # not cached yet (the hub raises several kinds)
        return hf_hub_download(repo_id, filename, revision=revision)


def _pin_t5(model_config, t5):
    """Point every T5 prompt conditioner at the pinned T5 files (their folder)."""
    folder = None
    for name in t5["files"]:
        folder = os.path.dirname(_fetch(t5["repo_id"], name, t5["revision"]))
    for cond in model_config["model"]["conditioning"]["configs"]:
        if cond["type"] == "t5":
            cond["config"]["model_path"] = folder
    return model_config


def _model(state, *, repo_id, revision, config_file, checkpoint, t5):
    """The model for ``checkpoint`` (loaded once; replaces the one held before)."""
    key = (repo_id, revision, checkpoint)
    if state["loaded"] != key:
        import gc

        import torch
        from stable_audio_tools.models.factory import create_model_from_config
        from stable_audio_tools.models.utils import (
            copy_state_dict,
            load_ckpt_state_dict,
        )

        state["model"] = state["loaded"] = None
        gc.collect()
        with open(_fetch(repo_id, config_file, revision)) as f:
            model_config = _pin_t5(json.load(f), t5)
        weights = _fetch(repo_id, checkpoint, revision)
        model = create_model_from_config(model_config)
        copy_state_dict(model, load_ckpt_state_dict(weights))
        model = model.to(state["device"]).eval().requires_grad_(False)
        if state["device"] == "mps":
            torch.mps.empty_cache()
        state.update(model=model, model_config=model_config, loaded=key)
    return state["model"], state["model_config"]


def render(
    state,
    *,
    repo_id,
    revision,
    config_file,
    checkpoint,
    t5,
    prompt,
    seconds,
    steps,
    cfg_scale,
    seed,
    sampler,
    sigma_min,
    sigma_max,
    out,
    negative_prompt=None,
):
    """Generate ``seconds`` of audio for ``prompt`` with our seed; save it at ``out``."""
    import numpy as np
    import soundfile as sf
    import torch
    from stable_audio_tools.inference.generation import generate_diffusion_cond

    model, model_config = _model(
        state,
        repo_id=repo_id,
        revision=revision,
        config_file=config_file,
        checkpoint=checkpoint,
        t5=t5,
    )
    sample_rate = int(model_config["sample_rate"])
    window = int(model_config["sample_size"])
    total = max(1, round(seconds))  # whole seconds, as in training
    conditioning = [{"prompt": prompt, "seconds_start": 0, "seconds_total": total}]
    negative = (
        [{"prompt": negative_prompt, "seconds_start": 0, "seconds_total": total}]
        if negative_prompt
        else None
    )
    with torch.inference_mode():
        audio = generate_diffusion_cond(
            model,
            steps=int(steps),
            cfg_scale=float(cfg_scale),
            conditioning=conditioning,
            negative_conditioning=negative,
            sample_size=window,
            seed=int(seed),
            device=state["device"],
            apg_scale=0.0,  # plain CFG: no float64 (see the module docstring)
            sampler_type=sampler,
            sigma_min=float(sigma_min),
            sigma_max=float(sigma_max),
        )
    # (channels, samples) of the first take, trimmed from the window to the clip
    audio = (
        audio[0].to(torch.float32).cpu().numpy()[:, : int(round(seconds * sample_rate))]
    )
    peak = float(np.abs(audio).max()) if audio.size else 0.0
    if peak > 0:
        audio = audio / peak
    sf.write(out, np.clip(audio, -1, 1).T, sample_rate, subtype="PCM_16")
    return {
        "out": out,
        "sample_rate": sample_rate,
        "seconds": audio.shape[-1] / sample_rate,
        "device": state["device"],
    }
