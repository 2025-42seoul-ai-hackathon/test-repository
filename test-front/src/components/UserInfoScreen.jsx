import React, { useEffect, useState } from 'react';

const DEFAULT_INFO = {
  dob: '',
  gender: '',
  meals: { breakfast: '08:00', lunch: '12:00', dinner: '19:00' },
};

export default function UserInfoScreen({ value, onChange }) {
  const [info, setInfo] = useState(value || DEFAULT_INFO);

  useEffect(() => {
    setInfo(value || DEFAULT_INFO);
  }, [value]);

  const update = (patch) => {
    const next = { ...info, ...patch };
    setInfo(next);
    onChange && onChange(next);
  };

  const updateMeal = (key, v) => {
    const next = { ...info, meals: { ...info.meals, [key]: v } };
    setInfo(next);
    onChange && onChange(next);
  };

  return (
    <div className="main-content">
      <div className="section-title">내 정보</div>

      <div className="card wide">
        <div className="form-row">
          <label>생년월일</label>
          <input type="date" value={info.dob} onChange={(e) => update({ dob: e.target.value })} />
        </div>
        <div className="form-row">
          <label>성별</label>
          <select value={info.gender} onChange={(e) => update({ gender: e.target.value })}>
            <option value="">선택</option>
            <option value="F">여성</option>
            <option value="M">남성</option>
          </select>
        </div>

        <div className="section-subtitle">식사 시간</div>
        <div className="form-row">
          <label>아침</label>
          <input type="time" value={info.meals.breakfast} onChange={(e) => updateMeal('breakfast', e.target.value)} />
        </div>
        <div className="form-row">
          <label>점심</label>
          <input type="time" value={info.meals.lunch} onChange={(e) => updateMeal('lunch', e.target.value)} />
        </div>
        <div className="form-row">
          <label>저녁</label>
          <input type="time" value={info.meals.dinner} onChange={(e) => updateMeal('dinner', e.target.value)} />
        </div>
      </div>
    </div>
  );
}
