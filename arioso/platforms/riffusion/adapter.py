"""Riffusion adapter using the riffusion library or diffusers fallback."""

import warnings

from arioso.base import AudioResult, Song

# Default spectrogram-to-audio parameters
_SAMPLE_RATE = 44100
_N_FFT = 2048
_HOP_LENGTH = 512


class Adapter:
    """Riffusion adapter with dual backend support.

    Tries the ``riffusion`` library first for full spectrogram-to-audio
    support.  Falls back to the ``diffusers`` StableDiffusion pipeline
    which generates a spectrogram image and converts it to audio via
    inverse STFT.
    """

    def __init__(self, config: dict):
        self.config = config
        self._pipe = None
        self._use_riffusion_lib = False

    def _ensure_model(self):
        """Lazy-load the pipeline."""
        if self._pipe is not None:
            return
        try:
            from riffusion.riffusion_pipeline import RiffusionPipeline

            self._pipe = RiffusionPipeline.load_checkpoint(
                "riffusion/riffusion-model-v1"
            )
            self._use_riffusion_lib = True
        except ImportError:
            from diffusers import StableDiffusionPipeline

            self._pipe = StableDiffusionPipeline.from_pretrained(
                "riffusion/riffusion-model-v1"
            )
            self._use_riffusion_lib = False

    def generate(
        self,
        prompt: str,
        *,
        negative_prompt: str = "",
        seed: int = None,
        guidance: float = 7.0,
        num_steps: int = 50,
        audio_input_strength: float = 0.75,
        **kwargs,
    ) -> Song:
        """Generate audio from a text prompt via spectrogram synthesis.

        Args:
            prompt: Text description of desired music.
            negative_prompt: Elements to avoid in generation.
            seed: Random seed for reproducibility.
            guidance: Classifier-free guidance scale.
            num_steps: Number of diffusion inference steps.
            audio_input_strength: Denoising strength (0-1).

        Returns:
            A Song with audio_array populated.
        """
        self._ensure_model()

        if self._use_riffusion_lib:
            return self._generate_riffusion_lib(
                prompt,
                negative_prompt=negative_prompt,
                seed=seed,
                guidance=guidance,
                num_steps=num_steps,
                audio_input_strength=audio_input_strength,
            )
        return self._generate_diffusers(
            prompt,
            negative_prompt=negative_prompt,
            seed=seed,
            guidance=guidance,
            num_steps=num_steps,
        )

    # ------------------------------------------------------------------
    # riffusion library backend
    # ------------------------------------------------------------------

    def _generate_riffusion_lib(
        self,
        prompt,
        *,
        negative_prompt,
        seed,
        guidance,
        num_steps,
        audio_input_strength,
    ) -> Song:
        from dataclasses import dataclass

        @dataclass
        class _PromptInput:
            prompt: str
            seed: int
            denoising: float
            guidance: float

        seed_val = seed if seed is not None else 42
        start = _PromptInput(
            prompt=prompt,
            seed=seed_val,
            denoising=audio_input_strength,
            guidance=guidance,
        )
        end = _PromptInput(
            prompt=negative_prompt or prompt,
            seed=seed_val,
            denoising=audio_input_strength,
            guidance=guidance,
        )

        result = self._pipe.riffuse(
            start,
            end,
            alpha=0.0,
            num_inference_steps=num_steps,
        )

        # The riffusion pipeline returns a (image, audio_segment) tuple
        _, audio_segment = result
        import numpy as np

        audio_array = np.array(audio_segment.get_array_of_samples()).astype(np.float32)
        # Normalize to [-1, 1]
        max_val = np.iinfo(np.int16).max
        audio_array = audio_array / max_val

        return Song(
            audio=AudioResult(
                audio_array=audio_array,
                sample_rate=_SAMPLE_RATE,
                format="wav",
            ),
            platform="riffusion",
            status="complete",
            metadata={
                "backend": "riffusion_lib",
                "seed": seed_val,
                "guidance": guidance,
                "num_steps": num_steps,
            },
        )

    # ------------------------------------------------------------------
    # diffusers fallback backend
    # ------------------------------------------------------------------

    def _generate_diffusers(
        self,
        prompt,
        *,
        negative_prompt,
        seed,
        guidance,
        num_steps,
    ) -> Song:
        import torch
        import numpy as np

        generator = None
        if seed is not None:
            generator = torch.Generator().manual_seed(seed)

        pipe_kwargs = {
            "prompt": prompt,
            "num_inference_steps": num_steps,
            "guidance_scale": guidance,
            "generator": generator,
        }
        if negative_prompt:
            pipe_kwargs["negative_prompt"] = negative_prompt

        result = self._pipe(**pipe_kwargs)
        spectrogram_image = result.images[0]

        # Convert spectrogram image to audio via inverse STFT
        audio_array = _spectrogram_image_to_audio(spectrogram_image)

        return Song(
            audio=AudioResult(
                audio_array=audio_array,
                sample_rate=_SAMPLE_RATE,
                format="wav",
            ),
            platform="riffusion",
            status="complete",
            metadata={
                "backend": "diffusers",
                "seed": seed,
                "guidance": guidance,
                "num_steps": num_steps,
            },
        )


