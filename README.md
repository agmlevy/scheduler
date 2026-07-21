# schedule-automation

Homeschool and soccer training/game schedule automation.

## Files

### Schedule Data
- `lesson_schedule.json` - Academic lesson schedule
- `training_schedule.json` - Soccer training sessions
- `games_schedule.json` - EFU U14B 2012/13 N1 game schedule (N1 Southeast District 2, FCL 2026-2027)

### Calendar Exports
- `schedule.ics` - Full calendar (lessons + training + games)
- `games_schedule.ics` - Games-only calendar for sharing with team and parents

## Usage

Generate calendar files:
```bash
npm install
node calendar_export.js        # Full schedule
node games_calendar_export.js  # Games only (for team/parent sharing)
```

## Game Schedule (2026-2027 Season)

EFU U14B 2012/13 N1 - N1 Southeast District 2 (FCL)

| Date | Time | Opponent | Home/Away |
|------|------|----------|-----------|
| Aug 22, 2026 | 8:00 AM | N1 B2012/13 (FL) | Away |
| Aug 29, 2026 | 8:00 AM | 2014Elite Colo Colo | Away |
| Sep 12, 2026 | 8:00 AM | 14UB BULLS N1 | Home |
| Sep 19, 2026 | 8:00 AM | N1 B2012/13 JPA (FL) | Home |
| Sep 26, 2026 | 8:00 AM | Schulz Academy 2013 N1 (FL) | Away |
| Sep 27, 2026 | 8:00 AM | N1 B2012/13 Black (FL) | Home |
| Oct 03, 2026 | 8:00 AM | 14UB BULLS N1 | Away |
| Oct 17, 2026 | 8:00 AM | PBU N1 B2012/13 (FL) | Home |
| Oct 24, 2026 | 8:00 AM | 2013 Boys Tiempo N1 (FL) | Away |
| Oct 31, 2026 | 8:00 AM | 2014Elite Colo Colo | Home |
| Feb 20, 2027 | 7:00 AM | 2013 Boys Tiempo N1 (FL) | Home |
| Feb 21, 2027 | 7:00 AM | N1 B2012/13 (FL) | Home |
| Mar 06, 2027 | 7:00 AM | Schulz Academy 2013 N1 (FL) | Home |
| Mar 07, 2027 | 7:00 AM | N1 B2012/13 Black (FL) | Away |
| Mar 13, 2027 | 7:00 AM | PBU N1 B2012/13 (FL) | Away |
| Apr 03, 2027 | 8:00 AM | N1 B2012/13 JPA (FL) | Away |