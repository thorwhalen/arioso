"""MusicGen adapter using audiocraft (preferred) or transformers.

The adapter holds the modes; ``backends.py`` holds how each library runs them.

Supports text-to-music generation and, via ``facebook/musicgen-melody``,
melody-conditioned generation (the ``melody`` affordance / ``arioso.enhance``
stage): the output follows the pitch contour of an input audio while taking its
style from the text prompt.

It also *continues* a recording (the ``continue_from`` affordance): the last
``prompt_seconds`` of the audio are fed to the model as an audio prompt and it
generates what comes next, chained over ``rounds`` calls for longer extensions.
This is the local fallback for extending audio that a hosted extend route
refuses (``sunoapi.upload_extend`` rejects uploads matching a catalogued
composition; thorwhalen/arioso#29).
"""

from __future__ import annotations

from collections.abc import Callable

from arioso.base import AudioResult, Song
from arioso._audio import to_audio_ref
from arioso.platforms.musicgen.backends import (
    AudiocraftBackend,
    Backend,
    Sampling,
    TransformersBackend,
)

#: MusicGen's context window in seconds: an audio prompt plus the new audio it
#: generates must fit in it (transformers caps generation at 1500 frames).
WINDOW_SECONDS = 30.0
#: Crossfade from the original audio into the model's re-decoded prompt at each
#: seam, hiding the codec's reconstruction error there (a click otherwise).
SEAM_CROSSFADE_SECONDS = 0.01


def _load_backend(model_variant: str) -> Backend:
    """Load *model_variant* with audiocraft, or with transformers when audiocraft is
    not installed."""
    try:
        return AudiocraftBackend.load(model_variant)
    except ImportError:
        return TransformersBackend.load(model_variant)


