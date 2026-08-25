from __future__ import annotations

import numpy as np

from .config import AnalysisConfig
from .normalization import percentile_normalize, sigmoid


def resample_linear(y: np.ndarray, source_sr: int, target_sr: int) -> np.ndarray:
    if source_sr == target_sr:
        return np.asarray(y, dtype=np.float64)

    target_length = max(1, int(round(len(y) * target_sr / source_sr)))
    old_x = np.linspace(0.0, 1.0, num=len(y), endpoint=False)
    new_x = np.linspace(0.0, 1.0, num=target_length, endpoint=False)
    return np.interp(new_x, old_x, y).astype(np.float64)


def stft_magnitude(
    y: np.ndarray,
    n_fft: int,
    hop_length: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Return magnitude STFT and frame times using NumPy only."""
    if len(y) == 0:
        return np.empty((n_fft // 2 + 1, 0)), np.empty(0)

    pad = n_fft // 2
    padded = np.pad(y, (pad, pad), mode="constant")
    n_frames = 1 + max(0, (len(padded) - n_fft) // hop_length)

    window = np.hanning(n_fft)
    frames = np.lib.stride_tricks.sliding_window_view(padded, n_fft)[::hop_length]
    frames = frames[:n_frames]

    spectrum = np.fft.rfft(frames * window[None, :], axis=1)
    magnitude = np.abs(spectrum).T

    return magnitude, np.arange(n_frames, dtype=np.float64)


def frame_times(frame_indices: np.ndarray, sr: int, hop_length: int) -> np.ndarray:
    return frame_indices * hop_length / sr


def band_energy_db(
    power: np.ndarray,
    freqs: np.ndarray,
    low_hz: float,
    high_hz: float,
    eps: float = 1e-12,
) -> np.ndarray:
    mask = (freqs >= low_hz) & (freqs < high_hz)
    if not np.any(mask):
        return np.full(power.shape[1], -120.0, dtype=np.float64)

    mean_power = np.mean(power[mask], axis=0)
    return 10.0 * np.log10(mean_power + eps)


def spectral_centroid(magnitude: np.ndarray, freqs: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    denominator = np.sum(magnitude, axis=0) + eps
    return np.sum(freqs[:, None] * magnitude, axis=0) / denominator


def spectral_flux(magnitude: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    log_mag = np.log1p(magnitude + eps)
    delta = np.diff(log_mag, axis=1, prepend=log_mag[:, :1])
    positive_delta = np.maximum(delta, 0.0)
    return np.sqrt(np.sum(positive_delta ** 2, axis=0))


def spectral_contrast_basic(
    magnitude: np.ndarray,
    freqs: np.ndarray,
    bands: int = 6,
    eps: float = 1e-12,
) -> np.ndarray:
    """
    A lightweight spectral-contrast approximation.

    The spectrum is split into logarithmically spaced frequency regions.
    For each region, contrast is approximated by the difference between
    its upper and lower robust energy levels.
    """
    if magnitude.shape[1] == 0:
        return np.empty(0)

    valid = (freqs >= 200.0) & (freqs <= min(8_000.0, freqs[-1]))
    f = freqs[valid]
    m = magnitude[valid]

    if len(f) < bands * 2:
        return np.zeros(m.shape[1])

    edges = np.geomspace(max(20.0, f[0]), f[-1], bands + 1)
    contrasts = []

    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (f >= lo) & (f < hi)
        if np.count_nonzero(mask) < 2:
            continue
        region = m[mask]
        high = np.percentile(region, 90, axis=0)
        low = np.percentile(region, 10, axis=0)
        contrasts.append(20.0 * np.log10((high + eps) / (low + eps)))

    if not contrasts:
        return np.zeros(m.shape[1])

    return np.mean(np.vstack(contrasts), axis=0)


def aggregate_series(
    values: np.ndarray,
    times: np.ndarray,
    target_fps: float,
    reducer: str = "mean",
) -> tuple[np.ndarray, np.ndarray]:
    if len(values) == 0:
        return np.empty(0), np.empty(0)

    step = 1.0 / target_fps
    edges = np.arange(0.0, times[-1] + step * 1.0001, step)
    indices = np.digitize(times, edges, right=False) - 1

    output_values = []
    output_times = []

    for i in range(len(edges) - 1):
        mask = indices == i
        if not np.any(mask):
            continue
        chunk = values[mask]
        if reducer == "max":
            value = float(np.max(chunk))
        elif reducer == "median":
            value = float(np.median(chunk))
        else:
            value = float(np.mean(chunk))
        output_values.append(value)
        output_times.append(float((edges[i] + edges[i + 1]) / 2.0))

    return np.asarray(output_values), np.asarray(output_times)


def gaussian_beat_influence(
    times: np.ndarray,
    beat_times: np.ndarray,
    bpm: float,
    sigma_fraction: float,
) -> np.ndarray:
    if len(times) == 0 or len(beat_times) == 0 or bpm <= 0:
        return np.zeros_like(times, dtype=np.float64)

    period = 60.0 / bpm
    sigma = max(0.005, sigma_fraction * period)
    radius = 4.0 * sigma
    result = np.zeros_like(times, dtype=np.float64)

    for beat in beat_times:
        mask = np.abs(times - beat) <= radius
        if np.any(mask):
            local = np.exp(-((times[mask] - beat) ** 2) / (2.0 * sigma * sigma))
            result[mask] = np.maximum(result[mask], local)

    return result


def autocorrelation_tempo(
    onset: np.ndarray,
    frame_hop_seconds: float,
    min_bpm: float = 60.0,
    max_bpm: float = 180.0,
) -> tuple[float, np.ndarray]:
    """Estimate a dominant tempo from onset strength using autocorrelation."""
    if len(onset) < 4:
        return 0.0, np.empty(0, dtype=int)

    x = onset - np.mean(onset)
    corr = np.correlate(x, x, mode="full")[len(x) - 1:]

    min_lag = max(1, int(np.floor((60.0 / max_bpm) / frame_hop_seconds)))
    max_lag = min(len(corr) - 1, int(np.ceil((60.0 / min_bpm) / frame_hop_seconds)))

    if max_lag <= min_lag:
        return 0.0, np.empty(0, dtype=int)

    lag = min_lag + int(np.argmax(corr[min_lag:max_lag + 1]))
    period = lag * frame_hop_seconds
    bpm = 60.0 / period if period > 0 else 0.0
    return float(bpm), np.array([lag], dtype=int)


def detect_beats_from_onset(
    onset: np.ndarray,
    frame_hop_seconds: float,
    bpm: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate candidate beats by peak-picking onset activity at the estimated period."""
    if bpm <= 0 or len(onset) < 4:
        return np.empty(0, dtype=int), np.empty(0)

    period = max(1, int(round((60.0 / bpm) / frame_hop_seconds)))
    threshold = float(np.mean(onset) + 0.5 * np.std(onset))

    peaks: list[int] = []
    min_distance = max(1, period // 2)

    for i in range(1, len(onset) - 1):
        if onset[i] < threshold:
            continue
        if onset[i] >= onset[i - 1] and onset[i] >= onset[i + 1]:
            if not peaks or i - peaks[-1] >= min_distance:
                peaks.append(i)
            elif onset[i] > onset[peaks[-1]]:
                peaks[-1] = i

    if not peaks:
        return np.empty(0, dtype=int), np.empty(0)

    # Quantize candidates onto the nearest estimated beat grid.
    first = peaks[0]
    grid = [first]
    current = first
    while current + period < len(onset):
        current += period
        grid.append(current)

    grid_array = np.asarray(grid, dtype=int)
    beat_strengths = []

    for target in grid_array:
        radius = max(1, period // 4)
        lo = max(0, target - radius)
        hi = min(len(onset), target + radius + 1)
        local = onset[lo:hi]
        idx = lo + int(np.argmax(local))
        beat_strengths.append(float(onset[idx]))

    return grid_array, np.asarray(beat_strengths)


def build_high_resolution_features(y: np.ndarray, config: AnalysisConfig) -> dict:
    magnitude, indices = stft_magnitude(y, config.n_fft, config.hop_length)
    freqs = np.fft.rfftfreq(config.n_fft, d=1.0 / config.target_sr)
    times = frame_times(indices, config.target_sr, config.hop_length)

    power = magnitude ** 2
    rms = np.sqrt(np.mean(power, axis=0) + 1e-12)
    rms_db = 20.0 * np.log10(rms + 1e-12)

    bass_db = band_energy_db(power, freqs, config.bass_low_hz, config.bass_high_hz)
    mids_db = band_energy_db(power, freqs, config.bass_high_hz, config.mids_high_hz)
    highs_db = band_energy_db(power, freqs, config.mids_high_hz, config.highs_high_hz)

    centroid = spectral_centroid(magnitude, freqs)
    flux = spectral_flux(magnitude)
    contrast = spectral_contrast_basic(magnitude, freqs)

    return {
        "times": times,
        "magnitude": magnitude,
        "rms": rms,
        "rms_db": rms_db,
        "bass_db": bass_db,
        "mids_db": mids_db,
        "highs_db": highs_db,
        "centroid": centroid,
        "flux": flux,
        "contrast": contrast,
    }


def build_timeline(
    features: dict,
    beat_times: np.ndarray,
    tempo_bpm: float,
    config: AnalysisConfig,
) -> list[dict]:
    times = features["times"]
    energy = percentile_normalize(features["rms_db"])
    brightness = percentile_normalize(features["centroid"])
    novelty = percentile_normalize(features["flux"])
    onset = novelty.copy()
    contrast = percentile_normalize(features["contrast"])

    rhythm = 0.5 * onset + 0.5 * gaussian_beat_influence(
        times, beat_times, tempo_bpm, config.beat_sigma_fraction
    )

    context_window = max(
        3,
        int(round(config.context_seconds * config.stored_fps)),
    )
    kernel = np.ones(context_window, dtype=np.float64) / context_window
    mean_context = np.convolve(energy, kernel, mode="same")
    second_moment = np.convolve(energy ** 2, kernel, mode="same")
    context_std = np.sqrt(np.maximum(0.0, second_moment - mean_context ** 2))
    context_contrast = np.maximum(
        0.0,
        (energy - mean_context) / (context_std + 1e-9),
    )
    context_contrast = percentile_normalize(context_contrast)

    logits = (
        config.salience_w_energy * energy
        + config.salience_w_novelty * novelty
        + config.salience_w_rhythm * rhythm
        + config.salience_w_contrast * contrast
        + config.salience_w_context * context_contrast
        - config.salience_bias
    )
    salience = np.asarray(sigmoid(logits), dtype=np.float64)

    raw = {
        "bass_db": features["bass_db"],
        "mids_db": features["mids_db"],
        "highs_db": features["highs_db"],
        "rms": features["rms"],
        "rms_db": features["rms_db"],
        "spectral_centroid_hz": features["centroid"],
        "brightness": brightness,
        "onset_strength": onset,
        "novelty": novelty,
        "rhythm": rhythm,
        "context_contrast": context_contrast,
        "spectral_contrast": contrast,
        "salience": salience,
    }

    aggregated: dict[str, np.ndarray] = {}
    out_times: np.ndarray | None = None

    for key, values in raw.items():
        reducer = "max" if key in {"novelty", "onset_strength", "salience"} else "mean"
        agg, agg_times = aggregate_series(values, times, config.stored_fps, reducer)
        aggregated[key] = agg
        if out_times is None:
            out_times = agg_times

    frames = []
    assert out_times is not None

    for i, t in enumerate(out_times):
        frames.append({
            "time": float(t),
            "bass_db": float(aggregated["bass_db"][i]),
            "mids_db": float(aggregated["mids_db"][i]),
            "highs_db": float(aggregated["highs_db"][i]),
            "rms": float(aggregated["rms"][i]),
            "rms_db": float(aggregated["rms_db"][i]),
            "spectral_centroid_hz": float(aggregated["spectral_centroid_hz"][i]),
            "brightness": float(aggregated["brightness"][i]),
            "onset_strength": float(aggregated["onset_strength"][i]),
            "novelty": float(aggregated["novelty"][i]),
            "rhythm": float(aggregated["rhythm"][i]),
            "context_contrast": float(aggregated["context_contrast"][i]),
            "spectral_contrast": float(aggregated["spectral_contrast"][i]),
            "salience": float(aggregated["salience"][i]),
        })

    return frames
