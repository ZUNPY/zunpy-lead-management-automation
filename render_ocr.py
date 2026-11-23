"""OCR fallback for image-only JOB-001 PDFs.

RapidOCR is loaded lazily so digital PDFs pay no OCR startup cost.
PDF pages are rasterized sequentially with PDFium to bound memory usage.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import pypdfium2 as pdfium
from rapidocr import RapidOCR


MIN_LINE_CONFIDENCE = 0.55
MAX_OCR_PAGES = 10

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
        _ENGINE = RapidOCR()
    return _ENGINE


def _safe_close(value: object) -> None:
    close = getattr(value, "close", None)
    if callable(close):
        close()


def extract_pdf_ocr(data: bytes) -> OCRTextResult:
    """Rasterize and OCR an image-only PDF.

    Low-confidence individual lines are omitted before parsing. A document
    beyond MAX_OCR_PAGES is explicitly marked truncated so processing can
    fail closed to REVIEW rather than silently complete from partial OCR.
    """
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
                bitmap = page.render(scale=2.5)
                image = bitmap.to_pil().convert("RGB")
                result = _engine()(image)

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
    finally:
        _safe_close(document)

    confidence = sum(confidences) / len(confidences) if confidences else 0.0
    return OCRTextResult(
        text="\n".join(parts).strip(),
        mean_confidence=confidence,
        page_count=page_count,
        truncated=truncated,
    )
