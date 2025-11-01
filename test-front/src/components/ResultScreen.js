import React from 'react';

// --- NEW: 유저 나이 계산 ---
function calcAge(dobISO) {
  if (!dobISO) return null;
  const t = new Date(), d = new Date(dobISO);
  let a = t.getFullYear() - d.getFullYear();
  const m = t.getMonth() - d.getMonth();
  if (m < 0 || (m === 0 && t.getDate() < d.getDate())) a--;
  return a;
}

// --- NEW: ranges에서 나이에 맞는 블록 선택 ---
function pickRangeByAge(ranges, age) {
  if (!ranges || age == null) return null;
  if (age < 15 && ranges.child) return ranges.child;
  if (age >= 15 && ranges.adult) return ranges.adult;
  return null;
}

// --- NEW: 표시 헬퍼 ---
function fmtByRange(med, age) {
  const r = pickRangeByAge(med.ranges, age);
  const out = { freq: '-', dose: '-' };
  if (r?.freq_range?.min != null) {
    const { min, max } = r.freq_range;
    out.freq = (min === max) ? `1일 ${max}회` : `1일 ${min}~${max}회`;
  } else if (med.frequency) {
    out.freq = `1일 ${med.frequency}회`;
  }
  if (r?.dose_range?.min != null) {
    const { min, max, unit } = r.dose_range;
    out.dose = (min === max) ? `${max}${unit || ''}` : `${min}~${max}${unit || ''}`;
  } else if (med.per_dose) {
    out.dose = `${med.per_dose}${med.unit || ''}`;
  }
  return out;
}

// --- MODIFY: 컴포넌트 내부에서 나이 계산 ---
const userInfo = (() => {
  try { return JSON.parse(localStorage.getItem('userInfo')) || null; } catch { return null; }
})();
const age = userInfo?.dob ? calcAge(userInfo.dob) : null;


const ResultScreen = ({ medicines, onConfirm, onBack }) => {
  return (
    <>
      <div className="result-header">
        <button className="back-button" onClick={onBack}>←</button>
        <div className="header-title">인식된 약 정보</div>
      </div>

      <div className="result-content">
        {medicines.map((med, index) => (
          <div key={index} className="medicine-card">
            <div className="medicine-name">
              <span>💊</span>
              {med.name}
            </div>

            <div className="info-row">
              <div className="info-label">복용 횟수</div>
              <div className="info-value">{fmtByRange(med, age).freq}</div>
            </div>

            {/* 추가: 1회 복용량 */}
            <div className="info-row">
              <div className="info-label">1회 복용량</div>
              <div className="info-value">
                {(() => {
                  const r = med.ranges?.adult || med.ranges?.child;
                  const dr = r?.dose_range;
                  if (dr?.min != null && dr?.max != null) {
                    return dr.min === dr.max ? `${dr.max}${dr.unit || ''}` : `${dr.min}~${dr.max}${dr.unit || ''}`;
                  }
                  return med.per_dose ? `${med.per_dose}${med.unit || ''}` : '-';
                })()}
              </div>
            </div>

            <div className="info-row">
              <div className="info-label">복용 시점</div>
              <div className="info-value">{med.timing || '-'}</div>
            </div>

            <div className="info-row">
              <div className="info-label">처방 기간</div>
              <div className="info-value">
                {med.duration ? `${med.duration}일` : '0일'}
              </div>
            </div>

            {med.details && (
              <div className="info-row">
                <div className="info-label">약품 분류</div>
                <div className="info-value">
                  {med.details.classification || '일반의약품'}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      <button className="confirm-button" onClick={onConfirm}>
        알람 설정하기
      </button>
    </>
  );
};

export default ResultScreen;
