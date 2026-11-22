"""Cover every song in a folder: lyrics, one cover call per song, every take saved, resumable.

:func:`cover_folder` is the loop around one-song ``generate(audio_input=...)`` that a folder
job needs. Per source file it:

1. skips the song when the folder's manifest already records it as done or refused;
2. reuses the cover task the manifest recorded for it, when a run stopped between
   submitting and saving (so a crash or a re-run never pays twice), or else
3. transcribes its lyrics (``transcribe``, default :func:`vocal_lyrics`: the vocal stem
   from ``denote.separate``, transcribed by ``scribed``; only for a platform that takes
   lyrics), so the cover keeps the words; no words heard makes it instrumental; and
   submits one cover, recording the task id in the manifest before waiting for it;
4. waits for it and saves every take as ``<stem> (<platform> N).<ext>`` in ``dst``;
5. records the outcome in the manifest (``dst/covers.jsonl``, JSON lines, the last line
   of a song wins): ``done``, ``refused`` (a :class:`~arioso.base.CatalogMatchError`,
   final) or ``error`` (tried again on the next run: by reusing its task once, then by
   submitting anew).

>>> from arioso.base import AudioResult, Song
>>> import tempfile, pathlib
>>> src, dst = pathlib.Path(tempfile.mkdtemp()), pathlib.Path(tempfile.mkdtemp())
>>> _ = (src / "Lullaby.wav").write_bytes(b"RIFF")
>>> def fake(prompt, **kw):  # a platform that answers at once, with two takes
...     return [Song(id=f"t{i}", status="complete", platform="fake",
...                  audio=AudioResult(audio_bytes=b"ID3", format="mp3")) for i in (1, 2)]
>>> [r["outcome"] for r in cover_folder(src, dst, platform="fake", generate=fake,
...                                     transcribe=lambda p: "hush now")]
['done']
>>> sorted(p.name for p in dst.iterdir())
['Lullaby (fake 1).mp3', 'Lullaby (fake 2).mp3', 'covers.jsonl']
>>> cover_folder(src, dst, platform="fake", generate=fake, transcribe=None)  # resumed
[]
"""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Callable, Iterable, Optional, Union

from arioso.base import CatalogMatchError, Song

