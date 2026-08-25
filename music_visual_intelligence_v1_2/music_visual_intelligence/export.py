from __future__ import annotations

import csv
from pathlib import Path

from .models import SongAnalysis


def export_timeline_csv(
    analysis: SongAnalysis,
    output_path: str | Path,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    rows = [frame.__dict__ for frame in analysis.timeline]
    if not rows:
        output.write_text("", encoding="utf-8")
        return output

    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    return output
