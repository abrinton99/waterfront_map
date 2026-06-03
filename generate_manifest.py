#!/usr/bin/env python3
"""
generate_manifest.py

Scans a folder of photos, extracts EXIF GPS coordinates, generates thumbnails,
and outputs photos.json.

Usage:
    python generate_manifest.py /path/to/photos

Expects an optional descriptions.csv in the scanned folder with columns:
    filename, description

Outputs photos.json and a thumbnails/ subfolder in the current working directory.
"""

import argparse
import csv
import json
import os
import sys
import warnings
from pathlib import Path

# ── Configurable ────────────────────────────────────────────────────────────
# Set this to the public base URL where your photos are hosted.
# Thumbnails are expected at <BASE_URL><stem>_thumb<ext>
# Full images are expected at <BASE_URL><filename>
BASE_URL = "https://abrinton99.github.io/waterfront_map/images/"

# Maximum pixel dimension (width or height) for generated thumbnails
THUMB_MAX_PX = 600

# Text written into descriptions.csv for newly discovered photos, so there's a
# row to fill in. Edit the description here, not the placeholder, on later runs.
PLACEHOLDER_DESCRIPTION = "TODO: add description"
# ────────────────────────────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".tiff"}

try:
    from PIL import Image, ImageOps
    from PIL.ExifTags import TAGS, GPSTAGS
except ImportError:
    sys.exit("Pillow is required. Install it with: pip install Pillow")


def dms_to_decimal(dms, ref):
    """Convert degrees/minutes/seconds tuple to decimal degrees."""
    degrees, minutes, seconds = dms
    # Pillow returns IFDRational objects; convert to float
    d = float(degrees)
    m = float(minutes)
    s = float(seconds)
    decimal = d + m / 60 + s / 3600
    if ref in ("S", "W"):
        decimal = -decimal
    return decimal


def extract_gps(image_path):
    """Return (lat, lng) or None if GPS data is absent or unreadable."""
    try:
        with Image.open(image_path) as img:
            exif_data = img._getexif()
    except Exception as exc:
        warnings.warn(f"Could not open {image_path}: {exc}")
        return None

    if exif_data is None:
        return None

    # Locate the GPSInfo tag
    gps_info_tag = next(
        (tag for tag, name in TAGS.items() if name == "GPSInfo"), None
    )
    if gps_info_tag is None or gps_info_tag not in exif_data:
        return None

    raw_gps = exif_data[gps_info_tag]
    gps = {GPSTAGS.get(k, k): v for k, v in raw_gps.items()}

    required = {"GPSLatitude", "GPSLatitudeRef", "GPSLongitude", "GPSLongitudeRef"}
    if not required.issubset(gps):
        return None

    try:
        lat = dms_to_decimal(gps["GPSLatitude"], gps["GPSLatitudeRef"])
        lng = dms_to_decimal(gps["GPSLongitude"], gps["GPSLongitudeRef"])
    except Exception as exc:
        warnings.warn(f"Could not parse GPS for {image_path}: {exc}")
        return None

    return lat, lng


def resolve_descriptions_path(folder):
    """Return the descriptions.csv path to read from and write placeholders to.
    Prefers an existing file in the photos folder, then an existing one in the
    current working directory; if neither exists, defaults to the cwd path
    (where it will be created)."""
    folder_csv = folder / "descriptions.csv"
    if folder_csv.exists():
        return folder_csv
    return Path.cwd() / "descriptions.csv"


def load_descriptions(csv_path):
    """Load filename→description mapping from the given descriptions.csv path."""
    descriptions = {}
    if not csv_path.exists():
        return descriptions
    print(f"  Loading descriptions from: {csv_path}")
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filename = row.get("filename", "").strip()
            description = row.get("description", "").strip()
            if filename:
                descriptions[filename] = description
    return descriptions


def append_placeholders(csv_path, filenames):
    """Append a placeholder row to descriptions.csv for each new filename,
    writing a header first if the file doesn't exist yet."""
    if not filenames:
        return
    write_header = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["filename", "description"])
        for filename in filenames:
            writer.writerow([filename, PLACEHOLDER_DESCRIPTION])
    print(f"  Added {len(filenames)} placeholder description(s) to: {csv_path}")


