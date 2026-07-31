import io

import pytesseract
from PIL import Image
from pypdf import PdfReader
from pdf2image import convert_from_bytes

from app.config import CHUNK_OVERLAP, CHUNK_SIZE


def extract_from_pdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    parts = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(parts)
    if len(text.strip()) < 100 and len(reader.pages) <= 200:
        ocr_text = _ocr_pdf_pages(data)
        if ocr_text.strip():
            return ocr_text
    return text


def _ocr_pdf_pages(data: bytes, max_pages: int = 50) -> str:
    parts = []
    for img in convert_from_bytes(data)[:max_pages]:
        parts.append(_ocr_image(img))
    return "\n\n".join(parts)


def _ocr_image(image) -> str:
    return pytesseract.image_to_string(image)


def extract_from_image(data: bytes) -> str:
    image = Image.open(io.BytesIO(data))
    return pytesseract.image_to_string(image)


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
