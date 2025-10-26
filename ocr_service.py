#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
e약은요 API + PaddleOCR 파이프라인 (개선판)
- OCR 콘솔 출력(문장+신뢰도)
- 노이즈 필터, 오탈자 보정, 인접행 결합, 스코어링
- 단일 약 “인데놀정10mg | 1정 | 1일 2회 | 식후 | 2일” 안정 추출
"""
import os
import re
import sys
import requests
from typing import Dict, List, Optional, Any, Tuple
from datetime import time

# -----------------------------------------------------------
# OCR SERVICE
# -----------------------------------------------------------

os.environ["GLOG_minloglevel"] = "2"
os.environ["FLAGS_min_log_level"] = "2"

try:
    import paddle
    from paddleocr import PaddleOCR
except Exception:
    print("Import error. Ensure 'paddlepaddle-gpu' (or 'paddlepaddle') and 'paddleocr' are installed.")
    raise


class OCRService:
    """
    PaddleOCR 기반 텍스트 인식 서비스
    서버 시작 시 1번만 초기화하여 메모리에 유지
    """

    def __init__(self, device: str = 'auto', lang: str = 'korean', ocr_version: str = 'PP-OCRv3'):
        """
        Args:
            device: 'auto' | 'gpu' | 'cpu'
            lang: OCR 언어 (korean, english, etc)
            ocr_version: PaddleOCR 버전
        """
        self.device = self._resolve_device(device)
        self.lang = lang
        self.ocr_version = ocr_version

        # Paddle 디바이스 설정
        paddle.device.set_device("gpu" if self.device == "gpu" else "cpu")

        # OCR 모델 로드
        print(f">> Loading OCR model (device={self.device}, lang={self.lang})...")
        self.ocr = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            lang=self.lang,
            ocr_version=self.ocr_version,
            text_recognition_batch_size=4,
            device=self.device
        )
        print(f">> OCR model loaded successfully")

    def _resolve_device(self, opt: str) -> str:
        """디바이스 자동 감지"""
        if opt.lower() in ("gpu", "cuda"):
            return "gpu"
        if opt.lower() == "cpu":
            return "cpu"
        try:
            return "gpu" if paddle.device.is_compiled_with_cuda() else "cpu"
        except Exception:
            return "cpu"

    def process_image(self, image_path: str) -> Dict[str, Any]:
        """
        이미지 파일에서 텍스트 추출

        Args:
            image_path: 이미지 파일 경로

        Returns:
            {
                'texts': [...],
                'scores': [...],
                'boxes': [...],
                'counts': {'lines': N}
            }
        """
        if not os.path.isfile(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")

        print(f">> OCR processing: {image_path}")

        # OCR 실행
        res = self.ocr.predict(image_path)

        # 결과 정규화
        texts, scores, boxes = self._normalize_result(res)

        print(f">> Extracted {len(texts)} text lines")
        for i, (t, s) in enumerate(zip(texts, scores), 1):
            try:
                print(f"   {i:02d}. [{s:.2f}] {t}")
            except Exception:
                print(f"   {i:02d}. [{s}] {t}")

        return {
            'texts': texts,
            'scores': scores,
            'boxes': boxes,
            'counts': {'lines': len(texts)}
        }

    def _normalize_result(self, res) -> Tuple[List[str], List[float], List]:
        """
        PaddleOCR 결과를 표준 형식으로 변환

        Returns:
            (texts, scores, boxes)
        """
        
        texts: List[str] = []
        scores: List[float] = []
        boxes = []

        out = None
        if isinstance(res, list) and len(res) > 0:
            out = res[0]
        elif isinstance(res, dict):
            out = res

        if isinstance(out, dict):
            out = out.get("res", out)

            # 텍스트 추출
            texts = list(out.get("rec_texts", []))

            # 신뢰도 점수 추출
            scores = [float(s) for s in out.get("rec_scores", [])]

            # 박스 좌표 추출
            rb = out.get("rec_boxes", None)
            rp = out.get("rec_polys", None)
            if rb is not None:
                boxes = rb
            elif rp is not None:
                boxes = rp
            else:
                boxes = []

            # numpy array를 list로 변환
            try:
                if hasattr(boxes, "tolist"):
                    boxes = boxes.tolist()
            except Exception:
                pass

        return texts, scores, boxes

    def process_batch(self, image_paths: List[str]) -> List[Dict[str, Any]]:
        """
        여러 이미지를 배치로 처리

        Args:
            image_paths: 이미지 파일 경로 리스트

        Returns:
            결과 리스트
        """
        results = []
        for path in image_paths:
            try:
                result = self.process_image(path)
                results.append(result)
            except Exception as e:
                print(f"Error processing {path}: {e}", file=sys.stderr)
                results.append({
                    'error': str(e),
                    'texts': [],
                    'scores': [],
                    'boxes': []
                })
        return results