#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Flask API 서버 - 알약 도우미 백엔드
"""
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from ocr_service import OCRService
from medicine_api import MedicineAPIService

app = Flask(__name__)
CORS(app)  # React 개발 서버와 통신 허용

# 설정
UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 서비스 초기화 (서버 시작 시 1번만)
print(">> Initializing OCR service...")
ocr_service = OCRService(device='auto', lang='korean')
print(">> OCR service ready")

print(">> Initializing Medicine API service...")
medicine_service = MedicineAPIService()
print(">> Medicine API service ready")


def allowed_file(filename):
    """허용된 파일 확장자 체크"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/health', methods=['GET'])
def health_check():
    """서버 상태 체크"""
    return jsonify({
        'status': 'ok',
        'message': 'Server is running'
    })


@app.route('/api/ocr', methods=['POST'])
def ocr_endpoint():
    """
    약 봉투 이미지 OCR 처리
    
    Request:
        - file: 이미지 파일 (multipart/form-data)
    
    Response:
        {
            "status": "success",
            "data": {
                "texts": ["타이레놀 500mg", ...],
                "scores": [0.98, ...],
                "raw_result": {...}
            }
        }
    """
    # 파일 체크
    if 'file' not in request.files:
        return jsonify({
            'status': 'error',
            'message': '파일이 업로드되지 않았습니다'
        }), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({
            'status': 'error',
            'message': '파일이 선택되지 않았습니다'
        }), 400
    
    if not allowed_file(file.filename):
        return jsonify({
            'status': 'error',
            'message': '지원하지 않는 파일 형식입니다 (png, jpg, jpeg, gif만 가능)'
        }), 400
    
    try:
        # 파일 저장
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # OCR 처리
        result = ocr_service.process_image(filepath)
        
        # 임시 파일 삭제
        if os.path.exists(filepath):
            os.remove(filepath)
        
        return jsonify({
            'status': 'success',
            'data': result
        })
    
    except Exception as e:
        # 에러 발생 시 임시 파일 삭제
        if os.path.exists(filepath):
            os.remove(filepath)
        
        return jsonify({
            'status': 'error',
            'message': f'OCR 처리 중 오류가 발생했습니다: {str(e)}'
        }), 500


@app.route('/api/medicine/info', methods=['POST'])
def medicine_info_endpoint():
    """
    약 이름으로 상세 정보 조회
    
    Request:
        {
            "medicine_name": "타이레놀"
        }
    
    Response:
        {
            "status": "success",
            "data": {
                "name": "타이레놀정 500mg",
                "ingredients": "...",
                "efficacy": "...",
                ...
            }
        }
    """
    data = request.get_json()
    
    if not data or 'medicine_name' not in data:
        return jsonify({
            'status': 'error',
            'message': '약 이름이 제공되지 않았습니다'
        }), 400
    
    medicine_name = data['medicine_name']
    
    try:
        result = medicine_service.get_medicine_info(medicine_name)
        
        if result:
            return jsonify({
                'status': 'success',
                'data': result
            })
        else:
            return jsonify({
                'status': 'error',
                'message': '해당 약품 정보를 찾을 수 없습니다'
            }), 404
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'약품 정보 조회 중 오류가 발생했습니다: {str(e)}'
        }), 500


@app.route('/api/medicine/parse', methods=['POST'])
def parse_prescription_endpoint():
    """
    OCR 결과에서 처방 정보 파싱 + 약품 정보 조회
    
    Request:
        {
            "texts": ["타이레놀 500mg", "1일 3회", "식후 30분", ...]
        }
    
    Response:
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
    """
    data = request.get_json()
    
    if not data or 'texts' not in data:
        return jsonify({
            'status': 'error',
            'message': 'OCR 텍스트가 제공되지 않았습니다'
        }), 400
    
    texts = data['texts']
    
    try:
        # 처방전 파싱
        parsed = medicine_service.parse_prescription(texts)
        
        # 각 약품별 상세 정보 조회
        medicines = []
        for med in parsed['medicines']:
            detail = medicine_service.get_medicine_info(med['name'])
            medicines.append({
                **med,
                'details': detail
            })
        
        # 알림 시간 생성
        alarms = medicine_service.generate_alarms(medicines)
        
        return jsonify({
            'status': 'success',
            'data': {
                'medicines': medicines,
                'alarms': alarms
            }
        })
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'처방전 파싱 중 오류가 발생했습니다: {str(e)}'
        }), 500


@app.errorhandler(413)
def too_large(e):
    """파일 크기 초과 에러"""
    return jsonify({
        'status': 'error',
        'message': '파일 크기가 너무 큽니다 (최대 16MB)'
    }), 413


if __name__ == '__main__':
    # 개발 서버 실행
    # 프로덕션에서는 gunicorn 등 사용
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )