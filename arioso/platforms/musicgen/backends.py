"""The two ways to run MusicGen, behind one interface (thorwhalen/arioso#31).

The adapter holds the modes (text, melody, continuation: window checks, chaining, splicing); a
backend holds what one library needs to load a model and run it in each of them. ``audiocraft``
is Meta's library, ``transformers`` the HuggingFace port the adapter falls back to. Each backend
wraps a model that is already loaded, so building one is free; ``load`` is what loads one.

Both return the model's own output layout for text and melody, ``(channels, frames)`` from
audiocraft and ``(frames,)`` from transformers' first channel, and mono for a continuation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import numpy as np

    from arioso._audio import AudioRef

#: Codec frames per second, used when a model does not report its own.
DEFAULT_FRAME_RATE = 50


@dataclass(frozen=True, kw_only=True)
class Sampling:
    """Sampling settings shared by every MusicGen mode."""

    temperature: float
    top_k: int
    top_p: float
    guidance: float


class Backend(Protocol):
    """What the adapter needs from a library that runs a loaded MusicGen model."""

    @property
    def sample_rate(self) -> int:
        """Output samples per second."""

    @property
    def frame_rate(self) -> int:
        """Codec frames per second."""

    def text(self, prompt: str, *, seconds: float, sampling: Sampling) -> np.ndarray:
        """``seconds`` of audio for the text ``prompt``."""

    def melody(
        self, prompt: str, ref: AudioRef, *, seconds: float, sampling: Sampling
    ) -> np.ndarray:
        """``seconds`` of audio for ``prompt`` that follows the chroma of ``ref``."""

    def continuation(
        self, prompt: str, tail: np.ndarray, *, seconds: float, sampling: Sampling
    ) -> np.ndarray:
        """The re-decoded ``tail`` and ``seconds`` after it, mono."""


def _rate_or_default(rate) -> int:
    return int(rate) if isinstance(rate, (int, float)) and rate else DEFAULT_FRAME_RATE


def _device() -> str:
    """The torch device for the transformers path: ``$ARIOSO_TORCH_DEVICE``,
    else CUDA, else Apple MPS, else CPU (the CPU-only default made a
    30-second melody-conditioned generation take a quarter of an hour)."""
    import os

    import torch

    env = os.environ.get("ARIOSO_TORCH_DEVICE")
    if env:
        return env
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class AudiocraftBackend:
    """A loaded ``audiocraft.models.MusicGen``."""

    def __init__(self, model):
        self.model = model

    @classmethod
    def load(cls, model_variant: str) -> AudiocraftBackend:
        """Load ``model_variant`` (e.g. ``'facebook/musicgen-small'``) with audiocraft.

        Args:
            model_variant: A MusicGen checkpoint name.

        Returns:
            The backend wrapping the loaded model.

        Raises:
            ImportError: If audiocraft is not installed.
        """
        from audiocraft.models import MusicGen

        return cls(MusicGen.get_pretrained(model_variant))

    @property
    def sample_rate(self) -> int:
        """Output samples per second."""
        return int(self.model.sample_rate)

    @property
    def frame_rate(self) -> int:
        """Codec frames per second (50 for every MusicGen checkpoint)."""
        return _rate_or_default(getattr(self.model, "frame_rate", None))

    def text(self, prompt: str, *, seconds: float, sampling: Sampling) -> np.ndarray:
        """Generate from a text prompt.

        Args:
            prompt: Text description of the music.
            seconds: Length to generate.
            sampling: Sampling settings.

        Returns:
            The audio, ``(channels, frames)``.
        """
        self._set_params(seconds, sampling)
        return self.model.generate([prompt])[0].cpu().numpy()

    def melody(
        self, prompt: str, ref: AudioRef, *, seconds: float, sampling: Sampling
    ) -> np.ndarray:
        """Generate from a text prompt, following the chroma of ``ref``.

        Args:
            prompt: Text description of the music.
            ref: The audio whose melody to follow.
            seconds: Length to generate.
            sampling: Sampling settings.

        Returns:
            The audio, ``(channels, frames)``.
        """
        self._set_params(seconds, sampling)
        # generate_with_chroma wants (batch, channels, frames)
        wav = self.model.generate_with_chroma(
            [prompt], ref.as_waveform()[None], ref.sample_rate
        )
        return wav[0].cpu().numpy()

    def continuation(
        self, prompt: str, tail: np.ndarray, *, seconds: float, sampling: Sampling
    ) -> np.ndarray:
        """Continue ``tail`` (mono, at ``sample_rate``) by ``seconds``.

        Args:
            prompt: Text description of the music.
            tail: The audio prompt to continue.
            seconds: Length of new audio to generate after ``tail``.
            sampling: Sampling settings.

        Returns:
            The re-decoded ``tail`` followed by the new audio, mono.
        """
        import torch

        # audiocraft's duration covers the prompt and the continuation
        self._set_params(len(tail) / self.sample_rate + seconds, sampling)
        wav = self.model.generate_continuation(
            torch.from_numpy(tail).float()[None, None],
            self.sample_rate,
            descriptions=[prompt],
        )
        return wav[0].cpu().numpy().mean(axis=0)

    def _set_params(self, seconds: float, sampling: Sampling):
        """audiocraft generates ``int(duration * frame_rate)`` frames, so the duration is aimed
        mid-frame: float error can then never drop the last frame (``int(2.3 * 50)`` is 114)."""
        frames = round(seconds * self.frame_rate)
        self.model.set_generation_params(
            use_sampling=True,
            top_k=sampling.top_k,
            top_p=sampling.top_p,
            temperature=sampling.temperature,
            duration=(frames + 0.5) / self.frame_rate,
            cfg_coef=sampling.guidance,
        )


class TransformersBackend:
    """A loaded transformers ``Musicgen(Melody)ForConditionalGeneration`` and its processor."""

    def __init__(self, model, processor):
        self.model = model
        self.processor = processor

    @classmethod
    def load(cls, model_variant: str) -> TransformersBackend:
        """Load ``model_variant`` and its processor with transformers, on :func:`_device`.

        Args:
            model_variant: A MusicGen checkpoint name; a melody variant gets the
                melody-specific model class.

        Returns:
            The backend wrapping the loaded model and processor.
        """
        from transformers import AutoProcessor

        # Melody variants need the melody-specific model class.
        if "melody" in model_variant:
            from transformers import (
                MusicgenMelodyForConditionalGeneration as _ModelClass,
            )
        else:
            from transformers import (
                MusicgenForConditionalGeneration as _ModelClass,
            )

        model = _ModelClass.from_pretrained(model_variant).to(_device())
        return cls(model, AutoProcessor.from_pretrained(model_variant))

    @property
    def sample_rate(self) -> int:
        """Output samples per second."""
        return int(self.model.config.audio_encoder.sampling_rate)

    @property
    def frame_rate(self) -> int:
        """Codec frames per second (50 for every MusicGen checkpoint)."""
        encoder = self.model.config.audio_encoder
        return _rate_or_default(getattr(encoder, "frame_rate", None))

    @property
    def audio_channels(self) -> int:
        """Channels the decoder generates (2 for the stereo checkpoints); 1 when its
        config does not say, or it has none."""
        config = getattr(self.model.decoder, "config", None)
        return getattr(config, "audio_channels", 1)

    @property
    def delay_frames(self) -> int:
        """Frames the codebook delay pattern consumes from ``max_new_tokens`` (3 for the
        4-codebook checkpoints), so a call yields the seconds asked for."""
        config = getattr(self.model.decoder, "config", None)
        codebooks = getattr(config, "num_codebooks", None)
        channels = self.audio_channels
        if not isinstance(codebooks, int) or not isinstance(channels, int):
            return 0
        return max(codebooks // max(channels, 1) - 1, 0)

    def text(self, prompt: str, *, seconds: float, sampling: Sampling) -> np.ndarray:
        """Generate from a text prompt.

        Args:
            prompt: Text description of the music.
            seconds: Length to generate.
            sampling: Sampling settings.

        Returns:
            The first channel of the audio, ``(frames,)``.
        """
        inputs = self.processor(text=[prompt], padding=True, return_tensors="pt")
        return self._generate(inputs, seconds, sampling)[0, 0].cpu().numpy()

    def melody(
        self, prompt: str, ref: AudioRef, *, seconds: float, sampling: Sampling
    ) -> np.ndarray:
        """Generate from a text prompt, following the chroma of ``ref``.

        Args:
            prompt: Text description of the music.
            ref: The audio whose melody to follow, resampled to the processor's rate.
            seconds: Length to generate.
            sampling: Sampling settings.

        Returns:
            The first channel of the audio, ``(frames,)``.
        """
        audio, rate = ref.as_mono(
            target_rate=self.processor.feature_extractor.sampling_rate
        )
        inputs = self.processor(
            audio=audio,
            sampling_rate=rate,
            text=[prompt],
            padding=True,
            return_tensors="pt",
        )
        return self._generate(inputs, seconds, sampling)[0, 0].cpu().numpy()

    def continuation(
        self, prompt: str, tail: np.ndarray, *, seconds: float, sampling: Sampling
    ) -> np.ndarray:
        """Continue ``tail`` (mono, at ``sample_rate``) by ``seconds``.

        Args:
            prompt: Text description of the music.
            tail: The audio prompt to continue (duplicated for a stereo model).
            seconds: Length of new audio to generate after ``tail``.
            sampling: Sampling settings.

        Returns:
            The re-decoded ``tail`` followed by the new audio, mono.
        """
        import numpy as np

        stereo = self.audio_channels == 2
        inputs = self.processor(
            audio=[np.stack([tail, tail]) if stereo else tail],
            sampling_rate=self.sample_rate,
            text=[prompt],
            padding=True,
            return_tensors="pt",
        )
        return self._generate(inputs, seconds, sampling)[0].cpu().numpy().mean(axis=0)

    def _generate(self, inputs, seconds: float, sampling: Sampling):
        """Sample ``seconds`` of new audio: the ``(batch, channels, frames)`` tensor."""
        import torch

        with torch.no_grad():
            return self.model.generate(
                **inputs.to(self.model.device),
                max_new_tokens=round(seconds * self.frame_rate) + self.delay_frames,
                temperature=sampling.temperature,
                do_sample=True,
                top_k=sampling.top_k,
                top_p=sampling.top_p if sampling.top_p > 0 else None,
                guidance_scale=sampling.guidance,
            )
