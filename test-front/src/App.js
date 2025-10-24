import React, { useState } from 'react';
import './App.css';
import { uploadImageForOCR, parsePrescription } from './api';
import MainScreen from './components/MainScreen';
import LoadingScreen from './components/LoadingScreen';
import ResultScreen from './components/ResultScreen';
import AlarmScreen from './components/AlarmScreen';
import ListScreen from './components/ListScreen';
import BottomNav from './components/BottomNav';

function App() {
  const [screen, setScreen] = useState('main'); // main, loading, result, alarm, list
  const [activeTab, setActiveTab] = useState('home');
  const [ocrData, setOcrData] = useState(null);
  const [medicines, setMedicines] = useState([]);
  const [alarms, setAlarms] = useState([]);
  const [savedMedicines, setSavedMedicines] = useState([]);

  // 이미지 촬영/업로드 처리
  const handleCapture = async (file) => {
    setScreen('loading');

    try {
      // 1. OCR 처리
      const ocrResult = await uploadImageForOCR(file);

      if (ocrResult.status === 'success') {
        setOcrData(ocrResult.data);

        // 2. 처방전 파싱
        const parseResult = await parsePrescription(ocrResult.data.texts);

        if (parseResult.status === 'success') {
          setMedicines(parseResult.data.medicines);
          setAlarms(parseResult.data.alarms);
          setScreen('result');
        } else {
          alert('처방전 분석에 실패했습니다: ' + parseResult.message);
          setScreen('main');
        }
      } else {
        alert('이미지 인식에 실패했습니다: ' + ocrResult.message);
        setScreen('main');
      }
    } catch (error) {
      console.error('Error:', error);
      alert('오류가 발생했습니다. 다시 시도해주세요.');
      setScreen('main');
    }
  };

  // 알림 설정 확인
  const handleConfirmResult = () => {
    setScreen('alarm');
  };

  // 알림 저장
  const handleSaveAlarms = () => {
    // 저장된 약품 목록에 추가
    const newSavedMedicines = medicines.map((med, index) => ({
      medicine: med,
      alarms: alarms.filter(a => a.medicine === med.name),
      nextAlarm: alarms.find(a => a.medicine === med.name)?.time,
      progress: '0/' + (alarms.filter(a => a.medicine === med.name).length * parseInt(med.duration)) + '회 복용 완료'
    }));

    setSavedMedicines([...savedMedicines, ...newSavedMedicines]);
    
    // 알림 목록 화면으로 이동
    setActiveTab('list');
    setScreen('list');
  };

  // 뒤로가기
  const handleBack = () => {
    if (screen === 'result') {
      setScreen('main');
    } else if (screen === 'alarm') {
      setScreen('result');
    }
  };

  // 탭 변경
  const handleTabChange = (tab) => {
    setActiveTab(tab);
    if (tab === 'home') {
      setScreen('main');
    } else if (tab === 'list') {
      setScreen('list');
    } else if (tab === 'settings') {
      alert('설정 화면은 준비 중입니다.');
    }
  };

  // 헤더 렌더링
  const renderHeader = () => {
    if (screen === 'result' || screen === 'alarm') {
      return null; // 결과/알림 화면은 자체 헤더 사용
    }

    return (
      <div className="header">
        <div className="logo">
          <div className="logo-icon">💊</div>
          <div className="app-name">
            {screen === 'list' ? '복약 알림' : '알약 도우미'}
          </div>
        </div>
        <div className="settings-icon">⚙️</div>
      </div>
    );
  };

  // 화면 렌더링
  const renderScreen = () => {
    switch (screen) {
      case 'main':
        return <MainScreen onCapture={handleCapture} />;
      case 'loading':
        return <LoadingScreen />;
      case 'result':
        return (
          <ResultScreen
            medicines={medicines}
            onConfirm={handleConfirmResult}
            onBack={handleBack}
          />
        );
      case 'alarm':
        return (
          <AlarmScreen
            medicines={medicines}
            alarms={alarms}
            onSave={handleSaveAlarms}
            onBack={handleBack}
          />
        );
      case 'list':
        return <ListScreen savedMedicines={savedMedicines} />;
      default:
        return <MainScreen onCapture={handleCapture} />;
    }
  };

  // 하단 네비게이션 표시 여부
  const showBottomNav = screen === 'main' || screen === 'list';

  return (
    <div className="app">
      {renderHeader()}
      {renderScreen()}
      {showBottomNav && (
        <BottomNav activeTab={activeTab} onTabChange={handleTabChange} />
      )}
    </div>
  );
}

export default App;