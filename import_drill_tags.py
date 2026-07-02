"""
Import tags from drill_tags.csv into instagram_drill_library.json
and sync URLs into session_themes.json.

Supports comma- or pipe-delimited CSV (Excel sometimes saves as pipe).
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIBRARY_PATH = ROOT / "instagram_drill_library.json"
CSV_PATH = ROOT / "drill_tags.csv"
THEMES_PATH = ROOT / "session_themes.json"


def detect_delimiter(text: str) -> str:
    first_line = text.splitlines()[0] if text.splitlines() else ""
    if "|" in first_line and first_line.count("|") >= first_line.count(","):
        return "|"
    return ","


def parse_tags(value: str) -> list[str]:
    if not value or not str(value).strip():
        return []
    parts = re.split(r"[;:]", str(value))
    return [part.strip() for part in parts if part.strip()]


def import_csv() -> dict:
    library = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    if not CSV_PATH.exists():
        raise SystemExit(f"Missing {CSV_PATH}. Run: python export_drill_tags.py")

    raw = CSV_PATH.read_text(encoding="utf-8-sig")
    delimiter = detect_delimiter(raw)
    drills: list[dict] = []

    with CSV_PATH.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        for row in reader:
            drill_id = (row.get("id") or "").strip()
            if not drill_id:
                continue
            drills.append(
                {
                    "id": drill_id,
                    "theme": (row.get("theme") or "").strip(),
                    "url": (row.get("url") or "").strip(),
                    "tags": parse_tags(row.get("tags", "")),
                    "notes": (row.get("notes") or "").strip(),
                }
            )

    library["drills"] = drills
    LIBRARY_PATH.write_text(json.dumps(library, indent=2), encoding="utf-8")
    return library


def sync_themes(library: dict) -> None:
    themes_doc = json.loads(THEMES_PATH.read_text(encoding="utf-8"))
    urls_by_theme: dict[str, list[str]] = {}
    for drill in library.get("drills", []):
        theme = drill["theme"]
        urls_by_theme.setdefault(theme, []).append(drill["url"])

    for theme_key, theme in themes_doc.get("themes", {}).items():
        theme["instagramUrls"] = urls_by_theme.get(theme_key, [])

    themes_doc["meta"]["instagramDrillLibrary"] = LIBRARY_PATH.name
    THEMES_PATH.write_text(json.dumps(themes_doc, indent=2), encoding="utf-8")
    print(f"Synced instagramUrls into {THEMES_PATH.name}")


def main() -> None:
    library = import_csv()
    sync_themes(library)
    tagged = sum(1 for d in library["drills"] if d.get("tags"))
    print(
        f"Imported {len(library['drills'])} drills; "
        f"{tagged} tagged, {len(library['drills']) - tagged} untagged"
    )


if __name__ == "__main__":
    main()
