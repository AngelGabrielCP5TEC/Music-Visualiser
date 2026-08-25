from __future__ import annotations

import numpy as np


def percentile_normalize(values: np.ndarray, low: float = 5.0, high: float = 95.0) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    if values.size == 0:
        return values.copy()

    q_low, q_high = np.percentile(values, [low, high])
    if np.isclose(q_high, q_low):
        return np.zeros_like(values, dtype=np.float64)

    return np.clip((values - q_low) / (q_high - q_low), 0.0, 1.0)


def sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    x = np.asarray(x)
    out = np.empty_like(x, dtype=np.float64)
    positive = x >= 0
    out[positive] = 1.0 / (1.0 + np.exp(-x[positive]))
    exp_x = np.exp(x[~positive])
    out[~positive] = exp_x / (1.0 + exp_x)
    return out.item() if out.ndim == 0 else out
