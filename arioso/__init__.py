"""Arioso - Tools for programmatic song generation.

Arioso aggregates multiple music generation backends behind a unified interface.

Quick start (Suno via commercial proxy)::

    from arioso.suno import SunoProxyClient
    client = SunoProxyClient()
    songs = client.generate("upbeat summer pop")
    songs = client.wait_for_songs(songs)

Quick start (Suno via browser cookie)::

    from arioso.suno import SunoCookieClient
    client = SunoCookieClient()
    songs = client.generate("melancholic jazz ballad")
    songs = client.wait_for_songs(songs)
"""

from arioso.base import Song, MusicGenerator
