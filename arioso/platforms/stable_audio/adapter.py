"""Stable Audio Open adapter using HuggingFace Diffusers."""

from arioso.base import AudioResult, Song


class Adapter:
    """Stable Audio Open adapter with lazy model loading.

    Uses ``diffusers.StableAudioPipeline`` for local inference.
    """

    def __init__(self, config: dict):
        self.config = config
        self._pipe = None

    def _ensure_model(self):
        """Lazy-load the pipeline only when first generation is requested."""
        if self._pipe is not None:
            return
        import torch
        from diffusers import StableAudioPipeline

        self._pipe = StableAudioPipeline.from_pretrained(
            "stabilityai/stable-audio-open-1.0", torch_dtype=torch.float16
        )
        self._pipe = self._pipe.to("cuda" if torch.cuda.is_available() else "cpu")

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
        **kwargs,
    ) -> Song:
        """Generate audio from a text prompt.

        Args:
            prompt: Text description of desired audio.
            negative_prompt: Text description of undesired characteristics.
            duration: Length in seconds.
            num_steps: Number of diffusion inference steps.
            guidance: Classifier-free guidance scale.
            seed: Random seed for reproducibility.
            batch_size: Number of waveforms to generate.
            sampler: Sampler type for the diffusion process.

        Returns:
            A Song with audio_array populated.
        """
        import torch

        self._ensure_model()

        generator = None
        if seed is not None:
            device = self._pipe.device
            generator = torch.Generator(device=device).manual_seed(seed)

        output = self._pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            audio_end_in_s=duration,
            num_inference_steps=num_steps,
            num_waveforms_per_prompt=batch_size,
            generator=generator,
        )

        audio_array = output.audios[0]
        sample_rate = self._pipe.vae.sampling_rate

        return Song(
            audio=AudioResult(
                audio_array=audio_array,
                sample_rate=sample_rate,
                format="wav",
                duration_seconds=duration,
            ),
            platform="stable_audio",
            status="complete",
            metadata={"seed": seed, "num_steps": num_steps, "guidance": guidance},
        )
