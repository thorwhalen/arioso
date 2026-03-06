"""Suno adapter via sunoapi.org REST API."""

from arioso.base import AudioResult, Song
from arioso.platforms._base_adapter import BaseRestAdapter


class Adapter(BaseRestAdapter):
    """Adapter for Suno music generation via sunoapi.org.

    Handles the distinction between simple generation (prompt only)
    and custom generation (with lyrics).
    """

    def generate(
        self,
        prompt: str,
        *,
        genre: str = "",
        lyrics: str = "",
        title: str = "",
        instrumental: bool = False,
        model: str = "v3.5",
        wait_for_completion: bool = True,
        continue_from: str = "",
        continue_at: float = 0,
        **kwargs,
    ) -> list[Song]:
        """Generate music via sunoapi.org.

        Args:
            prompt: Text description of desired music.
            genre: Genre/style tags.
            lyrics: Custom lyrics (triggers custom_generate endpoint).
            title: Song title.
            instrumental: If True, generate without vocals.
            model: Suno model version.
            wait_for_completion: Block until audio is ready.
            continue_from: Clip ID to extend from.
            continue_at: Timestamp in seconds to continue from.

        Returns:
            List of Song objects (Suno typically returns 2 per call).
        """
        if lyrics:
            endpoint = "/api/v1/custom_generate"
            payload = {
                "prompt": lyrics,
                "tags": genre or prompt,
                "title": title,
                "make_instrumental": instrumental,
                "model_version": model,
                "wait_audio": wait_for_completion,
            }
        else:
            endpoint = "/api/v1/generate"
            payload = {
                "prompt": prompt,
                "make_instrumental": instrumental,
                "model_version": model,
                "wait_audio": wait_for_completion,
            }
            if genre:
                payload["tags"] = genre
            if title:
                payload["title"] = title

        if continue_from:
            payload["continue_clip_id"] = continue_from
            if continue_at:
                payload["continue_at"] = continue_at

        response = self.session.post(f"{self.base_url}{endpoint}", json=payload)
        response.raise_for_status()
        data = response.json()

        songs = []
        items = data if isinstance(data, list) else [data]
        for item in items:
            songs.append(
                Song(
                    id=item.get("id", ""),
                    title=item.get("title", title),
                    audio=AudioResult(
                        audio_url=item.get("audio_url", ""),
                        format="mp3",
                    ),
                    platform="sunoapi",
                    status="complete" if item.get("audio_url") else "pending",
                    metadata=item,
                )
            )
        return songs
