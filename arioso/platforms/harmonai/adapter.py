"""Harmonai (Dance Diffusion) adapter using diffusers."""

import warnings

from arioso.base import AudioResult, Song


class Adapter:
    """Dance Diffusion adapter with lazy model loading.

    Uses the ``diffusers`` library to run unconditional audio generation
    via the Dance Diffusion pipeline.
    """

    def __init__(self, config: dict):
        self.config = config
        self._pipe = None

    def _ensure_model(self):
        """Lazy-load the Dance Diffusion pipeline."""
        if self._pipe is not None:
            return
        from diffusers import DanceDiffusionPipeline

        self._pipe = DanceDiffusionPipeline.from_pretrained(
            "harmonai/jmann-small-190k-steps"
        )

    def generate(
        self,
        prompt: str = "",
        *,
        num_steps: int = 100,
        seed: int = None,
        batch_size: int = 1,
        **kwargs,
    ) -> Song:
        """Generate audio unconditionally.

        Args:
            prompt: Ignored (unconditional model). A warning is emitted
                if a non-empty prompt is provided.
            num_steps: Number of diffusion inference steps.
            seed: Random seed for reproducibility.
            batch_size: Number of audio samples to generate.

        Returns:
            A Song with audio_array populated.
        """
        if prompt:
            warnings.warn(
                "Harmonai Dance Diffusion is an unconditional model; "
                "the 'prompt' argument will be ignored.",
                stacklevel=2,
            )

        self._ensure_model()

        import torch

        generator = None
        if seed is not None:
            generator = torch.Generator().manual_seed(seed)

        result = self._pipe(
            num_inference_steps=num_steps,
            batch_size=batch_size,
            generator=generator,
        )

        audio_array = result.audios[0]
        sample_rate = self._pipe.unet.config.sample_rate

        return Song(
            audio=AudioResult(
                audio_array=audio_array,
                sample_rate=sample_rate,
                format="wav",
            ),
            platform="harmonai",
            status="complete",
            metadata={
                "num_steps": num_steps,
                "seed": seed,
                "batch_size": batch_size,
            },
        )
