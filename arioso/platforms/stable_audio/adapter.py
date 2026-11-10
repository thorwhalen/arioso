"""Stable Audio Open adapter using HuggingFace Diffusers.

Runs on :func:`arioso._util.torch_device` (CUDA, else Apple MPS, else CPU), in
float16 on CUDA only. The Stability AI repositories are gated: accept the
licence on the model's Hugging Face page and log in before the first load.
"""

from __future__ import annotations

import secrets
import warnings
from collections.abc import Callable
from typing import Any

from arioso.base import AudioResult, Song
from arioso._audio import to_audio_ref
from arioso._util import torch_device, torch_dtype
from arioso.platforms.stable_audio.config import DEFAULT_MODEL

#: Seeds are drawn below this bound when none is given, so every take records one.
SEED_BOUND = 2**31


def load_pipeline(model: str):
    """``diffusers.StableAudioPipeline`` for *model*, on the shared torch device."""
    from diffusers import StableAudioPipeline

    device = torch_device()
    pipe = StableAudioPipeline.from_pretrained(model, torch_dtype=torch_dtype(device))
    return pipe.to(device)


def make_torch_generator(device, seed: int):
    """A ``torch.Generator`` on *device* seeded with *seed*."""
    import torch

    return torch.Generator(device=device).manual_seed(seed)


class Adapter:
    """Stable Audio Open adapter with lazy model loading.

    Uses ``diffusers.StableAudioPipeline`` for local inference. ``load_pipeline``
    (model id -> pipeline) and ``make_generator`` ((device, seed) -> generator)
    are the seams that keep tests free of torch, diffusers and the gated weights.
    """

    def __init__(
        self,
        config: dict,
        *,
        load_pipeline: Callable[[str], Any] = load_pipeline,
        make_generator: Callable[[Any, int], Any] = make_torch_generator,
    ):
        self.config = config
        self._load_pipeline = load_pipeline
        self._make_generator = make_generator
        self._loaded: tuple[str, Any] | None = None  # (model id, its pipeline)

    def _pipeline(self, model: str):
        """The pipeline for *model*, loaded once per model id."""
        if self._loaded is None or self._loaded[0] != model:
            self._loaded = (model, self._load_pipeline(model))
        return self._loaded[1]

    def generate(
        self,
        prompt: str,
        *,
        negative_prompt: str = None,
        duration: float = 10.0,
        num_steps: int = 200,
        guidance: float = 7.0,
        seed: int = None,
        batch_size: int = 1,
        sampler: str = "dpmpp-3m-sde",
        audio_input=None,
        audio_input_strength: float = None,
        model: str = DEFAULT_MODEL,
        **kwargs,
    ) -> Song:
        """Generate audio from a text prompt, optionally conditioned on input audio.

        Args:
            prompt: Text description of desired audio.
            negative_prompt: Text description of undesired characteristics.
            duration: Length in seconds.
            num_steps: Number of diffusion inference steps.
            guidance: Classifier-free guidance scale.
            seed: Random seed for reproducibility. When omitted, one is drawn
                and recorded in ``metadata['seed']``, so every take can be redone.
            batch_size: Number of waveforms to generate.
            sampler: Sampler type for the diffusion process.
            audio_input: Optional input audio to condition on (audio-to-audio):
                a Song/AudioResult/bytes/path/(array, sample_rate)/NumPy waveform.
                Passed to the pipeline as ``initial_audio_waveforms`` -- i.e. the
                model continues/initializes from this audio.
            audio_input_strength: Accepted for API symmetry but **ignored** --
                the diffusers ``StableAudioPipeline`` exposes no denoise/strength
                control (that is a stable-audio-tools/ComfyUI feature). A warning
                is emitted if a value is passed alongside ``audio_input``.
            model: Hugging Face id of a Stable Audio checkpoint that
                ``StableAudioPipeline`` loads.

        Returns:
            A Song with audio_array populated.
        """
        pipe = self._pipeline(model)
        if seed is None:
            seed = secrets.randbelow(SEED_BOUND)
        device = getattr(pipe, "device", "cpu")
        generator = self._make_generator(device, seed)

        call_kwargs = dict(
            prompt=prompt,
            negative_prompt=negative_prompt,
            audio_end_in_s=duration,
            num_inference_steps=num_steps,
            guidance_scale=guidance,
            num_waveforms_per_prompt=batch_size,
            generator=generator,
            output_type="np",  # a host array, not a tensor left on the GPU
        )

        if audio_input is not None:
            if audio_input_strength is not None:
                warnings.warn(
                    "stable_audio (diffusers StableAudioPipeline) has no "
                    "strength/denoise control; 'audio_input_strength' is "
                    "ignored. The input audio is used as the initial waveform "
                    "(continuation/init), not a strength-blended remix.",
                    stacklevel=2,
                )
            ref = to_audio_ref(audio_input)
            waveform = ref.as_waveform()  # (channels, frames)
            # pipeline wants (batch, channels, frames), on its own device and dtype
            call_kwargs["initial_audio_waveforms"] = waveform.unsqueeze(0).to(
                device=device, dtype=getattr(pipe, "dtype", None)
            )
            call_kwargs["initial_audio_sampling_rate"] = ref.sample_rate

        output = pipe(**call_kwargs)

        audio_array = output.audios[0]
        sample_rate = pipe.vae.sampling_rate

        return Song(
            audio=AudioResult(
                audio_array=audio_array,
                sample_rate=sample_rate,
                format="wav",
                duration_seconds=duration,
            ),
            platform=self.config.get("name", "stable_audio"),
            status="complete",
            metadata={
                "model": model,
                "seed": seed,
                "device": str(device),  # the same seed differs across devices
                "num_steps": num_steps,
                "guidance": guidance,
                "audio_to_audio": audio_input is not None,
            },
        )
