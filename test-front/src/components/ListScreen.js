import React from 'react';

const ListScreen = ({ savedMedicines }) => {
  return (
    <>
      <div className="result-content">
        {savedMedicines.length === 0 ? (
          <div style={{ 
            display: 'flex', 
            flexDirection: 'column', 
            alignItems: 'center', 
            justifyContent: 'center',
            height: '100%',
            color: '#7F8C8D'
          }}>
            <div style={{ fontSize: '64px', marginBottom: '16px', opacity: 0.3 }}>
              📭
            </div>
            <div style={{ fontSize: '16px' }}>등록된 알림이 없습니다</div>
          </div>
        ) : (
          savedMedicines.map((item, index) => (
            <div key={index} className="medicine-list-item">
              <div className="medicine-header">
                <div className="medicine-title">
                  <span>💊</span>
                  {item.medicine.name}
                </div>
                <div className="status-badge status-active">진행중</div>
              </div>
              <div className="next-alarm">
                🔔 다음 알림: {item.nextAlarm || '예정 없음'}
              </div>
              <div className="progress-info">
                {item.progress || '0/0회 복용 완료'} · {item.medicine.duration}
              </div>
            </div>
          ))
        )}
      </div>
    </>
  );
};

export default ListScreen;
