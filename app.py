#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from ocr_service import OCRService
from medicine_api import MedicineAPIService

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

print(">> Initializing OCR service...")
ocr_service = OCRService(device='auto', lang='korean')
print(">> OCR service ready")

print(">> Initializing Medicine API service...")
medicine_service = MedicineAPIService(lexicon_path="./drug_lexicon.txt")
print(">> Medicine API service ready")


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'message': 'Server is running'})


@app.route('/api/ocr', methods=['POST'])
def ocr_endpoint():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': '파일이 업로드되지 않았습니다'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': '파일이 선택되지 않았습니다'}), 400
    if not allowed_file(file.filename):
        return jsonify({'status': 'error', 'message': '지원하지 않는 파일 형식입니다 (png, jpg, jpeg, gif만 가능)'}), 400

    filepath = None
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        result = ocr_service.process_image(filepath)

        if os.path.exists(filepath):
            os.remove(filepath)

        return jsonify({'status': 'success', 'data': result})
    except Exception as e:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'status': 'error', 'message': f'OCR 처리 중 오류가 발생했습니다: {str(e)}'}), 500


@app.route('/api/medicine/info', methods=['POST'])
def medicine_info_endpoint():
    data = request.get_json()
    if not data or 'medicine_name' not in data:
        return jsonify({'status': 'error', 'message': '약 이름이 제공되지 않았습니다'}), 400

    name = data['medicine_name']
    try:
        result = medicine_service.get_medicine_info(name)
        if result:
            return jsonify({'status': 'success', 'data': result})
        return jsonify({'status': 'error', 'message': '해당 약품 정보를 찾을 수 없습니다'}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'약품 정보 조회 중 오류가 발생했습니다: {str(e)}'}), 500


@app.route('/api/medicine/parse', methods=['POST'])
def parse_prescription_endpoint():
    data = request.get_json()
    if not data or 'texts' not in data:
        return jsonify({'status': 'error', 'message': 'OCR 텍스트가 제공되지 않았습니다'}), 400

    texts = data['texts']
    scores = data.get('scores')

    try:
        parsed = medicine_service.parse_prescription(texts, scores=scores)

        medicines = []
        for med in parsed['medicines']:
            detail = medicine_service.get_medicine_info(med['name'])
            medicines.append({**med, 'details': detail})

        alarms = medicine_service.generate_alarms(medicines)

        return jsonify({
            'status': 'success',
            'data': {
                'medicines': medicines,
                'alarms': alarms,
                'candidates': parsed.get('candidates', [])
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'처방전 파싱 중 오류가 발생했습니다: {str(e)}'}), 500


@app.errorhandler(413)
def too_large(e):
    return jsonify({'status': 'error', 'message': '파일 크기가 너무 큽니다 (최대 16MB)'}), 413


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
