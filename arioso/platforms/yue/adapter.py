"""YuE adapter supporting fal.ai REST API and local CLI backends."""

import os
import warnings

from arioso.base import AudioResult, Song


def _duration_to_segments(duration: float) -> int:
    """Convert a duration in seconds to an approximate number of YuE segments.

    Each segment is roughly 30 seconds of audio.
    """
    return max(1, int(round(duration / 30)))


class Adapter:
    """YuE adapter with dual backend support.

    Prefers the fal.ai hosted API when ``FAL_KEY`` is set.  Falls back to
    local subprocess invocation of ``infer.py`` otherwise.
    """

    def __init__(self, config: dict):
        self.config = config
        self._backend = None

    def _resolve_backend(self):
        """Determine which backend to use."""
        if self._backend is not None:
            return self._backend
        if os.environ.get("FAL_KEY"):
            self._backend = "fal"
        else:
            self._backend = "local"
        return self._backend

    def generate(
        self,
        prompt: str,
        *,
        lyrics: str = "",
        duration: float = 30.0,
        model: str = "m-a-p/YuE-s1-7B-anneal-en-cot",
        batch_size: int = 4,
        max_tokens: int = 3000,
        repetition_penalty: float = 1.1,
        audio_input: str = "",
        **kwargs,
    ) -> Song:
        """Generate music from genre description and lyrics.

        Args:
            prompt: Genre/style description (mapped to ``genre_txt``).
            lyrics: Lyrics text (mapped to ``lyrics_txt``).
            duration: Desired length in seconds (converted to segments).
            model: Stage-1 model identifier.
            batch_size: Stage-2 batch size.
            max_tokens: Maximum new tokens for generation.
            repetition_penalty: Token repetition penalty.
            audio_input: Path to a vocal track prompt file, if any.

        Returns:
            A Song with audio_url or audio_bytes populated.
        """
        backend = self._resolve_backend()
        if backend == "fal":
            return self._generate_fal(
                prompt,
                lyrics=lyrics,
                duration=duration,
                model=model,
                batch_size=batch_size,
                max_tokens=max_tokens,
                repetition_penalty=repetition_penalty,
                audio_input=audio_input,
            )
        return self._generate_local(
            prompt,
            lyrics=lyrics,
            duration=duration,
            model=model,
            batch_size=batch_size,
            max_tokens=max_tokens,
            repetition_penalty=repetition_penalty,
            audio_input=audio_input,
        )

    # ------------------------------------------------------------------
    # fal.ai backend
    # ------------------------------------------------------------------

    def _generate_fal(
        self,
        prompt,
        *,
        lyrics,
        duration,
        model,
        batch_size,
        max_tokens,
        repetition_penalty,
        audio_input,
    ) -> Song:
        try:
            import fal_client
        except ImportError as exc:
            raise ImportError(
                "The fal_client package is required for the fal.ai backend. "
                "Install it with: pip install fal-client"
            ) from exc

        arguments = {
            "genre_txt": prompt,
            "lyrics_txt": lyrics,
            "run_n_segments": _duration_to_segments(duration),
            "stage1_model": model,
            "stage2_batch_size": batch_size,
            "max_new_tokens": max_tokens,
            "repetition_penalty": repetition_penalty,
        }
        if audio_input:
            arguments["vocal_track_prompt_path"] = audio_input

        result = fal_client.subscribe("fal-ai/yue", arguments=arguments)

        audio_url = ""
        audio_bytes = None
        if isinstance(result, dict):
            audio_url = result.get("audio_url", result.get("url", ""))
            if not audio_url:
                # Some fal responses nest the URL
                output = result.get("output", {})
                if isinstance(output, dict):
                    audio_url = output.get("url", "")

        return Song(
            audio=AudioResult(
                audio_url=audio_url,
                audio_bytes=audio_bytes,
                format="wav",
            ),
            platform="yue",
            status="complete",
            metadata={
                "backend": "fal",
                "model": model,
                "segments": _duration_to_segments(duration),
            },
        )

    # ------------------------------------------------------------------
    # Local CLI backend (subprocess)
    # ------------------------------------------------------------------

    def _generate_local(
        self,
        prompt,
        *,
        lyrics,
        duration,
        model,
        batch_size,
        max_tokens,
        repetition_penalty,
        audio_input,
    ) -> Song:
        import subprocess
        import tempfile

        segments = _duration_to_segments(duration)

        # Write genre and lyrics to temporary files for the CLI
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as genre_f:
            genre_f.write(prompt)
            genre_path = genre_f.name

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as lyrics_f:
            lyrics_f.write(lyrics)
            lyrics_path = lyrics_f.name

        output_dir = tempfile.mkdtemp(prefix="yue_output_")

        cmd = [
            "python",
            "infer.py",
            "--genre_txt", genre_path,
            "--lyrics_txt", lyrics_path,
            "--run_n_segments", str(segments),
            "--stage1_model", model,
            "--stage2_batch_size", str(batch_size),
            "--max_new_tokens", str(max_tokens),
            "--repetition_penalty", str(repetition_penalty),
            "--output_dir", output_dir,
        ]
        if audio_input:
            cmd.extend(["--vocal_track_prompt_path", audio_input])

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Local YuE inference requires the infer.py script from the "
                "YuE repository to be available on PATH. See: "
                "https://github.com/multimodal-art-projection/YuE"
            ) from exc

        # Find the generated audio file
        audio_bytes = None
        for fname in os.listdir(output_dir):
            if fname.endswith(".wav"):
                with open(os.path.join(output_dir, fname), "rb") as f:
                    audio_bytes = f.read()
                break

        if audio_bytes is None:
            warnings.warn(
                "No .wav file found in YuE output directory; "
                "generation may have failed."
            )

        return Song(
            audio=AudioResult(
                audio_bytes=audio_bytes,
                format="wav",
            ),
            platform="yue",
            status="complete" if audio_bytes else "error",
            metadata={
                "backend": "local",
                "model": model,
                "segments": segments,
                "output_dir": output_dir,
            },
        )
