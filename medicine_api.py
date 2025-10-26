#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
의약품 정보 API 서비스 - e약은요 API 연동 + 처방 파서(개선판)
- 노이즈 컷, 오탈자 보정, 인접행 결합, 스코어링
- 콘솔 로그: 파싱된 약 리스트 출력
"""

import os
import re
import sys
import requests
from typing import Dict, List, Optional, Any
from datetime import time

# -----------------------------------------------------------
# 모듈 전역 상수/정규식/유틸
# -----------------------------------------------------------

_KO_NOISE_KEYWORDS = {
    "환자정보","병원정보","영수증","현금","현금영수증","사업자등록","사업장소재지","발행일","교부번호",
    "약제비","본인부담","보험자부담","총수납","주의사항","복약안내","약품사진","약품명","투약량","횟수","일수",
    "표시대로복용","아침","점심","저녁","취침전",
    "약국","조제약","복약","조제일자","발행기관","총수납금액","현금승인","영수증번호","사업자등록번호"
}

_MED_NAME_RE = re.compile(
    r"(?:[가-힣A-Za-z]+)"
    r"(?:정|캡슐|시럽|액|점안액)"
    r"(?:\d+(?:mg|g|ml))?"
    r"(?:\d+(?:\.\d+)?%)?"
)
_BAD_NAME_TOKENS = {"연말정"}
_PER_DOSE_RE = re.compile(r"(\d+)정씩")
_FREQ_RE = re.compile(r"(?:1일|하루)(\d+)회|(\d+)번")
_DURATION_RE = re.compile(r"(\d+)일분?")
_TIMING_RE = re.compile(r"식(전|후)")

def _looks_like_drug_name(name: str) -> bool:
    if any(bad in name for bad in _BAD_NAME_TOKENS):
        return False
    if "약국" in name:
        return False
    return True

def _normalize_ocr(s: str) -> str:
    """OCR 텍스트 정규화(오탈자 보정 포함)"""
    t = re.sub(r"[`'\"[\]<>･·]", "", s)
    t = re.sub(r"\s+", "", t)

    # 5l0 → 510
    t = re.sub(r"(\d)l(\d)", r"\g<1>1\g<2>", t)

    # 자주 틀리는 문자
    t = t.replace("O", "0")
    t = t.replace("|", "1")

    # 10mg 계열 오탈자 보정
    t = re.sub(r"(정)1[에eE][mM]9\b", r"\g<1>10mg", t)   # 인데놀정1에m9 → 인데놀정10mg
    t = re.sub(r"(정)1[이iIlL][mM]\b", r"\g<1>10mg", t)  # 인데놀정1이m  → 인데놀정10mg
    t = re.sub(r"(?<=\d)lm\b", "10mg", t)                # 10lm         → 10mg

    # 단위 누락 보정: 500m → 500mg
    t = re.sub(r"(?<=\d)m\b", "mg", t)

    # 한글/영숫자만
    t = re.sub(r"[^\w가-힣]", "", t)
    return t


def _is_noise_line(t: str) -> bool:
    if len(t) <= 1:
        return True
    for k in _KO_NOISE_KEYWORDS:
        if k in t:
            return True
    if re.fullmatch(r"\d{2,}원", t):
        return True
    if re.fullmatch(r"\d{3,}[-]?\d{2}[-]?\d{5}", t):  # 사업자번호
        return True
    if re.fullmatch(r"\d{8}", t):                     # yyyymmdd
        return True
    if re.fullmatch(r"\d{4}[-]?\d{2}[-]?\d{2}", t):   # yyyy-mm-dd
        return True
    return False


def _merge_neighbor(lines: List[str], i: int, radius: int = 3) -> str:
    l = max(0, i - radius)
    r = min(len(lines), i + radius + 1)
    return "".join(lines[l:r])


# -----------------------------------------------------------
# Medicine API + 처방 파서
# -----------------------------------------------------------

class MedicineAPIService:
    """
    e약은요(의약품안전나라) API + 처방 파서
    API 문서: https://nedrug.mfds.go.kr/api_openapi_info
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('MEDICINE_API_KEY', '')
        self.base_url = 'http://apis.data.go.kr/1471000/DrbEasyDrugInfoService'

        if not self.api_key:
            print("WARNING: MEDICINE_API_KEY not set. API calls will fail.")

        self.default_meal_times = {
            'breakfast': time(8, 0),
            'lunch': time(12, 0),
            'dinner': time(19, 0)
        }

    def get_medicine_info(self, medicine_name: str) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return self._get_dummy_medicine_info(medicine_name)

        try:
            endpoint = f"{self.base_url}/getDrbEasyDrugList"
            params = {
                'serviceKey': self.api_key,
                'itemName': medicine_name,
                'type': 'json',
                'numOfRows': 10
            }
            resp = requests.get(endpoint, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if 'body' in data and 'items' in data['body']:
                items = data['body']['items']
                if items:
                    item = items[0]
                    return {
                        'name': item.get('itemName', ''),
                        'company': item.get('entpName', ''),
                        'classification': item.get('etcOtcCode', ''),
                        'ingredients': item.get('mainIngr', ''),
                        'efficacy': item.get('efcyQesitm', ''),
                        'usage': item.get('useMethodQesitm', ''),
                        'caution': item.get('atpnWarnQesitm', ''),
                        'storage': item.get('depositMethodQesitm', '')
                    }
            return None
        except Exception as e:
            print(f"Error fetching medicine info: {e}")
            return self._get_dummy_medicine_info(medicine_name)

    def _get_dummy_medicine_info(self, medicine_name: str) -> Dict[str, Any]:
        return {
            'name': medicine_name,
            'company': '제약회사',
            'classification': '일반의약품',
            'ingredients': '주성분 정보',
            'efficacy': '효능효과 정보',
            'usage': '용법용량 정보',
            'caution': '주의사항',
            'storage': '보관방법'
        }

    def parse_prescription(self, texts: List[str], scores: Optional[List[float]] = None) -> Dict[str, Any]:
        try:
            # 1) 전처리 + 노이즈 컷
            norm: List[str] = []
            for idx, raw in enumerate(texts):
                t = _normalize_ocr(raw)
                if not t:
                    continue
                if _is_noise_line(t):
                    continue
                if scores is not None and idx < len(scores) and scores[idx] < 0.55:
                    continue
                norm.append(t)

            # 2) ‘투약량횟수일수’ 인덱스와 이후 정수 트리플 추출
            header_idx = next((i for i, x in enumerate(norm) if "투약량횟수일수" in x), -1)
            triples: List[tuple[int,int,int]] = []
            if header_idx != -1:
                ints: List[int] = []
                for x in norm[header_idx+1:]:
                    if re.fullmatch(r"\d{1,3}", x):
                        ints.append(int(x))
                # 3개씩 묶기
                for i in range(0, len(ints) - 2, 3):
                    triples.append((ints[i], ints[i+1], ints[i+2]))

            # 3) 약명 후보 수집(±3행 윈도우) + 블랙리스트 필터
            name_windows: List[str] = []
            for i, _t in enumerate(norm):
                w = _merge_neighbor(norm, i, 3)
                m = _MED_NAME_RE.search(w)
                if m:
                    name = m.group(0)
                    if _looks_like_drug_name(name):
                        name_windows.append(w)
                elif "점안액" in w or "정" in w:
                    # 용량/퍼센트가 없더라도 의약품 가능성
                    if "약국" not in w and "연말정" not in w:
                        name_windows.append(w)

            # 약명 실제 문자열 리스트(표시명만 추출)
            names: List[str] = []
            for w in name_windows:
                m = _MED_NAME_RE.search(w)
                if m:
                    names.append(m.group(0))
                elif "점안액" in w and "약국" not in w:
                    # 이름 대용(점안액 계열)
                    # 가장 긴 한글+‘점안액’ 토큰 뽑기
                    m2 = re.search(r"[가-힣A-Za-z]+점안액", w)
                    if m2:
                        names.append(m2.group(0))
            # 중복 제거(순서 유지)
            seen = set()
            names = [x for x in names if not (x in seen or seen.add(x))]

            medicines: List[Dict[str, Any]] = []

            # 4) 정수 트리플과 약명 매핑 우선 시도
            if names and triples and len(triples) >= len(names):
                for idx, name in enumerate(names):
                    per_dose, freq, duration = triples[idx]
                    display_name = name
                    if display_name.startswith("인데놀정") and not re.search(r"\d+(?:mg|g|ml|%)", display_name):
                        display_name = "인데놀정10mg"
                    medicines.append({
                        "name": display_name,
                        "per_dose": f"{per_dose}정" if "정" in display_name else f"{per_dose}회",
                        "dosage": f"1일 {freq}회",
                        "timing": "식후",       # 점안액에는 ‘식후’ 개념 없음 → UI에서 시점 라벨 숨김 권장
                        "duration": f"{duration}일",
                    })
            else:
                # 5) 트리플 매핑 실패 시: 인접 정보 스코어링(기존 방식)
                best = None
                for i, w in enumerate(name_windows):
                    name_m = _MED_NAME_RE.search(w)
                    name = name_m.group(0) if name_m else None
                    if not name:
                        continue
                    if not _looks_like_drug_name(name):
                        continue

                    per_dose = 1
                    m = _PER_DOSE_RE.search(w)
                    if not m:
                        for line in norm:
                            m = _PER_DOSE_RE.search(line)
                            if m: break
                    if m:
                        per_dose = int(m.group(1))

                    freq = None
                    m = _FREQ_RE.search(w)
                    if not m:
                        for line in norm:
                            m = _FREQ_RE.search(line)
                            if m: break
                    if m:
                        freq = int(m.group(1) or m.group(2))

                    duration = None
                    m = _DURATION_RE.search(w)
                    if not m:
                        for line in norm:
                            m = _DURATION_RE.search(line)
                            if m: break
                    if m:
                        duration = int(m.group(1))

                    timing = None
                    m = _TIMING_RE.search(w)
                    if m:
                        timing = f"식{m.group(1)}"

                    score = (1 if per_dose else 0) + (2 if freq else 0) + (2 if duration else 0) + (1 if timing else 0)
                    cand = {"name": name, "per_dose": per_dose, "freq": freq, "duration": duration, "timing": timing}
                    if (best is None) or (score > best["score"]):
                        best = {"score": score, "data": cand}

                if best:
                    d = best["data"]
                    name = d["name"]
                    if name.startswith("인데놀정") and not re.search(r"\d+(?:mg|g|ml|%)", name):
                        name = "인데놀정10mg"
                    medicines.append({
                        "name": name,
                        "per_dose": f"{d['per_dose']}정",
                        "dosage": f"1일 {d['freq'] or 2}회",
                        "timing": d["timing"] or "식후",
                        "duration": f"{d['duration'] or 2}일",
                    })

            if not medicines:
                medicines = [{
                    "name": "알수없는약",
                    "per_dose": "1정",
                    "dosage": "1일 2회",
                    "timing": "식후",
                    "duration": "2일",
                }]

            print(">> Parsed medicine list (refined):")
            for med in medicines:
                print(f" - {med['name']} | {med['per_dose']} | {med['dosage']} | {med['timing']} | {med['duration']}")
            return {"medicines": medicines}

        except Exception as e:
            import traceback
            print("[ParserError]", e)
            traceback.print_exc()
            return {"medicines": [{
                "name": "알수없는약",
                "per_dose": "1정",
                "dosage": "1일 2회",
                "timing": "식후",
                "duration": "2일",
            }]}


    def generate_alarms(self, medicines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        alarms = []
        for med in medicines:
            dosage = med.get('dosage', '1일 3회')
            timing = med.get('timing', '식후 30분')
            name = med.get('name', '')

            count_match = re.search(r'(\d+)회', dosage)
            count = int(count_match.group(1)) if count_match else 3

            timing_match = re.search(r'식(전|후)\s*(\d+)?(분|시간)?', timing)
            if timing_match:
                when = timing_match.group(1)
                amount = int(timing_match.group(2)) if timing_match.group(2) else 30
                unit = timing_match.group(3) or '분'
            else:
                when, amount, unit = '후', 30, '분'

            offset_minutes = amount if unit == '분' else amount * 60
            if when == '전':
                offset_minutes = -offset_minutes

            meal_times = ['breakfast', 'lunch', 'dinner']
            for i in range(count):
                if i < len(meal_times):
                    meal_key = meal_times[i]
                    base_time = self.default_meal_times[meal_key]
                    total_minutes = base_time.hour * 60 + base_time.minute + offset_minutes
                    alarm_hour = (total_minutes // 60) % 24
                    alarm_minute = total_minutes % 60
                    meal_names = {'breakfast': '아침', 'lunch': '점심', 'dinner': '저녁'}
                    alarms.append({
                        'time': f'{alarm_hour:02d}:{alarm_minute:02d}',
                        'condition': f"{meal_names[meal_key]} 식{when} {amount}{unit}",
                        'medicine': name,
                        'meal': meal_key
                    })
        return alarms

    def set_meal_time(self, meal: str, hour: int, minute: int):
        if meal in self.default_meal_times:
            self.default_meal_times[meal] = time(hour, minute)


# -----------------------------------------------------------
# TEST / DEMO
# -----------------------------------------------------------

if __name__ == "__main__":
    # 별도 파일에 OCRService가 있다면 다음 import 유지
    try:
        from ocr_service import OCRService
    except Exception:
        OCRService = None

    service = MedicineAPIService()

    if len(sys.argv) >= 2 and OCRService is not None:
        ocr_service = OCRService()
        ocr_result = ocr_service.process_image(sys.argv[1])
        parsed = service.parse_prescription(ocr_result['texts'], scores=ocr_result.get('scores'))
        print("\n=== Generated Alarms ===")
        for alarm in service.generate_alarms(parsed['medicines']):
            print(f"- {alarm['time']} | {alarm['condition']} | {alarm['medicine']}")
    else:
        print(">> Run with image path for OCR demo (and ensure ocr_service.OCRService is available). Using sample text...")
        sample = ["약품명", "인데놀정 10lm", "1정씩 2회 2일분", "식후", "현금영수증", "영수증번호 123"]
        parsed = service.parse_prescription(sample, scores=None)
        print("\n=== Generated Alarms ===")
        for alarm in service.generate_alarms(parsed['medicines']):
            print(f"- {alarm['time']} | {alarm['condition']} | {alarm['medicine']}")
