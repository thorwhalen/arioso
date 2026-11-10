"""ACE-Step 1.5 worker: runs inside the ACE-Step-1.5 checkout's environment (see the config).

The worker's working directory is the checkout, which ``acestep`` needs as its project
root (checkpoints download into ``checkpoints/`` there on first use).

``load()`` -> the state: the checkout root and a cache of handlers, one ``(DiT, LM)`` pair
per ``(dit, lm)``, loaded on first use and kept. On Apple Silicon the LM runs on MLX and
the DiT on MPS/MLX (ACE-Step's own defaults).
``render(state, *, caption, seconds, steps, guidance, seed, dit, lm, out_dir, ...)`` ->
``{"out", "key", "params"}``: one take saved in ``out_dir``.
"""

import os
import platform
import sys


def load():
    """The checkout root (put on ``sys.path``) and an empty handler cache."""
    root = os.getcwd()
    if root not in sys.path:
        sys.path.insert(0, root)
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    return {"root": root, "handlers": {}}


def _is_apple_silicon():
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def _handlers_for(state, dit, lm):
    key = (dit, lm)
    if key not in state["handlers"]:
        from acestep.handler import AceStepHandler

        dit_h = AceStepHandler()
        msg, ok = dit_h.initialize_service(
            project_root=state["root"], config_path=dit, device="auto"
        )
        if not ok:
            raise RuntimeError(f"ACE-Step DiT {dit!r} failed to load: {msg}")
        llm_h = None
        if lm:
            from acestep.llm_inference import LLMHandler

            llm_h = LLMHandler()
            msg, ok = llm_h.initialize(
                checkpoint_dir=os.path.join(state["root"], "checkpoints"),
                lm_model_path=lm,
                backend="mlx" if _is_apple_silicon() else "pt",
                device="auto",
            )
            if not ok:
                raise RuntimeError(f"ACE-Step LM {lm!r} failed to load: {msg}")
        state["handlers"][key] = (dit_h, llm_h)
    return state["handlers"][key]


def render(
    state,
    *,
    caption,
    seconds,
    steps,
    guidance,
    seed,
    dit,
    out_dir,
    lm=None,
    task_type="text2music",
    lyrics=None,
    instrumental=True,
    bpm=None,
    key=None,
    timesignature=None,
    src_audio=None,
    reference_audio=None,
    cover_strength=1.0,
):
    """Generate one take with our seed and controls; return where it was saved."""
    from acestep.inference import GenerationConfig, GenerationParams, generate_music

    dit_h, llm_h = _handlers_for(state, dit, lm)
    params = GenerationParams(
        task_type=task_type,
        thinking=llm_h is not None,
        caption=caption,
        lyrics=lyrics or "[Instrumental]",
        instrumental=instrumental,
        bpm=bpm,
        keyscale=key or "",
        timesignature=timesignature or "",
        duration=seconds,
        inference_steps=steps,
        guidance_scale=guidance,
        seed=seed,
        src_audio=src_audio,
        reference_audio=reference_audio,
        audio_cover_strength=cover_strength,
    )
    # use_random_seed=False: otherwise ACE-Step draws its own seed and ignores ours.
    config = GenerationConfig(
        batch_size=1, use_random_seed=False, seeds=[seed], audio_format="wav"
    )
    res = generate_music(dit_h, llm_h, params=params, config=config, save_dir=out_dir)
    if not res.success:
        raise RuntimeError(res.error or res.status_message)
    audio = res.audios[0]
    if not audio.get("path"):
        raise RuntimeError(
            f"ACE-Step reported success but saved no audio: {res.status_message}"
        )
    return {
        "out": audio["path"],
        "key": audio.get("key"),
        "params": {
            k: v
            for k, v in (audio.get("params") or {}).items()
            if isinstance(v, (str, int, float, bool, type(None)))
        },
    }
