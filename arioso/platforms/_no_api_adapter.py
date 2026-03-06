"""Shared adapter for platforms with no public API."""

from arioso.base import Song


class NoApiAdapter:
    """Adapter for platforms that have no programmatic access.

    Raises NotImplementedError with guidance on how to use the platform
    via its native interface.
    """

    def __init__(self, config: dict):
        self.config = config
        self.name = config.get("display_name", config.get("name", "Unknown"))
        self.website = config.get("website", "")
        self.notes = config.get("notes", "")

    def generate(self, prompt: str, **kwargs) -> Song:
        msg = f"{self.name} has no public API for programmatic generation."
        if self.website:
            msg += f" Use via: {self.website}"
        if self.notes:
            msg += f"\n{self.notes}"
        raise NotImplementedError(msg)
