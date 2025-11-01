import React from 'react';

export default function BottomNav({ activeTab, onTabChange }) {
  return (
    <div className="bottom-nav">
      <div className={`nav-item ${activeTab === 'home' ? 'active' : ''}`} onClick={() => onTabChange('home')}>
        <div className="nav-icon">🏠</div>
        <div className="nav-label">홈</div>
      </div>
      <div className={`nav-item ${activeTab === 'list' ? 'active' : ''}`} onClick={() => onTabChange('list')}>
        <div className="nav-icon">⏰</div>
        <div className="nav-label">알람</div>
      </div>
      <div className={`nav-item ${activeTab === 'user' ? 'active' : ''}`} onClick={() => onTabChange('user')}>
        <div className="nav-icon">👤</div>
        <div className="nav-label">내 정보</div>
      </div>
    </div>
  );
}
