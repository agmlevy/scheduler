const fs = require('fs');
const { writeFileSync } = require('fs');
const { createEvents } = require('ics');

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
    title: item.activity,
    start: [year, month, day, hour, minute],
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
  writeFileSync('./schedule.ics', value);
  console.log(
    `schedule.ics created: ${lessons.length} lessons + ${themedTraining.length} training/recovery blocks.`,
  );
});
