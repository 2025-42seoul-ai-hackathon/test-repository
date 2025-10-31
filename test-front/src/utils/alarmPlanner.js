function hhmmToDate(hhmm) {
  const [h, m] = hhmm.split(':').map(Number);
  const d = new Date();
  d.setHours(h, m, 0, 0);
  return d;
}
function addMinutes(date, minutes) {
  const d = new Date(date);
  d.setMinutes(d.getMinutes() + minutes);
  return d;
}
function midpoint(a, b) {
  return new Date((a.getTime() + b.getTime()) / 2);
}
function fmt(date) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function planTimesByTiming(timing, meals, timesNeeded) {
  const B = hhmmToDate(meals.breakfast || '08:00');
  const L = hhmmToDate(meals.lunch || '12:00');
  const D = hhmmToDate(meals.dinner || '19:00');

  let slots = [];
  if (timing === '식후') {
    slots = [addMinutes(B, 30), addMinutes(L, 30), addMinutes(D, 30)];
  } else if (timing === '식전') {
    slots = [addMinutes(B, -30), addMinutes(L, -30), addMinutes(D, -30)];
  } else if (timing === '식간') {
    slots = [midpoint(B, L), midpoint(L, D), addMinutes(D, 90)];
  } else if (timing === '취침전') {
    slots = [addMinutes(D, 120), addMinutes(D, 120), addMinutes(D, 120)];
  } else {
    slots = [addMinutes(B, 120), addMinutes(L, 120), addMinutes(D, 120)]; // 공복
  }
  return slots.slice(0, Math.max(1, timesNeeded)).map(fmt);
}
