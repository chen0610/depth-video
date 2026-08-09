from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


CANVAS_SIZE = 1024
BACKGROUND = "#090A0C"
ACCENT = "#A8FF3E"
LINE = "#2A2E34"
DEPTH_TONES = ("#F4F6F1", "#C0C4C0", "#858B8A", "#4D5255", "#202328")


def create_icon() -> Image.Image:
    image = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (56, 56, 968, 968),
        radius=190,
        fill=BACKGROUND,
        outline=LINE,
        width=18,
    )

    bar_width = 82
    gap = 42
    bar_left = 205
    bar_bottom = 646
    heights = (172, 286, 410, 536)
    for index, height in enumerate(heights):
        left = bar_left + index * (bar_width + gap)
        draw.rounded_rectangle(
            (left, bar_bottom - height, left + bar_width, bar_bottom),
            radius=24,
            fill=ACCENT,
        )

    strip_left = 205
    strip_top = 724
    strip_width = 123
    for index, tone in enumerate(DEPTH_TONES):
        left = strip_left + index * strip_width
        draw.rectangle((left, strip_top, left + strip_width, strip_top + 76), fill=tone)

    return image


def save_iconset(image: Image.Image, output_dir: Path) -> None:
    iconset_dir = output_dir / "DepthVideo.iconset"
    iconset_dir.mkdir(parents=True, exist_ok=True)
    for size in (16, 32, 128, 256, 512):
        image.resize((size, size), Image.Resampling.LANCZOS).save(
            iconset_dir / f"icon_{size}x{size}.png"
        )
        retina_size = size * 2
        image.resize((retina_size, retina_size), Image.Resampling.LANCZOS).save(
            iconset_dir / f"icon_{size}x{size}@2x.png"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Depth Video desktop icons")
    parser.add_argument("--output-dir", type=Path, default=Path("assets"))
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    icon = create_icon()
    icon.resize((512, 512), Image.Resampling.LANCZOS).save(output_dir / "icon.png")
    icon.save(
        output_dir / "icon.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    save_iconset(icon, output_dir)
    print(f"Generated desktop icons in {output_dir}")


if __name__ == "__main__":
    main()
