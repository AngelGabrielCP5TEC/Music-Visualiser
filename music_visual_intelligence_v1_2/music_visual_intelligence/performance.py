from __future__ import annotations

import os
import platform
import time

import psutil


class PerformanceMonitor:
    def __init__(self) -> None:
        self.process = psutil.Process(os.getpid())
        self.started = time.perf_counter()
        self.peak_rss = self.process.memory_info().rss

    def sample(self) -> None:
        self.peak_rss = max(self.peak_rss, self.process.memory_info().rss)

    def finish(self, audio_seconds: float) -> dict:
        self.sample()
        elapsed = time.perf_counter() - self.started
        return {
            "wall_time_seconds": elapsed,
            "audio_seconds": audio_seconds,
            "real_time_factor": elapsed / max(audio_seconds, 1e-9),
            "audio_seconds_per_processing_second": audio_seconds / max(elapsed, 1e-9),
            "peak_rss_mb": self.peak_rss / (1024 * 1024),
            "platform": platform.platform(),
            "python": platform.python_version(),
        }
