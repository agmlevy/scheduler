"""
Copy schedule.ics to the GoDaddy site workspace for SFTP upload.

Usage:
  python publish_calendar.py
  npm run publish
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "schedule.ics"
# Site repo is sibling of dev/ (not inside schedule_automation's parent only)
SITE_ROOT = Path(
    os.environ.get(
        "GRASSROOTS_SITE_ROOT",
        str(ROOT.parent.parent / "grassroots-soccer-site"),
    )
)
DEST = SITE_ROOT / "schedule.ics"


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(
            f"Missing {SOURCE}. Run `npm run calendar` first to generate schedule.ics."
        )

    DEST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE, DEST)
    print(f"Copied {SOURCE.name} -> {DEST}")
    print("Upload via SFTP (save file or uploadOnSave) to publish on GoDaddy.")
    print("Subscribe URL: https://eastfloridaunited.com/schedule.ics")


if __name__ == "__main__":
    main()
