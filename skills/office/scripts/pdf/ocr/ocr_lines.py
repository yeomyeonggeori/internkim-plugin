#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR


ENGINE_PARAMETERS = {
    "Global.use_cls": False,
    "Global.log_level": "error",
    "Rec.lang_type": LangRec.KOREAN,
    "Rec.ocr_version": OCRVersion.PPOCRV5,
    "Rec.model_type": ModelType.MOBILE,
}


def image_lines(engine: RapidOCR, image_path: str) -> list[dict]:
    result = engine(image_path)
    if not result.txts:
        return []
    return [line(text, box, score) for text, box, score in zip(result.txts, result.boxes, result.scores)]


def line(text: str, box, score: float) -> dict:
    horizontal = [float(point[0]) for point in box]
    vertical = [float(point[1]) for point in box]
    return {"text": text, "x0": min(horizontal), "x1": max(horizontal), "top": min(vertical), "bottom": max(vertical), "score": round(float(score), 3)}


def main(arguments: list[str]) -> None:
    output_path, image_paths = arguments[0], arguments[1:]
    engine = RapidOCR(params=ENGINE_PARAMETERS)
    with open(output_path, "w", encoding="utf-8") as output:
        json.dump([image_lines(engine, image_path) for image_path in image_paths], output, ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv[1:])
