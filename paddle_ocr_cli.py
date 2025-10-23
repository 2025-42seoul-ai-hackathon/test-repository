#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse, json, os, sys
from datetime import datetime
os.environ["GLOG_minloglevel"] = "2"
os.environ["FLAGS_min_log_level"] = "2"

try:
    import paddle
    from paddleocr import PaddleOCR
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    print("Import error. Ensure 'paddlepaddle-gpu' (or 'paddlepaddle') and 'paddleocr' are installed.")
    raise

def resolve_device(opt: str) -> str:
    if opt.lower() in ("gpu", "cuda"): return "gpu"
    if opt.lower() == "cpu": return "cpu"
    try:
        return "gpu" if paddle.device.is_compiled_with_cuda() else "cpu"
    except Exception:
        return "cpu"

def main():
    ap = argparse.ArgumentParser(description="PaddleOCR 3.x simple CLI")
    ap.add_argument("--input","-i", required=True)
    ap.add_argument("--lang", default="korean")
    ap.add_argument("--device", default="auto")           # auto|gpu|cpu
    ap.add_argument("--save_dir", default="./ocr_out")
    ap.add_argument("--ocr_version", default="PP-OCRv3")  # ko/jp는 v3 권장
    ap.add_argument("--rec_batch_num", type=int, default=4)
    args = ap.parse_args()

    img_path = args.input
    if not os.path.isfile(img_path):
        print(f"Input not found: {img_path}", file=sys.stderr); sys.exit(2)
    os.makedirs(args.save_dir, exist_ok=True)

    device = resolve_device(args.device)
    paddle.device.set_device("gpu" if device == "gpu" else "cpu")

    ocr = PaddleOCR(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,     # 권한 충돌 모델 차단
        lang=args.lang,
        ocr_version=args.ocr_version,
        text_recognition_batch_size=args.rec_batch_num,
        device=device
    )

    print(">> OCR predict start")
    res = ocr.predict(img_path)
    print(">> OCR predict done")

    # ---- 결과 정규화 ----
    texts, scores, boxes = [], [], []
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
            # 넘파이 → 파이썬 리스트
            if hasattr(boxes, "tolist"):
                boxes = boxes.tolist()
        except Exception:
            pass
    print(f">> extracted lines={len(texts)}")

    # ---- JSON 저장 (항상 먼저) ----
    base = os.path.splitext(os.path.basename(img_path))[0]
    json_path = os.path.join(args.save_dir, f"{base}_res.json")
    payload = {
        "input_path": os.path.abspath(img_path),
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "device": device,
        "lang": args.lang,
        "ocr_version": args.ocr_version,
        "counts": {"lines": len(texts)},
        "texts": texts,
        "scores": scores,
        "boxes": boxes,
        "vis_path": None,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"JSON: {json_path}")

    # ---- 시각화 저장 ----
    vis_path = None
    try:
        image = Image.open(img_path).convert("RGB")
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        for poly, txt, sc in zip(boxes, texts, scores):
            try:
                draw.polygon([tuple(pt) for pt in poly], outline=(255, 0, 0))
                x = min(pt[0] for pt in poly); y = min(pt[1] for pt in poly)
                label = f"{txt} {sc:.2f}" if txt else f"{sc:.2f}"
                draw.text((x, max(0, y - 12)), label, fill=(255, 0, 0), font=font)
            except Exception:
                continue
        vis_path = os.path.join(args.save_dir, f"{base}_vis.jpg")
        image.save(vis_path, quality=95)
        print(f"VIS : {vis_path}")
    except Exception:
        import traceback; traceback.print_exc()

    print(f"OK | device={device} | lines={len(texts)}")

if __name__ == "__main__":
    main()
