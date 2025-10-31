export function calcAge(dobISO) {
  if (!dobISO) return null;
  const today = new Date();
  const dob = new Date(dobISO);
  let age = today.getFullYear() - dob.getFullYear();
  const m = today.getMonth() - dob.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < dob.getDate())) age--;
  return age;
}

export function normalizeTiming(text) {
  if (!text) return '';
  let t = text.replace(/\s+/g, ' ');
  // 부정형 선치환 → 식후
  t = t.replace(/공복[^가-힣A-Za-z0-9]{0,5}을\s*피하[세요]*/g, '식후');
  t = t.replace(/빈\s*속을\s*피하[세요]*/g, '식후');

  if (/식후/.test(t)) return '식후';
  if (/식전/.test(t)) return '식전';
  if (/식간/.test(t)) return '식간';
  if (/취침\s*전/.test(t)) return '취침전';
  if (/공복(?:\(빈\s*속\))?/.test(t)) return '공복';
  return '';
}

export function selectAgeBlock(text, age) {
  if (!text) return text;
  if (age == null) return text;

  const lines = text.split(/[\n\.]+/).map(s => s.trim()).filter(Boolean);
  const child = lines.filter(s => /(만\s*8세|만\s*15세\s*미만|소아|어린이)/.test(s));
  const adult = lines.filter(s => /(성인|만\s*15세\s*이상)/.test(s));

  if (age < 15 && child.length) return child.join(' ');
  if (age >= 15 && adult.length) return adult.join(' ');
  return text;
}

export function parseDoseFreq(text) {
  if (!text) return { perDose: 0, frequency: 0 };

  let frequency = 0;
  const freq = text.match(/(?:1일|하루|매일)\s*(\d+)(?:~(\d+))?\s*(?:회|번)/) ||
               text.match(/(\d+)(?:~(\d+))?\s*(?:회|번)\s*(?:복용|투여)/);
  if (freq) frequency = parseInt(freq[2] || freq[1], 10);

  let perDose = 0;
  const dose = text.match(/1회\s*(\d+)\s*(정|캡슐)/) || text.match(/(\d+)\s*(정|캡슐)\s*씩/);
  if (dose) perDose = parseInt(dose[1], 10);

  return { perDose, frequency };
}
