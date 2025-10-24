import React from 'react';

const AlarmScreen = ({ medicines, alarms, onSave, onBack }) => {
  // 약품별로 알림 그룹화
  const groupedAlarms = medicines.reduce((acc, med) => {
    acc[med.name] = alarms.filter(alarm => alarm.medicine === med.name);
    return acc;
  }, {});

  return (
    <>
      <div className="result-header">
        <button className="back-button" onClick={onBack}>←</button>
        <div className="header-title">알림 설정</div>
      </div>

      <div className="result-content">
        <div className="alarm-info">
          <div className="alarm-info-text">
            💡 기본 식사 시간으로 알림이 설정되었어요.<br />
            시간을 변경하고 싶으면 수정 버튼을 눌러주세요.
          </div>
        </div>

        {medicines.map((med, index) => (
          <div key={index} className="medicine-section">
            <div className="section-title">
              <span>💊</span>
              {med.name}
            </div>
            <div className="alarm-list">
              {groupedAlarms[med.name]?.map((alarm, idx) => (
                <div key={idx} className="alarm-item">
                  <div className="alarm-time-info">
                    <div className="alarm-time">{alarm.time}</div>
                    <div className="alarm-condition">{alarm.condition}</div>
                  </div>
                  <button className="edit-button">수정</button>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <button className="save-button" onClick={onSave}>
        ✓ 알림 저장하기
      </button>
    </>
  );
};

export default AlarmScreen;
