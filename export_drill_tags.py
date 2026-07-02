"""
Export instagram_drill_library.json to drill_tags.csv for tagging in Excel.
Import back with import_drill_tags.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIBRARY_PATH = ROOT / "instagram_drill_library.json"
CSV_PATH = ROOT / "drill_tags.csv"


def export_csv() -> None:
    library = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    rows = library.get("drills", [])
    delimiter = "|"
    if CSV_PATH.exists():
        first = CSV_PATH.read_text(encoding="utf-8-sig").splitlines()[:1]
        if first and "," in first[0] and first[0].count(",") > first[0].count("|"):
            delimiter = ","
    with CSV_PATH.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["id", "theme", "url", "tags", "notes"],
            delimiter=delimiter,
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "id": row["id"],
                    "theme": row["theme"],
                    "url": row["url"],
                    "tags": "; ".join(row.get("tags") or []),
                    "notes": row.get("notes", ""),
                }
            )
    print(f"Wrote {len(rows)} rows to {CSV_PATH} (delimiter: {repr(delimiter)})")


if __name__ == "__main__":
    export_csv()
