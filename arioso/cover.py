"""Cover every song in a folder: lyrics, one cover call per song, every take saved, resumable.

:func:`cover_folder` is the loop around one-song ``generate(audio_input=...)`` that a folder
job needs. Per source file it:

1. skips the song when the folder's manifest already records it as done or refused;
2. transcribes its lyrics (``transcribe``, default :func:`vocal_lyrics`: the vocal stem
   from ``denote.separate``, transcribed by ``scribed``), so the cover keeps the words;
   no words heard means an instrumental cover;
3. reuses a cover task already submitted for that song (``find_task``; for sunoapi, its
   ``SunoTasks`` store), so a crash or a re-run never pays twice, or submits one;
4. waits for it, saves every take as ``<stem> (<platform> N).<ext>`` in ``dst``;
5. appends one record per song to ``dst/<manifest>`` (JSON lines): done, refused (a
   :class:`~arioso.base.CatalogMatchError`, final) or error (retried on the next run).

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
from pathlib import Path
from typing import Callable, Iterable, Optional, Union

from arioso.base import CatalogMatchError, Song

#: The audio files :func:`cover_folder` picks up from the source folder.
AUDIO_EXTENSIONS = (".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".aiff", ".aif")
#: The manifest's file name, inside the target folder.
DFLT_MANIFEST = "covers.jsonl"
#: Outcomes that end a song's job; any other (an error) is tried again on the next run.
FINAL_OUTCOMES = ("done", "refused")
#: How much the source shapes the cover (upload-cover's ``audioWeight``), as in #69's run.
DFLT_STRENGTH = 0.9
#: Waiting for a hosted cover: seconds between status checks, and the most to wait.
DFLT_POLL_INTERVAL, DFLT_TIMEOUT = 15.0, 1200.0
#: Task-store statuses that mean the task failed (it is resubmitted, not reused).
_FAILED_STATUS_WORDS = ("FAIL", "ERROR")


def vocal_lyrics(path, *, separate=None, transcribe=None, **transcribe_kwargs) -> str:
    """The words sung in ``path``: its vocal stem (``denote.separate``), transcribed.

    One line per transcript segment; ``""`` when no words are heard. ``separate`` and
    ``transcribe`` default to ``denote.separate`` and ``scribed.transcribe`` (both
    imported only here); ``transcribe_kwargs`` go to the transcriber (``backend``,
    ``model``, ``language``, ...).
    """
    import tempfile

    import librosa
    import soundfile as sf

    if separate is None:
        from denote import separate
    if transcribe is None:
        from scribed import transcribe
    audio, rate = librosa.load(str(path), sr=None, mono=False)
    stems = separate(audio, sr=rate)
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "vocals.wav"
        sf.write(wav, _frames_last(stems.vocals).T, stems.sr)
        segments = transcribe(str(wav), **transcribe_kwargs)
        lines = [s.text.strip() for s in segments if s.text.strip()]
    return "\n".join(lines)


def _frames_last(audio):
    """``audio`` as ``(channels, frames)``, from mono or either orientation."""
    import numpy as np

    audio = np.asarray(audio)
    if audio.ndim == 1:
        return audio[None, :]
    return audio if audio.shape[0] <= audio.shape[1] else audio.T


def find_suno_task(title: str, *, platform: str = "sunoapi") -> Optional[str]:
    """The id of an upload-cover task already submitted for ``title``, not failed.

    Looks in the platform adapter's task store (sunoapi's ``SunoTasks``); ``None`` for
    a platform that keeps none.
    """
    from arioso.registry import get_platform

    tasks = getattr(get_platform(platform)["adapter"], "tasks", None)
    if tasks is None:
        return None
    for task_id in tasks:
        rec = tasks[task_id]
        status = str(rec.get("status", "")).upper()
        if (
            rec.get("operation") == "upload_cover"
            and rec.get("request_params", {}).get("title") == title
            and not any(w in status for w in _FAILED_STATUS_WORDS)
        ):
            return task_id
    return None


def wait_for_songs(
    songs: list,
    *,
    poll_interval: float = DFLT_POLL_INTERVAL,
    timeout: float = DFLT_TIMEOUT,
    check: Callable = None,
) -> list:
    """``songs`` once all complete: polled with ``check`` (default ``arioso.check_status``).

    Songs already complete (a local platform) come back as they are. Raises
    ``TimeoutError`` past ``timeout``, and ``RuntimeError`` on a song in error.
    """
    if check is None:
        from arioso import check_status as check
    start = time.monotonic()
    while True:
        errors = [s for s in songs if s.is_error]
        if errors:
            raise RuntimeError(f"cover failed: {errors[0].error_message}")
        if songs and all(s.status == "complete" for s in songs):
            return songs
        if time.monotonic() - start > timeout:
            raise TimeoutError(f"cover {songs[0].id!r} not complete after {timeout:g} s")
        time.sleep(poll_interval)
        songs = check(songs[0])


def save_takes(songs: list, folder, stem: str, *, platform: str) -> list:
    """Write each take as ``<stem> (<platform> N).<ext>``; returns their file names."""
    from arioso._audio import save_song

    base = Path(folder)
    # a dummy suffix: save_song puts the take's own format's suffix in its place
    return [
        save_song(song, base / f"{stem} ({platform} {i}).audio").name
        for i, song in enumerate(songs, 1)
    ]


def read_manifest(path) -> dict:
    """The last record of each song in a manifest (JSON lines), by source file name."""
    path = Path(path)
    if not path.is_file():
        return {}
    records = (json.loads(l) for l in path.read_text().splitlines() if l.strip())
    return {r["source"]: r for r in records}


def cover_folder(
    src,
    dst,
    *,
    platform: str = "sunoapi",
    audio_input_strength: float = DFLT_STRENGTH,
    transcribe: Optional[Callable] = vocal_lyrics,
    style: Union[str, Callable, None] = None,
    only: Optional[Iterable[str]] = None,
    generate: Callable = None,
    find_task: Optional[Callable] = None,
    wait: Callable = wait_for_songs,
    manifest: str = DFLT_MANIFEST,
    extensions: Iterable[str] = AUDIO_EXTENSIONS,
    **generate_kwargs,
) -> list:
    """Cover every audio file in ``src`` with ``platform``, takes saved in ``dst``.

    Returns the records written this run (one per song attempted; songs the manifest
    already holds as done or refused are skipped). See the module docstring for the
    steps.

    Args:
        src: The folder of source songs (files with one of ``extensions``).
        dst: The folder for the takes and the manifest (created if missing).
        platform: An arioso platform that takes ``audio_input``.
        audio_input_strength: How much the source shapes the cover, 0-1.
        transcribe: ``(path) -> lyrics``; ``""`` makes the cover instrumental. ``None``
            sends no lyrics (the platform hears the source as it is).
        style: The style for every song, or ``(path) -> style``; ``None`` sends none.
        only: Source stems to cover (default every file).
        generate: ``(prompt, **kwargs) -> list[Song]``; default ``arioso.generate_many``.
        find_task: ``(title) -> task id or None``, a cover already submitted for the
            song; default :func:`find_suno_task` for sunoapi, none otherwise.
        wait: ``(songs) -> songs``, all complete.
        manifest: The manifest's name in ``dst``.
        **generate_kwargs: Passed to every cover call (``model``, ``vocal_gender``, ...).
    """
    src, dst = Path(src), Path(dst)
    dst.mkdir(parents=True, exist_ok=True)
    if generate is None:
        from functools import partial

        import arioso

        generate = partial(arioso.generate_many, platform=platform)
    if find_task is None and platform == "sunoapi":
        find_task = find_suno_task
    exts = {e.lower() for e in extensions}
    only = set(only) if only is not None else None
    ledger = dst / manifest
    done = {
        k for k, r in read_manifest(ledger).items() if r["outcome"] in FINAL_OUTCOMES
    }
    files = sorted(
        f
        for f in src.iterdir()
        if f.suffix.lower() in exts and not f.name.startswith(".")
    )
    records = []
    for f in files:
        if f.name in done or (only is not None and f.stem not in only):
            continue
        rec = {"source": f.name, "platform": platform, "strength": audio_input_strength}
        try:
            rec.update(
                _cover_one(
                    f,
                    dst,
                    platform=platform,
                    strength=audio_input_strength,
                    transcribe=transcribe,
                    style=style(f) if callable(style) else style,
                    generate=generate,
                    find_task=find_task,
                    wait=wait,
                    **generate_kwargs,
                )
            )
        except CatalogMatchError as e:  # a policy refusal: final, never retried
            rec.update(outcome="refused", error=str(e), task_id=e.task_id)
        except Exception as e:  # keep going; the next run retries (no double pay)
            rec.update(outcome="error", error=f"{type(e).__name__}: {e}")
        with ledger.open("a") as fp:
            fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
        records.append(rec)
    return records


def _cover_one(
    path, dst, *, platform, strength, transcribe, style, generate, find_task, wait, **kw
) -> dict:
    title = path.stem
    lyrics = transcribe(path) if transcribe is not None else None
    instrumental = lyrics == ""
    task_id = find_task(title) if find_task is not None else None
    reused = task_id is not None
    if reused:
        songs = [Song(id=task_id, platform=platform, status="pending")]
    else:
        params = dict(audio_input=str(path), audio_input_strength=strength, title=title)
        if style:
            params["genre"] = style
        if lyrics:
            params["lyrics"] = lyrics
        if instrumental:
            params["instrumental"] = True
        songs = generate(style or "", **params, **kw)
        task_id = songs[0].id if songs else None
    songs = wait(songs)
    takes = save_takes(songs, dst, title, platform=platform)
    return {
        "outcome": "done",
        "task_id": task_id,
        "reused_task": reused,
        "instrumental": instrumental,
        "style": style,
        "lyrics": lyrics,
        "takes": takes,
    }
