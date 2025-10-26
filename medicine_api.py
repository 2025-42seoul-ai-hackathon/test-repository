#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
의약품 정보 API 서비스 - e약은요 API 연동
"""
import re
import requests
from typing import Dict, List, Optional, Any
from datetime import time


class MedicineAPIService:
    """
    e약은요(의약품안전나라) API를 통한 약품 정보 조회
    API 문서: https://nedrug.mfds.go.kr/api_openapi_info
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: e약은요 API 키 (환경변수 MEDICINE_API_KEY에서도 읽기 가능)
        """
        import os
        self.api_key = api_key or os.getenv('MEDICINE_API_KEY', '')
        self.base_url = 'http://apis.data.go.kr/1471000/DrbEasyDrugInfoService'
        
        if not self.api_key:
            print("WARNING: MEDICINE_API_KEY not set. API calls will fail.")
        
        # 기본 식사 시간 (수정 가능)
        self.default_meal_times = {
            'breakfast': time(8, 0),   # 아침 8시
            'lunch': time(12, 0),      # 점심 12시
            'dinner': time(19, 0)      # 저녁 7시
        }
    
    def get_medicine_info(self, medicine_name: str) -> Optional[Dict[str, Any]]:
        """
        약품명으로 상세 정보 조회
        
        Args:
            medicine_name: 약품명 (예: "타이레놀")
        
        Returns:
            약품 정보 딕셔너리 또는 None
        """
        if not self.api_key:
            # API 키 없을 때 더미 데이터 반환 (개발용)
            return self._get_dummy_medicine_info(medicine_name)
        
        try:
            # API 호출
            endpoint = f"{self.base_url}/getDrbEasyDrugList"
            params = {
                'serviceKey': self.api_key,
                'itemName': medicine_name,
                'type': 'json',
                'numOfRows': 10
            }
            
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # 결과 파싱
            if 'body' in data and 'items' in data['body']:
                items = data['body']['items']
                if items:
                    # 첫 번째 결과 반환
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
        """API 키 없을 때 더미 데이터 (개발/테스트용)"""
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
    
    def parse_prescription(self, texts: List[str]) -> Dict[str, Any]:
        """
        OCR 텍스트 리스트에서 처방 정보 파싱
        
        Args:
            texts: OCR로 추출된 텍스트 리스트
        
        Returns:
            {
                'medicines': [
                    {
                        'name': '약품명',
                        'dosage': '1일 3회',
                        'timing': '식후 30분',
                        'duration': '7일'
                    }
                ]
            }
        """
        medicines = []
        current_medicine = {}
        
        # 패턴 정의
        medicine_pattern = re.compile(r'([가-힣a-zA-Z]+\s*\d+\s*mg|[가-힣a-zA-Z]+정|[가-힣a-zA-Z]+캡슐)')
        dosage_pattern = re.compile(r'1일\s*(\d+)회|하루\s*(\d+)번')
        timing_pattern = re.compile(r'식(전|후)\s*(\d+)?(분|시간)?')
        duration_pattern = re.compile(r'(\d+)일분?')
        
        for text in texts:
            text = text.strip()
            
            # 약품명 찾기
            if medicine_pattern.search(text):
                # 이전 약품 정보 저장
                if current_medicine.get('name'):
                    medicines.append(current_medicine.copy())
                
                current_medicine = {
                    'name': text,
                    'dosage': '',
                    'timing': '',
                    'duration': ''
                }
            
            # 복용 횟수 찾기
            dosage_match = dosage_pattern.search(text)
            if dosage_match and current_medicine:
                count = dosage_match.group(1) or dosage_match.group(2)
                current_medicine['dosage'] = f'1일 {count}회'
            
            # 복용 시점 찾기
            timing_match = timing_pattern.search(text)
            if timing_match and current_medicine:
                when = timing_match.group(1)  # 전 or 후
                amount = timing_match.group(2) or ''
                unit = timing_match.group(3) or ''
                current_medicine['timing'] = f'식{when} {amount}{unit}'.strip()
            
            # 처방 기간 찾기
            duration_match = duration_pattern.search(text)
            if duration_match and current_medicine:
                days = duration_match.group(1)
                current_medicine['duration'] = f'{days}일'
        
        # 마지막 약품 정보 저장
        if current_medicine.get('name'):
            medicines.append(current_medicine)
        
        # 기본값 설정
        for med in medicines:
            if not med['dosage']:
                med['dosage'] = '1일 3회'  # 기본값
            if not med['timing']:
                med['timing'] = '식후 30분'  # 기본값
            if not med['duration']:
                med['duration'] = '7일'  # 기본값
        
        print(">> Parsed medicine list:")
        for med in medicines:
            print(f" - {med['name']} | {med['dosage']} | {med['timing']} | {med['duration']}")

        return {
            'medicines': medicines
        }
    
    def generate_alarms(self, medicines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        약품 정보로부터 알림 시간 생성
        
        Args:
            medicines: 약품 정보 리스트
        
        Returns:
            알림 정보 리스트
        """
        alarms = []
        
        for med in medicines:
            dosage = med.get('dosage', '1일 3회')
            timing = med.get('timing', '식후 30분')
            name = med.get('name', '')
            
            # 복용 횟수 추출
            count_match = re.search(r'(\d+)회', dosage)
            count = int(count_match.group(1)) if count_match else 3
            
            # 복용 시점 추출 (식전/식후, 시간)
            timing_match = re.search(r'식(전|후)\s*(\d+)?(분|시간)?', timing)
            if timing_match:
                when = timing_match.group(1)  # 전 or 후
                amount = int(timing_match.group(2)) if timing_match.group(2) else 30
                unit = timing_match.group(3) or '분'
            else:
                when = '후'
                amount = 30
                unit = '분'
            
            # 시간 계산
            offset_minutes = amount if unit == '분' else amount * 60
            if when == '전':
                offset_minutes = -offset_minutes
            
            # 알림 생성
            meal_times = ['breakfast', 'lunch', 'dinner']
            for i in range(count):
                if i < len(meal_times):
                    meal_key = meal_times[i]
                    base_time = self.default_meal_times[meal_key]
                    
                    # 시간 계산
                    total_minutes = base_time.hour * 60 + base_time.minute + offset_minutes
                    alarm_hour = (total_minutes // 60) % 24
                    alarm_minute = total_minutes % 60
                    
                    # 알림 정보
                    meal_names = {'breakfast': '아침', 'lunch': '점심', 'dinner': '저녁'}
                    
                    alarms.append({
                        'time': f'{alarm_hour:02d}:{alarm_minute:02d}',
                        'condition': f"{meal_names[meal_key]} 식{when} {amount}{unit}",
                        'medicine': name,
                        'meal': meal_key
                    })
        
        return alarms
    
    def set_meal_time(self, meal: str, hour: int, minute: int):
        """
        기본 식사 시간 변경
        
        Args:
            meal: 'breakfast' | 'lunch' | 'dinner'
            hour: 시 (0-23)
            minute: 분 (0-59)
        """
        if meal in self.default_meal_times:
            self.default_meal_times[meal] = time(hour, minute)


# 테스트용
if __name__ == "__main__":
    service = MedicineAPIService()
    
    # 테스트 1: 약품 정보 조회
    print("=== Test 1: Medicine Info ===")
    info = service.get_medicine_info("타이레놀")
    print(f"Name: {info['name']}")
    print(f"Company: {info['company']}")
    
    # 테스트 2: 처방전 파싱
    print("\n=== Test 2: Parse Prescription ===")
    texts = [
        "타이레놀 500mg",
        "1일 3회",
        "식후 30분",
        "7일분",
        "항생제 250mg",
        "1일 2회",
        "식후 1시간",
        "5일분"
    ]
    result = service.parse_prescription(texts)
    for med in result['medicines']:
        print(f"- {med['name']}: {med['dosage']}, {med['timing']}, {med['duration']}")
    
    # 테스트 3: 알림 생성
    print("\n=== Test 3: Generate Alarms ===")
    alarms = service.generate_alarms(result['medicines'])
    for alarm in alarms:
        print(f"- {alarm['time']} | {alarm['condition']} | {alarm['medicine']}")