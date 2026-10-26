"""MusicGen adapter using audiocraft (preferred) or transformers.

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

from arioso.base import AudioResult, Song
from arioso._audio import to_audio_ref

#: MusicGen's context window in seconds: an audio prompt plus the new audio it
#: generates must fit in it (transformers caps generation at 1500 frames).
WINDOW_SECONDS = 30.0
#: Codec frames per second, used when a model does not report its own.
DEFAULT_FRAME_RATE = 50
#: Crossfade from the original audio into the model's re-decoded prompt at each
#: seam, hiding the codec's reconstruction error there (a click otherwise).
SEAM_CROSSFADE_SECONDS = 0.01


class Adapter:
    """MusicGen adapter with lazy model loading.

    Tries ``audiocraft`` first; if unavailable, falls back to the
    HuggingFace ``transformers`` pipeline.
    """

    def __init__(self, config: dict):
        self.config = config
        self._model = None
        self._model_name = None
        self._use_transformers = False

    def _ensure_model(self, model_variant: str = "facebook/musicgen-small"):
        """Lazy-load the model only when first generation is requested."""
        if self._model is not None and self._model_name == model_variant:
            return
        try:
            from audiocraft.models import MusicGen

            self._model = MusicGen.get_pretrained(model_variant)
            self._model_name = model_variant
            self._use_transformers = False
        except ImportError:
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

            self._model = _ModelClass.from_pretrained(model_variant).to(_device())
            self._processor = AutoProcessor.from_pretrained(model_variant)
            self._model_name = model_variant
            self._use_transformers = True

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
                continuation alone is in ``metadata['continuation']``.
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
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                guidance=guidance,
            )

        if melody is not None and "melody" not in model:
            model = "facebook/musicgen-melody"
        self._ensure_model(model)

        if melody is not None:
            if self._use_transformers:
                return self._generate_transformers_melody(
                    prompt,
                    melody,
                    duration=duration,
                    temperature=temperature,
                    top_k=top_k,
                    top_p=top_p,
                    guidance=guidance,
                )
            return self._generate_audiocraft_melody(
                prompt,
                melody,
                duration=duration,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                guidance=guidance,
            )

        if self._use_transformers:
            return self._generate_transformers(
                prompt,
                duration=duration,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                guidance=guidance,
            )
        return self._generate_audiocraft(
            prompt,
            duration=duration,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            guidance=guidance,
        )

    def _generate_audiocraft(
        self, prompt, *, duration, temperature, top_k, top_p, guidance
    ) -> Song:
        self._set_audiocraft_params(
            duration=duration,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            guidance=guidance,
        )
        wav = self._model.generate([prompt])
        return _song(
            wav[0].cpu().numpy(),
            self._model.sample_rate,
            model=self._model_name,
            temperature=temperature,
        )

    def _generate_transformers(
        self, prompt, *, duration, temperature, top_k, top_p, guidance
    ) -> Song:
        inputs = self._processor(text=[prompt], padding=True, return_tensors="pt").to(
            self._model.device
        )
        audio_values = self._transformers_generate(
            inputs,
            seconds=duration,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            guidance=guidance,
        )
        return _song(
            audio_values[0, 0].cpu().numpy(),
            self._sample_rate(),
            model=self._model_name,
            temperature=temperature,
        )

    def _generate_audiocraft_melody(
        self, prompt, melody, *, duration, temperature, top_k, top_p, guidance
    ) -> Song:
        self._set_audiocraft_params(
            duration=duration,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            guidance=guidance,
        )
        ref = to_audio_ref(melody)
        melody_wav = ref.as_waveform()  # (channels, frames)
        # generate_with_chroma wants (batch, channels, frames)
        wav = self._model.generate_with_chroma(
            [prompt], melody_wav[None], ref.sample_rate
        )
        return _song(
            wav[0].cpu().numpy(),
            self._model.sample_rate,
            model=self._model_name,
            temperature=temperature,
            melody_conditioned=True,
        )

    def _generate_transformers_melody(
        self, prompt, melody, *, duration, temperature, top_k, top_p, guidance
    ) -> Song:
        audio, sample_rate = to_audio_ref(melody).as_mono(
            target_rate=self._processor.feature_extractor.sampling_rate
        )
        inputs = self._processor(
            audio=audio,
            sampling_rate=sample_rate,
            text=[prompt],
            padding=True,
            return_tensors="pt",
        ).to(self._model.device)
        audio_values = self._transformers_generate(
            inputs,
            seconds=duration,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            guidance=guidance,
        )
        return _song(
            audio_values[0, 0].cpu().numpy(),
            self._sample_rate(),
            model=self._model_name,
            temperature=temperature,
            melody_conditioned=True,
        )

    def _set_audiocraft_params(self, *, duration, temperature, top_k, top_p, guidance):
        """Sampling settings for the next audiocraft ``generate*`` call."""
        self._model.set_generation_params(
            use_sampling=True,
            top_k=top_k,
            top_p=top_p,
            temperature=temperature,
            duration=duration,
            cfg_coef=guidance,
        )

    def _transformers_generate(
        self, inputs, *, seconds, temperature, top_k, top_p, guidance
    ):
        """Sample *seconds* of new audio with transformers; returns the
        ``(batch, channels, frames)`` tensor. ``max_new_tokens`` adds the
        frames the delay pattern consumes, so the output is the full length."""
        import torch

        with torch.no_grad():
            return self._model.generate(
                **inputs,
                max_new_tokens=int(seconds * self._frame_rate()) + self._delay_frames(),
                temperature=temperature,
                do_sample=True,
                top_k=top_k,
                top_p=top_p if top_p > 0 else None,
                guidance_scale=guidance,
            )

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
        temperature,
        top_k,
        top_p,
        guidance,
    ) -> Song:
        """Extend *source* by ``rounds`` chained audio-prompted generations."""
        _check_continuation_window(prompt_seconds, extend_seconds, rounds)
        self._ensure_model(model)
        if self._use_transformers and "melody" in self._model_name:
            raise ValueError(
                f"musicgen: {self._model_name!r} cannot continue audio with "
                f"transformers (its audio input is melody chroma, not a prompt "
                f"to extend). Use a non-melody checkpoint such as "
                f"'facebook/musicgen-small'."
            )
        sample_rate = self._sample_rate()
        # Prompt lengths are whole codec frames, so the model re-decodes the
        # prompt to exactly as many samples as it was given, and dropping that
        # many from the output leaves the continuation alone.
        hop = sample_rate // self._frame_rate()

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
        sampling = dict(
            temperature=temperature, top_k=top_k, top_p=top_p, guidance=guidance
        )

        crossfade = int(SEAM_CROSSFADE_SECONDS * sample_rate)
        used_prompt = min(prompt_len, len(audio) // hop * hop)
        stitched = audio
        for _ in range(rounds):
            n = min(prompt_len, len(stitched) // hop * hop)
            out = self._continuation_round(
                prompt, stitched[-n:], extend_seconds=extend_seconds, **sampling
            )
            stitched = _splice(stitched, out, n, crossfade=crossfade)

        return _song(
            stitched,
            sample_rate,
            model=self._model_name,
            temperature=temperature,
            continued=True,
            continue_from_seconds=len(audio) / sample_rate,
            prompt_seconds=used_prompt / sample_rate,
            extend_seconds=extend_seconds,
            rounds=rounds,
            continuation=_audio_result(stitched[len(audio) :], sample_rate),
        )

    def _continuation_round(
        self, prompt, tail, *, extend_seconds, temperature, top_k, top_p, guidance
    ):
        """One audio-prompted call: the re-decoded *tail* followed by the new
        audio, mono."""
        import numpy as np
        import torch

        if self._use_transformers:
            stereo = getattr(self._model.decoder.config, "audio_channels", 1) == 2
            inputs = self._processor(
                audio=[np.stack([tail, tail]) if stereo else tail],
                sampling_rate=self._sample_rate(),
                text=[prompt],
                padding=True,
                return_tensors="pt",
            ).to(self._model.device)
            audio_values = self._transformers_generate(
                inputs,
                seconds=extend_seconds,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                guidance=guidance,
            )
            out = audio_values[0].cpu().numpy()
        else:
            self._set_audiocraft_params(
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                guidance=guidance,
                # audiocraft's duration covers the prompt and the continuation;
                # it takes int(duration * frame_rate) frames, so aim mid-frame
                # to keep float error from losing the last one.
                duration=(
                    len(tail) * self._frame_rate() // self._sample_rate()
                    + round(extend_seconds * self._frame_rate())
                    + 0.5
                )
                / self._frame_rate(),
            )
            prompt_wav = torch.from_numpy(tail).float()[None, None]
            wav = self._model.generate_continuation(
                prompt_wav, self._sample_rate(), descriptions=[prompt]
            )
            out = wav[0].cpu().numpy()
        return out.mean(axis=0)  # (channels, frames) -> mono

    def _delay_frames(self) -> int:
        """Frames the codebook delay pattern consumes from ``max_new_tokens``
        on the transformers path (3 for the 4-codebook checkpoints), so a
        call yields the seconds asked for."""
        decoder_config = getattr(self._model.decoder, "config", None)
        codebooks = getattr(decoder_config, "num_codebooks", None)
        channels = getattr(decoder_config, "audio_channels", 1)
        if not isinstance(codebooks, int) or not isinstance(channels, int):
            return 0
        return max(codebooks // max(channels, 1) - 1, 0)

    def _sample_rate(self) -> int:
        if self._use_transformers:
            return int(self._model.config.audio_encoder.sampling_rate)
        return int(self._model.sample_rate)

    def _frame_rate(self) -> int:
        """Codec frames per second (50 for every MusicGen checkpoint)."""
        if self._use_transformers:
            rate = getattr(self._model.config.audio_encoder, "frame_rate", None)
        else:
            rate = getattr(self._model, "frame_rate", None)
        if isinstance(rate, (int, float)) and rate:
            return int(rate)
        return DEFAULT_FRAME_RATE


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
