FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    PORT=7860 \
    DATA_DIR=/data \
    EASYOCR_MODULE_PATH=/data/.EasyOCR

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-ben \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision \
    && pip install -r requirements.txt

COPY . .

RUN mkdir -p /data/.EasyOCR && \
    python -c "import easyocr; easyocr.Reader(['bn', 'en'], gpu=False)" || true

EXPOSE 7860

CMD ["python", "run.py"]
