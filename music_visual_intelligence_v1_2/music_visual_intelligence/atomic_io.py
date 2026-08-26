from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_json(path: str | Path, payload: Any, *, indent: int = 2) -> Path:
    """Write JSON to `path` atomically.

    Writes to a temporary file in the same directory and then uses
    os.replace, which is atomic on POSIX and Windows. This avoids leaving
    a truncated/corrupt file behind if the process is interrupted
    mid-write (e.g. killed, crashes, or the disk fills up).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=indent, ensure_ascii=False)
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise

    return path
