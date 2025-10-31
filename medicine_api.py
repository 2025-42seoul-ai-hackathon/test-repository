#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
의약품 정보 API 서비스 + 처방 파서 (개별 토큰 기반 Lexicon 매칭)
"""
import os
import re
import sys
import requests
from typing import Dict, List, Optional, Any, Tuple, Set
from datetime import time
from collections import defaultdict

# ----------------------------- 공통 유틸 -----------------------------
_KO_NOISE_KEYWORDS = {
    "환자정보","병원정보","영수증","현금","현금영수증","사업자등록","사업장소재지","발행일","교부번호",
    "약제비","본인부담","보험자부담","총수납","주의사항","복약안내","약품사진","약품명","투약량","횟수","일수",
    "표시대로복용","아침","점심","저녁","취침전","약국","조제약","복약","조제일자","발행기관","총수납금액",
    "현금승인","영수증번호","사업자등록번호","복용완료일","투약량횟수일수","생리통에","효과","일반","제와"
}

_PER_DOSE_RE = re.compile(r"(\d+)정씩")
_FREQ_RE = re.compile(r"(?:1일|하루)(\d+)회|(\d+)번")
_DURATION_RE = re.compile(r"(\d+)일분?")
_TIMING_RE = re.compile(r"식(전|후)")

# --- NEW: 사용법을 소아/성인 문장으로 분리 ---
def _split_usage_by_age(usage_text: str):
    if not usage_text:
        return {'child': None, 'adult': None}
    lines = [s.strip() for s in re.split(r'[\n\.]+', usage_text) if s.strip()]
    child_lines = [s for s in lines if re.search(r'(만\s*8세|만\s*15세\s*미만|소아|어린이)', s)]
    adult_lines = [s for s in lines if re.search(r'(성인|만\s*15세\s*이상)', s)]
    child = ' '.join(child_lines) if child_lines else None
    adult = ' '.join(adult_lines) if adult_lines else None
    return {'child': child, 'adult': adult}

def _parse_usage_ranges(usage_text: str):
    """
    반환:
    {
        'dose_range': {'min': int|None, 'max': int|None, 'unit': str|''},
        'freq_range': {'min': int|None, 'max': int|None},
        'timing': '식후|식전|식간|취침전|공복|'
    }
    """
    res = {
        'dose_range': {'min': None, 'max': None, 'unit': ''},
        'freq_range': {'min': None, 'max': None},
        'timing': ''
    }
    if not usage_text:
        return res

    norm = re.sub(r'공복[^가-힣A-Za-z0-9]{0,5}을\s*피하[세요]*|빈\s*속을\s*피하[세요]*', '식후', usage_text)

    m = re.search(r'1회\s*(?:에\s*)?(\d+)(?:\s*~\s*(\d+))?\s*(정|캡슐|포|ml|mL)', norm)
    if not m:
        m = re.search(r'(\d+)(?:\s*~\s*(\d+))?\s*(정|캡슐|포|ml|mL)\s*씩', norm)
    if m:
        lo = int(m.group(1)); hi = int(m.group(2)) if m.group(2) else lo
        res['dose_range'] = {'min': lo, 'max': hi, 'unit': m.group(3)}

    m = re.search(r'(?:1일|하루|매일)\s*(\d+)(?:\s*~\s*(\d+))?\s*(?:회|번)', norm)
    if not m:
        m = re.search(r'(\d+)(?:\s*~\s*(\d+))?\s*(?:회|번)\s*(?:복용|투여)', norm)
    if m:
        lo = int(m.group(1)); hi = int(m.group(2)) if m.group(2) else lo
        res['freq_range'] = {'min': lo, 'max': hi}

    if re.search(r'식후', norm):        res['timing'] = '식후'
    elif re.search(r'식전', norm):      res['timing'] = '식전'
    elif re.search(r'식간', norm):      res['timing'] = '식간'
    elif re.search(r'취침\s*전', norm): res['timing'] = '취침전'
    elif re.search(r'공복(?:\(빈\s*속\))?', norm): res['timing'] = '공복'

    return res

def _normalize_ocr(s: str) -> str:
    """OCR 오인식 보정"""
    t = re.sub(r"[`'\"[\]<>･·]", "", s)
    t = re.sub(r"\s+", "", t)
    t = re.sub(r"(\d)l(\d)", r"\g<1>1\g<2>", t)
    t = t.replace("O", "0").replace("|", "1")
    t = re.sub(r"(정)1[에eE][mM]9\b", r"\g<1>10mg", t)
    t = re.sub(r"(정)1[이iIlL][mM]\b", r"\g<1>10mg", t)
    t = re.sub(r"(?<=\d)lm\b", "10mg", t)
    t = re.sub(r"(?<=\d)m\b", "mg", t)
    # 특수문자/숫자 제거하지 않음 (용량 정보 보존)
    return t

def _is_noise_line(t: str) -> bool:
    """노이즈 라인 판별"""
    if len(t) <= 1:
        return True
    for k in _KO_NOISE_KEYWORDS:
        if k in t:
            return True
    if re.fullmatch(r"\d{2,}원", t):
        return True
    if re.fullmatch(r"\d{3,}[-]?\d{2}[-]?\d{5}", t):
        return True
    if re.fullmatch(r"\d{8}", t):
        return True
    if re.fullmatch(r"\d{4}[-]?\d{2}[-]?\d{2}", t):
        return True
    return False

# ----------------------------- 개별 토큰 Lexicon 매칭 -----------------------------
class DrugLexicon:
    def __init__(self, items: List[str]):
        """
        items: ['이지앤6 이브 | 이브A정', '타이레놀 | 타이레놀정', ...]
        """
        self.drugs: List[Dict[str, Any]] = []
        
        for line in items:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if not parts:
                continue
            
            canonical = parts[0]
            aliases = parts
            
            # 각 약명을 개별 토큰으로 분해
            all_tokens: Set[str] = set()
            for alias in aliases:
                norm_alias = _normalize_ocr(alias)
                # 한글만 추출 (숫자/영문은 용량으로 간주)
                korean_tokens = re.findall(r'[가-힣]+', norm_alias)
                all_tokens.update(t for t in korean_tokens if len(t) >= 2)
            
            self.drugs.append({
                'canonical': canonical,
                'aliases': aliases,
                'tokens': all_tokens,
                'normalized_aliases': [_normalize_ocr(a) for a in aliases]
            })
        
        print(f">> Lexicon loaded: {len(self.drugs)} drugs")
        for d in self.drugs[:3]:  # 디버그용
            print(f"   - {d['canonical']}: tokens={d['tokens']}")

    def match_from_ocr_lines(self, ocr_lines: List[str]) -> List[Dict[str, Any]]:
        """
        OCR 라인 개별 비교 → Lexicon 토큰 매칭
        
        Returns:
            [{'canonical': '이지앤6 이브', 'score': 0.95, 'matched_line': '이브', ...}, ...]
        """
        results = []
        
        for line_idx, line in enumerate(ocr_lines):
            norm_line = _normalize_ocr(line)
            
            # 라인에서 한글 토큰 추출
            line_tokens = set(re.findall(r'[가-힣]+', norm_line))
            if not line_tokens:
                continue
            
            # 각 약품과 비교
            for drug in self.drugs:
                matched_tokens = line_tokens.intersection(drug['tokens'])
                if not matched_tokens:
                    continue
                
                # 점수 계산
                score = 0.0
                
                # 1. 단일 토큰 완전 일치 (0.6점)
                if len(matched_tokens) == 1 and len(line_tokens) == 1:
                    token = list(matched_tokens)[0]
                    # Lexicon에 해당 토큰이 독립적으로 있는지 확인
                    if any(token in alias.split() for alias in drug['aliases']):
                        score = 0.6
                    else:
                        score = 0.5
                
                # 2. 다중 토큰 매치 (0.8점)
                elif len(matched_tokens) >= 2:
                    score = 0.8
                
                # 3. 전체 alias와 유사도 체크
                max_similarity = 0.0
                for alias in drug['normalized_aliases']:
                    # 라인이 alias에 포함되거나 alias가 라인에 포함
                    if norm_line in alias or alias in norm_line:
                        max_similarity = 1.0
                        break
                    # 부분 일치
                    common_chars = sum(1 for c in norm_line if c in alias)
                    similarity = common_chars / max(len(norm_line), len(alias))
                    max_similarity = max(max_similarity, similarity)
                
                score = max(score, max_similarity * 0.9)
                
                if score >= 0.4:  # 임계값
                    results.append({
                        'canonical': drug['canonical'],
                        'aliases': drug['aliases'],
                        'score': score,
                        'matched_tokens': list(matched_tokens),
                        'matched_line': line,
                        'line_index': line_idx
                    })
        
        # 동일 canonical은 최고 점수만 유지
        by_canon: Dict[str, Dict[str, Any]] = {}
        for r in results:
            canon = r['canonical']
            if canon not in by_canon or r['score'] > by_canon[canon]['score']:
                by_canon[canon] = r
        
        final = list(by_canon.values())
        final.sort(key=lambda x: x['score'], reverse=True)
        return final

# ----------------------------- Medicine API + Parser -----------------------------
class MedicineAPIService:
    def __init__(self, api_key: Optional[str] = None, lexicon_path: Optional[str] = "./drug_lexicon.txt"):
        self.api_key = api_key or os.getenv('MEDICINE_API_KEY', '')
        self.base_url = 'http://apis.data.go.kr/1471000/DrbEasyDrugInfoService'
        if not self.api_key:
            print("WARNING: MEDICINE_API_KEY not set. API calls will fail.")

        self.default_meal_times = {
            'breakfast': time(8, 0),
            'lunch': time(12, 0),
            'dinner': time(19, 0)
        }

        # Lexicon 로드
        self.lexicon: Optional[DrugLexicon] = None
        if lexicon_path and os.path.exists(lexicon_path):
            try:
                with open(lexicon_path, 'r', encoding='utf-8') as f:
                    lines = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]
                if lines:
                    self.lexicon = DrugLexicon(lines)
            except Exception as e:
                print(f"Lexicon load error: {e}")

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
                    classification = (
                        item.get('etcOtcName')
                        or item.get('etcOtcCode')
                        or item.get('className')
                        or '일반의약품'
                    )
                    return {
                        'name': item.get('itemName', ''),
                        'company': item.get('entpName', ''),
                        'classification': classification,
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

    def _extract_dosage_info(self, lines: List[str], target_line_idx: int) -> Optional[str]:
        """약명 주변 라인에서 용량 정보 추출"""
        # 앞뒤 2줄 범위 확인
        start = max(0, target_line_idx - 2)
        end = min(len(lines), target_line_idx + 3)
        
        for line in lines[start:end]:
            # 숫자+단위 패턴 찾기
            match = re.search(r'(\d+(?:\.\d+)?)\s*(mg|g|ml|%|밀리그램)', line)
            if match:
                num = match.group(1)
                unit = match.group(2).replace('밀리그램', 'mg')
                return f"{num}{unit}"
        return None

    def _parse_usage_from_api(self, usage_text: str) -> Dict[str, Any]:
        result = {'per_dose': 0, 'frequency': 0, 'timing': ''}

        if not usage_text:
            return result

        print(f"   [DEBUG] Parsing usage: {usage_text[:150]}...")

        # 0) 의미 선치환: "공복을 피하여" 계열은 식후로 간주
        norm = usage_text
        norm = re.sub(r'공복[^가-힣A-Za-z0-9]{0,5}을\s*피하[세요]*', '식후', norm)
        norm = re.sub(r'공복[^가-힣A-Za-z0-9]{0,5}피하여', '식후', norm)
        norm = re.sub(r'빈\s*속을\s*피하[세요]*', '식후', norm)

        # 1) 1회 복용량
        for pattern in [
            r'1회\s*(?:에\s*)?(\d+)(?:~\d+)?\s*(?:정|캡슐)',
            r'(\d+)(?:~\d+)?\s*(?:정|캡슐)\s*씩',
            r'(\d+)\s*(?:정|캡슐)(?:\s*복용|\s*투여)?',
        ]:
            m = re.search(pattern, norm)
            if m:
                result['per_dose'] = int(m.group(1))
                print(f"   [DEBUG] per_dose matched: {m.group(0)} → {result['per_dose']}")
                break

        # 2) 1일 횟수
        for pattern in [
            r'(?:1일|하루|매일)\s*(\d+)(?:~(\d+))?\s*(?:회|번)',
            r'(\d+)(?:~(\d+))?\s*(?:회|번)\s*(?:복용|투여)',
        ]:
            m = re.search(pattern, norm)
            if m:
                lo = int(m.group(1))
                hi = int(m.group(2)) if m.lastindex and m.group(2) else lo
                # 알람 생성 목적상 상한을 채택(보수적 리마인드)
                result['frequency'] = hi
                print(f"   [DEBUG] frequency matched: {m.group(0)} → {result['frequency']}")
                break

        # 3) 타이밍: 식후/식전/식간/취침전 우선, 그 다음 '공복' 단독
        for regex, value in [
            (r'식후', '식후'),
            (r'식전', '식전'),
            (r'식간', '식간'),
            (r'취침\s*전', '취침전'),
            (r'공복(?:\(빈\s*속\))?', '공복'),
        ]:
            if re.search(regex, norm):
                result['timing'] = value
                print(f"   [DEBUG] timing matched: {regex} → {value}")
                break

        print(f"   [DEBUG] Final result: {result}")
        return result

    def parse_prescription(self, texts: List[str], scores: Optional[List[float]] = None) -> Dict[str, Any]:
        try:
            print(f"\n>> Starting parse with {len(texts)} OCR lines")

            # 1) 전처리
            clean_lines: List[str] = []
            clean_scores: List[Optional[float]] = []
            for idx, raw in enumerate(texts):
                norm = _normalize_ocr(raw)
                sc = scores[idx] if (scores and idx < len(scores)) else None
                if not norm:
                    continue
                if sc is not None and sc < 0.50:
                    continue
                if _is_noise_line(norm):
                    continue
                clean_lines.append(norm)
                clean_scores.append(sc)
            print(f">> Cleaned lines: {clean_lines}")

            # 2) Lexicon 매칭
            candidates: List[Dict[str, Any]] = []
            if self.lexicon:
                matches = self.lexicon.match_from_ocr_lines(clean_lines)
                print(f"\n>> Lexicon matches: {len(matches)}")
                for m in matches:
                    print(f"   - {m['canonical']} (score: {m['score']:.2f}, line: '{m['matched_line']}')")
                    dosage = self._extract_dosage_info(clean_lines, m['line_index'])
                    full_name = f"{m['canonical']} {dosage}" if dosage else m['canonical']
                    candidates.append({
                        'canonical': full_name,
                        'score': m['score'],
                        'matched_line': m['matched_line'],
                        'line_index': m['line_index']
                    })

            medicine_names = [c['canonical'] for c in candidates]
            medicines: List[Dict[str, Any]] = []

            # 3) 각 약명에 대해 e약은요 조회 → 사용법을 소아/성인으로 분리 → 범위를 통째로 추출
            for name in medicine_names:
                api_info = self.get_medicine_info(name)

                if api_info:
                    usage_text = api_info.get('usage', '') or ''
                    classification = (api_info.get('classification') or '일반의약품')

                    # --- 범위 추출 유틸 사용 ---
                    age_blocks = _split_usage_by_age(usage_text)
                    child_ranges = _parse_usage_ranges(age_blocks['child']) if age_blocks['child'] else {
                        'dose_range': {'min': None, 'max': None, 'unit': ''},
                        'freq_range': {'min': None, 'max': None},
                        'timing': ''
                    }
                    adult_ranges = _parse_usage_ranges(age_blocks['adult']) if age_blocks['adult'] else {
                        'dose_range': {'min': None, 'max': None, 'unit': ''},
                        'freq_range': {'min': None, 'max': None},
                        'timing': ''
                    }

                    # 하위호환 필드(단일값)는 성인 상한 → 없으면 소아 상한
                    per_dose = adult_ranges['dose_range']['max'] or child_ranges['dose_range']['max'] or 0
                    unit     = adult_ranges['dose_range']['unit'] or child_ranges['dose_range']['unit'] or ''
                    freq     = adult_ranges['freq_range']['max'] or child_ranges['freq_range']['max'] or 0
                    timing   = adult_ranges['timing'] or child_ranges['timing'] or '식후'

                    print(f"\n>> API usage for '{name}':")
                    print(f"   Raw: {usage_text[:150]}...")
                    print(f"   ChildRanges: {child_ranges}")
                    print(f"   AdultRanges: {adult_ranges}")

                    medicines.append({
                        "name": name,
                        "per_dose": per_dose,           # 단일 상한값(하위호환)
                        "unit": unit,                   # 단위(정/캡슐/포/ml 등)
                        "frequency": freq,              # 단일 상한값(하위호환)
                        "timing": timing,
                        "duration": 0,
                        # --- NEW: 프론트 선택용 원본 범위 동봉 ---
                        "ranges": {
                            "child": {"age_min": 8, "age_max": 14, **child_ranges},
                            "adult": {"age_min": 15, "age_max": None, **adult_ranges},
                        },
                        "details": { "classification": classification }
                    })
                else:
                    medicines.append({
                        "name": name,
                        "per_dose": 0,
                        "unit": "",
                        "frequency": 0,
                        "timing": '정보없음',
                        "duration": 0,
                        "ranges": {},
                        "details": { "classification": "일반의약품" }
                    })

            if not medicines:
                medicines = [{
                    "name": "약 정보 없음 (Lexicon 확인 필요)",
                    "per_dose": 0,
                    "unit": "",
                    "frequency": 0,
                    "timing": '정보없음',
                    "duration": 0,
                    "ranges": {},
                    "details": { "classification": "일반의약품" }
                }]

            print("\n>> Final parsed medicines:")
            for med in medicines:
                print(f"   - {med['name']} | 1회 {med.get('per_dose',0)}{med.get('unit','')} | 1일 {med.get('frequency',0)}회 | {med.get('timing','')} | {med.get('duration',0)}일")

            return {"medicines": medicines, "candidates": candidates}

        except Exception as e:
            import traceback
            print(f"\n[ParserError] {e}")
            traceback.print_exc()
            return {"medicines": [{
                "name": "파싱 오류",
                "per_dose": 0,
                "unit": "",
                "frequency": 0,
                "timing": '정보없음',
                "duration": 0,
                "ranges": {},
                "details": { "classification": "일반의약품" }
            }], "candidates": []}


    def generate_alarms(self, medicines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        복용 정보를 기반으로 알람 생성
        
        frequency가 0이면 알람 생성 안 함
        """
        alarms = []
        
        for med in medicines:
            freq = med.get('frequency', 0)
            timing = med.get('timing', '정보없음')
            name = med.get('name', '')
            per_dose = med.get('per_dose', 0)
            
            # 복용 횟수 정보가 없으면 알람 생성 불가
            if freq == 0:
                print(f">> Skipping alarm for '{name}': frequency is 0")
                continue
            
            # timing에서 식전/식후 파싱
            offset_minutes = 0
            if '식후' in timing:
                offset_minutes = 30
            elif '식전' in timing:
                offset_minutes = -30
            elif '식간' in timing:
                offset_minutes = 120  # 식후 2시간
            elif '취침전' in timing:
                # 취침 전은 특별 처리
                alarms.append({
                    'time': '22:00',
                    'condition': '취침 전',
                    'medicine': name,
                    'per_dose': per_dose,
                    'meal': 'bedtime'
                })
                continue
            
            # 복용 횟수에 따라 시간 배분
            meal_times = ['breakfast', 'lunch', 'dinner']
            for i in range(min(freq, 3)):  # 최대 3회까지
                meal_key = meal_times[i]
                base_time = self.default_meal_times[meal_key]
                
                total_minutes = base_time.hour * 60 + base_time.minute + offset_minutes
                alarm_hour = (total_minutes // 60) % 24
                alarm_minute = total_minutes % 60
                
                meal_names = {'breakfast': '아침', 'lunch': '점심', 'dinner': '저녁'}
                condition_text = f"{meal_names[meal_key]} {timing}" if timing != '정보없음' else meal_names[meal_key]
                
                alarms.append({
                    'time': f'{alarm_hour:02d}:{alarm_minute:02d}',
                    'condition': condition_text,
                    'medicine': name,
                    'per_dose': per_dose,
                    'meal': meal_key
                })
        
        return alarms


# ----------------------------- TEST -----------------------------
if __name__ == "__main__":
    try:
        from ocr_service import OCRService
    except Exception:
        OCRService = None

    service = MedicineAPIService()
    
    # 테스트 케이스: 제공된 OCR 결과
    test_lines = [
        "일반으으로",
        "썼대웅제와",
        "생리통에",
        "효과빠론액상형소염진통 제",
        "이져",
        "연질랩술",
        "이브",
        "-",
        "春술",
        "30",
        "이부프로펜",
        "파마브롬"
    ]
    
    test_scores = [0.63, 0.74, 1.00, 0.93, 0.71, 0.81, 0.95, 0.91, 0.93, 1.00, 0.93, 0.85]
    
    print("="*60)
    print("TEST: 약 상자 OCR 결과 파싱")
    print("="*60)
    
    parsed = service.parse_prescription(test_lines, scores=test_scores)
    
    print("\n=== Candidates ===")
    for c in parsed['candidates']:
        print(f"- {c['canonical']} (score: {c['score']:.2f})")
    
    print("\n=== Medicines ===")
    for m in parsed['medicines']:
        if m['per_dose'] == 0 and m['frequency'] == 0:
            print(f"- {m['name']}: 복용 정보 없음")
        else:
            print(f"- {m['name']}: {m['per_dose']}정, 1일 {m['frequency']}회, {m['timing']}")
    
    print("\n=== Generated Alarms ===")
    alarms = service.generate_alarms(parsed['medicines'])
    if alarms:
        for alarm in alarms:
            dose_text = f"{alarm['per_dose']}정" if alarm['per_dose'] > 0 else "?"
            print(f"- {alarm['time']} | {alarm['condition']} | {alarm['medicine']} ({dose_text})")
    else:
        print("알람 생성 불가 (복용 정보 없음)")