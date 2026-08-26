from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .atomic_io import atomic_write_json
from .models import (
    AudioEvent,
    AudioProperties,
    AutomaticDesign,
    BeatEvent,
    PaletteColor,
    Segment,
    SongAnalysis,
    TimelineFrame,
    construct_filtered,
)


def analysis_from_dict(payload: dict[str, Any]) -> SongAnalysis:
    audio = construct_filtered(AudioProperties, payload["audio"])
    timeline = [construct_filtered(TimelineFrame, item) for item in payload.get("timeline", [])]
    beats = [construct_filtered(BeatEvent, item) for item in payload.get("beats", [])]
    events = [construct_filtered(AudioEvent, item) for item in payload.get("events", [])]
    segments = [construct_filtered(Segment, item) for item in payload.get("segments", [])]

    auto_payload = payload.get("automatic_design")
    automatic = None
    if auto_payload:
        palette = [construct_filtered(PaletteColor, item) for item in auto_payload.get("palette", [])]
        automatic = AutomaticDesign(
            palette=palette,
            component_colors=auto_payload.get("component_colors", {}),
            multipliers=auto_payload.get("multipliers", {}),
            transition_smoothing=auto_payload.get("transition_smoothing", 0.6),
            beat_pulse_enabled=auto_payload.get("beat_pulse_enabled", True),
            beat_pulse_strength=auto_payload.get("beat_pulse_strength", 1.0),
        )

    return SongAnalysis(
        schema_version=payload["schema_version"],
        analysis_version=payload["analysis_version"],
        salience_model_version=payload.get("salience_model_version", "unknown"),
        source_fingerprint=payload["source_fingerprint"],
        audio=audio,
        global_features=payload.get("global_features", {}),
        timeline=timeline,
        beats=beats,
        events=events,
        segments=segments,
        automatic_design=automatic,
        performance=payload.get("performance", {}),
        created_at_utc=payload.get("created_at_utc", ""),
        metadata=payload.get("metadata", {}),
    )


class AnalysisCache:
    def __init__(self, root: str | Path = "cache/analyses") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, fingerprint: str, analysis_version: str) -> Path:
        return self.root / f"{fingerprint}_{analysis_version}.json"

    def get(
        self,
        fingerprint: str,
        analysis_version: str,
    ) -> SongAnalysis | None:
        path = self.path_for(fingerprint, analysis_version)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return analysis_from_dict(payload)

    def put(self, analysis: SongAnalysis) -> Path:
        path = self.path_for(analysis.source_fingerprint, analysis.analysis_version)
        return atomic_write_json(path, analysis.to_dict())
