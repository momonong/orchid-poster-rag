"""Render complete poster sections directly from the registered PDF; no model or service is used."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pymupdf as fitz
from PIL import Image

SECTION_KEYS = ("intro", "methods", "clue1", "clue2", "clue3", "discussion", "references", "supplementary")
DISCUSSION_AND_CONCLUSIONS = [0.703, 0.209, 0.977, 0.557]
EXTRA_REGIONS = {"references": [0.703, 0.559, 0.977, 0.640],
                 "supplementary": [0.703, 0.644, 0.977, 1.000]}


def build(root: Path, only: str | None = None) -> Path:
    root = root.resolve()
    registered = json.loads((root / "data" / "sources.json").read_text(encoding="utf-8"))["poster"]
    source = (root / registered["path"]).resolve()
    if not source.is_relative_to(root):
        raise ValueError("The registered poster must remain inside the project root.")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != registered["sha256"]:
        raise ValueError("Poster SHA-256 does not match data/sources.json; no assets were written.")
    output = root / ".orchid" / "assets" / "tour-preview"
    output.mkdir(parents=True, exist_ok=True)
    document = fitz.open(source)
    try:
        page = document[0]
        manifest = {
            "schema": 1,
            "source_document": "poster",
            "source_sha256": digest,
            "page": 1,
            "page_size_points": [page.rect.width, page.rect.height],
            "format": "lossless WebP",
            "note": "PDF text/vector detail is preserved at the rendered resolution; embedded raster figures retain their native-detail limit.",
            "images": {},
        }
        if only:
            previous = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            if previous["source_sha256"] != digest:
                raise ValueError("Selective rebuild needs a manifest from this exact PDF.")
            manifest["images"] = previous["images"]
        regions = {key: registered["regions"][key] for key in SECTION_KEYS if key in registered["regions"]}
        regions.update(EXTRA_REGIONS)
        regions["discussion"] = DISCUSSION_AND_CONCLUSIONS
        for key, bounds in {"overview": [0, 0, 1, 1], **regions}.items():
            if only and key != only:
                continue
            left, top, right, bottom = bounds
            clip = fitz.Rect(left * page.rect.width, top * page.rect.height,
                             right * page.rect.width, bottom * page.rect.height)
            widths = (800, 1600) if key == "overview" else (800, 1600, 2400)
            item = {"bounds": bounds, "variants": [], "poster_text": page.get_text("text", clip=clip).strip()}
            if key == "discussion":
                item["bounds_note"] = "Extends the registered Discussion region through Conclusions, before References."
            for target_width in widths:
                scale = target_width / clip.width
                pixels = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip,
                                         colorspace=fitz.csRGB, alpha=False)
                filename = f"{key}-{target_width}.webp"
                path = output / filename
                image = Image.frombytes("RGB", (pixels.width, pixels.height), pixels.samples)
                image.save(path, "WEBP", lossless=True, exact=True, method=5)
                item["variants"].append({"url": f"/assets/tour-preview/{filename}",
                                         "width": pixels.width, "height": pixels.height,
                                         "bytes": path.stat().st_size})
            manifest["images"][key] = item
            print(f"{key}: " + ", ".join(f"{v['width']}x{v['height']} ({v['bytes']} bytes)" for v in item["variants"]))
        destination = output / "manifest.json"
        destination.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return destination
    finally:
        document.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--only", choices=SECTION_KEYS, help="Rebuild one section in an existing matching manifest.")
    arguments = parser.parse_args()
    print(build(arguments.root, arguments.only))
