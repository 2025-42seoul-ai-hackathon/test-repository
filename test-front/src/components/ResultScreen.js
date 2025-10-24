import React from 'react';

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
              <div className="info-value">{med.dosage}</div>
            </div>
            <div className="info-row">
              <div className="info-label">복용 시점</div>
              <div className="info-value">{med.timing}</div>
            </div>
            <div className="info-row">
              <div className="info-label">처방 기간</div>
              <div className="info-value">{med.duration}</div>
            </div>
            {med.details && (
              <div className="info-row">
                <div className="info-label">약품 분류</div>
                <div className="info-value">{med.details.classification}</div>
              </div>
            )}
          </div>
        ))}
      </div>

      <button className="confirm-button" onClick={onConfirm}>
        알림 설정하기
      </button>
    </>
  );
};

export default ResultScreen;
