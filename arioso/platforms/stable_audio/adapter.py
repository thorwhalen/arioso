"""Stable Audio Open adapter using HuggingFace Diffusers."""

import warnings

from arioso.base import AudioResult, Song
from arioso._audio import to_audio_ref


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
        audio_input=None,
        audio_input_strength: float = None,
        **kwargs,
    ) -> Song:
        """Generate audio from a text prompt, optionally conditioned on input audio.

        Args:
            prompt: Text description of desired audio.
            negative_prompt: Text description of undesired characteristics.
            duration: Length in seconds.
            num_steps: Number of diffusion inference steps.
            guidance: Classifier-free guidance scale.
            seed: Random seed for reproducibility.
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

        Returns:
            A Song with audio_array populated.
        """
        self._ensure_model()

        generator = None
        if seed is not None:
            import torch

            device = self._pipe.device
            generator = torch.Generator(device=device).manual_seed(seed)

        call_kwargs = dict(
            prompt=prompt,
            negative_prompt=negative_prompt,
            audio_end_in_s=duration,
            num_inference_steps=num_steps,
            num_waveforms_per_prompt=batch_size,
            generator=generator,
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
            # pipeline wants (batch, channels, frames)
            call_kwargs["initial_audio_waveforms"] = waveform.unsqueeze(0)
            call_kwargs["initial_audio_sampling_rate"] = ref.sample_rate

        output = self._pipe(**call_kwargs)

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
            metadata={
                "seed": seed,
                "num_steps": num_steps,
                "guidance": guidance,
                "audio_to_audio": audio_input is not None,
            },
        )
