deactivate
Remove-Item -Recurse -Force .\venv

# README — PaddleOCR CLI (Windows, PowerShell)

## 요구사항

* Windows 10/11, NVIDIA GPU + 최신 드라이버
* CUDA 12.9, cuDNN(Windows에 설치되어 CUDA 경로에 배치됨)
* **Python 3.10.x (필수)**
  ※ 3.11/3.12/3.13 미지원. `py -3.10` 또는 3.10 절대경로 사용.

## 0) PowerShell 실행 정책

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## 1) 저장소 클론

```powershell
git clone <THIS_REPO_URL> paddle-ocr-cli
cd paddle-ocr-cli
```
## 2) Python 3.10 가상환경 생성·활성화

Python 명령어 자체가 3.10 버전을 가리키고 있다고 가정한다.
```powershell
# 가상환경 생성
python -m venv venv

# PowerShell에서 가상환경 활성화
.\venv\Scripts\Activate.ps1
```

활성화 후 프롬프트가 (venv) PS ...> 형태로 바뀌면 성공이다.

## 3) 의존성 설치(요구사항 파일 사용)

`requirements.txt`는 Paddle 전용 인덱스를 포함한다.

```powershell
& .\venv\Scripts\python.exe -m pip install --upgrade pip
& .\venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 4) 모델 캐시 경로(권장)

Windows 사용자 폴더 권한 문제 회피를 위해 프로젝트 내부에 캐시 지정.

```powershell
$env:PADDLEX_HOME = "$PWD\paddlex_cache"
New-Item -ItemType Directory -Force -Path $env:PADDLEX_HOME | Out-Null
```

## 5) 실행

예시 입력 이미지: `D:\user\Desktop\img1.jpg`
출력 폴더: `.\ocr_out`

```powershell
& .\venv\Scripts\python.exe .\paddle_ocr_cli.py `
  --input "D:\user\Desktop\img1.jpg" `
  --lang korean `
  --ocr_version PP-OCRv3 `
  --device gpu `
  --save_dir ".\ocr_out" `
  --rec_batch_num 2
```

정상 종료 로그 예:

```
>> OCR predict start
Resized image size (...) exceeds max_side_limit of 4000. Resizing to fit within limit.
>> OCR predict done
>> extracted lines= N
JSON: .\ocr_out\img1_res.json
VIS : .\ocr_out\img1_vis.jpg
OK | device=gpu | lines=N
```

## 6) 산출물

* `.\ocr_out\img1_res.json` : 인식 텍스트/점수/박스 좌표(JSON)
* `.\ocr_out\img1_vis.jpg` : 바운딩 박스와 라벨이 그려진 시각화 이미지

## 7) 사용 옵션

* `--input` 입력 이미지 경로
* `--lang` `korean` | `japan` | `ch` | `en` …
* `--ocr_version` **PP-OCRv3** 권장(ko/jp 지원). v4/v5는 ko 미지원/변경 가능성 큼
* `--device` `gpu` | `cpu` | `auto`
* `--save_dir` 출력 폴더
* `--rec_batch_num` 인식 배치(저사양 GPU면 2~4)

## 8) 문제 해결

* 결과가 비어 있음
  → 고해상도 이미지는 2000px 이하로 리사이즈 후 재시도
  → `--rec_batch_num 2`로 축소
  → `--lang`이 실제 언어와 일치하는지 확인(`korean`/`japan`)
* CUDA/드라이버 불일치
  → NVIDIA 드라이버 최신화, CUDA 12.9/ cuDNN이 설치되어 있는지 점검
  → `nvidia-smi`로 드라이버 인식 확인

## 9) 가상환경 비활성화

작업 완료 후 가상환경을 종료할 때:
```powershell
deactivate
```
