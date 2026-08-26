from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import time

import numpy as np
import soundfile as sf

from .config import AnalysisConfig
from .dsp import (
    autocorrelation_tempo,
    build_high_resolution_features,
    build_timeline,
    detect_beats_from_onset,
    resample_linear,
)
from .models import (
    AudioEvent,
    AudioProperties,
    BeatEvent,
    Segment,
    SongAnalysis,
    TimelineFrame,
)
from .performance import PerformanceMonitor


def fingerprint_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _z_threshold_to_percentile(z_threshold: float) -> float:
    """Map a z-score threshold to the equivalent normal-distribution
    percentile rank (e.g. z=2.0 -> ~97.7th percentile).

    `novelty` is percentile-normalized and clipped to [0, 1] upstream
    (see normalization.percentile_normalize), which caps roughly the top
    5% of values at exactly 1.0. That clipping structurally bounds how
    large a *parametric* z-score (mean/std) can get -- with several
    frames tied at the ceiling, the standard deviation is inflated enough
    that a z-score of 2.0 is effectively unreachable, so a mean/std gate
    silently detects nothing even on audio with obvious spectral changes.
    A percentile-rank gate on the actual sample avoids that normality
    assumption while keeping the z_threshold config value's original,
    intuitive meaning ("flag roughly the top N% most novel frames").
    """
    return 100.0 * (0.5 * (1.0 + math.erf(z_threshold / math.sqrt(2.0))))


def detect_change_events(
    frames: list[dict],
    z_threshold: float,
    min_gap: float = 1.0,
) -> list[AudioEvent]:
    if len(frames) < 3:
        return []

    times = np.asarray([frame["time"] for frame in frames], dtype=np.float64)
    novelty = np.asarray([frame["novelty"] for frame in frames], dtype=np.float64)

    if np.std(novelty) < 1e-12:
        return []

    percentile_rank = _z_threshold_to_percentile(z_threshold)
    threshold_value = float(np.percentile(novelty, percentile_rank))
    candidates = np.flatnonzero(novelty >= threshold_value)
    selected: list[int] = []

    for idx in candidates:
        idx = int(idx)
        if not selected:
            selected.append(idx)
            continue

        previous = selected[-1]
        if times[idx] - times[previous] >= min_gap:
            selected.append(idx)
        elif novelty[idx] > novelty[previous]:
            selected[-1] = idx

    return [
        AudioEvent(
            time=float(times[idx]),
            event_type="significant_change",
            strength=float(novelty[idx]),
            confidence=float(np.clip(novelty[idx], 0.0, 1.0)),
        )
        for idx in selected
    ]


def build_segments(
    events: list[AudioEvent],
    duration: float,
    min_segment_seconds: float,
) -> list[Segment]:
    boundaries = [0.0]
    for event in events:
        if event.time <= min_segment_seconds:
            continue
        if event.time >= duration - min_segment_seconds:
            continue
        if event.time - boundaries[-1] >= min_segment_seconds:
            boundaries.append(event.time)

    if boundaries[-1] < duration:
        boundaries.append(duration)

    segments = []
    for start, end in zip(boundaries[:-1], boundaries[1:]):
        confidence = 0.5
        internal = [event.confidence for event in events if start <= event.time <= end]
        if internal:
            confidence = float(np.mean(internal))
        segments.append(
            Segment(
                start=float(start),
                end=float(end),
                confidence=float(np.clip(confidence, 0.0, 1.0)),
            )
        )
    return segments


def analyze_audio(
    path: str | Path,
    config: AnalysisConfig | None = None,
) -> SongAnalysis:
    config = config or AnalysisConfig()
    source = Path(path).resolve()

    if not source.exists():
        raise FileNotFoundError(f"Audio file not found: {source}")

    monitor = PerformanceMonitor()
    phase: dict[str, float] = {}

    t0 = time.perf_counter()
    audio_data, source_sr = sf.read(source, always_2d=True, dtype="float64")
    phase["decode_seconds"] = time.perf_counter() - t0

    y = np.mean(audio_data, axis=1)
    y = resample_linear(y, source_sr, config.target_sr)

    duration = len(y) / config.target_sr
    audio = AudioProperties(
        sample_rate=config.target_sr,
        channels=int(audio_data.shape[1]),
        duration_seconds=float(duration),
        samples=int(len(y)),
        source_path=str(source),
    )

    t0 = time.perf_counter()
    features = build_high_resolution_features(y, config)
    phase["feature_extraction_seconds"] = time.perf_counter() - t0
    monitor.sample()

    t0 = time.perf_counter()
    frame_hop_seconds = config.hop_length / config.target_sr
    tempo_bpm, _ = autocorrelation_tempo(
        features["flux"],
        frame_hop_seconds,
    )
    beat_indices, beat_strengths = detect_beats_from_onset(
        features["flux"],
        frame_hop_seconds,
        tempo_bpm,
    )
    beat_times = beat_indices * frame_hop_seconds
    phase["beat_detection_seconds"] = time.perf_counter() - t0
    monitor.sample()

    t0 = time.perf_counter()
    timeline_dicts = build_timeline(
        features,
        beat_times,
        tempo_bpm,
        config,
    )
    changes = detect_change_events(
        timeline_dicts,
        config.significant_change_z,
    )
    segments = build_segments(
        changes,
        duration,
        config.min_segment_seconds,
    )
    phase["temporal_model_seconds"] = time.perf_counter() - t0
    monitor.sample()

    t0 = time.perf_counter()
    fingerprint = fingerprint_file(source)
    phase["fingerprint_seconds"] = time.perf_counter() - t0

    # Single call to finish() — it already samples RSS and reports platform/python.
    perf_summary = monitor.finish(duration)
    phase.update({
        "total_seconds": perf_summary["wall_time_seconds"],
        "real_time_factor": perf_summary["real_time_factor"],
        "audio_seconds_per_processing_second": perf_summary["audio_seconds_per_processing_second"],
        "peak_rss_mb": perf_summary["peak_rss_mb"],
        "python": perf_summary["python"],
        "platform": perf_summary["platform"],
    })

    beats = [
        BeatEvent(
            time=float(time_value),
            strength=float(strength),
            confidence=1.0,
        )
        for time_value, strength in zip(beat_times, beat_strengths)
    ]

    analysis = SongAnalysis(
        schema_version=config.schema_version,
        analysis_version=config.analysis_version,
        salience_model_version=config.salience_model_version,
        source_fingerprint=fingerprint,
        audio=audio,
        global_features={
            "tempo_bpm": tempo_bpm,
            "mean_rms_db": float(np.mean(features["rms_db"])),
            "max_rms_db": float(np.max(features["rms_db"])),
            "mean_centroid_hz": float(np.mean(features["centroid"])),
            "internal_fps": float(config.target_sr / config.hop_length),
            "stored_fps": float(config.stored_fps),
            "n_fft": config.n_fft,
            "hop_length": config.hop_length,
        },
        timeline=[TimelineFrame(**frame) for frame in timeline_dicts],
        beats=beats,
        events=changes,
        segments=segments,
        automatic_design=None,
        performance=phase,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        metadata={
            "analysis_notes": "SciPy-free V1.1 canonical local analysis.",
        },
    )
    return analysis


def save_json(analysis: SongAnalysis, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(analysis.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output
