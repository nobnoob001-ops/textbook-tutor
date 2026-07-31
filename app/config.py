import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = Path(__file__).resolve().parent / "static"

APP_NAME = os.getenv("APP_NAME", "Textbook Tutor")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

DEFAULT_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

CHUNK_SIZE = 800
CHUNK_OVERLAP = 120
EMBED_BATCH_SIZE = 64
TOP_K_SOURCES = 5

DATA_DIR.mkdir(parents=True, exist_ok=True)
