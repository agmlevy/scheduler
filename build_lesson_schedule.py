"""
Retime homeschool lessons into the morning stack.

Reads schedule.json (legacy lesson plan) + school_config.json → lesson_schedule.json
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE_PATH = ROOT / "schedule.json"
SCHOOL_CONFIG_PATH = ROOT / "school_config.json"
OUTPUT_PATH = ROOT / "lesson_schedule.json"


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def is_lesson(item: dict) -> bool:
    if item.get("type") == "Training":
        return False
    if item.get("type") == "Lesson":
        return True
    return bool(item.get("subject")) and item.get("type") not in {"Training", "Recovery"}


def load_source_lessons() -> dict[str, list[dict]]:
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    by_date: dict[str, list[dict]] = {}
    for item in source:
        if not is_lesson(item):
            continue
        by_date.setdefault(item["date"], []).append(item)
    for lessons in by_date.values():
        lessons.sort(key=lambda row: row.get("timeStart", ""))
    return by_date


def generate() -> list[dict]:
    school = json.loads(SCHOOL_CONFIG_PATH.read_text(encoding="utf-8"))
    by_date = load_source_lessons()
    slots_by_weekday = {int(k): v for k, v in school["weekdaySlots"].items()}

    schedule: list[dict] = []
    for day, lessons in sorted(by_date.items()):
        weekday = parse_date(day).weekday()
        slots = slots_by_weekday.get(weekday, [])
        for slot in slots:
            index = slot["lessonIndex"]
            if index >= len(lessons):
                continue
            lesson = lessons[index]
            schedule.append(
                {
                    "activity": lesson.get("activity", "Lesson"),
                    "subject": lesson.get("subject", lesson.get("activity", "Lesson")),
                    "date": day,
                    "timeStart": slot["timeStart"],
                    "durationHours": slot["durationHours"],
                    "type": "Lesson",
                    "details": lesson.get("details", f"{lesson.get('subject', 'Lesson')} homeschool lesson"),
                }
            )
    return schedule


def main() -> None:
    schedule = generate()
    OUTPUT_PATH.write_text(json.dumps(schedule, indent=2), encoding="utf-8")
    print(f"Wrote {len(schedule)} morning lesson blocks to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
