"""End-to-end integration test.

Runs the full analyze_audio() pipeline against the synthetic test signal
(tools/generate_test_tone.py), which has known, deliberate frequency
changes at 3s, 6s, and 9s. This validates that decoding, STFT, band
energies, novelty/flux, change detection and segmentation all work
together correctly -- not just in isolation, like the unit tests do.
"""
from __future__ import annotations

import numpy as np
import soundfile as sf

from music_visual_intelligence.analysis import analyze_audio
from music_visual_intelligence.config import AnalysisConfig
from tools.generate_test_tone import BOUNDARY_TIMES, build_test_signal, SR


def test_pipeline_detects_known_frequency_changes(tmp_path):
    signal = build_test_signal()
    wav_path = tmp_path / "test_signal.wav"
    sf.write(wav_path, signal, SR)

    analysis = analyze_audio(wav_path, AnalysisConfig())

    # Basic sanity on the audio properties themselves.
    assert analysis.audio.sample_rate == SR
    assert abs(analysis.audio.duration_seconds - 12.0) < 0.05
    assert len(analysis.timeline) > 0

    # There should be a detected change near each boundary (100Hz -> 440Hz
    # -> 2000Hz -> layered). Allow a tolerance window since detection
    # snaps to the nearest aggregated (10fps) frame and the change-event
    # picker requires a minimum gap between events.
    event_times = sorted(event.time for event in analysis.events)
    assert len(event_times) >= 1, "expected at least one detected change event"

    tolerance_seconds = 1.0
    matched_boundaries = 0
    for boundary in BOUNDARY_TIMES:
        if any(abs(event_time - boundary) <= tolerance_seconds for event_time in event_times):
            matched_boundaries += 1

    # We don't require every single boundary to be caught (novelty-based
    # detection is intentionally simple in V1), but the majority of the
    # deliberately engineered changes should show up.
    assert matched_boundaries >= 2, (
        f"expected at least 2 of {BOUNDARY_TIMES} to be detected as change "
        f"events, got detected events at {event_times}"
    )

    # Segments should exist and cover the whole track without gaps.
    assert len(analysis.segments) >= 1
    assert analysis.segments[0].start == 0.0
    assert abs(analysis.segments[-1].end - analysis.audio.duration_seconds) < 1e-6

    # Bass should clearly dominate in the 0-3s window vs. the highs band,
    # and the opposite should hold in the 6-9s window.
    times = np.asarray([frame.time for frame in analysis.timeline])
    bass = np.asarray([frame.bass_db for frame in analysis.timeline])
    highs = np.asarray([frame.highs_db for frame in analysis.timeline])

    early_mask = (times >= 0.5) & (times <= 2.5)
    late_mask = (times >= 6.5) & (times <= 8.5)

    assert np.mean(bass[early_mask]) > np.mean(highs[early_mask])
    assert np.mean(highs[late_mask]) > np.mean(bass[late_mask])

    # Performance metrics should be populated and internally consistent.
    assert analysis.performance["real_time_factor"] > 0
    assert analysis.performance["peak_rss_mb"] > 0
