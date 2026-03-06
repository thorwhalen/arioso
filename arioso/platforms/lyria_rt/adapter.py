"""Google Lyria RealTime adapter using the google-genai SDK."""

import asyncio
import os

from arioso.base import AudioResult, Song


class Adapter:
    """Lyria RealTime adapter using streaming music sessions.

    Creates a live music session via the ``google-genai`` SDK, sends a
    prompt, collects PCM audio chunks for a configurable duration, and
    returns them as a single ``Song``.
    """

    def __init__(self, config: dict):
        self.config = config

    def _make_client(self):
        """Create a google-genai Client, raising a clear error if missing."""
        try:
            from google import genai
        except ImportError:
            raise ImportError(
                "The 'google-genai' package is required for the Lyria RealTime "
                "adapter. Install it with:  pip install google-genai"
            )
        api_key = os.environ.get(
            self.config.get("auth", {}).get("env_var", "GOOGLE_API_KEY"), ""
        )
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY environment variable is not set. "
                "Obtain one at https://aistudio.google.com/apikey"
            )
        return genai.Client(api_key=api_key)

    def generate(
        self,
        prompt: str,
        *,
        duration: float = 10.0,
        bpm: int = None,
        key: str = None,
        energy: float = None,
        brightness: float = None,
        guidance: float = 4.0,
        temperature: float = 1.1,
        top_k: int = 40,
        seed: int = None,
        prompt_weight: float = None,
        **kwargs,
    ) -> Song:
        """Generate music using a Lyria RealTime streaming session.

        Args:
            prompt: Text description of desired music.
            duration: Seconds of audio to collect from the stream.
            bpm: Beats per minute (60-200).
            key: Musical scale (e.g. ``"C_MAJOR"``).
            energy: Density / energy level (0-1).
            brightness: Spectral brightness (0-1).
            guidance: Guidance strength (0-6).
            temperature: Sampling temperature (0-3).
            top_k: Top-k sampling (1-1000).
            seed: Random seed for reproducibility (0-2.1B).
            prompt_weight: Weight applied to the WeightedPrompt.

        Returns:
            A Song with PCM audio bytes at 48 kHz.
        """
        pcm_data = asyncio.run(
            self._agenerate(
                prompt,
                duration=duration,
                bpm=bpm,
                key=key,
                energy=energy,
                brightness=brightness,
                guidance=guidance,
                temperature=temperature,
                top_k=top_k,
                seed=seed,
                prompt_weight=prompt_weight,
            )
        )
        return Song(
            audio=AudioResult(
                audio_bytes=pcm_data,
                format="pcm",
                sample_rate=48000,
                duration_seconds=duration,
            ),
            platform="lyria_rt",
            status="complete",
            metadata={
                "guidance": guidance,
                "temperature": temperature,
                "top_k": top_k,
            },
        )

    async def _agenerate(
        self,
        prompt: str,
        *,
        duration: float,
        bpm: int,
        key: str,
        energy: float,
        brightness: float,
        guidance: float,
        temperature: float,
        top_k: int,
        seed: int,
        prompt_weight: float,
    ) -> bytes:
        """Async helper that drives the live music session."""
        from google.genai import types

        client = self._make_client()

        # Build MusicGenerationConfig
        gen_config_kwargs = {
            "guidance": guidance,
            "temperature": temperature,
            "top_k": top_k,
        }
        if bpm is not None:
            gen_config_kwargs["bpm"] = bpm
        if key is not None:
            gen_config_kwargs["scale"] = key
        if energy is not None:
            gen_config_kwargs["density"] = energy
        if brightness is not None:
            gen_config_kwargs["brightness"] = brightness
        if seed is not None:
            gen_config_kwargs["seed"] = seed

        music_gen_config = types.MusicGenerationConfig(**gen_config_kwargs)
        live_config = types.LiveMusicConfig(music_generation_config=music_gen_config)

        async with client.aio.live.music_sessions.create(
            model="models/lyria-realtime-exp",
            config=live_config,
        ) as session:
            # Build and send the weighted prompt
            weight = prompt_weight if prompt_weight is not None else 1.0
            weighted_prompt = types.WeightedPrompt(text=prompt, weight=weight)
            await session.set_weighted_prompts(prompts=[weighted_prompt])
            await session.play()

            # Collect PCM chunks for the requested duration
            chunks = []
            collected = 0.0
            bytes_per_second = 48000 * 2  # 16-bit mono PCM at 48 kHz
            target_bytes = int(duration * bytes_per_second)

            async for message in session.receive():
                if message.server_content and message.server_content.model_turn:
                    for part in message.server_content.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            chunks.append(part.inline_data.data)
                            collected += len(part.inline_data.data)
                            if collected >= target_bytes:
                                break
                if collected >= target_bytes:
                    break

        return b"".join(chunks)
