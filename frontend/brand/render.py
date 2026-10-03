"""Render the PWA icons from the SVG sources.

Usage: python render.py
Needs any Python with cairosvg; the PNGs are committed, so building the app does not.
"""

import shutil
from pathlib import Path

import cairosvg

BRAND = Path(__file__).parent
PUBLIC = BRAND.parent / "public"

# (source svg, output file, size in px)
ICONS = [
    ("icon.svg", "pwa-192x192.png", 192),
    ("icon.svg", "pwa-512x512.png", 512),
    ("icon.svg", "apple-touch-icon.png", 180),
    ("icon-maskable.svg", "maskable-512x512.png", 512),
]


def main() -> None:
    PUBLIC.mkdir(exist_ok=True)
    for source_name, output, size in ICONS:
        source = BRAND / source_name
        cairosvg.svg2png(
            url=str(source), write_to=str(PUBLIC / output), output_width=size, output_height=size
        )
    shutil.copy(BRAND / "icon.svg", PUBLIC / "favicon.svg")
    print(f"Rendered icons into {PUBLIC}")


if __name__ == "__main__":
    main()
