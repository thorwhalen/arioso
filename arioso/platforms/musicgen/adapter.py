"""MusicGen adapter using audiocraft (preferred) or transformers."""

from arioso.base import AudioResult, Song


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
            from transformers import AutoProcessor, MusicgenForConditionalGeneration

            self._model = MusicgenForConditionalGeneration.from_pretrained(
                model_variant
            )
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
        **kwargs,
    ) -> Song:
        """Generate music from a text prompt.

        Args:
            prompt: Text description of desired music.
            duration: Length in seconds.
            temperature: Sampling randomness.
            top_k: Top-k sampling parameter.
            top_p: Top-p nucleus sampling.
            guidance: Classifier-free guidance scale.
            model: Model variant name (e.g. 'facebook/musicgen-small').

        Returns:
            A Song with audio_array populated.
        """
        self._ensure_model(model)

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
        self._model.set_generation_params(
            use_sampling=True,
            top_k=top_k,
            top_p=top_p,
            temperature=temperature,
            duration=duration,
            cfg_coef=guidance,
        )
        wav = self._model.generate([prompt])
        audio_array = wav[0].cpu().numpy()
        sample_rate = self._model.sample_rate

        return Song(
            audio=AudioResult(
                audio_array=audio_array,
                sample_rate=sample_rate,
                format="wav",
                duration_seconds=duration,
            ),
            platform="musicgen",
            status="complete",
            metadata={"model": self._model_name, "temperature": temperature},
        )

    def _generate_transformers(
        self, prompt, *, duration, temperature, top_k, top_p, guidance
    ) -> Song:
        import torch

        inputs = self._processor(text=[prompt], padding=True, return_tensors="pt")
        # MusicGen generates ~50 tokens per second of audio at 32kHz
        max_new_tokens = int(duration * 50)

        with torch.no_grad():
            audio_values = self._model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=True,
                top_k=top_k,
                top_p=top_p if top_p > 0 else None,
                guidance_scale=guidance,
            )

        audio_array = audio_values[0, 0].cpu().numpy()
        sample_rate = self._model.config.audio_encoder.sampling_rate

        return Song(
            audio=AudioResult(
                audio_array=audio_array,
                sample_rate=sample_rate,
                format="wav",
                duration_seconds=duration,
            ),
            platform="musicgen",
            status="complete",
            metadata={"model": self._model_name, "temperature": temperature},
        )