class Adapter:
    """MusicGen adapter with lazy model loading.

    Tries ``audiocraft`` first; if unavailable, falls back to the
    HuggingFace ``transformers`` pipeline. ``load_backend`` (model variant ->
    :class:`Backend`) replaces that choice.
    """

    def __init__(
        self, config: dict, *, load_backend: Callable[[str], Backend] = _load_backend
    ):
        self.config = config
        self._load_backend = load_backend
        self._loaded: Backend | None = None
        self._model_name: str | None = None

    def generate(
        self,
        prompt: str,
        *,
        duration: float = 8.0,
        temperature: float = 1.0,
        top_k: int = 250,
        top_p: float = 0.0,
        guidance: float = 3.0,
        model: str = "facebook/musicgen-small",
        melody=None,
        continue_from=None,
        continue_at: float | None = None,
        prompt_seconds: float = 10.0,
        extend_seconds: float | None = None,
        rounds: int = 1,
        **kwargs,
    ) -> Song:
        """Generate music from a text prompt, optionally following a melody or
        continuing a recording.

        Args:
            prompt: Text description of desired music.
            duration: Length in seconds.
            temperature: Sampling randomness.
            top_k: Top-k sampling parameter.
            top_p: Top-p nucleus sampling.
            guidance: Classifier-free guidance scale.
            model: Model variant name (e.g. 'facebook/musicgen-small'). When a
                ``melody`` is supplied and ``model`` isn't already a melody
                variant, it is switched to ``facebook/musicgen-melody``.
            melody: Optional input audio whose pitch contour the output follows
                (a Song/AudioResult/bytes/path/(array, sample_rate)/waveform).
                This is the ``arioso.enhance`` path for musicgen.
            continue_from: Optional audio to extend, in any of the forms
                ``melody`` accepts. The result is this audio followed by its
                continuation (mono, at the model's sample rate); the
                continuation alone is in ``metadata['continuation']``. Each
                seam crossfades over 10 ms into the model's re-decoded prompt,
                so join the result, not the original plus the continuation.
            continue_at: Continue from this time (seconds) in
                ``continue_from`` instead of from its end; what follows it is
                dropped.
            prompt_seconds: Length of the tail of the audio fed to the model as
                the prompt for each round.
            extend_seconds: New audio per round, in seconds (default
                ``duration``). ``prompt_seconds + extend_seconds`` must fit in
                :data:`WINDOW_SECONDS`.
            rounds: Number of chained continuation calls, each prompted by the
                tail of the audio so far, so the extension totals
                ``rounds * extend_seconds``.

        Returns:
            A Song with audio_array populated.
        """
        sampling = Sampling(
            temperature=temperature, top_k=top_k, top_p=top_p, guidance=guidance
        )
        if continue_from is not None:
            if melody is not None:
                raise ValueError(
                    "musicgen: melody and continue_from cannot be combined -- "
                    "MusicGen continues an audio prompt or follows a melody's "
                    "chroma, not both in one call."
                )
            return self._continue(
                prompt,
                continue_from,
                continue_at=continue_at,
                prompt_seconds=prompt_seconds,
                extend_seconds=duration if extend_seconds is None else extend_seconds,
                rounds=rounds,
                model=model,
                sampling=sampling,
            )

        if melody is not None and "melody" not in model:
            model = "facebook/musicgen-melody"
        backend = self._backend(model)
        if melody is None:
            audio, extra = backend.text(prompt, seconds=duration, sampling=sampling), {}
        else:
            ref = to_audio_ref(melody)
            audio = backend.melody(prompt, ref, seconds=duration, sampling=sampling)
            extra = {"melody_conditioned": True}
        return _song(
            audio,
            backend.sample_rate,
            model=self._model_name,
            temperature=temperature,
            **extra,
        )

    def _backend(self, model: str) -> Backend:
        """The *model* loaded (once per variant) behind the interface of its library."""
        if self._loaded is None or self._model_name != model:
            self._loaded = self._load_backend(model)
            self._model_name = model
        return self._loaded

    def _continue(
        self,
        prompt,
        source,
        *,
        continue_at,
        prompt_seconds,
        extend_seconds,
        rounds,
        model,
        sampling: Sampling,
    ) -> Song:
        """Extend *source* by ``rounds`` chained audio-prompted generations."""
        import importlib.util
        import os

        _check_continuation_window(prompt_seconds, extend_seconds, rounds)
        if isinstance(source, str) and not os.path.exists(source):
            raise ValueError(
                f"musicgen: continue_from={source!r} is not a file. musicgen "
                f"runs locally and continues the audio itself (a path, bytes, "
                f"Song or (array, sample_rate)), not a hosted clip id or URL."
            )
        # transformers is the fallback when audiocraft is missing; refuse before
        # loading a multi-GB checkpoint that cannot do this
        if "melody" in model and importlib.util.find_spec("audiocraft") is None:
            raise ValueError(
                f"musicgen: {model!r} cannot continue audio with "
                f"transformers (its audio input is melody chroma, not a prompt "
                f"to extend). Use a non-melody checkpoint such as "
                f"'facebook/musicgen-small'."
            )
        backend = self._backend(model)
        sample_rate = backend.sample_rate
        # Prompt lengths are whole codec frames, so the model re-decodes the
        # prompt to exactly as many samples as it was given, and dropping that
        # many from the output leaves the continuation alone.
        hop = sample_rate // backend.frame_rate

        audio, _ = to_audio_ref(source).as_mono(target_rate=sample_rate)
        if continue_at is not None:
            if not 0 < continue_at <= len(audio) / sample_rate:
                raise ValueError(
                    f"musicgen: continue_at={continue_at} is outside the "
                    f"{len(audio) / sample_rate:.2f} s of continue_from."
                )
            audio = audio[: int(continue_at * sample_rate)]
        if len(audio) < hop:
            raise ValueError(
                f"musicgen: continue_from has {len(audio)} samples to continue "
                f"from; at least one codec frame ({hop} samples) is needed."
            )
        prompt_len = max(hop, int(prompt_seconds * sample_rate) // hop * hop)

        crossfade = int(SEAM_CROSSFADE_SECONDS * sample_rate)
        used_prompt = min(prompt_len, len(audio) // hop * hop)
        stitched = audio
        for _ in range(rounds):
            n = min(prompt_len, len(stitched) // hop * hop)
            out = backend.continuation(
                prompt, stitched[-n:], seconds=extend_seconds, sampling=sampling
            )
            stitched = _splice(stitched, out, n, crossfade=crossfade)

        return _song(
            stitched,
            sample_rate,
            model=self._model_name,
            temperature=sampling.temperature,
            continued=True,
            continue_from_seconds=len(audio) / sample_rate,
            prompt_seconds=used_prompt / sample_rate,
            extend_seconds=extend_seconds,
            rounds=rounds,
            continuation=_audio_result(stitched[len(audio) :], sample_rate),
        )


def _splice(audio, out, n, *, crossfade):
    """Append the continuation in *out* (whose first *n* samples re-decode the
    prompt, the last *n* of *audio*), crossfading into the re-decoded prompt
    over the last *crossfade* samples of *audio*."""
    import numpy as np

    decoded, new = out[:n], out[n:]
    audio = audio.copy()
    xf = min(crossfade, n)
    if xf:
        ramp = np.linspace(0.0, 1.0, xf, dtype=audio.dtype)
        audio[-xf:] = audio[-xf:] * (1 - ramp) + decoded[-xf:] * ramp
    return np.concatenate([audio, new.astype(audio.dtype)])


def _check_continuation_window(
    prompt_seconds, extend_seconds, rounds, *, window=WINDOW_SECONDS
):
    """Raise early, before a model loads, on a continuation that cannot run."""
    if prompt_seconds <= 0 or extend_seconds <= 0:
        raise ValueError(
            f"musicgen: prompt_seconds and extend_seconds must be positive, got "
            f"{prompt_seconds} and {extend_seconds}."
        )
    if prompt_seconds + extend_seconds > window:
        raise ValueError(
            f"musicgen: prompt_seconds + extend_seconds = "
            f"{prompt_seconds + extend_seconds} exceeds MusicGen's {window} s "
            f"window. Extend in shorter steps with rounds=N instead (each round "
            f"adds extend_seconds)."
        )
    if not isinstance(rounds, int) or rounds < 1:
        raise ValueError(f"musicgen: rounds must be a positive int, got {rounds!r}.")


def _song(audio_array, sample_rate, *, model, temperature, **metadata) -> Song:
    """A complete musicgen Song of *audio_array*, ``(frames,)`` or
    ``(channels, frames)``, with ``model``, ``temperature`` and *metadata*."""
    return Song(
        audio=_audio_result(audio_array, sample_rate),
        platform="musicgen",
        status="complete",
        metadata={"model": model, "temperature": temperature, **metadata},
    )


def _audio_result(audio_array, sample_rate) -> AudioResult:
    """WAV-format AudioResult; its duration is the length of the frames axis."""
    return AudioResult(
        audio_array=audio_array,
        sample_rate=sample_rate,
        format="wav",
        duration_seconds=audio_array.shape[-1] / sample_rate,
    )
