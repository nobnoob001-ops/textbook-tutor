import threading

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import ai, database as db, search
from app.config import (
    APP_NAME,
    DEFAULT_ADMIN_PASSWORD,
    EMBED_BATCH_SIZE,
    STATIC_DIR,
)
from app.text_extract import (
    chunk_text,
    extract_from_image,
    extract_from_pdf,
    extract_from_text,
)

app = FastAPI(title=APP_NAME)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

DEFAULT_SETTINGS = {
    "class_name": "this class",
    "chat_base_url": "https://api.openai.com/v1",
    "chat_api_key": "",
    "chat_model": "gpt-4o-mini",
    "embed_base_url": "https://api.openai.com/v1",
    "embed_api_key": "",
    "embed_model": "text-embedding-3-small",
    "admin_password": DEFAULT_ADMIN_PASSWORD,
}


def _ensure_defaults():
    for key, value in DEFAULT_SETTINGS.items():
        if db.get_setting(key) is None:
            db.set_setting(key, value)


db.init_db()
_ensure_defaults()


def _extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        return extract_from_pdf(data)
    if name.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")):
        return extract_from_image(data)
    if name.endswith((".txt", ".md")):
        return extract_from_text(data)
    raise HTTPException(status_code=400, detail="Unsupported file type")


def _file_type(filename: str) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        return "pdf"
    if name.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")):
        return "image"
    return "text"


def _process_book(book_id: int, filename: str, data: bytes, settings: dict):
    try:
        text = _extract_text(filename, data)
        if not text.strip():
            raise ValueError("No readable text found in the file.")
        chunks = chunk_text(text)
        if not chunks:
            raise ValueError("No readable text found in the file.")

        all_embeddings = []
        for i in range(0, len(chunks), EMBED_BATCH_SIZE):
            batch = chunks[i : i + EMBED_BATCH_SIZE]
            all_embeddings.extend(
                ai.embed_texts(
                    batch,
                    settings["embed_base_url"],
                    settings["embed_api_key"],
                    settings["embed_model"],
                )
            )
        db.add_chunks(book_id, chunks, all_embeddings)
        db.set_book_status(book_id, "ready", chunk_count=len(chunks))
    except Exception as e:
        db.set_book_status(book_id, "error", error=str(e))


def _check_admin(password: str) -> bool:
    return bool(password) and password == db.get_setting("admin_password")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/admin")
def admin_page():
    return FileResponse(STATIC_DIR / "admin.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "app": APP_NAME, "books": len(db.list_books())}


@app.post("/api/admin/login")
def admin_login(password: str = Form(...)):
    if _check_admin(password):
        return {"ok": True}
    raise HTTPException(status_code=401, detail="Wrong admin password")


@app.get("/api/admin/settings")
def get_settings(x_admin_password: str = Header(default="")):
    if not _check_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="Not authorized")
    return db.get_all_settings()


@app.put("/api/admin/settings")
def save_settings(
    payload: dict,
    x_admin_password: str = Header(default=""),
):
    if not _check_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="Not authorized")
    allowed = set(DEFAULT_SETTINGS.keys())
    for key, value in payload.items():
        if key in allowed:
            db.set_setting(key, str(value))
    return {"ok": True}


@app.post("/api/admin/books")
def add_book(
    file: UploadFile = File(...),
    x_admin_password: str = Header(default=""),
):
    if not _check_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="Not authorized")
    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    book_id = db.add_book(file.filename or "untitled", _file_type(file.filename or ""))
    settings = db.get_all_settings()
    thread = threading.Thread(
        target=_process_book,
        args=(book_id, file.filename or "untitled", data, settings),
        daemon=True,
    )
    thread.start()
    return {"id": book_id, "name": file.filename}


@app.get("/api/admin/books")
def list_books(x_admin_password: str = Header(default="")):
    if not _check_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="Not authorized")
    return db.list_books()


@app.delete("/api/admin/books/{book_id}")
def remove_book(book_id: int, x_admin_password: str = Header(default="")):
    if not _check_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="Not authorized")
    db.delete_book(book_id)
    return {"ok": True}


@app.post("/api/ask")
async def ask(
    question: str = Form(default=""),
    file: UploadFile | None = None,
):
    chunks = db.get_all_chunks()
    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="No textbook has been added yet. Ask your admin to add the class textbook first.",
        )

    file_text = ""
    if file is not None and file.filename:
        file_text = _extract_text(file.filename, await file.read())

    combined = "\n\n".join(part for part in (question.strip(), file_text.strip()) if part)
    if not combined:
        raise HTTPException(status_code=400, detail="No question given.")

    settings = db.get_all_settings()
    try:
        query_embedding = ai.embed_texts(
            [combined],
            settings["embed_base_url"],
            settings["embed_api_key"],
            settings["embed_model"],
        )[0]
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Search failed: {e}")

    sources = search.rank_chunks(chunks, query_embedding)

    system_prompt = (
        f"You are {APP_NAME}, a friendly and expert teacher for {settings['class_name']}."
        " Always answer clearly, step by step, and give real-life examples."
        " Use the class textbook material below when it helps."
        " If the material does not cover the question, still answer helpfully"
        " from your own knowledge at the level of the class."
        " Never say you cannot help or that something is not in the book."
        " Keep answers in simple, easy-to-understand language."
    )

    context = "\n\n".join(
        f"[From: {source['book']}]\n{source['text']}" for source in sources
    )
    user_prompt = (
        "Class textbook material:\n"
        f"{context}\n\n"
        f"Student question:\n{combined}"
    )

    try:
        answer = ai.chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            settings["chat_base_url"],
            settings["chat_api_key"],
            settings["chat_model"],
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI call failed: {e}")

    return {"answer": answer, "sources": sources, "class": settings["class_name"]}
