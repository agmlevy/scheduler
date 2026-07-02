"""
Generate themed training blocks (~50 min sessions + sequence-based drill sessions).

Reads session_themes.json + training_config.json and writes training_schedule.json.
School lessons stay in schedule.json; calendar_export.js merges both files.

Sequence schedule (Mon-Thu):
  - a (plyometrics): everyday
  - g (ball mastery): Tue/Thu after 'a'
  - b/c (coordination): Mon/Wed after 'a'
  - e (wall passes): last everyday
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


def load_all_drills() -> list[dict]:
    if not INSTAGRAM_LIBRARY_PATH.exists():
        return []
    library = json.loads(INSTAGRAM_LIBRARY_PATH.read_text(encoding="utf-8"))
    return library.get("drills", [])


def load_instagram_drills(theme_key: str) -> list[dict]:
    if not INSTAGRAM_LIBRARY_PATH.exists():
        return []
    library = json.loads(INSTAGRAM_LIBRARY_PATH.read_text(encoding="utf-8"))
    return [d for d in library.get("drills", []) if d.get("theme") == theme_key]


def get_drills_by_sequence(all_drills: list[dict], sequence_prefix: str) -> list[dict]:
    """Get drills matching a sequence prefix (e.g., 'a' matches 'a1', 'a2', etc.)."""
    matching = []
    for drill in all_drills:
        seq = drill.get("sequence", "")
        if seq and (seq == sequence_prefix or seq.startswith(sequence_prefix)):
            matching.append(drill)
    matching.sort(key=lambda d: d.get("sequence", ""))
    return matching


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


def format_sequence_drills(drills: list[dict]) -> list[str]:
    """Format drills for a sequence block, sorted by sequence and showing minutes."""
    lines: list[str] = []
    for drill in drills:
        seq = drill.get("sequence", "?")
        minutes = drill.get("minutes")
        time_str = f" ({minutes} min)" if minutes else ""
        tags = drill.get("tags") or []
        tag_str = f" [{', '.join(tags)}]" if tags else ""
        note = f" — {drill['notes']}" if drill.get("notes") else ""
        lines.append(f"• [{seq}]{time_str}{tag_str} {drill['url']}{note}")
    return lines


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


def build_sequence_details(
    sequence_groups: list[str],
    all_drills: list[dict],
    seq_config: dict,
) -> tuple[str, int]:
    """Build details text for a sequence-based session and calculate total minutes."""
    lines: list[str] = ["Drill sequence for today:", ""]
    total_minutes = 0

    for seq_group in sequence_groups:
        drills = get_drills_by_sequence(all_drills, seq_group)
        if not drills:
            continue

        group_minutes = sum(d.get("minutes") or 0 for d in drills)
        total_minutes += group_minutes

        lines.append(f"[{seq_group.upper()}] — {group_minutes} min total")
        lines.extend(format_sequence_drills(drills))
        lines.append("")

    if total_minutes == 0:
        total_minutes = 50

    return "\n".join(lines), total_minutes


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
    meals = config.get("meals", [])
    sequence_schedule = config.get("sequenceSchedule", {})
    seq_weekdays = sequence_schedule.get("weekdays", {})
    seq_config = sequence_schedule.get("sequences", {})

    all_drills = load_all_drills()

    schedule: list[dict] = []
    current = start
    while current <= end:
        weekday = current.weekday()

        # Add meals for every day
        for meal in meals:
            minutes = meal.get("durationMinutes", 30)
            schedule.append(
                {
                    "activity": meal["name"],
                    "subject": "Nutrition",
                    "sessionTheme": "meal",
                    "sessionSlot": "meal",
                    "date": current.isoformat(),
                    "timeStart": meal["timeStart"],
                    "durationHours": round(minutes / 60, 4),
                    "durationMinutes": minutes,
                    "type": "Meal",
                    "location": "Home",
                    "details": meal.get("description", ""),
                }
            )

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
            weekday_sequences = seq_weekdays.get(str(weekday), [])
            if weekday_sequences:
                details, total_minutes = build_sequence_details(
                    weekday_sequences, all_drills, seq_config
                )
                first_seq = seq_config.get(weekday_sequences[0], {})
                time_start = first_seq.get("timeStart") or "07:15"

                schedule.append(
                    {
                        "activity": "Drill Sequences",
                        "subject": "Soccer",
                        "sessionTheme": "sequence_drills",
                        "sessionSlot": "primary",
                        "sequences": weekday_sequences,
                        "date": current.isoformat(),
                        "timeStart": time_start,
                        "durationHours": round(total_minutes / 60, 4),
                        "durationMinutes": total_minutes,
                        "type": "Training",
                        "location": "Training Field",
                        "details": details,
                    }
                )

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
