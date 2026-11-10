"""The ways to run MusicGen, behind one interface (thorwhalen/arioso#31, #54).

The adapter holds the modes (text, melody, continuation: window checks, chaining, splicing); a
backend holds what one library needs to load a model and run it in each of them. ``audiocraft``
is Meta's library, ``transformers`` the HuggingFace port, and ``mlx`` Apple's MLX port
(``ml-explore/mlx-examples``), which runs in its own environment through a worker and only
does text. Each backend wraps a model that is already loaded, so building one is free;
``load`` is what loads one.

Which one runs (:func:`select_backend_class`): ``$ARIOSO_MUSICGEN_BACKEND`` when set; else
MLX for a text take on Apple Silicon when its runtime is installed; else audiocraft when it
imports; else transformers. On Apple Silicon, transformers runs on the CPU unless
``$ARIOSO_TORCH_DEVICE`` says otherwise: on MPS it was 15-30x slower and grew Metal memory
on every decoding step (42 GB after three 10 s clips on an M1 Max).

audiocraft and transformers return the model's own layout for text and melody,
``(channels, frames)`` from audiocraft and ``(frames,)`` from transformers' first channel, and
mono for a continuation; MLX returns ``(frames,)``.
"""

from __future__ import annotations

import os
import tempfile
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional, Protocol

from arioso._util import TORCH_DEVICE_ENV_VAR, torch_device

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

    @classmethod
    def can_continue(cls, model_variant: str) -> bool:
        """Whether this library can continue audio with ``model_variant`` (cheap: loads nothing)."""

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


#: Forces a backend: ``audiocraft``, ``transformers`` or ``mlx``.
BACKEND_ENV_VAR = "ARIOSO_MUSICGEN_BACKEND"
#: MusicGen's context in seconds (1500 frames); the MLX port does not stop there itself.
MLX_MAX_SECONDS = 30.0
#: The checkpoints the MLX port loads.
MLX_CHECKPOINTS = frozenset(
    f"facebook/musicgen-{size}" for size in ("small", "medium", "large")
)
#: What a backend is asked to do: plain text, follow a melody, or continue audio.
TASKS = ("text", "melody", "continuation")


def select_backend_class(model_variant: str, *, task: str = "text") -> type[Backend]:
    """The library that runs ``model_variant`` for ``task`` (see the module docstring).

    Loads no checkpoint, so it can be asked before a multi-GB one is read; a present but
    broken audiocraft install falls back like a missing one.
    """
    forced = os.environ.get(BACKEND_ENV_VAR)
    if forced and forced not in BACKENDS:
        raise ValueError(
            f"${BACKEND_ENV_VAR}={forced!r}: expected one of {sorted(BACKENDS)}"
        )
    if forced and (forced != "mlx" or task == "text"):
        return BACKENDS[forced]  # mlx forced only where it can run: text
    if task == "text" and MlxBackend.available(model_variant):
        return MlxBackend
    try:
        import audiocraft.models  # noqa: F401
    except ImportError:
        return TransformersBackend
    return AudiocraftBackend


def _transformers_device(model_variant: str) -> str:
    """:func:`~arioso._util.torch_device`, except CPU for the text checkpoints on Apple MPS.

    Text (and continuation) decoding of ``musicgen-small`` on MPS is pathological
    (thorwhalen/arioso#54): slower than the CPU and growing Metal memory per step. The melody
    checkpoint keeps MPS, where it was measured faster than the CPU (a 30 s melody take took a
    quarter of an hour on the CPU). An explicit ``$ARIOSO_TORCH_DEVICE`` always wins.
    """
    device = torch_device()
    if (
        device == "mps"
        and not os.environ.get(TORCH_DEVICE_ENV_VAR)
        and "melody" not in model_variant
    ):
        return "cpu"
    return device


def _rate_or_default(rate) -> int:
    return int(rate) if isinstance(rate, (int, float)) and rate else DEFAULT_FRAME_RATE


#: Kept under its old name; the choice is shared by every local platform.
_device = torch_device


