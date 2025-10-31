import React, { useEffect, useState } from 'react';
import './App.css';
import { uploadImageForOCR, parsePrescription, getMedicineInfo } from './api';

import BottomNav from './components/BottomNav';
import UserInfoScreen from './components/UserInfoScreen';

// 기존 화면 컴포넌트가 프로젝트에 이미 존재한다고 가정
// 없으면 최소한의 더미 UI로 대체해도 무방
import MainScreen from './components/MainScreen';
import LoadingScreen from './components/LoadingScreen';
import ResultScreen from './components/ResultScreen';
import AlarmScreen from './components/AlarmScreen';
import ListScreen from './components/ListScreen';

import { calcAge, normalizeTiming, parseDoseFreq, selectAgeBlock } from './utils/usageParser';
import { planTimesByTiming } from './utils/alarmPlanner';

function App() {
  const [screen, setScreen] = useState('main'); // main | loading | result | alarm | list | user
  const [activeTab, setActiveTab] = useState('home');

  const [ocrData, setOcrData] = useState(null);
  const [medicines, setMedicines] = useState([]);
  const [alarms, setAlarms] = useState([]);
  const [savedMedicines, setSavedMedicines] = useState([]);

  const [userInfo, setUserInfo] = useState(() => {
    try { return JSON.parse(localStorage.getItem('userInfo')) || null; } catch { return null; }
  });
  useEffect(() => {
    if (userInfo) localStorage.setItem('userInfo', JSON.stringify(userInfo));
  }, [userInfo]);

  const handleCapture = async (file) => {
    setScreen('loading');
    try {
      const ocrResult = await uploadImageForOCR(file);
      if (ocrResult.status === 'success') {
        setOcrData(ocrResult.data);
        const parseResult = await parsePrescription(ocrResult.data.texts, ocrResult.data.scores);
        if (parseResult.status === 'success') {
          setMedicines(parseResult.data.medicines || []);
          setAlarms(parseResult.data.alarms || []);
          setScreen('result');
        } else {
          alert('처방전 분석 실패: ' + (parseResult.message || ''));
          setScreen('main');
        }
      } else {
        alert('OCR 실패: ' + (ocrResult.message || ''));
        setScreen('main');
      }
    } catch (e) {
      console.error(e);
      alert('오류 발생');
      setScreen('main');
    }
  };

  // 결과 확정 → 유저 정보 기반 알람 재계산
  const handleConfirmResult = async () => {
    const info = userInfo || { dob: '', gender: '', meals: { breakfast: '08:00', lunch: '12:00', dinner: '19:00' } };
    const age = calcAge(info.dob);
    const nextAlarms = [];

    for (const med of medicines) {
      // 약 상세 사용법 조회
      let usage = '';
      try {
        const detail = await getMedicineInfo(med.name);
        usage = (detail?.data?.usage || detail?.usage || '').trim();
      } catch {
        usage = '';
      }
      const selected = selectAgeBlock(usage, age);
      const timing = normalizeTiming(selected) || med.timing || '식후';
      const { frequency } = parseDoseFreq(selected);
      const timesPerDay = Math.max(frequency || med.frequency || 1, 1);

      const times = planTimesByTiming(timing, info.meals, timesPerDay);
      times.forEach((t) => {
        nextAlarms.push({ medicine: med.name, time: t, condition: timing });
      });
    }

    setAlarms(nextAlarms);
    setScreen('alarm');
  };

  const handleSaveAlarms = () => {
    const newSaved = medicines.map((m) => {
      const mine = alarms.filter(a => a.medicine === m.name);
      return {
        medicine: m,
        alarms: mine,
        nextAlarm: mine[0]?.time || '',
        progress: '0/' + (mine.length * parseInt(m.duration || 0, 10)) + '회 복용 완료'
      };
    });
    setSavedMedicines([...savedMedicines, ...newSaved]);
    setActiveTab('list');
    setScreen('list');
  };

  const handleBack = () => {
    if (screen === 'result') setScreen('main');
    else if (screen === 'alarm') setScreen('result');
    else if (screen === 'user') { setActiveTab('home'); setScreen('main'); }
  };

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    if (tab === 'home') setScreen('main');
    else if (tab === 'list') setScreen('list');
    else if (tab === 'user') setScreen('user');
  };

  const renderHeader = () => {
    if (screen === 'result' || screen === 'alarm') return null;
    return (
      <div className="header">
        <div className="logo">
          <div className="logo-icon">💊</div>
          <div className="app-name">{screen === 'list' ? '복약 알림' : screen === 'user' ? '유저 정보' : '알약 도우미'}</div>
        </div>
        {/* 설정 아이콘 제거 */}
      </div>
    );
  };

  const renderScreen = () => {
    switch (screen) {
      case 'main':   return <MainScreen onCapture={handleCapture} />;
      case 'loading':return <LoadingScreen />;
      case 'result': return <ResultScreen medicines={medicines} onConfirm={handleConfirmResult} onBack={handleBack} />;
      case 'alarm':  return <AlarmScreen medicines={medicines} alarms={alarms} onSave={handleSaveAlarms} onBack={handleBack} />;
      case 'list':   return <ListScreen savedMedicines={savedMedicines} />;
      case 'user':   return <UserInfoScreen value={userInfo} onChange={setUserInfo} />;
      default:       return <MainScreen onCapture={handleCapture} />;
    }
  };

  const showBottomNav = screen === 'main' || screen === 'list' || screen === 'user';

  return (
    <div className="app">
      {renderHeader()}
      {renderScreen()}
      {showBottomNav && <BottomNav activeTab={activeTab} onTabChange={handleTabChange} />}
    </div>
  );
}

export default App;
