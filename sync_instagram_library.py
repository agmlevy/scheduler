"""Sync instagram_drill_library.json URLs into session_themes.json (no CSV needed)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIBRARY_PATH = ROOT / "instagram_drill_library.json"
THEMES_PATH = ROOT / "session_themes.json"


def main() -> None:
    library = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    themes_doc = json.loads(THEMES_PATH.read_text(encoding="utf-8"))
    urls_by_theme: dict[str, list[str]] = {}
    for drill in library.get("drills", []):
        urls_by_theme.setdefault(drill["theme"], []).append(drill["url"])

    for theme_key, theme in themes_doc.get("themes", {}).items():
        theme["instagramUrls"] = urls_by_theme.get(theme_key, [])

    themes_doc["meta"]["instagramDrillLibrary"] = LIBRARY_PATH.name
    THEMES_PATH.write_text(json.dumps(themes_doc, indent=2), encoding="utf-8")
    print(f"Synced {sum(len(v) for v in urls_by_theme.values())} URLs into session themes")


if __name__ == "__main__":
    main()
