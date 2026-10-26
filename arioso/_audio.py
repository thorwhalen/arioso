"""Audio-input normalization for the enhance / audio-conditioning stage, and the small pitch
and DSP primitives (``hz_to_midi``, ``varispeed``, ``highpass``, ``loop_drone``) that
:mod:`arioso.analysis` and :mod:`arioso.seeds` share.

The facade's :func:`arioso.enhance` and the audio-accepting adapters
(``stable_audio``, ``musicgen`` melody, ``udio`` …) each want the input audio in
a slightly different concrete form -- a file path, a NumPy waveform, or a torch
tensor. This module is the single ingress: :func:`to_audio_ref` accepts any of
the forms a caller is likely to have and returns an :class:`AudioRef` whose lazy
accessors produce whichever form an adapter needs.

Accepted inputs (see :func:`to_audio_ref`):

- a generated :class:`~arioso.base.Song` or :class:`~arioso.base.AudioResult`
- raw encoded audio ``bytes`` (e.g. MP3/WAV file contents)
- a filesystem path as ``str`` or :class:`pathlib.Path`
- a NumPy waveform paired with its rate as ``(array, sample_rate)``
- a bare NumPy waveform (sample rate must then be supplied out of band)

All heavy dependencies (``numpy``, ``soundfile``, ``torch``) are imported lazily,
so ``import arioso`` never requires them; a precise ``ImportError`` is raised
only if a conversion that needs one is actually requested.
"""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path
from typing import Any, Optional


def _is_ndarray(value: Any) -> bool:
    """True if *value* is a NumPy ndarray, without importing numpy eagerly."""
    typ = type(value)
    if typ.__module__ != "numpy":
        return False
    try:
        import numpy as np

        return isinstance(value, np.ndarray)
    except ImportError:  # pragma: no cover - numpy present wherever ndarrays are
        return False


class AudioRef:
    """A lazy, format-agnostic handle to a piece of audio.

    Construct it via :func:`to_audio_ref` rather than directly. Exactly one of
    ``path`` / ``data`` / ``array`` describes the source; :attr:`sample_rate` is
    known immediately for array/tuple sources and decoded on demand otherwise.
    The accessors (:meth:`as_array`, :meth:`as_mono`, :meth:`as_path`,
    :meth:`as_waveform`)
    produce the requested concrete form, converting (and caching) as needed.
    """

    def __init__(
        self,
        *,
        path: Optional[str] = None,
        data: Optional[bytes] = None,
        array: Any = None,
        sample_rate: Optional[int] = None,
    ):
        self._path = str(path) if path is not None else None
        self._data = data
        self._array = array
        self._sample_rate = sample_rate
        self._tmp_path: Optional[str] = None  # temp file we created, for cleanup

    # -- sample rate -------------------------------------------------------
    @property
    def sample_rate(self) -> int:
        """The audio sample rate in Hz (decoding a header if necessary)."""
        if self._sample_rate:
            return self._sample_rate
        if self._path is not None or self._data is not None:
            self.as_array()  # decodes and caches sample_rate as a side effect
            if self._sample_rate:
                return self._sample_rate
        raise ValueError(
            "sample_rate is unknown for this audio input. Pass audio as "
            "(array, sample_rate), a file path, encoded bytes, or a Song/"
            "AudioResult that carries a sample_rate."
        )

    # -- concrete forms ----------------------------------------------------
    def as_array(self):
        """Return the waveform as a NumPy array (shape ``(frames, channels)``).

        Decodes ``path`` / ``data`` via :mod:`soundfile` on first call and caches
        the result (and the discovered sample rate).
        """
        if self._array is not None:
            return self._array
        try:
            import soundfile as sf
        except ImportError as e:  # pragma: no cover - exercised only w/o soundfile
            raise ImportError(
                "Decoding audio from a path or bytes needs 'soundfile' "
                "(pip install soundfile)."
            ) from e
        if self._path is not None:
            array, sr = sf.read(self._path, always_2d=False)
        elif self._data is not None:
            array, sr = sf.read(io.BytesIO(self._data), always_2d=False)
        else:  # pragma: no cover - unreachable given constructor invariants
            raise ValueError("AudioRef has no audio source to read.")
        self._array = array
        self._sample_rate = int(sr)
        return array

    def as_path(self, *, suffix: str = ".wav") -> str:
        """Return a filesystem path to the audio (writing a temp WAV if needed).

        Adapters that shell out or upload a file (e.g. ``udio``, ``yue``) use
        this. A temp file created here is tracked and removed by :meth:`cleanup`.
        """
        if self._path is not None:
            return self._path
        fd, tmp = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        if self._data is not None:
            with open(tmp, "wb") as f:
                f.write(self._data)
        else:
            try:
                import soundfile as sf
            except ImportError as e:  # pragma: no cover
                raise ImportError(
                    "Writing a waveform array to a file needs 'soundfile' "
                    "(pip install soundfile)."
                ) from e
            sf.write(tmp, self._array, self.sample_rate)
        self._tmp_path = tmp
        return tmp

    def as_mono(self, *, target_rate: Optional[int] = None) -> tuple[Any, int]:
        """Return ``(audio, sample_rate)``: mono float32, at *target_rate* if given.

        Multichannel audio is averaged over its smaller axis, so both
        ``(frames, channels)`` and ``(channels, frames)`` work. Resampling uses
        :mod:`librosa` and only happens when the rate differs. Float32 matters
        for the transformers MusicGen feature extractor: it resamples with
        torchaudio, which fails on the float64 NumPy arrays soundfile returns
        (``torch.arange`` rejects a NumPy dtype). Handing it mono float32 at its
        own rate means it never has to resample.
        """
        import numpy as np

        audio = _channels_first(self.as_array()).mean(axis=0)
        sample_rate = self.sample_rate
        if target_rate and sample_rate != target_rate:
            try:
                import librosa
            except ImportError as e:  # pragma: no cover - exercised only w/o librosa
                raise ImportError(
                    "Resampling audio needs 'librosa' (pip install librosa)."
                ) from e
            audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=target_rate)
            sample_rate = target_rate
        return audio.astype(np.float32), sample_rate

    def as_waveform(self):
        """Return the audio as a torch tensor of shape ``(channels, frames)``.

        This is the form neural backends want (``stable_audio``'s
        ``initial_audio_waveforms``, ``musicgen`` melody chroma). Mono audio is
        returned as ``(1, frames)``; a 2-D array may be either way round.
        """
        try:
            import torch
        except ImportError as e:  # pragma: no cover - exercised only w/o torch
            raise ImportError(
                "Building a waveform tensor needs 'torch' (pip install torch)."
            ) from e
        return torch.as_tensor(_channels_first(self.as_array()))

    def cleanup(self) -> None:
        """Remove any temp file this ref created via :meth:`as_path`."""
        if self._tmp_path and os.path.exists(self._tmp_path):
            try:
                os.remove(self._tmp_path)
            finally:
                self._tmp_path = None


