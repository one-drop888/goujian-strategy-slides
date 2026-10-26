#!/usr/bin/env python3
"""Compose the 1280x640 repository social preview from actual render PNGs."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 640
BG = "#0d1726"
PANEL = "#132238"
BORDER = "#2b4260"
TEXT = "#f4f7fb"
MUTED = "#9fb0c7"
ACCENT = "#e0a13a"
FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
TITLE = "Goujian Strategy Slides"
SUBTITLE = "Analytical visual intelligence for strategy decks"
EYEBROW = "Native PPTX  ·  data-faithful charts  ·  structural QA"
FOOTER_LINES = (
    "Actual LibreOffice renders of synthetic V1.3 fixtures — no mockups or stock assets.",
    "Rendered from generated PPTX files; source render hashes are in the companion JSON.",
)
STATUS_MARKERS = ("NOT_RUN", "PASS", "FAIL", "visual review", "review status")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def font(name, size):
    return ImageFont.truetype(str(FONT_DIR / name), size)


def fit(img, width, height):
    scale = max(width / img.width, height / img.height)
    resized = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--meta", required=True)
    parser.add_argument("--title", default=TITLE)
    parser.add_argument("--subtitle", default=SUBTITLE)
    parser.add_argument("--source", action="append", required=True,
                        help="label|png path|slide number")
    args = parser.parse_args()
    if len(args.source) != 3:
        raise SystemExit("exactly three --source entries are required")

    sources = []
    thumbs = []
    for entry in args.source:
        label, path, page = entry.split("|")
        if Path(path).is_absolute() or ".." in Path(path).parts:
            raise SystemExit(f"source path must be repository-relative: {path}")
        file = Path(path)
        if not file.is_file():
            raise SystemExit(f"missing render: {file}")
        image = Image.open(file).convert("RGB")
        thumbs.append((label, fit(image, 360, 203)))
        sources.append({"label": label, "path": path, "page": int(page),
                        "width": image.width, "height": image.height, "sha256": sha256(file)})

    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, W, 8), fill=ACCENT)
    draw.text((60, 54), args.title, font=font("DejaVuSans-Bold.ttf", 54), fill=TEXT)
    draw.text((60, 126), args.subtitle, font=font("DejaVuSans.ttf", 26), fill=MUTED)
    draw.text((60, 174), EYEBROW, font=font("DejaVuSans.ttf", 20), fill=ACCENT)

    for index, (label, thumb) in enumerate(thumbs):
        x = 60 + index * 400
        y = 250
        draw.rectangle((x, y, x + 360, y + 203), fill=PANEL, outline=BORDER, width=2)
        canvas.paste(thumb, (x, y))
        draw.text((x, y + 216), label, font=font("DejaVuSans-Bold.ttf", 18), fill=TEXT)

    for offset, line in enumerate(FOOTER_LINES):
        draw.text((60, 552 + offset * 30), line, font=font("DejaVuSans.ttf", 18 if offset == 0 else 16),
                  fill=MUTED)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, format="PNG", optimize=True)
    meta = {
        "schema_version": "1.3",
        "purpose": "GitHub repository social preview; uploaded manually, no repository settings were changed.",
        "size": {"width": W, "height": H},
        "sha256": sha256(out),
        "bytes": out.stat().st_size,
        "title": args.title,
        "subtitle": args.subtitle,
        "sources": sources,
        "review": {"status": "NOT_RUN", "note": "Documentation composition from actual renders; not a visual approval."},
        "manual_steps": [
            "Upload this PNG at GitHub repository Settings > General > Social preview.",
            "Keep the repository settings unchanged until the release candidate is accepted.",
        ],
    }
    Path(args.meta).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "sha256": meta["sha256"], "sources": len(sources)}))


if __name__ == "__main__":
    main()
