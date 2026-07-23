const fs = require('fs');
const crypto = require('crypto');
const { writeFileSync } = require('fs');
const { createEvents } = require('ics');

const TIMEZONE = 'America/New_York';
const TEAM_NAME = 'EFU U14B 2012/13 N1';

function generateUID(item) {
  const key = `${item.date}-${item.timeStart}-${item.activity}-game`;
  const hash = crypto.createHash('md5').update(key).digest('hex').slice(0, 16);
  return `${hash}@efu-games`;
}

function loadJson(path) {
  if (!fs.existsSync(path)) {
    return [];
  }
  return JSON.parse(fs.readFileSync(path, 'utf-8'));
}

const games = loadJson('./games_schedule.json');

const events = games.map((item) => {
  const [year, month, day] = item.date.split('-').map(Number);
  const [hour, minute] = item.timeStart.split(':').map(Number);
  const durationHours = Math.floor(item.durationHours);
  const durationMinutes = Math.round((item.durationHours - durationHours) * 60);

  const homeAwayIndicator = item.homeAway === 'Home' ? '🏠' : '✈️';
  const title = `${homeAwayIndicator} ${TEAM_NAME} vs ${item.opponent}`;
  
  return {
    uid: generateUID(item),
    title: title,
    start: [year, month, day, hour, minute],
    startInputType: 'local',
    startOutputType: 'local',
    calName: `${TEAM_NAME} Game Schedule`,
    duration: { hours: durationHours, minutes: durationMinutes },
    description: `${item.homeAway.toUpperCase()} GAME\n\nOpponent: ${item.opponent}\nLeague: ${item.league}\n\n${item.homeTeam} vs ${item.awayTeam}`,
    location: item.homeAway === 'Home' ? 'Home Field (TBD)' : `Away - ${item.opponent}`,
  };
});

createEvents(events, (error, value) => {
  if (error) {
    console.log(error);
    return;
  }
  
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
  
  let ics = value.replace(
    'X-PUBLISHED-TTL:PT1H',
    `X-PUBLISHED-TTL:PT1H\nBEGIN:${tzBlock}`
  );
  
  ics = ics.replace(
    'X-WR-CALNAME:Untitled',
    `X-WR-CALNAME:${TEAM_NAME} Games`
  );
  
  ics = ics.replace(/DTSTART:(\d{8}T\d{6})$/gm, 'DTSTART;TZID=America/New_York:$1');
  
  writeFileSync('./games_schedule.ics', ics);
  console.log(`games_schedule.ics created: ${games.length} games for team/parent sharing.`);
});
