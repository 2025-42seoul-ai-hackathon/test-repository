# 알약 도우미 - React 프론트엔드

와이어프레임 디자인을 구현한 React 웹앱

## 프로젝트 구조

```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── components/
│   │   ├── MainScreen.js       # 메인 촬영 화면
│   │   ├── LoadingScreen.js    # 로딩 화면
│   │   ├── ResultScreen.js     # 인식 결과 화면
│   │   ├── AlarmScreen.js      # 알림 설정 화면
│   │   ├── ListScreen.js       # 알림 목록 화면
│   │   └── BottomNav.js        # 하단 네비게이션
│   ├── App.js                  # 메인 앱
│   ├── App.css                 # 스타일
│   ├── api.js                  # API 통신
│   ├── index.js                # 엔트리포인트
│   └── index.css               # 기본 스타일
├── package.json
└── .env                        # 환경변수
```

## 설치 및 실행

### 1. 의존성 설치

```bash
cd frontend
npm install
```

### 2. 개발 서버 실행

```bash
npm start
```

브라우저에서 `http://localhost:3000` 자동 열림

### 3. 백엔드 서버 실행 필수

프론트엔드 실행 전에 백엔드 API 서버가 실행 중이어야 합니다.

```bash
# 다른 터미널에서
cd backend
python app.py
```

## 주요 기능

### 화면 흐름

```
1. 메인 화면 (촬영)
   ↓
2. 로딩 화면 (OCR 처리)
   ↓
3. 결과 확인 화면 (약품 정보)
   ↓
4. 알림 설정 화면 (시간 확인/수정)
   ↓
5. 알림 목록 화면 (등록된 알림 관리)
```

### 컴포넌트 설명

**MainScreen**
- 카메라/파일 선택 인터페이스
- 촬영 버튼 클릭 → 파일 선택

**LoadingScreen**
- OCR 처리 중 로딩 애니메이션
- API 응답 대기

**ResultScreen**
- OCR로 인식된 약품 정보 표시
- 약품별 복용 정보 카드

**AlarmScreen**
- 자동 생성된 알림 시간 표시
- 알림 수정 버튼 (준비 중)
- 알림 저장

**ListScreen**
- 저장된 약품 목록
- 다음 알림 시간
- 복용 진행 상황

**BottomNav**
- 홈 / 알림목록 / 설정 탭

## 환경변수

`.env` 파일에서 설정:

```
REACT_APP_API_URL=http://localhost:5000
```

## API 연동

`src/api.js`에서 백엔드 API와 통신:

- `uploadImageForOCR(file)` - 이미지 업로드 및 OCR
- `parsePrescription(texts)` - 처방전 파싱
- `getMedicineInfo(name)` - 약품 정보 조회
- `checkHealth()` - 서버 상태 체크

## 스타일

와이어프레임과 동일한 디자인:
- 파란색/녹색 그라데이션 (#4A90E2, #66BB6A)
- 미니멀하고 친근한 UI
- 큰 터치 영역 (노인/어린이 고려)
- 명확한 시각적 피드백

## 빌드

프로덕션 빌드:

```bash
npm run build
```

`build/` 폴더에 최적화된 정적 파일 생성

## 배포

### Vercel 배포

```bash
npm install -g vercel
vercel
```

### Netlify 배포

```bash
npm install -g netlify-cli
netlify deploy --prod
```

환경변수 `REACT_APP_API_URL`을 배포된 백엔드 주소로 설정

## 추가 개발 항목

- [ ] 알림 시간 수정 기능
- [ ] 보호자 연동 기능
- [ ] 복용 체크 기능
- [ ] 설정 화면 구현
- [ ] 로컬스토리지 저장
- [ ] PWA 지원 (오프라인, 푸시 알림)
- [ ] 다크모드
- [ ] 다국어 지원

## 문제 해결

### CORS 에러

백엔드 `app.py`에서 CORS 설정 확인:
```python
from flask_cors import CORS
CORS(app)
```

### API 연결 실패

1. 백엔드 서버 실행 상태 확인
2. 포트 번호 확인 (5000)
3. 방화벽 설정 확인

### 카메라 접근 안됨

HTTPS 환경 필요. 개발 시 localhost는 허용됨.

## 라이선스

MIT