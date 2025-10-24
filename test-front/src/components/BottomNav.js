import React from 'react';

const BottomNav = ({ activeTab, onTabChange }) => {
  return (
    <div className="bottom-nav">
      <div 
        className={`nav-item ${activeTab === 'home' ? 'active' : ''}`}
        onClick={() => onTabChange('home')}
      >
        <div className="nav-icon">🏠</div>
        <div className="nav-label">홈</div>
      </div>
      <div 
        className={`nav-item ${activeTab === 'list' ? 'active' : ''}`}
        onClick={() => onTabChange('list')}
      >
        <div className="nav-icon">🔔</div>
        <div className="nav-label">알림목록</div>
      </div>
      <div 
        className={`nav-item ${activeTab === 'settings' ? 'active' : ''}`}
        onClick={() => onTabChange('settings')}
      >
        <div className="nav-icon">⚙️</div>
        <div className="nav-label">설정</div>
      </div>
    </div>
  );
};

export default BottomNav;
