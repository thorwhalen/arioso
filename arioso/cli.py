"""The functions behind the ``arioso`` command line.

Plain functions with no CLI library in sight: :mod:`arioso.__main__` projects
:data:`commands` onto a parser with ``cw``. Each returns what the command prints.
"""

from __future__ import annotations


def generate(
    prompt: str,
    *,
    platform: str = "musicgen",
    duration: float = 10.0,
    output: str = "out.wav",
    model: str = None,
    seed: int = None,
) -> str:
    """Generate music from a text prompt and write it to a file.

    Args:
        prompt: Text description of the music.
        platform: The platform to generate with (see ``arioso platforms``).
        duration: Length in seconds.
        output: Where to write the audio. A waveform is written as WAV; encoded
            audio from a hosted platform keeps its own format, and the suffix
            follows it.
        model: The platform's model or checkpoint, when it offers a choice.
        seed: Random seed, on platforms that take one.

    Returns:
        The path written.
    """
    import arioso
    from arioso._audio import save_song

    kwargs = {"duration": duration}
    if model is not None:
        kwargs["model"] = model
    if seed is not None:
        kwargs["seed"] = seed
    song = arioso.generate(prompt, platform=platform, **kwargs)
    return str(save_song(song, output))


def platforms() -> list[str]:
    """List the platforms with their access type, weights licence and commercial use.

    Returns:
        The table's lines, a header first.
    """
    from arioso import PLATFORM_TABLE_FIELDS, platform_table

    rows = [PLATFORM_TABLE_FIELDS] + [
        tuple(str(row[f]) for f in PLATFORM_TABLE_FIELDS) for row in platform_table()
    ]
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    return [
        "  ".join(cell.ljust(w) for cell, w in zip(row, widths)).rstrip()
        for row in rows
    ]


#: The commands of the ``arioso`` command line (the SSOT its parser is built from).
commands = {"generate": generate, "platforms": platforms}
