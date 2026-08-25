from __future__ import annotations

import json
from pathlib import Path

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
        return SongIdentity(**json.loads(path.read_text(encoding="utf-8")))

    def put(self, fingerprint: str, identity: SongIdentity) -> Path:
        path = self.path_for(fingerprint)
        path.write_text(
            json.dumps(identity.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path