def _spectrogram_image_to_audio(image):
    """Convert a spectrogram PIL image to a 1-D audio array.

    This is a simplified inverse: the image is treated as a log-magnitude
    spectrogram, and Griffin-Lim is used for phase reconstruction.
    """
    import numpy as np

    # Convert to grayscale numpy array
    spec_array = np.array(image.convert("L")).astype(np.float32)
    # Flip vertically (low frequencies at bottom in the image)
    spec_array = spec_array[::-1, :]
    # Rescale from [0, 255] to approximate dB range, then to linear
    spec_db = spec_array / 255.0 * 80.0 - 80.0  # range roughly [-80, 0] dB
    spec_linear = 10.0 ** (spec_db / 20.0)

    # Griffin-Lim reconstruction
    audio = _griffin_lim(spec_linear, n_iter=32)
    return audio


def _griffin_lim(magnitude, *, n_iter=32):
    """Reconstruct audio from a magnitude spectrogram using Griffin-Lim."""
    import numpy as np

    n_fft = (magnitude.shape[0] - 1) * 2
    hop_length = _HOP_LENGTH

    # Random initial phase
    phase = np.exp(2j * np.pi * np.random.random(magnitude.shape))
    for _ in range(n_iter):
        stft = magnitude * phase
        # Inverse STFT
        audio = _istft(stft, hop_length=hop_length)
        # Re-analyze
        recon = _stft(audio, n_fft=n_fft, hop_length=hop_length)
        # Update phase
        phase = np.exp(1j * np.angle(recon))

    audio = np.real(_istft(magnitude * phase, hop_length=hop_length))
    # Normalize
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val
    return audio.astype(np.float32)


def _stft(audio, *, n_fft, hop_length):
    """Simple STFT using numpy."""
    import numpy as np

    window = np.hanning(n_fft)
    n_frames = 1 + (len(audio) - n_fft) // hop_length
    frames = np.stack(
        [
            audio[i * hop_length : i * hop_length + n_fft] * window
            for i in range(n_frames)
        ],
        axis=1,
    )
    return np.fft.rfft(frames, axis=0)


def _istft(stft_matrix, *, hop_length):
    """Simple inverse STFT using numpy."""
    import numpy as np

    n_fft = (stft_matrix.shape[0] - 1) * 2
    window = np.hanning(n_fft)
    n_frames = stft_matrix.shape[1]
    length = n_fft + hop_length * (n_frames - 1)
    audio = np.zeros(length)
    window_sum = np.zeros(length)

    for i in range(n_frames):
        frame = np.real(np.fft.irfft(stft_matrix[:, i]))
        start = i * hop_length
        audio[start : start + n_fft] += frame * window
        window_sum[start : start + n_fft] += window**2

    # Normalize by window overlap
    nonzero = window_sum > 1e-8
    audio[nonzero] /= window_sum[nonzero]
    return audio
