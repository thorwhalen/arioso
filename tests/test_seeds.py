"""Melody-over-drone seeds on synthetic signals (thorwhalen/arioso#27).

The contour cleaning, the score skyline, the drone and the render are numpy only; the f0 tracker is
faked so the recording path runs without librosa. The drone check and melody check close the loop:
a rendered seed must hold its drone, and a low line must be lifted out of it.
"""

import numpy as np
import pytest

from arioso.analysis import drone_report
from arioso.seeds import (
    drone_sa,
    musicgen_melody,
    drone_tonic,
    highpass,
    musicgen_variation,
    recorded_drone,
    varispeed,
    Contour,
    audio_contour,
    bowed,
    drop_blips,
    fix_octaves,
    hdemucs_vocals,
    loop_drone,
    melody_contour,
    melody_over_drone,
    mono_share,
    notes_contour,
    sa_midi,
    tanpura,
    tuning_offset,
)

SR = 8000
NAN = np.nan


def test_drop_blips_silences_short_stretches():
    midi = np.array([60.0] * 5 + [NAN] * 3 + [62.0] * 30)
    out = drop_blips(midi, fps=100, min_s=0.12)
    assert np.all(np.isnan(out[:8])) and np.all(out[8:] == 62.0)


def test_fix_octaves_moves_jumps_back():
    midi = np.full(100, 62.0)
    midi[40:45] = 74.0  # tracker jumped an octave up
    midi[70:72] = 38.0  # and two down
    out = fix_octaves(midi, fps=100, window_s=0.5)
    assert np.allclose(out, 62.0)


def test_tuning_offset_is_circular():
    assert tuning_offset(np.array([60.3, 62.3, NAN, 64.3])) == pytest.approx(0.3)
    # 49 cents sharp and 49 flat average to the quarter-tone, not to in-tune
    assert abs(tuning_offset(np.array([60.49, 61.51]))) == pytest.approx(0.5)


def _fake_tracker(f0_hz, voiced, fps=100.0):
    def track(y, sr):
        return f0_hz, voiced, fps

    return track


def test_audio_contour_gates_cleans_and_retunes():
    fps, n = 100.0, 300
    f0 = np.full(n, 440.0 * 2 ** (0.2 / 12))  # A4, 20 cents sharp
    f0[100:105] = 880.0 * 2 ** (0.2 / 12)  # an octave slip
    voiced = np.ones(n, bool)
    voiced[200:203] = False  # a 30 ms gap
    y = np.ones(int(n / fps * SR))
    y[int(2.5 * SR) :] = 0.0  # silence the tracker still calls voiced: gated

    c = audio_contour(
        (y, SR), separator=None, f0_tracker=_fake_tracker(f0, voiced, fps)
    )

    assert c.fps == fps and len(c.midi) == n
    kept = ~np.isnan(c.midi[:200])
    assert kept.sum() >= 195  # the octave slip is folded back, not dropped
    assert np.allclose(c.midi[:200][kept], 69.0)  # and retuned onto A4
    assert not np.isnan(c.midi[240])  # loud frames before the cut stay
    assert np.all(np.isnan(c.midi[260:]))  # the silence is gated


def test_audio_contour_runs_the_separator():
    seen = {}

    def separator(y, sr):
        seen["shape"] = np.shape(y)
        return np.ones(SR), SR

    track = _fake_tracker(np.full(100, 220.0), np.ones(100, bool))
    c = audio_contour((np.ones((SR, 2)), SR), separator=separator, f0_tracker=track)
    assert seen["shape"] == (SR, 2)
    assert np.allclose(c.midi, 57.0)


def test_notes_contour_skyline_glide_and_vibrato():
    notes = [(0.0, 2.0, 55), (0.5, 1.0, 67), (2.0, 3.0, 60)]  # 67 sits over 55
    c = notes_contour(
        notes, fps=100, glide_s=0.1, vibrato_delay_s=0.3, vibrato_semitones=0.2
    )
    assert c.midi[20] == 55 and c.midi[70] == 67  # the highest note sounds
    assert 55 < c.midi[201] < 60  # glides from 55 into the touching 60
    assert c.midi[215] == 60
    late = c.midi[260:300]
    assert 0.3 < late.max() - late.min() <= 0.4  # vibrato, +-0.2 once ramped in


