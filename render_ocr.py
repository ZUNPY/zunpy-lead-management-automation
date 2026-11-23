"""Low-memory OCR fallback for image-only JOB-001 PDFs.

This configuration is intentionally conservative for Render Free (512 MB):
PP-OCRv4 mobile models, no orientation classifier, one ONNX thread and
sequential page rasterization.
"""

from __future__ import annotations

import gc
from dataclasses import dataclass
from io import BytesIO

import pypdfium2 as pdfium
from rapidocr import EngineType, LangDet, LangRec, ModelType, OCRVersion, RapidOCR


MIN_LINE_CONFIDENCE = 0.55
MAX_OCR_PAGES = 10
OCR_RENDER_SCALE = 1.7

_ENGINE: RapidOCR | None = None


@dataclass(frozen=True)
class OCRTextResult:
    text: str
    mean_confidence: float
    page_count: int
    truncated: bool


def _engine() -> RapidOCR:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = RapidOCR(
            params={
                "Global.use_cls": False,
                "Global.max_side_len": 1400,
                "Det.engine_type": EngineType.ONNXRUNTIME,
                "Det.lang_type": LangDet.MULTI,
                "Det.model_type": ModelType.MOBILE,
                "Det.ocr_version": OCRVersion.PPOCRV4,
                "Det.limit_side_len": 960,
                "Rec.engine_type": EngineType.ONNXRUNTIME,
                "Rec.lang_type": LangRec.LATIN,
                "Rec.model_type": ModelType.MOBILE,
                "Rec.ocr_version": OCRVersion.PPOCRV4,
                "Rec.rec_batch_num": 1,
                "EngineConfig.onnxruntime.intra_op_num_threads": 1,
                "EngineConfig.onnxruntime.inter_op_num_threads": 1,
                "EngineConfig.onnxruntime.enable_cpu_mem_arena": False,
            }
        )
    return _ENGINE


def _safe_close(value: object) -> None:
    close = getattr(value, "close", None)
    if callable(close):
        close()


def extract_pdf_ocr(data: bytes) -> OCRTextResult:
    """Rasterize and OCR an image-only PDF with bounded memory use."""
    document = pdfium.PdfDocument(BytesIO(data))
    parts: list[str] = []
    confidences: list[float] = []
    page_count = len(document)
    truncated = page_count > MAX_OCR_PAGES

    try:
        for page_index in range(min(page_count, MAX_OCR_PAGES)):
            page = document[page_index]
            bitmap = None
            image = None
            try:
                bitmap = page.render(scale=OCR_RENDER_SCALE)
                image = bitmap.to_pil().convert("RGB")
                result = _engine()(image, use_cls=False)

                raw_txts = getattr(result, "txts", None)
                raw_scores = getattr(result, "scores", None)
                if raw_txts is None:
                    continue

                txts = [str(value).strip() for value in list(raw_txts)]
                if raw_scores is None:
                    scores = [0.0] * len(txts)
                else:
                    scores = [float(value) for value in list(raw_scores)]

                kept: list[str] = []
                for index, text in enumerate(txts):
                    if not text:
                        continue
                    score = scores[index] if index < len(scores) else 0.0
                    if score >= MIN_LINE_CONFIDENCE:
                        kept.append(text)
                        confidences.append(score)

                if kept:
                    parts.append("\n".join(kept))
            finally:
                if image is not None:
                    _safe_close(image)
                if bitmap is not None:
                    _safe_close(bitmap)
                _safe_close(page)
                gc.collect()
    finally:
        _safe_close(document)
        gc.collect()

    confidence = sum(confidences) / len(confidences) if confidences else 0.0
    return OCRTextResult(
        text="\n".join(parts).strip(),
        mean_confidence=confidence,
        page_count=page_count,
        truncated=truncated,
    )
