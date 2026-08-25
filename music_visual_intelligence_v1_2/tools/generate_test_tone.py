from pathlib import Path

import numpy as np
import soundfile as sf


OUT = Path("data/test_signal.wav")
SR = 44_100
DURATION = 12.0

t = np.arange(int(SR * DURATION)) / SR
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
fade_len = int(0.02 * SR)
fade = np.linspace(0, 1, fade_len)
for start in (0, 3 * SR, 6 * SR, 9 * SR):
    start = int(start)
    end = min(len(y), start + fade_len)
    y[start:end] *= fade[: end - start]

OUT.parent.mkdir(parents=True, exist_ok=True)
sf.write(OUT, y.astype(np.float32), SR)
print(f"Generated {OUT}")
