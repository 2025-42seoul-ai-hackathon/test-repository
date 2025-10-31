// src/api.js
// 1) 환경변수 우선순위: VITE_API_BASE → REACT_APP_API_URL → ''(동일 오리진)
// 2) 끝/앞 슬래시 정규화
const ENV_VITE = (typeof import.meta !== 'undefined' && import.meta.env) ? import.meta.env.VITE_API_BASE : undefined;
// CRA 빌드 시 process.env는 번들 타임 치환됨
const ENV_CRA  = (typeof process !== 'undefined' && process.env) ? process.env.REACT_APP_API_URL : undefined;

const RAW_BASE = ENV_VITE ?? ENV_CRA ?? '';
//const BASE = (R// src/api.js
// === BASE URL 설정 ===
const BASE = 'http://localhost:5000'; // 또는 .env의 REACT_APP_API_URL 적용 시 process.env로 변경

// === 공통 JSON 파서 ===
async function _json(res) {
  const txt = await res.text();
  try { return JSON.parse(txt); } catch { return { status: 'error', message: txt || 'parse error' }; }
}
const url = (p) => `${BASE}/${String(p).replace(/^\/+/, '')}`;

// === OCR 업로드 ===
export async function uploadImageForOCR(file) {
  const form = new FormData();
  form.append('file', file); // 백엔드에서 request.files['file'] 사용
  const res = await fetch(url('api/ocr'), { method: 'POST', body: form });
  return _json(res);
}

// === 처방전 파싱 ===
export async function parsePrescription(texts, scores = []) {
  const res = await fetch(url('api/medicine/parse'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ texts, scores }), // key 명은 texts
  });
  return _json(res);
}

// === 약 정보 조회 ===
export async function getMedicineInfo(name) {
  const res = await fetch(url('api/medicine/info'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ medicine_name: name }),
  });
  return _json(res);
}