#: The audio files :func:`cover_folder` picks up from the source folder.
AUDIO_EXTENSIONS = (".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".aiff", ".aif")
#: The manifest's file name, inside the target folder.
DFLT_MANIFEST = "covers.jsonl"
#: Outcomes that end a song's job; ``error`` is tried again on the next run.
FINAL_OUTCOMES = ("done", "refused")
#: How much the source shapes the cover. Higher than ``tools.DFLT_AUDIO_WEIGHT`` (0.5): a
#: folder cover is meant to keep each song (the #69 run used 0.9).
DFLT_STRENGTH = 0.9
#: Waiting for a hosted cover: seconds between status checks, and the most to wait.
DFLT_POLL_INTERVAL, DFLT_TIMEOUT = 15.0, 1200.0
#: ``transcribe``'s default: :func:`vocal_lyrics` when the platform takes lyrics, else none.
AUTO = "auto"


def vocal_lyrics(path, *, separate=None, transcribe=None, **transcribe_kwargs) -> str:
    """The words sung in ``path``: its vocal stem (``denote.separate``), transcribed.

    One line per transcript segment; ``""`` when no words are heard. ``separate`` and
    ``transcribe`` default to ``denote.separate`` and ``scribed.transcribe`` (both
    imported only here; ``pip install arioso[cover]``); ``transcribe_kwargs`` go to the
    transcriber (``backend``, ``model``, ``language``, ...).
    """
    import tempfile

    import librosa

    from arioso._audio import write_wav

    if separate is None:
        from denote import separate
    if transcribe is None:
        from scribed import transcribe
    audio, rate = librosa.load(str(path), sr=None, mono=False)
    stems = separate(audio, sr=rate)
    with tempfile.TemporaryDirectory() as tmp:
        wav = write_wav(stems.vocals, stems.sr, Path(tmp) / "vocals.wav")
        segments = transcribe(str(wav), **transcribe_kwargs)
        lines = [s.text.strip() for s in segments if s.text.strip()]
    return "\n".join(lines)


def cover_params(
    path, *, lyrics: Optional[str], style: Optional[str], strength: float
) -> dict:
    """The cover call's keyword arguments for one song (unified names).

    ``lyrics=""`` (no words heard) asks for an instrumental; ``None`` sends nothing.
    """
    params = dict(
        audio_input=str(path), audio_input_strength=strength, title=Path(path).stem
    )
    if style:
        params["genre"] = style
    if lyrics:
        params["lyrics"] = lyrics
    elif lyrics == "":
        params["instrumental"] = True
    return params


def wait_for_songs(
    songs: list,
    *,
    poll_interval: float = DFLT_POLL_INTERVAL,
    timeout: float = DFLT_TIMEOUT,
    check: Callable = None,
) -> list:
    """``songs`` once all complete, polled with ``check`` (default ``arioso.check_status``).

    Songs already complete (a local platform) come back at once. Raises ``TimeoutError``
    past ``timeout``, and ``RuntimeError`` on a song in error.
    """
    if not songs:
        raise ValueError("no songs to wait for (the cover call returned none)")
    if check is None:
        from arioso import check_status as check
    start = time.monotonic()
    while True:
        errors = [s for s in songs if s.is_error]
        if errors:
            raise RuntimeError(f"cover failed: {errors[0].error_message}")
        if all(s.status == "complete" for s in songs):
            return songs
        if time.monotonic() - start > timeout:
            raise TimeoutError(
                f"cover {songs[0].id!r} not complete after {timeout:g} s"
            )
        songs = check(songs[0])
        if not all(s.status == "complete" for s in songs):
            time.sleep(poll_interval)


def save_takes(songs: list, folder, stem: str, *, platform: str) -> list:
    """Write each take as ``<stem> (<platform> N).<ext>``; returns their file names."""
    from arioso._audio import save_song

    base = Path(folder)
    # a placeholder suffix: save_song puts the take's own format's suffix in its place
    return [
        save_song(song, base / f"{stem} ({platform} {i}).audio").name
        for i, song in enumerate(songs, 1)
    ]


def read_manifest(path) -> dict:
    """The last record of each song in a manifest (JSON lines), by source file name.

    A line that does not parse (a run killed mid-write) is skipped.
    """
    path = Path(path)
    if not path.is_file():
        return {}
    last = {}
    for line in path.read_text().splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict) and "source" in rec:
            last[rec["source"]] = rec
    return last


def _reusable_task(rec: Optional[dict]) -> Optional[str]:
    """The task a song's last record says to wait for again, if any.

    A ``submitted`` record (the run stopped while waiting) and an ``error`` after a fresh
    submission are reused; an ``error`` that already came from a reused task is not (its
    task is failed or expired), so the song is submitted anew.
    """
    if not rec or not rec.get("task_id"):
        return None
    if rec["outcome"] == "submitted":
        return rec["task_id"]
    if rec["outcome"] == "error" and not rec.get("reused_task"):
        return rec["task_id"]
    return None


def _platform_params(platform: str) -> Optional[set]:
    """The parameters ``platform`` takes, or ``None`` for one arioso does not know."""
    from arioso.registry import get_config

    try:
        config = get_config(platform)
    except KeyError:
        return None
    return set(config.get("supported_affordances", ())) | set(
        config.get("adapter_params", ())
    )


