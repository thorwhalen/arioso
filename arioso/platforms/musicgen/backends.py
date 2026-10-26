"""The two ways to run MusicGen, behind one interface (thorwhalen/arioso#31).

The adapter holds the modes (text, melody, continuation: window checks, chaining, splicing); a
backend holds what one library needs to run a loaded model in each of them. ``audiocraft`` is
Meta's library, ``transformers`` the HuggingFace port the adapter falls back to. Each backend
wraps a model that is already loaded, so building one is free.

Both return the model's own output layout for text and melody, ``(channels, frames)`` from
audiocraft and ``(frames,)`` from transformers' first channel, and mono for a continuation.
"""

from dataclasses import dataclass

#: Codec frames per second, used when a model does not report its own.
DEFAULT_FRAME_RATE = 50


@dataclass(frozen=True)
class Sampling:
    """Sampling settings shared by every MusicGen mode."""

    temperature: float = 1.0
    top_k: int = 250
    top_p: float = 0.0
    guidance: float = 3.0


def _rate_or_default(rate) -> int:
    return int(rate) if isinstance(rate, (int, float)) and rate else DEFAULT_FRAME_RATE


class AudiocraftBackend:
    """A loaded ``audiocraft.models.MusicGen``."""

    def __init__(self, model, processor=None):
        self.model = model

    @property
    def sample_rate(self) -> int:
        return int(self.model.sample_rate)

    @property
    def frame_rate(self) -> int:
        """Codec frames per second (50 for every MusicGen checkpoint)."""
        return _rate_or_default(getattr(self.model, "frame_rate", None))

    def text(self, prompt: str, *, seconds: float, sampling: Sampling):
        self._set_params(seconds, sampling)
        return self.model.generate([prompt])[0].cpu().numpy()

    def melody(self, prompt: str, ref, *, seconds: float, sampling: Sampling):
        """Follow the chroma of ``ref`` (an ``AudioRef``)."""
        self._set_params(seconds, sampling)
        # generate_with_chroma wants (batch, channels, frames)
        wav = self.model.generate_with_chroma(
            [prompt], ref.as_waveform()[None], ref.sample_rate
        )
        return wav[0].cpu().numpy()

    def continuation(self, prompt: str, tail, *, seconds: float, sampling: Sampling):
        """The re-decoded ``tail`` (mono, at ``sample_rate``) and ``seconds`` after it, mono."""
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

    @property
    def sample_rate(self) -> int:
        return int(self.model.config.audio_encoder.sampling_rate)

    @property
    def frame_rate(self) -> int:
        """Codec frames per second (50 for every MusicGen checkpoint)."""
        encoder = self.model.config.audio_encoder
        return _rate_or_default(getattr(encoder, "frame_rate", None))

    @property
    def delay_frames(self) -> int:
        """Frames the codebook delay pattern consumes from ``max_new_tokens`` (3 for the
        4-codebook checkpoints), so a call yields the seconds asked for."""
        config = getattr(self.model.decoder, "config", None)
        codebooks = getattr(config, "num_codebooks", None)
        channels = getattr(config, "audio_channels", 1)
        if not isinstance(codebooks, int) or not isinstance(channels, int):
            return 0
        return max(codebooks // max(channels, 1) - 1, 0)

    def text(self, prompt: str, *, seconds: float, sampling: Sampling):
        inputs = self.processor(text=[prompt], padding=True, return_tensors="pt")
        return self._generate(inputs, seconds, sampling)[0, 0].cpu().numpy()

    def melody(self, prompt: str, ref, *, seconds: float, sampling: Sampling):
        """Follow the chroma of ``ref`` (an ``AudioRef``)."""
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

    def continuation(self, prompt: str, tail, *, seconds: float, sampling: Sampling):
        """The re-decoded ``tail`` (mono, at ``sample_rate``) and ``seconds`` after it, mono."""
        import numpy as np

        stereo = getattr(self.model.decoder.config, "audio_channels", 1) == 2
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