def _channels_first(array) -> Any:
    """``array`` as float32 ``(channels, frames)``, integer PCM scaled to [-1, 1].

    soundfile gives ``(frames, channels)``; librosa, torchaudio and arioso's own
    adapters give ``(channels, frames)``. The longer axis is taken to be time,
    so a clip shorter than its channel count is read the wrong way round (a
    shape cannot tell those apart).
    """
    import numpy as np

    audio = np.asarray(array)
    if np.issubdtype(audio.dtype, np.integer):  # PCM -> [-1, 1]
        audio = audio / np.iinfo(audio.dtype).max
    audio = np.atleast_2d(audio.astype(np.float32))
    return np.ascontiguousarray(audio.T if audio.shape[0] > audio.shape[1] else audio)


def to_audio_ref(value: Any) -> AudioRef:
    """Normalize any supported audio input into an :class:`AudioRef`.

    Args:
        value: One of an :class:`AudioRef` (returned as-is), a
            :class:`~arioso.base.Song`, an :class:`~arioso.base.AudioResult`,
            raw encoded ``bytes``, a ``str``/:class:`~pathlib.Path` file path, an
            ``(array, sample_rate)`` pair, or a bare NumPy waveform array.

    Returns:
        An :class:`AudioRef` wrapping the input.

    Raises:
        TypeError: If *value* is not a supported audio input form.
        ValueError: If a ``Song``/``AudioResult`` carries only a remote
            ``audio_url`` (fetch it first with :func:`arioso.fetch_audio`).
    """
    from arioso.base import AudioResult, Song

    if isinstance(value, AudioRef):
        return value

    if isinstance(value, Song):
        return to_audio_ref(value.audio)

    if isinstance(value, AudioResult):
        if value.audio_array is not None:
            return AudioRef(
                array=value.audio_array, sample_rate=value.sample_rate or None
            )
        if value.audio_bytes is not None:
            return AudioRef(data=value.audio_bytes)
        if value.audio_url:
            raise ValueError(
                "This audio is only a remote URL. Download it first with "
                "arioso.fetch_audio(song), then pass the result to enhance()."
            )
        raise ValueError("AudioResult carries no audio (array/bytes/url all empty).")

    if isinstance(value, (bytes, bytearray)):
        return AudioRef(data=bytes(value))

    if isinstance(value, (str, Path)):
        return AudioRef(path=str(value))

    # (array, sample_rate) pair
    if isinstance(value, (tuple, list)) and len(value) == 2 and _is_ndarray(value[0]):
        array, sr = value
        return AudioRef(array=array, sample_rate=int(sr))

    if _is_ndarray(value):
        return AudioRef(array=value)

    raise TypeError(
        f"Unsupported audio input type {type(value).__name__!r}. Pass a Song, "
        "AudioResult, bytes, a file path, an (array, sample_rate) pair, or a "
        "NumPy waveform array."
    )