def cover_folder(
    src,
    dst,
    *,
    platform: str = "sunoapi",
    audio_input_strength: float = DFLT_STRENGTH,
    transcribe: Union[Callable, str, None] = AUTO,
    style: Union[str, Callable, None] = None,
    only: Optional[Iterable[str]] = None,
    params: Callable = cover_params,
    generate: Callable = None,
    wait: Callable = wait_for_songs,
    manifest: str = DFLT_MANIFEST,
    extensions: Iterable[str] = AUDIO_EXTENSIONS,
    **generate_kwargs,
) -> list:
    """Cover every audio file in ``src`` with ``platform``, takes saved in ``dst``.

    Returns the records written this run (one per song attempted; songs the manifest
    already holds as done or refused are skipped). See the module docstring.

    Args:
        src: The folder of source songs (files with one of ``extensions``).
        dst: The folder for the takes and the manifest (created if missing).
        platform: An arioso platform that takes ``audio_input``.
        audio_input_strength: How much the source shapes the cover, 0-1.
        transcribe: ``(path) -> lyrics``; ``""`` makes the cover instrumental, ``None``
            sends no lyrics. The default uses :func:`vocal_lyrics` when ``platform``
            takes lyrics, and none otherwise.
        style: The style for every song, or ``(path) -> style``; ``None`` sends none.
        only: Source stems to cover (default every file).
        params: ``(path, *, lyrics, style, strength) -> kwargs`` for the cover call
            (default :func:`cover_params`); parameters ``platform`` does not take are
            dropped.
        generate: ``(prompt, **kwargs) -> list[Song]``; default ``arioso.generate_many``.
        wait: ``(songs) -> songs``, all complete (default :func:`wait_for_songs`).
        manifest: The manifest's name in ``dst``.
        **generate_kwargs: Passed to every cover call (``model``, ``vocal_gender``, ...).
    """
    src, dst = Path(src), Path(dst)
    exts = {e.lower() for e in extensions}
    files = sorted(
        f
        for f in src.iterdir()
        if f.suffix.lower() in exts and not f.name.startswith(".")
    )
    twins = [s for s, n in Counter(f.stem for f in files).items() if n > 1]
    if twins:  # their takes would share names
        raise ValueError(
            f"cover_folder: several files share the stems {twins} in {src}"
        )
    dst.mkdir(parents=True, exist_ok=True)
    takes_params = _platform_params(platform)
    if transcribe == AUTO:
        takes_lyrics = takes_params is None or "lyrics" in takes_params
        transcribe = vocal_lyrics if takes_lyrics else None
    if generate is None:
        from functools import partial

        from arioso import generate_many

        generate = partial(generate_many, platform=platform)
    only = set(only) if only is not None else None
    ledger = dst / manifest

    def write(rec):
        with ledger.open("a") as fp:
            fp.write(json.dumps(rec, ensure_ascii=False) + "\n")

    last = read_manifest(ledger)
    records = []
    for f in files:
        prev = last.get(f.name)
        if (prev and prev["outcome"] in FINAL_OUTCOMES) or (
            only is not None and f.stem not in only
        ):
            continue
        rec = {"source": f.name, "platform": platform}
        task_id = _reusable_task(prev)
        try:
            if task_id:
                rec.update(
                    {
                        k: prev.get(k)
                        for k in ("strength", "style", "lyrics", "instrumental")
                    }
                )
                rec.update(task_id=task_id, reused_task=True)
                songs = [Song(id=task_id, platform=platform, status="pending")]
            else:
                lyrics = transcribe(f) if transcribe is not None else None
                song_style = style(f) if callable(style) else style
                kwargs = params(
                    f, lyrics=lyrics, style=song_style, strength=audio_input_strength
                )
                if takes_params is not None:
                    kwargs = {
                        k: v
                        for k, v in kwargs.items()
                        if k in takes_params or k == "audio_input"
                    }
                rec.update(
                    strength=audio_input_strength,
                    style=song_style,
                    lyrics=lyrics,
                    instrumental=bool(kwargs.get("instrumental")),
                    reused_task=False,
                )
                songs = generate(song_style or "", **kwargs, **generate_kwargs)
                task_id = songs[0].id if songs else None
                rec["task_id"] = task_id
                write(
                    {**rec, "outcome": "submitted"}
                )  # before the wait: never pay twice
            rec.update(
                outcome="done",
                takes=save_takes(wait(songs), dst, f.stem, platform=platform),
            )
        except CatalogMatchError as e:  # a policy refusal: final, never retried
            rec.update(outcome="refused", error=str(e))
            rec["task_id"] = rec.get("task_id") or e.task_id
        except Exception as e:  # keep going; the next run retries (see _reusable_task)
            rec.update(outcome="error", error=f"{type(e).__name__}: {e}")
        write(rec)
        records.append(rec)
    return records
