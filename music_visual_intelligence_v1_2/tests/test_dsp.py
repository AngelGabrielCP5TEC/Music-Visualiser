import numpy as np

from music_visual_intelligence.analysis import detect_change_events
from music_visual_intelligence.dsp import (
    aggregate_series,
    autocorrelation_tempo,
    spectral_flux,
)


def test_aggregate_series():
    times = np.arange(0, 2, 0.01)
    values = np.ones_like(times)
    result, result_times = aggregate_series(values, times, 10)
    assert 19 <= len(result) <= 21
    assert len(result) == len(result_times)
    assert np.allclose(result, 1.0)


def test_spectral_flux_detects_change():
    a = np.ones((5, 10))
    b = np.ones((5, 10)) * 2.0
    spectrum = np.concatenate([a, b], axis=1)
    flux = spectral_flux(spectrum)
    assert flux[10] > 0
    assert np.max(flux) > 0


def test_tempo_from_periodic_onset():
    hop_seconds = 512 / 44_100
    bpm = 120.0
    period_frames = round((60 / bpm) / hop_seconds)
    onset = np.zeros(2_000)
    onset[100::period_frames] = 1.0

    estimate, _ = autocorrelation_tempo(onset, hop_seconds)
    assert 110 <= estimate <= 130


def test_detect_change_events_fires_on_clipped_ceiling_distribution():
    """Regression test for a bug where change detection never fired.

    `novelty` is percentile-normalized and clipped to [0, 1] before this
    function ever sees it, which pins several frames at exactly 1.0. A
    parametric z-score (mean/std) over that kind of distribution rarely
    reaches the configured threshold (2.0), so real spikes were silently
    never reported. This reproduces that shape directly (mostly low
    values with a clear spike near the ceiling) and checks the spike is
    actually detected.
    """
    frames = []
    for i in range(60):
        novelty = 0.05
        if i == 30:
            novelty = 1.0
        frames.append({"time": i * 0.1, "novelty": novelty})

    events = detect_change_events(frames, z_threshold=2.0)

    assert len(events) >= 1
    assert any(abs(event.time - 3.0) < 0.15 for event in events)