# --------------------------------------------------------------------------------------------
# Pitch and DSP primitives (numpy is imported where used, so ``import arioso`` stays light)


def hz_to_midi(hz):
    """Fractional MIDI number of a frequency in Hz (NaN for 0 Hz and under)."""
    import numpy as np

    with np.errstate(divide="ignore", invalid="ignore"):
        return 69.0 + 12.0 * np.log2(np.asarray(hz, dtype=float) / 440.0)


def midi_to_hz(midi):
    """Frequency in Hz of a (fractional) MIDI number."""
    import numpy as np

    return 440.0 * 2.0 ** ((np.asarray(midi, dtype=float) - 69.0) / 12.0)


def loop_drone(
    y: np.ndarray, sr: int, seconds: float, *, crossfade_s: float = 1.0
) -> np.ndarray:
    """A recorded drone repeated to ``seconds`` with equal-power crossfades at the joins."""
    import numpy as np

    y = to_audio_ref((y, sr)).as_mono()[0]
    n, fade = int(seconds * sr), int(crossfade_s * sr)
    if len(y) <= 2 * fade:
        raise ValueError(
            f"a {len(y) / sr:.1f} s drone is too short for {crossfade_s} s crossfades"
        )
    theta = np.linspace(0, np.pi / 2, fade)
    fade_in, fade_out = np.sin(theta), np.cos(theta)  # equal power: squares sum to 1
    step = len(y) - fade
    out = np.zeros(n + len(y))
    for start in range(0, n, step):
        piece = y.copy()
        if start:
            piece[:fade] *= fade_in
            out[start : start + fade] *= fade_out
        out[start : start + len(y)] += piece
    return out[:n].astype(y.dtype)


def varispeed(
    y: np.ndarray, sr: int, *, semitones: float = 0.0, sr_out: int | None = None
) -> np.ndarray:
    """``y`` played ``semitones`` higher (pitch and tempo move together, a tape sped up) and
    resampled to ``sr_out``, in one band-limited FFT resampling.

    For a drone this beats a phase vocoder: no smearing of the strings' attacks, and a cycle a
    few percent faster or slower goes unnoticed.
    """
    import numpy as np

    ratio = (sr / (sr_out or sr)) * 2 ** (
        semitones / 12
    )  # input samples per output sample
    if ratio == 1:
        return np.asarray(y, dtype=float)
    n_out = int(round(len(y) / ratio))
    spectrum = np.fft.rfft(y)[: n_out // 2 + 1]
    return np.fft.irfft(spectrum, n=n_out) * (n_out / len(y))


def highpass(
    y: np.ndarray, sr: int, cutoff_hz: float, *, width_hz: float | None = None
) -> np.ndarray:
    """``y`` with nothing left under ``cutoff_hz``: an FFT mask that is zero up to the cutoff
    and rises to one over the next ``width_hz`` (default half the cutoff) as a raised cosine, so
    there is no ringing edge."""
    import numpy as np

    if not len(y):
        raise ValueError("highpass needs a non-empty signal")
    width = cutoff_hz / 2 if width_hz is None else width_hz
    spectrum = np.fft.rfft(y)
    freqs = np.fft.rfftfreq(len(y), 1 / sr)
    rise = np.clip((freqs - cutoff_hz) / max(width, 1e-9), 0, 1)
    return np.fft.irfft(spectrum * np.sin(rise * np.pi / 2) ** 2, n=len(y))
