from __future__ import annotations

from collections import Counter
from pathlib import Path

from PIL import Image

from .models import AutomaticDesign, PaletteColor


def extract_palette(image_path: str | Path, color_count: int = 5) -> list[PaletteColor]:
    image = Image.open(image_path).convert("RGB")
    image.thumbnail((256, 256))
    quantized = image.quantize(colors=color_count, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette()
    counts = Counter(quantized.getdata())
    total = max(1, sum(counts.values()))

    colors: list[PaletteColor] = []
    for index, count in counts.most_common(color_count):
        base = index * 3
        rgb = [int(palette[base]), int(palette[base + 1]), int(palette[base + 2])]
        colors.append(PaletteColor(rgb=rgb, proportion=float(count / total)))
    return colors


def generate_automatic_design(
    image_path: str | Path | None,
    color_count: int = 5,
) -> AutomaticDesign:
    if image_path is None:
        return AutomaticDesign()

    palette = extract_palette(image_path, color_count)
    component_colors = {}
    for component, color in zip(("bass", "mids", "highs"), palette[:3]):
        component_colors[component] = color.rgb

    return AutomaticDesign(
        palette=palette,
        component_colors=component_colors,
    )
