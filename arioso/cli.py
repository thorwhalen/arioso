"""The functions behind the ``arioso`` command line.

Plain functions with no CLI library in sight: :mod:`arioso.__main__` projects
:data:`commands` onto a parser with ``cw``. Each returns what the command prints.
"""

from __future__ import annotations


def generate(
    prompt: str,
    *,
    platform: str = "musicgen",
    duration: float = None,
    output: str = "out.wav",
    model: str = None,
    seed: int = None,
) -> str:
    """Generate music from a text prompt and write it to a file.

    Args:
        prompt: Text description of the music.
        platform: The platform to generate with (see ``arioso platforms``).
        duration: Length in seconds (default: the platform's own).
        output: Where to write the audio. A waveform is written as WAV and
            encoded audio from a hosted platform keeps its own format; either
            way the suffix follows the format.
        model: The platform's model or checkpoint, when it offers a choice.
        seed: Random seed, on platforms that take one.

    Returns:
        The path written.
    """
    import arioso
    from arioso._audio import save_song

    if platform not in arioso.list_platforms():
        raise ValueError(
            f"Unknown platform {platform!r}. See `arioso platforms` for the list."
        )
    given = {"duration": duration, "model": model, "seed": seed}
    kwargs = {k: v for k, v in given.items() if v is not None}
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


def compare(
    contenders: str,
    *,
    prompts: str = None,
    duration: float = 10.0,
    seed: int = 0,
    out_dir: str = "arioso_compare",
    warmup: float = 2.0,
    allow_hosted: bool = False,
    min_free_gb: float = None,
    timeout: float = None,
    preload: str = None,
    no_page: bool = False,
) -> list[str]:
    """Render the same prompts with several platforms; time, measure and check each take.

    Each contender runs in its own process, one after the other, with one progress line per
    take on stderr. Takes go to ``<out_dir>/<run>/<contender>/``, one JSON line per take to
    ``<out_dir>/results.jsonl``.

    Args:
        contenders: Comma-separated platforms, each optionally with options:
            ``stable_audio_3,magenta_rt,ace_step:runtime=local``.
        prompts: A JSON file holding a list of prompts (``text``, and optionally ``id``,
            ``bpm``, ``key``, ``melody``, ``duration``); default: three built-in prompts.
        duration: Seconds asked of each take.
        seed: Random seed, on platforms that take one.
        out_dir: Where takes, records and the page go.
        warmup: Seconds generated once per contender before the timed takes (0: none).
        allow_hosted: Allow platforms that call a paid hosted service.
        min_free_gb: Skip a contender when less memory than this is available.
        timeout: Seconds a contender may run before it is killed (with its workers).
        preload: Comma-separated modules (``module`` or ``module:function``) that
            register third-party platforms.
        no_page: Do not write ``<out_dir>/<run>/index.html`` (a page of players).

    Returns:
        A summary table, one line per contender, then the paths written.

    Raises:
        ValueError: When every take failed (the command exits 1).
    """
    import sys
    from pathlib import Path

    from arioso import compare as ac

    prompt_list = ac.load_prompts(prompts)
    records = []
    for rec in ac.compare(
        contenders,
        prompt_list,
        duration=duration,
        seed=seed,
        out_dir=out_dir,
        warmup=warmup or None,
        allow_hosted=allow_hosted,
        min_free_gb=min_free_gb,
        timeout=timeout,
        preload=[m for m in (preload or "").split(",") if m.strip()],
    ):
        records.append(rec)
        status = rec.get("error") or f"{rec.get('gen_s')} s, RTF {rec.get('rtf')}"
        print(
            f"{rec['contender']} {rec['prompt']}: {status}", file=sys.stderr, flush=True
        )
    if records and all("error" in r for r in records):
        raise ValueError(
            "every take failed:\n" + "\n".join(ac.summary_lines(records)[1:])
        )
    lines = ac.summary_lines(records) + [str(Path(out_dir) / ac.RESULTS_FILE)]
    if not no_page and records:
        run_dir = Path(out_dir) / records[0]["run_id"]
        lines.append(
            str(ac.compare_page(records, run_dir / "index.html", prompts=prompt_list))
        )
    return lines


def schema(platform: str, *, indent: int = 2) -> str:
    """Print the JSON Schema of the parameters a platform accepts.

    Common parameters (shared names across platforms) are marked
    ``"x-arioso": {"group": "common"}``; the platform's own extras ``"extra"``.
    A web form, an agent tool or a validator can be generated from it.

    Args:
        platform: The platform (see ``arioso platforms``).
        indent: JSON indentation (0: one line).

    Returns:
        The schema as JSON.
    """
    import json

    import arioso
    from arioso.schema import param_schema

    if platform not in arioso.list_platforms():
        raise ValueError(
            f"Unknown platform {platform!r}. See `arioso platforms` for the list."
        )
    return json.dumps(param_schema(platform), indent=indent or None)


#: The commands of the ``arioso`` command line (the SSOT its parser is built from).
commands = {
    "generate": generate,
    "platforms": platforms,
    "compare": compare,
    "schema": schema,
}