class AudiocraftBackend:
    """A loaded ``audiocraft.models.MusicGen``."""

    def __init__(self, model):
        self.model = model

    @classmethod
    def can_continue(cls, model_variant: str) -> bool:
        """Every checkpoint takes an audio prompt to extend."""
        return True

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
    def can_continue(cls, model_variant: str) -> bool:
        """Not a melody checkpoint: its audio input is melody chroma, not a prompt to extend."""
        return "melody" not in model_variant

    @classmethod
    def load(cls, model_variant: str) -> TransformersBackend:
        """Load ``model_variant`` and its processor with transformers, on :func:`_transformers_device`.

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

        model = _ModelClass.from_pretrained(model_variant).to(
            _transformers_device(model_variant)
        )
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


class MlxBackend:
    """MusicGen on MLX, in the ``mlx-examples`` runtime's own process (text only).

    The model lives in a :class:`~arioso._isolated.Worker` running
    :mod:`arioso.platforms.musicgen._mlx_driver`; audio comes back through a ``.npy`` file.
    ``top_p`` has no MLX counterpart (a non-zero one is warned about and ignored).
    """

    def __init__(self, worker, model_variant: str, info: dict):
        """Wrap a started ``worker`` that has loaded ``model_variant`` (``info``: its rates)."""
        self.worker = worker
        self.model_variant = model_variant
        self.info = info

    @staticmethod
    def runtime():
        """The ``mlx-examples`` runtime (see the musicgen config's ``mlx_runtime``)."""
        from arioso._isolated import Runtime
        from arioso.platforms.musicgen.config import PLATFORM_CONFIG

        return Runtime(**PLATFORM_CONFIG["mlx_runtime"])

    @classmethod
    def supports(cls, model_variant: str) -> bool:
        """Whether the MLX port runs ``model_variant``: Meta's mono text checkpoints only
        (the port reads their audiocraft ``state_dict.bin``; fine-tunes in transformers
        format have none)."""
        return model_variant in MLX_CHECKPOINTS

    @classmethod
    def available(cls, model_variant: str) -> bool:
        """Apple Silicon, a supported checkpoint, and the runtime installed (cheap)."""
        from arioso._isolated import is_apple_silicon

        return (
            is_apple_silicon()
            and cls.supports(model_variant)
            and cls.runtime().installed()
        )

    @classmethod
    def can_continue(cls, model_variant: str) -> bool:
        """No: the MLX port generates from text only."""
        return False

    @classmethod
    def load(
        cls, model_variant: str, *, make_worker: Optional[Callable[..., object]] = None
    ) -> MlxBackend:
        """Start the worker and load ``model_variant`` in it.

        Raises:
            ValueError: For a checkpoint the MLX port does not run.
            arioso._isolated.RuntimeNotInstalled: With the commands that install it.
        """
        from arioso._isolated import Worker
        from arioso.platforms.musicgen.config import PLATFORM_CONFIG

        if not cls.supports(model_variant):
            raise ValueError(
                f"musicgen: the MLX backend runs the mono text checkpoints, not "
                f"{model_variant!r}; unset ${BACKEND_ENV_VAR} to use another backend."
            )
        runtime = cls.runtime()
        worker = (make_worker or Worker)(
            runtime.interpreter(), PLATFORM_CONFIG["mlx_driver"], cwd=runtime.workdir()
        )
        info = worker.call({"op": "load", "model": model_variant})
        return cls(worker, model_variant, info)

    @property
    def sample_rate(self) -> int:
        """Output samples per second."""
        return int(self.info["sample_rate"])

    @property
    def frame_rate(self) -> int:
        """Codec frames per second."""
        return _rate_or_default(self.info.get("frame_rate"))

    def text(self, prompt: str, *, seconds: float, sampling: Sampling) -> np.ndarray:
        """``seconds`` of mono audio for ``prompt``, ``(frames,)``."""
        import numpy as np

        if seconds > MLX_MAX_SECONDS:
            warnings.warn(
                f"musicgen (mlx): {seconds} s is past MusicGen's {MLX_MAX_SECONDS:.0f} s "
                "context; the take degrades after it.",
                stacklevel=2,
            )
        if sampling.top_p:
            warnings.warn(
                f"musicgen (mlx): top_p={sampling.top_p} is ignored; the MLX port "
                "samples with top_k only.",
                stacklevel=2,
            )
        with tempfile.TemporaryDirectory(prefix="arioso_mlx_mg_") as tmp:
            out = Path(tmp) / "audio.npy"
            self.worker.call(
                {
                    "op": "text",
                    "model": self.model_variant,
                    "prompt": prompt,
                    "seconds": seconds,
                    "top_k": sampling.top_k,
                    "temperature": sampling.temperature,
                    "guidance": sampling.guidance,
                    "out": str(out),
                }
            )
            return np.load(out)

    def melody(self, prompt, ref, *, seconds, sampling):
        """Not on MLX: the selection sends melody takes to another backend."""
        raise NotImplementedError(
            "musicgen: the MLX backend does not follow melodies; "
            f"unset ${BACKEND_ENV_VAR} (or set it to transformers)."
        )

    def continuation(self, prompt, tail, *, seconds, sampling):
        """Not on MLX: the selection sends continuations to another backend."""
        raise NotImplementedError(
            "musicgen: the MLX backend does not continue audio; "
            f"unset ${BACKEND_ENV_VAR} (or set it to transformers)."
        )

    def close(self):
        """Stop the worker (the model is released)."""
        self.worker.close()


#: The backends by the name ``$ARIOSO_MUSICGEN_BACKEND`` takes.
BACKENDS = {
    "audiocraft": AudiocraftBackend,
    "transformers": TransformersBackend,
    "mlx": MlxBackend,
}
