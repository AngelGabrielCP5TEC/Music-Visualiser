from __future__ import annotations

import json
from pathlib import Path

from .atomic_io import atomic_write_json
from .models import construct_filtered
from .recognition import SongIdentity


class IdentityCache:
    def __init__(self, root: str | Path = "cache/identity") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, fingerprint: str) -> Path:
        return self.root / f"{fingerprint}.json"

    def get(self, fingerprint: str) -> SongIdentity | None:
        path = self.path_for(fingerprint)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        # Filtered construction: tolerates schema drift the same way
        # AnalysisCache does, instead of failing on unknown/missing keys.
        return construct_filtered(SongIdentity, payload)

    def put(self, fingerprint: str, identity: SongIdentity) -> Path:
        path = self.path_for(fingerprint)
        return atomic_write_json(path, identity.to_dict())
