"""ACE-Step 1.5 worker: runs inside the ACE-Step-1.5 checkout's environment (see the config).

The worker's working directory is the checkout, which ``acestep`` needs as its project
root (checkpoints download into ``checkpoints/`` there on first use). The DiT and the
optional 5 Hz LM load once per ``(dit, lm)`` and stay loaded. On Apple Silicon the LM runs
on MLX and the DiT on MPS/MLX (ACE-Step's own defaults).
"""

import os
import sys

from arioso._isolated import is_apple_silicon, serve

ROOT = os.getcwd()
sys.path.insert(0, ROOT)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
_handlers = {}


def _handlers_for(dit, lm):
    key = (dit, lm)
    if key not in _handlers:
        from acestep.handler import AceStepHandler

        dit_h = AceStepHandler()
        msg, ok = dit_h.initialize_service(project_root=ROOT, config_path=dit, device="auto")
        if not ok:
            raise RuntimeError(f"ACE-Step DiT {dit!r} failed to load: {msg}")
        llm_h = None
        if lm:
            from acestep.llm_inference import LLMHandler

            llm_h = LLMHandler()
            msg, ok = llm_h.initialize(checkpoint_dir=os.path.join(ROOT, "checkpoints"), lm_model_path=lm,
                                       backend="mlx" if is_apple_silicon() else "pt", device="auto")
            if not ok:
                raise RuntimeError(f"ACE-Step LM {lm!r} failed to load: {msg}")
        _handlers[key] = (dit_h, llm_h)
    return _handlers[key]


def handle(req):
    from acestep.inference import GenerationConfig, GenerationParams, generate_music

    dit_h, llm_h = _handlers_for(req["dit"], req.get("lm"))
    params = GenerationParams(
        task_type=req.get("task_type", "text2music"),
        thinking=llm_h is not None,
        caption=req["caption"],
        lyrics=req.get("lyrics") or "[Instrumental]",
        instrumental=req.get("instrumental", True),
        bpm=req.get("bpm"),
        keyscale=req.get("key") or "",
        timesignature=req.get("timesignature") or "",
        duration=req["seconds"],
        inference_steps=req["steps"],
        guidance_scale=req["guidance"],
        seed=req["seed"],
        src_audio=req.get("src_audio"),
        reference_audio=req.get("reference_audio"),
        audio_cover_strength=req.get("cover_strength", 1.0),
    )
    # use_random_seed=False: otherwise ACE-Step draws its own seed and ignores ours.
    config = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[req["seed"]], audio_format="wav")
    res = generate_music(dit_h, llm_h, params=params, config=config, save_dir=req["out_dir"])
    if not res.success:
        raise RuntimeError(res.error or res.status_message)
    audio = res.audios[0]
    if not audio.get("path"):
        raise RuntimeError(f"ACE-Step reported success but saved no audio: {res.status_message}")
    return {"out": audio["path"], "key": audio.get("key"), "params": {
        k: v for k, v in (audio.get("params") or {}).items() if isinstance(v, (str, int, float, bool, type(None)))
    }}


if __name__ == "__main__":
    serve(handle)
