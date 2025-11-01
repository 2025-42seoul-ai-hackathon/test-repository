import React, { useRef } from 'react';

const MainScreen = ({ onCapture }) => {
  const fileInputRef = useRef(null);

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      onCapture(file);
    }
  };

  const handleCaptureClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <>
      <div className="main-content">
        <div className="camera-illustration">
          <div className="pulse"></div>
          <div className="camera-icon">📷</div>
        </div>
        <div className="main-text">약 이름을 촬영해주세요</div>
        <div className="sub-text">
          처방전 봉투 또는 약 상자를 찍으면<br />
          자동으로 복약 알람을 설정해드려요
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          capture="environment"
          onChange={handleFileSelect}
        />
        <button className="capture-button" onClick={handleCaptureClick}>
          📸 촬영하기
        </button>
      </div>
    </>
  );
};

export default MainScreen;
