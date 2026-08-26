from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any, TypeVar

T = TypeVar("T")


def construct_filtered(cls: type[T], payload: dict[str, Any]) -> T:
    """Build a dataclass instance from a dict, ignoring unknown keys.

    This keeps deserialization forward/backward compatible: JSON produced
    by an older or newer schema version can still be loaded as long as the
    fields it shares with the current dataclass are enough to construct it.
    Used by every cache/store that round-trips dataclasses through JSON
    (analyses, identities, designs) so they all behave the same way when
    the schema evolves.
    """
    known = {f.name for f in fields(cls)}
    return cls(**{key: value for key, value in payload.items() if key in known})


@dataclass
class AudioProperties:
    sample_rate: int
    channels: int
    duration_seconds: float
    samples: int
    source_path: str


@dataclass
class TimelineFrame:
    time: float
    bass_db: float
    mids_db: float
    highs_db: float
    rms: float
    rms_db: float
    spectral_centroid_hz: float
    brightness: float
    onset_strength: float
    novelty: float
    rhythm: float
    context_contrast: float
    spectral_contrast: float
    salience: float


@dataclass
class BeatEvent:
    time: float
    strength: float
    confidence: float = 1.0


@dataclass
class AudioEvent:
    time: float
    event_type: str
    strength: float
    confidence: float = 1.0


@dataclass
class Segment:
    start: float
    end: float
    confidence: float
    label: str | None = None


@dataclass
class PaletteColor:
    rgb: list[int]
    proportion: float


@dataclass
class AutomaticDesign:
    palette: list[PaletteColor] = field(default_factory=list)
    component_colors: dict[str, list[int]] = field(default_factory=dict)
    multipliers: dict[str, float] = field(default_factory=lambda: {
        "bass": 1.0,
        "mids": 1.0,
        "highs": 1.0,
        "energy": 1.0,
        "rhythm": 1.0,
        "novelty": 1.0,
        "salience": 1.0,
    })
    transition_smoothing: float = 0.6
    beat_pulse_enabled: bool = True
    beat_pulse_strength: float = 1.0


@dataclass
class PersonalDesign:
    design_id: str
    name: str
    base_analysis_fingerprint: str
    component_colors: dict[str, list[int]] = field(default_factory=dict)
    multipliers: dict[str, float] = field(default_factory=dict)
    transition_smoothing: float | None = None
    beat_pulse_enabled: bool | None = None
    beat_pulse_strength: float | None = None
    segment_labels: dict[str, str] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SongAnalysis:
    schema_version: str
    analysis_version: str
    salience_model_version: str
    source_fingerprint: str
    audio: AudioProperties
    global_features: dict[str, Any]
    timeline: list[TimelineFrame]
    beats: list[BeatEvent]
    events: list[AudioEvent]
    segments: list[Segment]
    automatic_design: AutomaticDesign | None
    performance: dict[str, Any]
    created_at_utc: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
