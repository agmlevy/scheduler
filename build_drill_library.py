import json
import re
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent
VIDEOS_ROOT = ROOT / "videos"


def extract_pdf_catalog(pdf_path: Path) -> dict:
    reader = PdfReader(str(pdf_path))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    rel = pdf_path.relative_to(ROOT).as_posix()

    named = []
    for pattern in [
        r"\n([A-Z][A-Za-z0-9 /\-]{3,50}(?:Rondo|Drill|Warm-ups?|Decisions))\n",
        r"\n([A-Z][^\n]{4,60})\nWHY USE IT",
    ]:
        for match in re.finditer(pattern, text):
            title = match.group(1).strip()
            if "SoccerCoach" not in title and title not in named:
                named.append(title)

    for match in re.finditer(r"DRILL\s*(\d+)", text, re.I):
        title = f"DRILL {match.group(1)}"
        if title not in named:
            named.append(title)

    for title in [
        "Cone Countdown",
        "Half Field Possession",
        "Basic Ball Control",
        "Effective Marking",
        "Defending in Small Groups",
        "Individual and Team Defending",
        "Anatomy Dribble",
        "The Tuck Jump",
        "Advance Your Simple Rondo",
        "Simple Rondo",
        "Final Pass Rondo",
        "Pressing Rondo",
        "Combination Rondo",
        "Control Game Rondo",
        "Rondo Shoot On Sight",
        "6v4 Play Out Rondo",
        "7v4 Creating Space Rondo",
        "5v2 Pass and Move Rondo",
        "2v1/1v1 Decisions Rondo",
    ]:
        if title.lower() in text.lower() and title not in named:
            named.append(title)

    theme_keywords = {
        "possession": r"possession",
        "pressing": r"press(?:ing)?",
        "rondos": r"rondo",
        "finishing": r"finish|shoot(?:ing)?|scor(?:e|ing)",
        "defending": r"defend|defensive",
        "passing": r"pass(?:ing)?",
        "agility": r"agility|movement off the ball",
        "dribbling": r"dribbl",
        "goalkeeping": r"goalkeeper|keeper",
        "endurance": r"endurance|conditioning|fitness",
        "warm-up": r"warm[\s-]?up",
        "tactical": r"tactical|overload|line.?break",
    }
    lower = text.lower()
    themes = [theme for theme, pat in theme_keywords.items() if re.search(pat, lower)]

    return {
        "relativePath": rel,
        "filename": pdf_path.name,
        "pageCount": len(reader.pages),
        "namedDrills": sorted(set(named), key=str.lower),
        "themes": themes,
        "characterCount": len(text),
    }


def build_video_entries() -> tuple[list[dict], dict, dict, dict]:
    entries = []
    by_category = {}
    by_pack = {}
    prefix_by_cat = {}

    for mp4 in sorted(VIDEOS_ROOT.rglob("*.mp4")):
        rel = mp4.relative_to(ROOT).as_posix()
        parts = mp4.relative_to(VIDEOS_ROOT).parts
        category = mp4.parent.name
        pack = parts[0] if parts else "unknown"
        stem = mp4.stem.lstrip("!")
        prefix_match = re.match(r"^([a-z]+)_", stem, re.I)
        id_prefix = prefix_match.group(1).lower() if prefix_match else "unknown"

        entries.append(
            {
                "id": stem,
                "filename": mp4.name,
                "category": category,
                "pack": pack,
                "relativePath": rel,
                "idPrefix": id_prefix,
            }
        )
        by_category[category] = by_category.get(category, 0) + 1
        by_pack[pack] = by_pack.get(pack, 0) + 1
        prefix_by_cat.setdefault(category, {})
        prefix_by_cat[category][id_prefix] = prefix_by_cat[category].get(id_prefix, 0) + 1

    return entries, by_category, by_pack, prefix_by_cat


def verify_categories(by_category: dict, pdf_catalog: list[dict]) -> dict:
    category_theme_map = {
        "Agility Drills": ["agility", "warm-up", "rondos"],
        "Defensive Drills": ["defending", "pressing"],
        "Endurance Drills": ["endurance"],
        "Finishing Drills": ["finishing"],
        "Goalkeeper Drills": ["goalkeeping"],
        "Passing Drills": ["passing", "possession", "rondos"],
        "Dribbling & Agility": ["dribbling", "agility"],
        "Finishing": ["finishing"],
    }
    all_pdf_themes = {theme for pdf in pdf_catalog for theme in pdf["themes"]}
    verification = {}

    for category, expected in category_theme_map.items():
        matched = [theme for theme in expected if theme in all_pdf_themes]
        count = by_category.get(category, 0)
        if count == 0:
            status = "empty"
        elif matched:
            status = "verified"
        else:
            status = "unverified"

        note = None
        if category == "Endurance Drills" and not matched:
            note = "No endurance-specific content in the 3 bonus PDFs; category exists only in video folders."

        verification[category] = {
            "videoCount": count,
            "expectedThemes": expected,
            "matchedPdfThemes": matched,
            "status": status,
            "note": note,
        }

    return verification


def write_verification_md(library: dict) -> None:
    lines = [
        "# Drill Library Verification",
        "",
        f"Generated: {library['generatedAt']}",
        "",
        "## Video catalog",
        f"- **{library['summary']['totalVideos']}** MP4 files across **{len(library['summary']['categories'])}** categories",
        "",
    ]
    for category, count in sorted(library["summary"]["categories"].items()):
        item = library["categoryVerification"][category]
        lines.append(f"- {category}: {count} videos — **{item['status']}**")
        if item["matchedPdfThemes"]:
            lines.append(f"  - PDF themes: {', '.join(item['matchedPdfThemes'])}")
        if item["note"]:
            lines.append(f"  - Note: {item['note']}")

    lines.extend(["", "## PDF sources"])
    for pdf in library["pdfCatalog"]:
        lines.append(f"### {pdf['filename']}")
        lines.append(f"- Pages: {pdf['pageCount']} | Themes: {', '.join(pdf['themes'])}")
        lines.append(f"- Named drills/sessions extracted: **{len(pdf['namedDrills'])}**")
        if pdf["namedDrills"]:
            lines.append("- Samples: " + "; ".join(pdf["namedDrills"][:10]))
        lines.append("")

    (ROOT / "drill_library_verification.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    pdf_catalog = [extract_pdf_catalog(pdf) for pdf in sorted(VIDEOS_ROOT.rglob("*.pdf"))]
    entries, by_category, by_pack, prefix_by_cat = build_video_entries()
    verification = verify_categories(by_category, pdf_catalog)

    library = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "totalVideos": len(entries),
            "totalPdfs": len(pdf_catalog),
            "categories": dict(sorted(by_category.items())),
            "packs": dict(sorted(by_pack.items())),
            "idPrefixesByCategory": prefix_by_cat,
        },
        "pdfCatalog": pdf_catalog,
        "categoryVerification": verification,
        "videos": entries,
    }

    (ROOT / "drill_library.json").write_text(json.dumps(library, indent=2), encoding="utf-8")
    write_verification_md(library)

    print(f"Wrote {len(entries)} videos, {len(pdf_catalog)} PDFs")
    for pdf in pdf_catalog:
        print(f"  {pdf['filename']}: {len(pdf['namedDrills'])} named drills")


if __name__ == "__main__":
    main()
