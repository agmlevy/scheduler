"""
Generate themed training blocks (~50 min sessions + evening drill snacks).

Reads session_themes.json + training_config.json and writes training_schedule.json.
School lessons stay in schedule.json; calendar_export.js merges both files.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
THEMES_PATH = ROOT / "session_themes.json"
CONFIG_PATH = ROOT / "training_config.json"
OUTPUT_PATH = ROOT / "training_schedule.json"
INSTAGRAM_LIBRARY_PATH = ROOT / "instagram_drill_library.json"


def load_instagram_drills(theme_key: str) -> list[dict]:
    if not INSTAGRAM_LIBRARY_PATH.exists():
        return []
    library = json.loads(INSTAGRAM_LIBRARY_PATH.read_text(encoding="utf-8"))
    return [d for d in library.get("drills", []) if d.get("theme") == theme_key]


def format_drill_links(theme_key: str, fallback_urls: list[str]) -> list[str]:
    drills = load_instagram_drills(theme_key)
    if drills:
        lines: list[str] = []
        by_tag: dict[str, list[dict]] = {}
        untagged: list[dict] = []
        for drill in drills:
            tags = drill.get("tags") or []
            if tags:
                label = ", ".join(tags)
                by_tag.setdefault(label, []).append(drill)
            else:
                untagged.append(drill)

        for label in sorted(by_tag):
            lines.append(f"[{label}]")
            for drill in by_tag[label]:
                note = f" — {drill['notes']}" if drill.get("notes") else ""
                lines.append(f"  • {drill['url']}{note}")

        if untagged:
            if by_tag:
                lines.append("[untagged — add tags in drill_tags.csv]")
            for drill in untagged:
                note = f" — {drill['notes']}" if drill.get("notes") else ""
                lines.append(f"• {drill['url']}{note}")
        return lines

    if fallback_urls:
        return [f"• {url}" for url in fallback_urls]
    return []


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def week_index(start: date, current: date) -> int:
    return (current - start).days // 7


def build_details(theme: dict, variation: dict, variation_week: int) -> str:
    lines = [
        f"Week {variation_week + 1} focus: {variation['label']}",
        variation["emphasis"],
        "",
        "Session structure:",
    ]
    for block in theme.get("structure", []):
        lines.append(f"• {block['block']} ({block['minutes']} min) — {block['notes']}")

    link_lines = format_drill_links(theme.get("_key", ""), theme.get("instagramUrls") or [])
    if link_lines:
        lines.extend(["", "Instagram drill library:"])
        lines.extend(link_lines)
    else:
        lines.extend(
            [
                "",
                "Instagram drill library: add links in instagram_drill_library.json "
                f"or session_themes.json → {theme.get('_key', 'theme')}.instagramUrls",
            ]
        )

    focus = theme.get("focus") or []
    if focus:
        lines.extend(["", "Theme focus: " + ", ".join(focus)])

    return "\n".join(lines)


def session_type(theme_key: str) -> str:
    if theme_key == "yoga_stretch":
        return "Recovery"
    return "Training"


def duration_minutes(theme_key: str, theme: dict, meta: dict) -> int:
    if theme_key == "yoga_stretch":
        return theme.get("durationMinutes") or meta.get("yogaStretchMinutes", 15)
    if theme_key == "drill_snacks":
        return theme.get("durationMinutes") or meta.get("drillSnackMinutes", 20)
    return theme.get("durationMinutes") or meta.get("sessionLengthMinutes", 50)


def append_session(
    schedule: list[dict],
    *,
    current: date,
    start: date,
    theme_key: str,
    theme: dict,
    time_start: str,
    cycle: int,
    meta: dict,
    slot: str | None = None,
) -> None:
    variations = theme.get("variations") or [{"label": "Standard", "emphasis": ""}]
    v_index = week_index(start, current) % min(len(variations), cycle)
    variation = variations[v_index % len(variations)]
    minutes = duration_minutes(theme_key, theme, meta)

    schedule.append(
        {
            "activity": theme["title"],
            "subject": "Soccer" if theme_key != "yoga_stretch" else "Recovery",
            "sessionTheme": theme_key,
            "sessionSlot": slot,
            "variationWeek": (week_index(start, current) % cycle) + 1,
            "variationLabel": variation["label"],
            "date": current.isoformat(),
            "timeStart": time_start,
            "durationHours": round(minutes / 60, 4),
            "durationMinutes": minutes,
            "type": session_type(theme_key),
            "location": theme.get("location", "Training Field"),
            "details": build_details(theme, variation, v_index),
        }
    )


def generate() -> list[dict]:
    themes_doc = json.loads(THEMES_PATH.read_text(encoding="utf-8"))
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    themes = themes_doc["themes"]
    meta = themes_doc["meta"]
    cycle = meta["variationCycleWeeks"]

    start = parse_date(config["startDate"])
    end = parse_date(config["endDate"])
    rest_days = set(config.get("restDays", []))

    sessions_by_weekday: dict[int, list[dict]] = {}
    for entry in config.get("weeklySessions", []):
        sessions_by_weekday.setdefault(entry["weekday"], []).append(entry)

    daily_sessions = config.get("dailySessions", [])

    schedule: list[dict] = []
    current = start
    while current <= end:
        weekday = current.weekday()

        for daily in daily_sessions:
            theme_key = daily["theme"]
            theme = dict(themes[theme_key])
            theme["_key"] = theme_key
            append_session(
                schedule,
                current=current,
                start=start,
                theme_key=theme_key,
                theme=theme,
                time_start=daily["timeStart"],
                cycle=cycle,
                meta=meta,
                slot="daily",
            )

        if weekday not in rest_days:
            for session in sessions_by_weekday.get(weekday, []):
                theme_key = session["theme"]
                theme = dict(themes[theme_key])
                theme["_key"] = theme_key
                append_session(
                    schedule,
                    current=current,
                    start=start,
                    theme_key=theme_key,
                    theme=theme,
                    time_start=session["timeStart"],
                    cycle=cycle,
                    meta=meta,
                    slot=session.get("slot"),
                )

        current += timedelta(days=1)

    return schedule


def main() -> None:
    schedule = generate()
    OUTPUT_PATH.write_text(json.dumps(schedule, indent=2), encoding="utf-8")
    print(f"Wrote {len(schedule)} themed training blocks to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
