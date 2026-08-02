import io
import logging

import pytesseract
from PIL import Image
from pypdf import PdfReader
from pdf2image import convert_from_bytes

from app.config import CHUNK_OVERLAP, CHUNK_SIZE

_OCR_LANG = "ben+eng"

_EASYOCR_READER = None


def _easyocr_reader():
    global _EASYOCR_READER
    if _EASYOCR_READER is not None:
        return _EASYOCR_READER or None
    try:
        import easyocr

        _EASYOCR_READER = easyocr.Reader(["bn", "en"], gpu=False)
    except Exception:
        logging.exception("EasyOCR init failed; falling back to tesseract")
        _EASYOCR_READER = False
    return _EASYOCR_READER or None


def _ocr_image(image) -> str:
    reader = _easyocr_reader()
    if reader is not None:
        try:
            import numpy as np

            results = reader.readtext(np.array(image), paragraph=True)
            text = "\n".join(line[1] for line in results if line[1].strip())
            if text.strip():
                return text
        except Exception:
            logging.exception("EasyOCR readtext failed; falling back to tesseract")
    return pytesseract.image_to_string(image, lang=_OCR_LANG)


def extract_from_pdf(data: bytes) -> str:
    parts = [text for _, text in extract_from_pdf_pages(data)]
    return "\n".join(parts)


def extract_from_pdf_pages(data: bytes) -> list[tuple[int, str]]:
    reader = PdfReader(io.BytesIO(data))
    pages = [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
    total_text = "\n".join(text for _, text in pages)
    if len(total_text.strip()) < 100 and len(reader.pages) <= 200:
        ocr_pages = _ocr_pdf_pages(data)
        if any(t.strip() for t in ocr_pages):
            return [(i + 1, text) for i, text in enumerate(ocr_pages)]
    return pages


def _ocr_pdf_pages(data: bytes, max_pages: int = 50) -> list[str]:
    return [_ocr_image(img) for img in convert_from_bytes(data)[:max_pages]]


def extract_from_image(data: bytes) -> str:
    image = Image.open(io.BytesIO(data))
    return _ocr_image(image)


def extract_from_text(data: bytes) -> str:
    for enc in ("utf-8", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def chunk_text(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not text:
        return []
    if len(text) <= CHUNK_SIZE:
        return [text]

    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + CHUNK_SIZE, n)
        if end < n:
            break_at = _find_break(text[start:end])
            if break_at is not None:
                end = start + break_at
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


def _find_break(window: str) -> int | None:
    for marker in ("\n\n", "\n", ". ", "? ", "! "):
        idx = window.rfind(marker)
        if idx != -1 and idx > len(window) * 0.5:
            return idx + len(marker)
    return None
