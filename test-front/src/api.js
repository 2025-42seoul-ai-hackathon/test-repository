import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // OCR 처리 시간 고려
  headers: {
    'Content-Type': 'application/json',
  },
});

// OCR 처리
export const uploadImageForOCR = async (file) => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await api.post('/api/ocr', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.data;
};

// 처방전 파싱 + 알림 생성
export const parsePrescription = async (texts) => {
  const response = await api.post('/api/medicine/parse', { texts });
  return response.data;
};

// 약품 정보 조회
export const getMedicineInfo = async (medicineName) => {
  const response = await api.post('/api/medicine/info', {
    medicine_name: medicineName,
  });
  return response.data;
};

// 서버 상태 체크
export const checkHealth = async () => {
  const response = await api.get('/health');
  return response.data;
};

export default api;