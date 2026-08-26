from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from pathlib import Path

from .atomic_io import atomic_write_json
from .models import AutomaticDesign, PersonalDesign


class DesignStore:
    """Persistent store for automatic and personal visual designs."""

    def __init__(self, root: str | Path = "cache/designs") -> None:
        self.root = Path(root)
        self.automatic_dir = self.root / "automatic"
        self.personal_dir = self.root / "personal"
        self.automatic_dir.mkdir(parents=True, exist_ok=True)
        self.personal_dir.mkdir(parents=True, exist_ok=True)

    def save_automatic(self, fingerprint: str, design: AutomaticDesign) -> Path:
        path = self.automatic_dir / f"{fingerprint}.json"
        return atomic_write_json(path, asdict(design))

    def create_personal(
        self,
        name: str,
        fingerprint: str,
        base: AutomaticDesign | None = None,
    ) -> PersonalDesign:
        design_id = str(uuid.uuid4())
        design = PersonalDesign(
            design_id=design_id,
            name=name,
            base_analysis_fingerprint=fingerprint,
            component_colors=dict(base.component_colors) if base else {},
            multipliers=dict(base.multipliers) if base else {},
            transition_smoothing=base.transition_smoothing if base else None,
            beat_pulse_enabled=base.beat_pulse_enabled if base else None,
            beat_pulse_strength=base.beat_pulse_strength if base else None,
        )
        return design

    def save_personal(self, design: PersonalDesign) -> Path:
        path = self.personal_dir / f"{design.design_id}.json"
        return atomic_write_json(path, design.to_dict())

    def list_personal(self, fingerprint: str | None = None) -> list[dict]:
        result = []
        for path in sorted(self.personal_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if fingerprint is None or payload.get("base_analysis_fingerprint") == fingerprint:
                result.append(payload)
        return result
