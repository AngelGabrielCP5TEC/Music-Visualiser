import numpy as np

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
