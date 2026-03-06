"""Base types and protocols for music generation backends."""

from typing import Protocol, runtime_checkable, Any, Optional, Sequence
from dataclasses import dataclass, field


@dataclass
class Song:
    """A generated song with its metadata and audio data.

    Attributes:
        id: Provider-specific identifier for the song.
        title: Song title (may be auto-generated).
        audio_url: URL to download the audio file.
        audio_bytes: Raw audio bytes (populated after download).
        status: Generation status (submitted, queued, streaming, complete).
        metadata: Provider-specific metadata dict.
    """

    id: str
    title: str = ""
    audio_url: str = ""
    audio_bytes: Optional[bytes] = field(default=None, repr=False)
    status: str = "pending"
    metadata: dict = field(default_factory=dict)


@runtime_checkable
class MusicGenerator(Protocol):
    """Protocol that all music generation backends must implement.

    This is the contract that consumer code depends on. Adding a new backend
    means writing a class that satisfies this protocol.
    """

    def generate(
        self,
        prompt: str,
        *,
        style: str = "",
        title: str = "",
        lyrics: str = "",
        instrumental: bool = False,
        **kwargs: Any,
    ) -> list[Song]:
        """Generate songs from a text prompt.

        Args:
            prompt: Natural language description of the desired song.
            style: Genre/style tags (e.g. "upbeat pop, female vocals").
            title: Desired song title.
            lyrics: Explicit lyrics with structural tags ([Verse], [Chorus], etc.).
            instrumental: If True, generate without vocals.
            **kwargs: Provider-specific parameters.

        Returns:
            A list of Song objects (most providers return 2 per call).
        """
        ...

    def get_song(self, song_id: str) -> Song:
        """Retrieve a song by its provider-specific ID.

        Args:
            song_id: The ID returned from a generate() call.

        Returns:
            A Song object with current status and metadata.
        """
        ...

    def wait_for_songs(
        self,
        songs: Sequence[Song],
        *,
        timeout: float = 300,
        poll_interval: float = 5,
    ) -> list[Song]:
        """Poll until all songs reach 'complete' status or timeout.

        Args:
            songs: Songs to wait for.
            timeout: Max seconds to wait.
            poll_interval: Seconds between status checks.

        Returns:
            Updated list of Song objects.
        """
        ...