def test_notes_contour_needs_notes():
    with pytest.raises(ValueError):
        notes_contour([])


def test_melody_contour_sends_midi_to_the_score_path(monkeypatch):
    import arioso.seeds as seeds

    monkeypatch.setattr(seeds, "midi_contour", lambda src, **kw: ("midi", src))
    monkeypatch.setattr(seeds, "audio_contour", lambda src, sr, **kw: ("audio", src))
    assert melody_contour("song.MID")[0] == "midi"
    assert melody_contour(b"MThd\x00\x00")[0] == "midi"
    assert melody_contour("song.wav")[0] == "audio"


def test_sa_midi():
    assert sa_midi("C#") == 49 and sa_midi("Db", octave=4) == 61 and sa_midi(50) == 50


def test_tanpura_holds_its_drone():
    r = drone_report(tanpura("C#", seconds=20, sr=SR), SR, sa="C#")
    assert r.drone == ("C#", "G#") and r.sa_offset == 0 and r.holds()


def test_tanpura_ma_tuning():
    r = drone_report(tanpura("D", second=5, seconds=20, sr=SR), SR, sa="D")
    assert set(r.drone) == {"D", "G"} and r.sa_offset == 0


def test_loop_drone_length_and_smooth_joins():
    t = np.arange(3 * SR) / SR
    y = np.sin(2 * np.pi * 110.3 * t) * (0.5 + 0.1 * t)  # no whole cycles, and it rises
    out = loop_drone(y, SR, 10, crossfade_s=0.5)
    assert len(out) == 10 * SR
    plain = np.tile(y, 4)[: 10 * SR]  # a splice with no crossfade jumps at each join
    assert np.max(np.abs(np.diff(plain))) > 3 * np.max(np.abs(np.diff(y)))
    assert np.max(np.abs(np.diff(out))) < 1.2 * np.max(np.abs(np.diff(y)))
    with pytest.raises(ValueError):
        loop_drone(y[: SR // 2], SR, 10, crossfade_s=0.5)


def _tune(seconds=12.0, base=50):
    """A slow line of whole notes around ``base`` (a low, male-register melody)."""
    steps = [0, 2, 4, 5, 7, 5, 4, 2]
    dur = seconds / len(steps)
    return notes_contour(
        [(i * dur, (i + 1) * dur - 0.1, base + s) for i, s in enumerate(steps)]
    )


def test_melody_over_drone_lifts_a_low_line_out_of_the_drone():
    y, sr = melody_over_drone(_tune(), "D", sr=SR)
    assert sr == SR and np.max(np.abs(y)) == pytest.approx(0.9)
    r = drone_report(y, sr, sa="D")
    assert r.drone == ("D", "A") and r.holds()

    low, _ = melody_over_drone(_tune(), "D", sr=SR, floor_midi=None)
    assert not drone_report(low, SR, sa="D").holds()


def _energy_at(y, hz):
    spectrum = np.abs(np.fft.rfft(y))
    return spectrum[int(round(hz * len(y) / SR))] / spectrum.sum()


def test_melody_over_drone_takes_a_recorded_bed():
    bed = tanpura(
        "C#", seconds=6, sr=SR, seed=7
    )  # a "recording" in C#, shorter than the tune
    y, _ = melody_over_drone(_tune(), "D", sr=SR, drone=bed, lead_in_s=0)
    assert len(y) == pytest.approx(_tune().seconds * SR, abs=2)
    r = drone_report(y, SR, sa="D")
    assert r.drone == ("D", "A") and r.sa_offset == 0  # retuned from C# to D


def test_contour_at_rate_holds_into_silence():
    c = Contour(midi=np.array([60.0, 62.0, NAN, 64.0]), fps=1.0)
    p = c.at_rate(4)
    assert p[0] == 60 and p[2] == 61  # interpolates inside a note
    assert np.all(p[4:8] == 62.0)  # holds up to the silence
    assert np.all(np.isnan(p[8:12])) and np.all(p[12:] == 64)


def test_melody_match_ranks_the_right_seed():
    pytest.importorskip("librosa")
    from arioso.analysis import melody_match

    seed, sr = melody_over_drone(_tune(base=62), "D", sr=SR)
    slower = Contour(midi=_tune(base=62).midi, fps=100 / 1.1)
    take, _ = melody_over_drone(slower, "D", sr=SR, drone_db=-4)
    other_notes = [
        (i * 1.5, i * 1.5 + 1.4, 62 + s)
        for i, s in enumerate([7, 0, 9, 3, 11, 1, 8, 2])
    ]
    other, _ = melody_over_drone(notes_contour(other_notes), "D", sr=SR)
    drone_only = tanpura("D", seconds=len(seed) / sr, sr=sr)
    true = melody_match(take, seed, sr)
    assert true > melody_match(other, seed, sr) + 0.2
    assert melody_match(drone_only, seed, sr) < 0.6  # the drone is not the tune
    assert melody_match(seed, take, sr) == pytest.approx(true, abs=0.05)  # symmetric


def test_fix_octaves_keeps_real_leaps():
    midi = np.full(100, 60.0)
    midi[40:55] = 67.0  # a fifth up for 0.15 s: a leap, not a tracker slip
    midi[70:85] = 69.0  # a sixth
    assert np.array_equal(fix_octaves(midi, fps=100), midi)


def test_audio_contour_raises_when_nothing_is_voiced():
    track = _fake_tracker(np.full(100, 220.0), np.zeros(100, bool))
    with pytest.raises(ValueError, match="no melody"):
        audio_contour((np.ones(SR), SR), separator=None, f0_tracker=track)


def test_hdemucs_rejects_a_segment_shorter_than_its_overlap():
    with pytest.raises(ValueError, match="overlap"):
        hdemucs_vocals(np.zeros(SR), SR, segment_s=1.0, overlap_s=1.0)


def test_overlapping_same_pitch_notes_do_not_depend_on_order():
    notes = [(0.0, 1.0, 60), (0.5, 2.0, 60)]
    a = notes_contour(notes, fps=100, vibrato_semitones=0)
    b = notes_contour(notes[::-1], fps=100, vibrato_semitones=0)
    assert np.array_equal(a.midi, b.midi, equal_nan=True)


def test_repeated_touching_notes_are_restruck():
    c = notes_contour([(0.0, 1.0, 60), (1.0, 2.0, 60)], fps=100, vibrato_semitones=0)
    # the first ends restrike_s (5 frames) early, so the second is heard as a new note
    assert np.all(np.isnan(c.midi[95:100])) and c.midi[94] == 60 and c.midi[100] == 60


class _Note:
    def __init__(self, start, end, pitch=70):
        self.start, self.end, self.pitch = start, end, pitch


def _track(notes, name="", is_drum=False):
    return type("Instrument", (), {"notes": notes, "name": name, "is_drum": is_drum})


def test_mono_share():
    assert mono_share([_Note(i * 0.5, i * 0.5 + 0.4) for i in range(10)]) == 1.0
    chords = [_Note(i, i + 1.0) for i in range(5) for _ in range(3)]
    assert mono_share(chords) == 0.0


def test_default_track_is_the_line_above_the_bass():
    from arioso.seeds import _melody_track

    line = _track([_Note(i * 0.5, i * 0.5 + 0.4, 72) for i in range(40)], "flute")
    pad = _track([_Note(i, i + 1.0, 64) for i in range(20) for _ in range(3)], "pad")
    bass = _track([_Note(i * 0.4, i * 0.4 + 0.3, 40) for i in range(90)], "bass")
    picked = _melody_track([pad, bass, line], min_mono=0.95, min_median_midi=55)
    assert picked.name == "flute"
    with pytest.raises(ValueError, match="pass track="):
        _melody_track([pad, bass], min_mono=0.95, min_median_midi=55)


def test_bowed_enters_on_the_new_pitch():
    sr = SR
    pitch = np.concatenate(
        [np.full(sr, 57.0), np.full(sr // 2, np.nan), np.full(sr, 69.0)]
    )
    y = bowed(pitch, sr, harmonics=1, fade_s=0.04)
    entry = y[int(1.5 * sr) - 160 : int(1.5 * sr)]  # the fade-in before the note starts
    # its zero crossings run at the new note's rate (440 Hz), not the old one's (220 Hz)
    crossings = np.sum(np.diff(np.sign(entry)) != 0) / (len(entry) / sr) / 2
    assert crossings == pytest.approx(440, rel=0.3)


def test_tanpura_plucks_end_without_a_tick():
    # a 16 s cycle and 3.9 s of drone: one string plucked once, its pluck cut at 3.9 s.
    # Without a fade it would still ring at exp(-3.9 / 2.5), a fifth of its start, and click.
    y = tanpura("C#", seconds=3.9, sr=SR, cycle_s=16, harmonics=1)
    assert np.max(np.abs(y[: SR // 2])) > 0.5
    assert np.max(np.abs(y[-int(0.005 * SR) :])) < 1e-3


def test_varispeed_moves_pitch_and_rate():
    t = np.arange(SR) / SR
    y = np.sin(2 * np.pi * 200 * t)
    up = varispeed(y, SR, semitones=12)  # an octave up, half as long
    assert len(up) == SR // 2
    peak_hz = np.argmax(np.abs(np.fft.rfft(up))) * SR / len(up)
    assert peak_hz == pytest.approx(400, abs=2)
    resampled = varispeed(y, SR, sr_out=SR // 2)  # same pitch at half the rate
    assert len(resampled) == SR // 2
    spectrum = np.abs(np.fft.rfft(resampled))
    assert np.argmax(spectrum) == pytest.approx(200, abs=1)  # 1 s: bin = Hz
    assert np.allclose(varispeed(y, SR), y)


def test_recorded_drone_refuses_a_big_move():
    drone = recorded_drone(tanpura("E", seconds=6, sr=SR), SR, max_shift=2)
    assert drone_report(drone("F", seconds=10, sr=SR), SR, sa="F").sa_offset == 0
    with pytest.raises(ValueError, match="max_shift"):
        drone("A", seconds=10, sr=SR)  # E -> A is 5 semitones


def test_recorded_drone_retunes_to_the_cent():
    # a tanpura tuned 40 cents sharp of E: a whole-semitone move would leave it 40 cents off
    rec = tanpura(52.4, seconds=8, sr=SR)  # MIDI 52.4: E3 + 40 cents
    assert drone_tonic(rec, SR) == pytest.approx(4.4, abs=0.08)
    bed = recorded_drone(rec, SR)("F", seconds=8, sr=SR)  # F3 = MIDI 53
    assert drone_tonic(bed, SR, sa="F") == pytest.approx(5.0, abs=0.08)


def test_recorded_drone_names_its_sa_when_asked():
    # told the recording's Sa is E, asking for B moves it there; it does not re-read it as Ma-tuned
    drone = recorded_drone(tanpura("E", seconds=6, sr=SR), SR, rec_sa="E", max_shift=7)
    assert drone_report(drone("B", seconds=8, sr=SR), SR, sa="B").drone == ("B", "F#")


def test_recorded_drone_rejects_what_is_not_a_drone():
    t = np.arange(2 * SR) / SR
    chords = np.concatenate(
        [
            sum(np.sin(2 * np.pi * f * t) for f in c)
            for c in [
                (65.4, 82.4, 98.0),
                (87.3, 110.0, 130.8),
                (98.0, 123.5, 146.8),
                (73.4, 87.3, 110.0),
            ]
            * 2
        ]
    )
    with pytest.raises(ValueError, match="not a drone"):
        recorded_drone(chords, SR)


def test_highpass_cuts_the_whole_drone_band():
    t = np.arange(2 * SR) / SR
    tenor = np.sin(2 * np.pi * 233.1 * t)  # A#3, inside drone_report's band
    assert _rms_at(highpass(tenor, SR, 261.6), 233.1) < 1e-6 * _rms_at(tenor, 233.1)
    with pytest.raises(ValueError):
        highpass(np.zeros(0), SR, 261.6)


def test_highpass_removes_the_bass_and_keeps_the_rest():
    t = np.arange(2 * SR) / SR
    y = np.sin(2 * np.pi * 80 * t) + np.sin(2 * np.pi * 600 * t)
    out = highpass(y, SR, 260)
    assert _rms_at(out, 80) < 0.01 * _rms_at(y, 80)
    assert _rms_at(out, 600) == pytest.approx(_rms_at(y, 600), rel=0.01)


def _rms_at(y, hz):
    spectrum = np.abs(np.fft.rfft(y))
    return spectrum[int(round(hz * len(y) / SR))]


def test_musicgen_variation_conditions_on_voice_and_drone_then_drops_the_bass():
    seen = {}

    def generate(audio, sr, *, prompt, seconds):
        seen.update(audio=audio, sr=sr, prompt=prompt, seconds=seconds)
        t = np.arange(int(seconds * sr)) / sr
        lo = np.where(t < seconds / 2, 65.4, 87.3)  # its own bass, C2 then F2
        hi = np.where(t < seconds / 2, 196.0, 233.1)  # and tenor, G3 then A#3
        take = np.sin(2 * np.pi * lo * t) + np.sin(2 * np.pi * hi * t)
        take = take + 0.5 * np.sin(2 * np.pi * 587.3 * t)  # under a melody
        return varispeed(take, sr, sr_out=2 * sr), 2 * sr  # at the model's own rate

    voice = _tune(seconds=40)
    voice_audio, _ = melody_over_drone(voice, "D", sr=SR, drone_db=-80, lead_in_s=0)
    y, sr = musicgen_variation(
        voice_audio, "D", sr=SR, prompt="sarangi", generate=generate
    )

    assert (
        seen["prompt"] == "sarangi" and seen["seconds"] == 30.0
    )  # capped at the window
    assert len(seen["audio"]) == 30 * SR
    condition = drone_report(seen["audio"], SR, sa="D")
    assert condition.drone == ("D", "A")  # the drone is in the conditioning mix
    assert sr == 2 * SR and len(y) == 30 * sr
    r = drone_report(y, sr, sa="D")
    assert r.drone == ("D", "A") and r.holds()  # the take's own bass and tenor are gone


def _strings(notes_and_gains, seconds=8, sr=SR):
    """A steady drone of harmonic tones, (MIDI pitch, gain) each, with a weak fundamental."""
    t = np.arange(int(seconds * sr)) / sr
    y = 0
    for midi, gain in notes_and_gains:
        f0 = 440 * 2 ** ((midi - 69) / 12)
        y = y + gain * sum(
            h**-0.5 * np.sin(2 * np.pi * h * f0 * t) * (0.3 if h == 1 else 1)
            for h in range(1, 8)
            if h * f0 < sr / 2
        )
    return y / np.max(np.abs(y))


def test_drone_sa_assumes_pa_tuning_even_when_pa_is_louder():
    # Sa E2/E3 soft, Pa B2 loud: "the stronger of the pair" would say B
    y = _strings([(40, 0.4), (52, 0.4), (47, 1.0)])
    assert set(drone_report(y, SR).drone) == {"E", "B"}
    assert drone_sa(y, SR) == "E"


def test_recorded_drone_checks_rec_sa_and_the_peak():
    rec = tanpura("E", seconds=6, sr=SR)
    with pytest.raises(ValueError, match="not one of the notes"):
        recorded_drone(rec, SR, rec_sa="F")
    with pytest.raises(ValueError, match="no spectral peak"):
        drone_tonic(np.zeros(4 * SR), SR, sa="E")


def test_recorded_drone_cuts_fades_before_looping():
    rec = tanpura("E", seconds=12, sr=SR)
    fade = np.linspace(0, 1, 3 * SR)
    rec[: 3 * SR] *= fade
    rec[-3 * SR :] *= fade[::-1]
    bed = recorded_drone(rec, SR)("E", seconds=40, sr=SR)
    hop = SR // 4
    level = np.sqrt(np.mean(bed[: len(bed) // hop * hop].reshape(-1, hop) ** 2, axis=1))
    assert 20 * np.log10(level.min() / np.median(level)) > -6  # no dip at the joins


def test_a_recording_with_its_own_rate_is_a_drone():
    rec = tanpura("D", seconds=6, sr=2 * SR)  # recorded at twice the output rate
    y, _ = melody_over_drone(_tune(), "D", sr=SR, drone=(rec, 2 * SR), lead_in_s=0)
    r = drone_report(y, SR, sa="D")
    assert r.drone == ("D", "A") and r.sa_offset == 0  # not an octave down


def test_musicgen_melody_routes_through_the_melody_affordance(monkeypatch):
    import arioso
    from arioso.base import AudioResult, Song

    calls = {}

    def enhance(audio, prompt, **kwargs):
        calls.update(audio=audio, prompt=prompt, **kwargs)
        out = np.ones((2, 3200)) * 0.5  # stereo at 32 kHz
        return Song(
            audio=AudioResult(audio_array=out, sample_rate=32000), platform="musicgen"
        )

    monkeypatch.setattr(arioso, "enhance", enhance)
    y, sr = musicgen_melody(np.zeros(SR), SR, prompt="sarangi", seconds=1.0)
    assert calls["platform"] == "musicgen" and calls["as_"] == "melody"
    assert calls["duration"] == 1.0 and calls["prompt"] == "sarangi"
    assert sr == 32000 and y.shape == (3200,)


def test_audio_contour_takes_denote_shaped_results():
    from types import SimpleNamespace

    n, fps = 100, 100.0
    f0 = np.full(n, 220.0)
    f0[40:60] = np.nan  # unvoiced, as denote marks it

    def separate(y, sr):
        return SimpleNamespace(vocals=np.ones(SR), sr=SR, stems={})

    def get_pitch(y, sr):
        return SimpleNamespace(
            times=np.arange(n) / fps, frequencies=f0, confidence=np.ones(n)
        )

    c = audio_contour((np.ones((SR, 2)), SR), separator=separate, f0_tracker=get_pitch)
    assert c.fps == pytest.approx(fps)
    assert np.allclose(c.midi[:40], 57.0) and np.all(np.isnan(c.midi[40:60]))


def test_audio_contour_follows_the_trackers_own_times():
    from types import SimpleNamespace

    rate, hop = 44100, 512  # 86.13 fps: no whole number of samples per frame drift
    n = int(300 * rate / hop)  # five minutes
    times = np.arange(n) * hop / rate + 0.5  # and a first frame half a second in
    f0 = np.full(n, 220.0)
    f0[::7] = 0.0  # some trackers mark unvoiced frames with 0, not NaN
    y = np.zeros(300 * rate + rate)
    loud_from = 200 * rate  # the recording is silent until 200 s
    y[loud_from:] = 1.0

    def get_pitch(y, sr):
        return SimpleNamespace(times=times, frequencies=f0)

    c = audio_contour((y, rate), separator=None, f0_tracker=get_pitch, min_note_s=0)
    t = np.arange(len(c.midi)) / c.fps
    voiced = ~np.isnan(c.midi)
    assert not voiced[t < 199.9].any()  # the gate holds to the true silence, no drift
    assert voiced[(t > 200.2) & (t < 300)].mean() > 0.8
    assert np.all(np.isnan(c.midi[: int(0.5 * c.fps)]))  # shifted onto its first time
    assert np.isfinite(c.midi[voiced]).all()  # 0 Hz is unvoiced, not -inf


@pytest.mark.parametrize(
    "result, match",
    [
        ({"times": np.arange(5) / 100, "frequencies": np.ones(4)}, "per frame"),
        ({"times": np.zeros(5), "frequencies": np.ones(5)}, "increasing"),
        ({"times": np.arange(1) / 100, "frequencies": np.ones(1)}, "two or more"),
    ],
)
def test_audio_contour_names_a_bad_tracker_result(result, match):
    from types import SimpleNamespace

    with pytest.raises(ValueError, match=match):
        audio_contour(
            (np.ones(SR), SR),
            separator=None,
            f0_tracker=lambda y, sr: SimpleNamespace(**result),
        )
