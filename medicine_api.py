#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
의약품 정보 API 서비스 + 처방 파서 (개별 토큰 기반 Lexicon 매칭)
- 중복 변형 토큰(보정/접두 n-gram/제형 변형) 루트 단위로 접기
- DF/IDF를 토큰 루트 기준으로 계산
- 같은 줄/같은 canonical 중복 방지
- candidates는 canonical로 dedupe, 용량은 display_name에만 부착
"""
import os
import re
import sys
import math
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
        'freq_range': {'min': int|None, 'max': None|int},
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

# ----------------------------- NEW: 한글 자모 퍼지 매칭 & 노이즈 토큰 -----------------------------
_HANGUL_BASE = 0xAC00
_ONSETS = [chr(c) for c in range(ord('ᄀ'), ord('ᄒ')+1)]
_NUCS   = [chr(c) for c in range(ord('ᅡ'), ord('ᅵ')+1)]
_CODS   = [''] + [chr(c) for c in range(ord('ᆨ'), ord('ᇂ')+1)]

def _to_jamo(s: str) -> str:
    out = []
    for ch in s:
        code = ord(ch)
        if 0xAC00 <= code <= 0xD7A3:
            syll = code - _HANGUL_BASE
            onset = syll // 588
            nuc   = (syll % 588) // 28
            coda  = syll % 28
            out.extend([_ONSETS[onset], _NUCS[nuc]])
            if coda: out.append(_CODS[coda])
        else:
            out.append(ch)
    return ''.join(out)

def _levenshtein(a: str, b: str) -> int:
    if a == b: return 0
    if not a: return len(b)
    if not b: return len(a)
    prev = list(range(len(b)+1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            ins = cur[j-1] + 1
            dele = prev[j] + 1
            sub = prev[j-1] + (ca != cb)
            cur.append(min(ins, dele, sub))
        prev = cur
    return prev[-1]

def _jamo_sim(a: str, b: str) -> float:
    ja, jb = _to_jamo(a), _to_jamo(b)
    d = _levenshtein(ja, jb)
    L = max(len(ja), len(jb))
    if L == 0: return 0.0
    return max(0.0, 1.0 - d / max(2, L))

# 제형/수식어 노이즈 토큰 확장
_NOISE_TOKENS = {
    '일','회','전','후','식전','식후','분','정','캡슐','mg','m g','병의원','영수증','번호','복약','안내',
    '피알','서방','장용'
}
def _is_noise_token(tok: str) -> bool:
    return tok in _NOISE_TOKENS or tok.isdigit()

# --- NEW: 제형/접두·접미 제거 + 접두 n-gram 생성 ---
_AFFIX_DROP_RE = re.compile(r'(서방|장용|피알|에스알|SR|ER|OD|에스)')
_FORM_SUFFIX_RE = re.compile(r'(정|캡슐|시럽|현탁|정제|정밀)$')

def _strip_affixes(token: str) -> str:
    t = _AFFIX_DROP_RE.sub('', token)
    t = _FORM_SUFFIX_RE.sub('', t)
    return t

def _prefix_ngrams(token: str, min_len: int = 2, max_len: int = 4) -> Set[str]:
    out = set()
    L = len(token)
    up = min(L, max_len)
    for k in range(min_len, up + 1):
        out.add(token[:k])
    return out

# --- NEW: 변형 접기(루트 기반) ---
def _token_root(tok: str) -> str:
    base = _strip_affixes(tok)
    return _to_jamo(base)

def _collapse_variants(tokens: Set[str]) -> Set[str]:
    """
    같은 루트를 공유하는 변형 토큰(원본, 접두 n-gram, 제형/접미 변형 등)을
    대표 1개(가장 긴 토큰)로 압축한다.
    """
    by_root: Dict[str, str] = {}
    for t in tokens:
        r = _token_root(t)
        if not r:
            continue
        prev = by_root.get(r)
        if prev is None or len(t) > len(prev):
            by_root[r] = t
    return set(by_root.values())

def _roots(tokens: Set[str]) -> Set[str]:
    out = set()
    for t in tokens:
        r = _token_root(t)
        if r:
            out.add(r)
    return out

# ----------------------------- 개별 토큰 Lexicon 매칭 -----------------------------
class DrugLexicon:
    def __init__(self, items: List[str]):
        """
        items: ['이지앤6 이브 | 이브A정', '타이레놀 | 타이레놀정', ...]
        """
        self.drugs: List[Dict[str, Any]] = []
        self.token_df: Dict[str, int] = {}  # 루트 DF

        temp_drugs: List[Dict[str, Any]] = []
        for line in items:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if not parts:
                continue

            canonical = parts[0]
            aliases = parts

            # 각 약명을 개별 토큰으로 분해
            all_tokens: Set[str] = set()
            normalized_aliases = []
            for alias in aliases:
                norm_alias = _normalize_ocr(alias)
                normalized_aliases.append(norm_alias)
                # 한글만 추출 (숫자/영문은 용량으로 간주)
                korean_tokens = re.findall(r'[가-힣]+', norm_alias)
                for t in korean_tokens:
                    if len(t) < 2:
                        continue
                    base = _strip_affixes(t)
                    if len(base) >= 2:
                        all_tokens.add(base)
                        all_tokens.update(_prefix_ngrams(base))
                    # 원본 토큰도 유지
                    all_tokens.add(t)

            # 변형 접기 + 루트 집합
            all_tokens = _collapse_variants(all_tokens)
            token_roots = _roots(all_tokens)

            temp_drugs.append({
                'canonical': canonical,
                'aliases': aliases,
                'tokens': all_tokens,
                'token_roots': token_roots,          # 루트 저장
                'normalized_aliases': normalized_aliases
            })

        # DF 집계(루트 기준)
        for d in temp_drugs:
            for r in d['token_roots']:
                self.token_df[r] = self.token_df.get(r, 0) + 1

        # 자모 캐시 및 최종 저장
        for d in temp_drugs:
            d['aliases_jamo'] = [_to_jamo(a) for a in d['normalized_aliases']]
            self.drugs.append(d)

        self.N_drugs = max(1, len(self.drugs))

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

            # 라인에서 한글 토큰 추출 + 잡음 제거 → 변형 접기
            raw_tokens = re.findall(r'[가-힣]+', norm_line)
            line_tokens_raw = {t for t in raw_tokens if not _is_noise_token(t)}
            if not line_tokens_raw:
                continue
            line_tokens = _collapse_variants(line_tokens_raw)
            line_roots  = _roots(line_tokens)

            seen_line_canon: Set[str] = set()  # 같은 줄에서 같은 canonical 중복 방지

            # 각 약품과 비교
            for drug in self.drugs:
                # 루트 레벨 매칭
                matched_roots = line_roots.intersection(drug['token_roots'])
                matched_tokens: Set[str] = set()
                if matched_roots:
                    # 라인 대표 토큰 중 루트 일치하는 것만 채택(보기용)
                    rep_by_root = { _token_root(t): t for t in line_tokens }
                    matched_tokens = { rep_by_root[r] for r in matched_roots if r in rep_by_root }

                # 점수 계산
                score = 0.0

                # [A] alias 포함/포함됨 강매칭
                hard_hit = False
                for alias in drug['normalized_aliases']:
                    if alias and (alias in norm_line or norm_line in alias):
                        score = max(score, 0.95)
                        hard_hit = True
                        break
                if not hard_hit:
                    # 접두/접미 결합 체크: 휴낙정 ⊂ 휴낙정아세클로페낙
                    for alias in drug['normalized_aliases']:
                        for tok in line_tokens:
                            if tok.startswith(alias) and len(alias) >= 2:
                                score = max(score, 0.95)
                                matched_tokens = matched_tokens.union({alias, tok})
                                hard_hit = True
                                break
                            if alias.startswith(tok) and len(tok) >= 2:
                                score = max(score, 0.90)
                                matched_tokens = matched_tokens.union({tok})
                                hard_hit = True
                                break
                        if hard_hit:
                            break

                # [B] 토큰 매치 기반 스코어 (루트 DF/IDF 사용)
                idf_boost = 0.0
                if matched_tokens:
                    for t in matched_tokens:
                        r = _token_root(t)
                        df = self.token_df.get(r, 1)
                        idf_boost = max(idf_boost, min(0.6, 0.2 + math.log(self.N_drugs / df + 1, 2) * 0.2))
                    base = 0.6 if len(matched_tokens) == 1 else 0.8
                    score = max(score, base + idf_boost)

                # [C] 자모 퍼지 유사도
                max_jamo_sim = 0.0
                for alias, alias_j in zip(drug['normalized_aliases'], drug['aliases_jamo']):
                    max_jamo_sim = max(max_jamo_sim, _jamo_sim(alias, norm_line))
                    for tok in line_tokens:
                        max_jamo_sim = max(max_jamo_sim, _jamo_sim(alias, tok))
                if max_jamo_sim >= 0.85:
                    score = max(score, 0.92 * max_jamo_sim)
                elif max_jamo_sim >= 0.70:
                    score = max(score, 0.80 * max_jamo_sim)

                # [D] 임계값: 잡음 비율 + 희귀 매치 시 완화
                if raw_tokens:
                    noise_cnt = sum(1 for t in raw_tokens if _is_noise_token(t))
                    noise_ratio = noise_cnt / len(raw_tokens)
                else:
                    noise_ratio = 0.0
                threshold = 0.45 if noise_ratio <= 0.5 else 0.5
                if matched_tokens and idf_boost >= 0.3:
                    threshold = min(threshold, 0.40)

                if score >= threshold:
                    # 같은 줄에서 동일 canonical 중복 차단
                    if drug['canonical'] in seen_line_canon:
                        continue
                    seen_line_canon.add(drug['canonical'])
                    results.append({
                        'canonical': drug['canonical'],
                        'aliases': drug['aliases'],
                        'score': round(min(score, 1.0), 2),
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
        start = max(0, target_line_idx - 2)
        end = min(len(lines), target_line_idx + 3)
        for line in lines[start:end]:
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

        norm = usage_text
        norm = re.sub(r'공복[^가-힣A-Za-z0-9]{0,5}을\s*피하[세요]*', '식후', norm)
        norm = re.sub(r'공복[^가-힣A-Za-z0-9]{0,5}피하여', '식후', norm)
        norm = re.sub(r'빈\s*속을\s*피하[세요]*', '식후', norm)

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

        for pattern in [
            r'(?:1일|하루|매일)\s*(\d+)(?:~(\d+))?\s*(?:회|번)',
            r'(\d+)(?:~(\d+))?\s*(?:회|번)\s*(?:복용|투여)',
        ]:
            m = re.search(pattern, norm)
            if m:
                lo = int(m.group(1))
                hi = int(m.group(2)) if m.lastindex and m.group(2) else lo
                result['frequency'] = hi
                print(f"   [DEBUG] frequency matched: {m.group(0)} → {result['frequency']}")
                break

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

                # 동일 canonical 중 최고점만
                best_by_canon: Dict[str, Dict[str, Any]] = {}
                for m in matches:
                    if (m['canonical'] not in best_by_canon) or (m['score'] > best_by_canon[m['canonical']]['score']):
                        best_by_canon[m['canonical']] = m

                for m in best_by_canon.values():
                    print(f"   - {m['canonical']} (score: {m['score']:.2f}, line: '{m['matched_line']}')")
                    dosage = self._extract_dosage_info(clean_lines, m['line_index'])
                    candidates.append({
                        'canonical': m['canonical'],  # dedupe key
                        'display_name': f"{m['canonical']} {dosage}" if dosage else m['canonical'],
                        'score': m['score'],
                        'matched_line': m['matched_line'],
                        'line_index': m['line_index']
                    })

            medicine_names = [c['canonical'] for c in candidates]  # API 조회 키
            name_for_display = {c['canonical']: c['display_name'] for c in candidates}
            medicines: List[Dict[str, Any]] = []

            # 3) 각 약명에 대해 e약은요 조회 → 사용법을 소아/성인으로 분리 → 범위를 통째로 추출
            for name in medicine_names:
                api_info = self.get_medicine_info(name)

                if api_info:
                    usage_text = api_info.get('usage', '') or ''
                    classification = (api_info.get('classification') or '일반의약품')

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

                    per_dose = adult_ranges['dose_range']['max'] or child_ranges['dose_range']['max'] or 0
                    unit     = adult_ranges['dose_range']['unit'] or child_ranges['dose_range']['unit'] or ''
                    freq     = adult_ranges['freq_range']['max'] or child_ranges['freq_range']['max'] or 0
                    timing   = adult_ranges['timing'] or child_ranges['timing'] or '식후'

                    print(f"\n>> API usage for '{name}':")
                    print(f"   Raw: {usage_text[:150]}...")
                    print(f"   ChildRanges: {child_ranges}")
                    print(f"   AdultRanges: {adult_ranges}")

                    medicines.append({
                        "name": name_for_display.get(name, name),  # 표시용 이름(용량 포함)
                        "per_dose": per_dose,
                        "unit": unit,
                        "frequency": freq,
                        "timing": timing,
                        "duration": 0,
                        "ranges": {
                            "child": {"age_min": 8, "age_max": 14, **child_ranges},
                            "adult": {"age_min": 15, "age_max": None, **adult_ranges},
                        },
                        "details": { "classification": classification }
                    })
                else:
                    medicines.append({
                        "name": name_for_display.get(name, name),
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

            if freq == 0:
                print(f">> Skipping alarm for '{name}': frequency is 0")
                continue

            offset_minutes = 0
            if '식후' in timing:
                offset_minutes = 30
            elif '식전' in timing:
                offset_minutes = -30
            elif '식간' in timing:
                offset_minutes = 120  # 식후 2시간
            elif '취침전' in timing:
                alarms.append({
                    'time': '22:00',
                    'condition': '취침 전',
                    'medicine': name,
                    'per_dose': per_dose,
                    'meal': 'bedtime'
                })
                continue

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
        "파마브롬",
        "피알'일4회레피즈"
    ]

    test_scores = [0.63, 0.74, 1.00, 0.93, 0.71, 0.81, 0.95, 0.91, 0.93, 1.00, 0.93, 0.85, 0.88]

    print("="*60)
    print("TEST: 약 상자 OCR 결과 파싱")
    print("="*60)

    parsed = service.parse_prescription(test_lines, scores=test_scores)

    print("\n=== Candidates ===")
    for c in parsed['candidates']:
        print(f"- {c.get('display_name', c['canonical'])} (score: {c['score']:.2f})")

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
