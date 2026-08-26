"""Generate a controlled synthetic signal for pipeline validation.

The signal is deliberately built with known frequency changes at fixed
timestamps so the analysis pipeline's change-detection can be checked
against ground truth:

    0-3 s    100 Hz
    3-6 s    440 Hz
    6-9 s    2000 Hz
    9-12 s   100 Hz + 2000 Hz

`build_test_signal()` is importable so tests can validate the DSP pipeline
against this same ground truth without duplicating the generation logic.
"""
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44_100
DURATION = 12.0
BOUNDARY_TIMES = (3.0, 6.0, 9.0)


def build_test_signal(sr: int = SR, duration: float = DURATION) -> np.ndarray:
    t = np.arange(int(sr * duration)) / sr
    y = np.zeros_like(t)

    # 0-3 s: bass
    m = (t >= 0) & (t < 3)
    y[m] = 0.25 * np.sin(2 * np.pi * 100 * t[m])

    # 3-6 s: mids
    m = (t >= 3) & (t < 6)
    y[m] = 0.25 * np.sin(2 * np.pi * 440 * t[m])

    # 6-9 s: highs
    m = (t >= 6) & (t < 9)
    y[m] = 0.25 * np.sin(2 * np.pi * 2_000 * t[m])

    # 9-12 s: layered change
    m = t >= 9
    y[m] = (
        0.20 * np.sin(2 * np.pi * 100 * t[m])
        + 0.20 * np.sin(2 * np.pi * 2_000 * t[m])
    )

    # Gentle boundary fades.
    fade_len = int(0.02 * sr)
    fade = np.linspace(0, 1, fade_len)
    for start in (0, 3 * sr, 6 * sr, 9 * sr):
        start = int(start)
        end = min(len(y), start + fade_len)
        y[start:end] *= fade[: end - start]

    return y.astype(np.float32)


if __name__ == "__main__":
    out = Path("data/test_signal.wav")
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(out, build_test_signal(), SR)
    print(f"Generated {out}")
