# 알약 도우미 백엔드 API

Flask 기반 OCR + 약품 정보 조회 API 서버

## 구조

```
backend/
├── app.py              # Flask API 서버
├── ocr_service.py      # PaddleOCR 래퍼
├── medicine_api.py     # e약은요 API 연동
├── requirements.txt    # 의존성
├── .env.example        # 환경변수 예시
└── uploads/            # 임시 이미지 저장 (자동 생성)
```

## 설치

### 1. 의존성 설치

```bash
# 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

**GPU 사용 시:**
```bash
# CPU 버전 제거
pip uninstall paddlepaddle

# GPU 버전 설치
pip install paddlepaddle-gpu
```

### 2. 환경변수 설정

```bash
# .env 파일 생성
cp .env.example .env

# .env 파일 편집하여 API 키 입력
# MEDICINE_API_KEY=실제_발급받은_키
```

**e약은요 API 키 발급:**
1. https://www.data.go.kr/ 회원가입
2. "의약품개요정보" API 신청
3. 발급받은 키를 `.env`에 입력

## 실행

```bash
# 개발 서버 실행
python app.py

# 또는
flask run
```

서버가 `http://localhost:5000`에서 실행됩니다.

## API 엔드포인트

### 1. 헬스 체크
```bash
GET /health

# 응답
{
  "status": "ok",
  "message": "Server is running"
}
```

### 2. OCR 처리
```bash
POST /api/ocr
Content-Type: multipart/form-data

# 요청
file: [이미지 파일]

# 응답
{
  "status": "success",
  "data": {
    "texts": ["타이레놀 500mg", "1일 3회", ...],
    "scores": [0.98, 0.95, ...],
    "counts": {"lines": 10}
  }
}
```

### 3. 약품 정보 조회
```bash
POST /api/medicine/info
Content-Type: application/json

# 요청
{
  "medicine_name": "타이레놀"
}

# 응답
{
  "status": "success",
  "data": {
    "name": "타이레놀정 500mg",
    "company": "제약회사",
    "classification": "일반의약품",
    "ingredients": "...",
    "efficacy": "...",
    ...
  }
}
```

### 4. 처방전 파싱 + 알림 생성
```bash
POST /api/medicine/parse
Content-Type: application/json

# 요청
{
  "texts": ["타이레놀 500mg", "1일 3회", "식후 30분", ...]
}

# 응답
{
  "status": "success",
  "data": {
    "medicines": [
      {
        "name": "타이레놀 500mg",
        "dosage": "1일 3회",
        "timing": "식후 30분",
        "duration": "7일",
        "details": {...}
      }
    ],
    "alarms": [
      {
        "time": "08:30",
        "condition": "아침 식후 30분",
        "medicine": "타이레놀 500mg"
      }
    ]
  }
}
```

## 테스트

### OCR 서비스 단독 테스트
```bash
python ocr_service.py test_image.jpg
```

### 약품 API 서비스 단독 테스트
```bash
python medicine_api.py
```

### cURL로 API 테스트
```bash
# OCR 테스트
curl -X POST http://localhost:5000/api/ocr \
  -F "file=@prescription.jpg"

# 약품 정보 테스트
curl -X POST http://localhost:5000/api/medicine/info \
  -H "Content-Type: application/json" \
  -d '{"medicine_name": "타이레놀"}'
```

## 프로덕션 배포

### Gunicorn 사용
```bash
# Gunicorn 설치
pip install gunicorn

# 실행
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Docker 사용
```dockerfile
FROM python:3.9

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

## 문제 해결

### PaddleOCR 모델 다운로드 실패
```bash
# 수동 다운로드 후 경로 지정
# ~/.paddleocr/ 디렉토리 확인
```

### GPU 메모리 부족
```bash
# CPU 모드로 전환
# app.py에서 device='cpu'로 설정
```

### CORS 에러
```bash
# flask-cors가 설치되어 있는지 확인
pip install flask-cors
```

## 주의사항

1. **보안**: 프로덕션에서는 파일 업로드 검증 강화 필요
2. **성능**: OCR 모델이 메모리를 많이 사용 (최소 2GB RAM 권장)
3. **API 키**: `.env` 파일은 절대 git에 커밋하지 말 것
4. **임시 파일**: `uploads/` 폴더는 주기적으로 정리 필요

## 다음 단계

1. React 프론트엔드 연동
2. 알림 저장/관리 기능 추가
3. 보호자 연동 기능 구현
4. 사용자 인증 추가