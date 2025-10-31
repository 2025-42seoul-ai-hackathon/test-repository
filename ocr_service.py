#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PaddleOCR 기반 OCR 서비스
"""
import os
import sys
from typing import Dict, Any, List, Tuple

os.environ["GLOG_minloglevel"] = "2"
os.environ["FLAGS_min_log_level"] = "2"

try:
    import paddle
    from paddleocr import PaddleOCR
except Exception:
    print("Import error. Ensure 'paddlepaddle-gpu' (or 'paddlepaddle') and 'paddleocr' are installed.")
    raise


class OCRService:
    def __init__(self, device: str = 'auto', lang: str = 'korean', ocr_version: str = 'PP-OCRv3'):
        self.device = self._resolve_device(device)
        self.lang = lang
        self.ocr_version = ocr_version

        paddle.device.set_device("gpu" if self.device == "gpu" else "cpu")

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
        print(">> OCR model loaded successfully")

    def _resolve_device(self, opt: str) -> str:
        if opt.lower() in ("gpu", "cuda"):
            return "gpu"
        if opt.lower() == "cpu":
            return "cpu"
        try:
            return "gpu" if paddle.device.is_compiled_with_cuda() else "cpu"
        except Exception:
            return "cpu"

    def process_image(self, image_path: str) -> Dict[str, Any]:
        if not os.path.isfile(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")

        print(f">> OCR processing: {image_path}")
        res = self.ocr.predict(image_path)
        texts, scores, boxes = self._normalize_result(res)

        print(f">> Extracted {len(texts)} text lines")
        for i, (t, s) in enumerate(zip(texts, scores), 1):
            try:
                print(f"   {i:02d}. [{s:.2f}] {t}")
            except Exception:
                print(f"   {i:02d}. [{s}] {t}")

        return {'texts': texts, 'scores': scores, 'boxes': boxes, 'counts': {'lines': len(texts)}}

    def _normalize_result(self, res) -> Tuple[List[str], List[float], List]:
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
            texts = list(out.get("rec_texts", []))
            scores = [float(s) for s in out.get("rec_scores", [])]
            rb = out.get("rec_boxes", None)
            rp = out.get("rec_polys", None)
            if rb is not None:
                boxes = rb
            elif rp is not None:
                boxes = rp
            else:
                boxes = []
            try:
                if hasattr(boxes, "tolist"):
                    boxes = boxes.tolist()
            except Exception:
                pass
        return texts, scores, boxes

    def process_batch(self, image_paths: List[str]) -> List[Dict[str, Any]]:
        results = []
        for path in image_paths:
            try:
                result = self.process_image(path)
                results.append(result)
            except Exception as e:
                print(f"Error processing {path}: {e}", file=sys.stderr)
                results.append({'error': str(e), 'texts': [], 'scores': [], 'boxes': []})
        return results
