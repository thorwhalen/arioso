"""Is a take a cover of its source? Lyric recall when there are words, melody rank otherwise.

Measured on the 2026-11-10 folder job (arioso#69, #81): six Suno upload-cover takes of three
home-recorded children's songs, scored against those three sources and three unrelated songs
by the same family. :func:`arioso.analysis.melody_match` alone cannot answer "is this take a
cover of that song": a take's score against its own source (0.57 to 0.71 on the mix) sits
inside the range of its scores against unrelated songs (up to 0.66), so no fixed threshold
separates them. Two signals did:

- **lyric recall** (the source's words found, in order, in the take's words): 0.60 to 0.94
  against the true source, at most 0.15 against any other, for every take with words;
- **melody rank**: for the instrumental takes, the true source had the highest
  ``melody_match`` of all six songs on the mix (by 0.05 to 0.11), though not in absolute terms.

So :func:`cover_closeness` reports both and gives a verdict from the one that applies: the
words when the source and the take both have them, else the melody's rank among
``references`` (other songs: the rest of the folder serves), else no verdict ("unclear").

>>> lyric_recall("stinky poo where are you", "oh stinky poo stinky poo where are you now")
1.0
>>> lyric_recall("stinky poo where are you", "climbing up the mountain")
0.0
>>> lyric_recall("", "anything") is None
True
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Callable, Iterable, Optional, Union

#: The fewest words a side must have for its lyric recall to count.
MIN_WORDS = 12
#: Lyric recall at or above this: the take sings the source's words (true pairs measured 0.60-0.94).
LYRIC_COVER = 0.4
#: Lyric recall at or below this, with words on both sides: not the source's song (others measured <= 0.15).
LYRIC_UNRELATED = 0.25
#: The rate audio is read at for the melody comparison.
DFLT_SR = 22050
#: ``transcribe``'s default: :func:`arioso.cover.vocal_lyrics`.
AUTO = "auto"

_WORD = re.compile(r"[^\W_]+(?:'[^\W_]+)*")


def words(text: str) -> list:
    """The words of ``text``, lowercased.

    >>> words("Stinky poo, where ARE you? Don't go!")
    ['stinky', 'poo', 'where', 'are', 'you', "don't", 'go']
    """
    return _WORD.findall((text or "").lower())


def lyric_recall(source_text: str, take_text: str) -> Optional[float]:
    """The share of the source's words the take sings, in order (``None`` when the source has none)."""
    ref, hyp = words(source_text), words(take_text)
    if not ref:
        return None
    blocks = difflib.SequenceMatcher(
        None, ref, hyp, autojunk=False
    ).get_matching_blocks()
    return round(sum(b.size for b in blocks) / len(ref), 3)


def _verdict(
    recall, take_words: int, source_words: int, rank, of: int, *, min_words: int
) -> tuple:
    """``(verdict, why)`` for one take: "cover", "not a cover" or "unclear"."""
    if source_words >= min_words and take_words >= min_words and recall is not None:
        if recall >= LYRIC_COVER:
            return "cover", f"it sings {recall:.0%} of the source's words"
        if recall <= LYRIC_UNRELATED:
            return "not a cover", f"it sings only {recall:.0%} of the source's words"
    if rank is not None:
        if rank == 1:
            return "cover", f"its melody is closest to the source's, of {of} songs"
        return "not a cover", f"{rank - 1} of {of - 1} other songs are closer in melody"
    return (
        "unclear",
        "no words to compare, and no other songs to rank the melody against",
    )


def cover_closeness(
    source,
    takes: Iterable,
    *,
    references: Iterable = (),
    transcribe: Union[Callable, str, None] = AUTO,
    source_text: Optional[str] = None,
    melody: Optional[Callable] = None,
    load: Optional[Callable] = None,
    min_words: int = MIN_WORDS,
) -> dict:
    """How close each take is to ``source``, and whether it is a cover of it.

    Matches ``cover_folder``'s ``assess`` keyword: ``(source_path, take_paths) -> dict``;
    give it references with ``functools.partial(cover_closeness, references=[...])``.

    Args:
        source: The source song's audio file.
        takes: The takes' audio files.
        references: Other songs' audio files, for the melody's rank (the source itself, if
            listed, is skipped). Without them a take with no words gets no verdict.
        transcribe: ``(path) -> text``; the default is :func:`arioso.cover.vocal_lyrics`
            (the vocal stem, transcribed: ``pip install arioso[cover]``); ``None`` skips
            the words.
        source_text: The source's words, when already known (it is then not transcribed).
        melody: ``(take, source, sr) -> float``, default :func:`arioso.analysis.melody_match`.
        load: ``(path) -> mono array`` at ``DFLT_SR``; default ``librosa.load``.
        min_words: The fewest words each side needs for the words to decide.

    Returns:
        ``{"source": name, "source_words": n, "references": [names], "takes": {name:
        {"lyric_recall", "take_words", "melody", "melody_rank", "verdict", "why"}}}``.
    """
    if transcribe == AUTO:
        from arioso.cover import vocal_lyrics as transcribe
    if melody is None:
        from arioso.analysis import melody_match as melody
    if load is None:

        def load(path):
            import librosa

            return librosa.load(str(path), sr=DFLT_SR, mono=True)[0]

    source = Path(source)
    others = [Path(r) for r in references if Path(r).resolve() != source.resolve()]
    if source_text is None and transcribe is not None:
        source_text = transcribe(source)
    n_source = len(words(source_text or ""))
    source_audio = load(source)
    other_audio = [load(r) for r in others]
    out = {}
    for take in map(Path, takes):
        take_text = transcribe(take) if transcribe is not None else ""
        recall = lyric_recall(source_text or "", take_text) if n_source else None
        audio = load(take)
        own = round(float(melody(audio, source_audio, DFLT_SR)), 3)
        rank = None
        if others:
            scores = [float(melody(audio, a, DFLT_SR)) for a in other_audio]
            rank = 1 + sum(s > own for s in scores)
        n_take = len(words(take_text))
        verdict, why = _verdict(
            recall, n_take, n_source, rank, len(others) + 1, min_words=min_words
        )
        out[take.name] = {
            "lyric_recall": recall,
            "take_words": n_take,
            "melody": own,
            "melody_rank": rank,
            "verdict": verdict,
            "why": why,
        }
    return {
        "source": source.name,
        "source_words": n_source,
        "references": [r.name for r in others],
        "takes": out,
    }