def build_urls(filename, thumb_subdir):
    """Return (thumbnail_url, full_url) for a given filename."""
    p = Path(filename)
    stem = p.stem
    ext = p.suffix
    subdir = f"{thumb_subdir}/" if thumb_subdir else ""
    thumbnail_url = f"{BASE_URL}{subdir}{stem}_thumb{ext}"
    full_url = f"{BASE_URL}{filename}"
    return thumbnail_url, full_url


def make_thumbnail(src_path, thumb_dir):
    """
    Resize src_path to fit within THUMB_MAX_PX on its longest side, preserving
    aspect ratio and EXIF orientation. Saves to thumb_dir/<stem>_thumb<ext>.
    Returns the output Path, or None on failure.
    """
    p = Path(src_path)
    out_path = thumb_dir / f"{p.stem}_thumb{p.suffix}"

    if out_path.exists():
        return out_path  # skip if already generated

    try:
        with Image.open(src_path) as img:
            # Honour EXIF rotation (important for phone photos)
            img = ImageOps.exif_transpose(img)

            # Convert palette/RGBA modes so JPEG save doesn't fail
            if img.mode in ("P", "RGBA"):
                img = img.convert("RGB")

            img.thumbnail((THUMB_MAX_PX, THUMB_MAX_PX), Image.LANCZOS)

            save_kwargs = {}
            if p.suffix.lower() in (".jpg", ".jpeg"):
                save_kwargs = {"quality": 82, "optimize": True}

            img.save(out_path, **save_kwargs)
    except Exception as exc:
        warnings.warn(f"Could not create thumbnail for {src_path}: {exc}")
        return None

    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate photos.json manifest and thumbnails from a folder of geotagged photos."
    )
    parser.add_argument("folder", help="Path to the folder containing photos")
    parser.add_argument(
        "-o",
        "--output",
        default="photos.json",
        help="Output file path (default: photos.json in current directory)",
    )
    parser.add_argument(
        "--thumbs-dir",
        default="thumbnails",
        help="Directory to write thumbnails into (default: thumbnails/)",
    )
    args = parser.parse_args()

    folder = Path(args.folder).expanduser().resolve()
    if not folder.is_dir():
        sys.exit(f"Error: '{folder}' is not a directory.")

    thumb_dir = folder / args.thumbs_dir
    thumb_dir.mkdir(parents=True, exist_ok=True)

    descriptions_path = resolve_descriptions_path(folder)
    descriptions = load_descriptions(descriptions_path)

    total = 0
    included = 0
    skipped = 0
    manifest = []
    new_files = []  # included photos with no descriptions.csv entry yet

    for path in sorted(folder.rglob("*")):
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if path.name.lower() == "descriptions.csv":
            continue
        # Skip files that are already thumbnails from a previous run
        if path.stem.endswith("_thumb"):
            continue

        total += 1
        gps = extract_gps(path)
        if gps is None:
            print(f"  [skip] {path.name} — no GPS data")
            skipped += 1
            continue

        thumb = make_thumbnail(path, thumb_dir)
        if thumb is None:
            print(f"  [skip] {path.name} — thumbnail generation failed")
            skipped += 1
            continue

        lat, lng = gps
        filename = path.name
        if filename not in descriptions:
            new_files.append(filename)
        description = descriptions.get(filename, "")
        thumbnail_url, full_url = build_urls(filename, args.thumbs_dir)

        manifest.append(
            {
                "filename": filename,
                "lat": round(lat, 7),
                "lng": round(lng, 7),
                "description": description,
                "thumbnail_url": thumbnail_url,
                "full_url": full_url,
            }
        )
        included += 1
        print(f"  [ok]   {path.name}")

    output_path = Path(args.output)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    append_placeholders(descriptions_path, new_files)

    print(f"\nDone.")
    print(f"  Manifest  : {output_path.resolve()}")
    print(f"  Thumbnails: {thumb_dir.resolve()}")
    print(f"  Total scanned : {total}")
    print(f"  Included      : {included}")
    print(f"  Skipped       : {skipped}")
    print(f"  New (placeholder added): {len(new_files)}")


if __name__ == "__main__":
    main()
