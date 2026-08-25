from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisConfig:
    """Canonical V1 audio-analysis parameters."""

    target_sr: int = 44_100
    n_fft: int = 2_048
    hop_length: int = 512
    stored_fps: float = 10.0

    bass_low_hz: float = 20.0
    bass_high_hz: float = 250.0
    mids_high_hz: float = 2_000.0
    highs_high_hz: float = 12_000.0

    context_seconds: float = 4.0
    min_segment_seconds: float = 8.0
    significant_change_z: float = 2.0
    beat_sigma_fraction: float = 0.08

    salience_w_energy: float = 1.2
    salience_w_novelty: float = 1.0
    salience_w_rhythm: float = 0.8
    salience_w_contrast: float = 0.6
    salience_w_context: float = 0.8
    salience_bias: float = 2.0

    schema_version: str = "1.1"
    analysis_version: str = "canonical-v1"
    salience_model_version: str = "salience-v1"
