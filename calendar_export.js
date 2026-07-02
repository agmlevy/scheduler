const fs = require('fs');
const crypto = require('crypto');
const { writeFileSync } = require('fs');
const { createEvents } = require('ics');

const TIMEZONE = 'America/New_York';

function generateUID(item) {
  // Create consistent UID based on date, time, and activity
  const key = `${item.date}-${item.timeStart}-${item.activity}`;
  const hash = crypto.createHash('md5').update(key).digest('hex').slice(0, 16);
  return `${hash}@homeschool-schedule`;
}

function loadJson(path) {
  if (!fs.existsSync(path)) {
    return [];
  }
  return JSON.parse(fs.readFileSync(path, 'utf-8'));
}

const lessons = loadJson('./lesson_schedule.json');
const themedTraining = loadJson('./training_schedule.json');
const schedule = [...lessons, ...themedTraining].sort((a, b) => {
  const dateCompare = a.date.localeCompare(b.date);
  if (dateCompare !== 0) {
    return dateCompare;
  }
  return a.timeStart.localeCompare(b.timeStart);
});

const events = schedule.map((item) => {
  const [year, month, day] = item.date.split('-').map(Number);
  const [hour, minute] = item.timeStart.split(':').map(Number);
  const durationHours = Math.floor(item.durationHours);
  const durationMinutes = Math.round((item.durationHours - durationHours) * 60);

  return {
    uid: generateUID(item),
    title: item.activity,
    start: [year, month, day, hour, minute],
    startInputType: 'local',
    startOutputType: 'local',
    calName: 'Homeschool Schedule',
    duration: { hours: durationHours, minutes: durationMinutes },
    description: item.details,
    location:
      item.location ||
      (item.type === 'Training' ? 'Training Field' : 'Home'),
  };
});

createEvents(events, (error, value) => {
  if (error) {
    console.log(error);
    return;
  }
  
  // Add timezone and fix DTSTART to include TZID
  const tzBlock = `VTIMEZONE
TZID:America/New_York
X-LIC-LOCATION:America/New_York
BEGIN:DAYLIGHT
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
TZNAME:EDT
DTSTART:19700308T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
TZNAME:EST
DTSTART:19701101T020000
RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU
END:STANDARD
END:VTIMEZONE`;
  
  // Insert timezone after VCALENDAR header and add TZID to DTSTART
  let ics = value.replace(
    'X-PUBLISHED-TTL:PT1H',
    `X-PUBLISHED-TTL:PT1H\nBEGIN:${tzBlock}`
  );
  
  // Add TZID to all DTSTART lines that don't have Z (UTC)
  ics = ics.replace(/DTSTART:(\d{8}T\d{6})$/gm, 'DTSTART;TZID=America/New_York:$1');
  
  writeFileSync('./schedule.ics', ics);
  console.log(
    `schedule.ics created: ${lessons.length} lessons + ${themedTraining.length} training/recovery blocks.`,
  );
});
