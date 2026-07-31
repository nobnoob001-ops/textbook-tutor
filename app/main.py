import json
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
    extract_from_pdf_pages,
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
        if filename.lower().endswith(".pdf"):
            text = _extract_text(filename, data)
            if not text.strip():
                raise ValueError("No readable text found in the file.")
            chunks = []
            pages = []
            for page_num, page_text in extract_from_pdf_pages(data):
                for c in chunk_text(page_text):
                    chunks.append(c)
                    pages.append(str(page_num))
        else:
            text = _extract_text(filename, data)
            if not text.strip():
                raise ValueError("No readable text found in the file.")
            chunks = chunk_text(text)
            pages = [None] * len(chunks)
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
        db.add_chunks(book_id, chunks, all_embeddings, pages)
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
        f"You are an expert teacher for {settings['class_name']}."
        " Answer exactly the question that was asked. Give a short, direct"
        " answer first. Do NOT add extra information, examples, background,"
        " or follow-up suggestions unless the question asks for them."
        " Never greet, introduce yourself, or write filler such as"
        " 'Sure!' or 'Here is your answer:'."
        " If the answer comes from the class textbook material, briefly"
        " mention the textbook. Always answer in the same language the"
        " student used in their question."
    )

    context = "\n\n".join(
        _format_source(source) for source in sources
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


def _format_source(source: dict) -> str:
    label = f"[From: {source['book']}"
    if source.get("page"):
        label += f", page {source['page']}"
    return f"{label}]\n{source['text']}"


def _embed_query(text: str, settings: dict) -> list[float]:
    return ai.embed_texts(
        [text],
        settings["embed_base_url"],
        settings["embed_api_key"],
        settings["embed_model"],
    )[0]


def _chat(text: str, settings: dict, system: str | None = None) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": text})
    return ai.chat_completion(
        messages,
        settings["chat_base_url"],
        settings["chat_api_key"],
        settings["chat_model"],
    )


def _parse_json_array(text: str) -> list | None:
    import re

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


@app.post("/api/answer-sheet")
async def answer_sheet(
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
        raise HTTPException(status_code=400, detail="No question paper given.")

    settings = db.get_all_settings()
    try:
        query_embedding = _embed_query(combined, settings)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Search failed: {e}")
    sources = search.rank_chunks(chunks, query_embedding, top_k=8)
    context = "\n\n".join(_format_source(s) for s in sources)

    system_prompt = (
        f"You are an expert teacher for {settings['class_name']}."
        " You are given a question paper and textbook material."
        " Answer every question on the paper, in order, numbered."
        " Use only the textbook material when it covers the question;"
        " otherwise answer from your own knowledge at the class level."
        " Answer each question concisely, directly, with no extra detail."
        " Respond with ONLY a JSON array, no other text, in this format:"
        ' [{"number": 1, "question": "...", "answer": "..."}]'
        " Answer in the language the paper is written in."
    )
    try:
        raw = _chat(
            "Question paper:\n" + combined + "\n\nClass textbook material:\n" + context,
            settings,
            system=system_prompt,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI call failed: {e}")

    items = _parse_json_array(raw)
    if items is None:
        return {"items": [{"number": 1, "question": "Paper", "answer": raw}], "sources": sources}
    return {"items": items, "sources": sources}


@app.post("/api/admin/papers")
def add_paper(
    file: UploadFile = File(...),
    x_admin_password: str = Header(default=""),
):
    if not _check_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="Not authorized")
    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    content = _extract_text(file.filename or "paper", data)
    if not content.strip():
        raise HTTPException(status_code=400, detail="No text could be read from the paper.")
    paper_id = db.add_paper(file.filename or "paper", content)
    settings = db.get_all_settings()
    thread = threading.Thread(
        target=_analyze_paper,
        args=(paper_id, content, settings),
        daemon=True,
    )
    thread.start()
    return {"id": paper_id, "name": file.filename}


def _analyze_paper(paper_id: int, content: str, settings: dict):
    try:
        chunks = db.get_all_chunks()
        if not chunks:
            return
        paper_chunks = chunk_text(content)[:40]
        embedding_map = {}
        for i in range(0, len(paper_chunks), EMBED_BATCH_SIZE):
            batch = paper_chunks[i : i + EMBED_BATCH_SIZE]
            for text, emb in zip(batch, ai.embed_texts(
                batch,
                settings["embed_base_url"],
                settings["embed_api_key"],
                settings["embed_model"],
            )):
                embedding_map[text] = emb
        counts: dict[int, int] = {}
        for text, emb in embedding_map.items():
            matches = search.rank_chunks(chunks, emb, top_k=1)
            if matches:
                cid = matches[0]["chunk_id"]
                counts[cid] = counts.get(cid, 0) + 1
        db.set_paper_matches(paper_id, counts)
    except Exception:
        db.set_paper_matches(paper_id, {})


@app.get("/api/admin/papers")
def papers_list(x_admin_password: str = Header(default="")):
    if not _check_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="Not authorized")
    return db.list_papers()


@app.delete("/api/admin/papers/{paper_id}")
def remove_paper(paper_id: int, x_admin_password: str = Header(default="")):
    if not _check_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="Not authorized")
    db.delete_paper(paper_id)
    return {"ok": True}


@app.get("/api/exam-focus")
async def exam_focus():
    paper_matches = db.get_all_paper_matches()
    if not paper_matches:
        raise HTTPException(
            status_code=400,
            detail="No past papers uploaded yet. Ask your admin to add past question papers.",
        )
    chunk_map = {}
    for row in paper_matches:
        try:
            matches = json.loads(row["matches"])
        except Exception:
            continue
        for cid, count in matches.items():
            chunk_map[int(cid)] = chunk_map.get(int(cid), 0) + int(count)

    all_chunks = db.get_all_chunks()
    by_id = {c[0]: c for c in all_chunks}
    topics = []
    for cid, count in sorted(chunk_map.items(), key=lambda x: -x[1])[:10]:
        if cid in by_id:
            _, book, content, _, page = by_id[cid]
            topics.append({"book": book, "page": page, "text": content[:300], "count": count})

    settings = db.get_all_settings()
    try:
        summary_text = "Past exam papers reference these textbook topics:\n"
        for t in topics:
            summary_text += f"- (appeared {t['count']}x) {t['text']}\n"
        summary = _chat(
            summary_text
            + "\nWrite a short exam-focus prediction for students: which 3 topics are"
            " most likely to appear next and why, based only on these. Be concise.",
            settings,
            system=f"You are an expert teacher for {settings['class_name']}. Be concise.",
        )
    except Exception as e:
        summary = f"Prediction unavailable: {e}"
    return {"topics": topics, "prediction": summary}


@app.post("/api/revision-notes")
async def revision_notes(topic: str = Form(default="")):
    topic = topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Enter a topic or chapter name.")
    chunks = db.get_all_chunks()
    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="No textbook has been added yet. Ask your admin to add the class textbook first.",
        )
    settings = db.get_all_settings()
    try:
        query_embedding = _embed_query(topic, settings)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Search failed: {e}")
    sources = search.rank_chunks(chunks, query_embedding, top_k=12)
    context = "\n\n".join(_format_source(s) for s in sources)
    system_prompt = (
        f"You are an expert teacher for {settings['class_name']}."
        " Turn the textbook material into quick revision notes."
        " Use short bullet points. Cover only the most important facts."
        " Be concise - 5-minute revision. No filler, no greetings."
        " Answer in the language the student used."
    )
    try:
        notes = _chat(
            "Topic: " + topic + "\n\nClass textbook material:\n" + context,
            settings,
            system=system_prompt,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI call failed: {e}")
    return {"notes": notes, "sources": sources}


@app.post("/api/flashcards")
async def flashcards(topic: str = Form(default="")):
    topic = topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Enter a topic or chapter name.")
    chunks = db.get_all_chunks()
    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="No textbook has been added yet. Ask your admin to add the class textbook first.",
        )
    settings = db.get_all_settings()
    try:
        query_embedding = _embed_query(topic, settings)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Search failed: {e}")
    sources = search.rank_chunks(chunks, query_embedding, top_k=12)
    context = "\n\n".join(_format_source(s) for s in sources)
    system_prompt = (
        f"You are an expert teacher for {settings['class_name']}."
        " Create study flashcards from the textbook material."
        " Each card: a key term or question on the front, the short answer on the back."
        " Make up to 15 cards. Respond with ONLY a JSON array, no other text:"
        ' [{"front": "...", "back": "..."}]'
        " Answer in the language the student used."
    )
    try:
        raw = _chat(
            "Topic: " + topic + "\n\nClass textbook material:\n" + context,
            settings,
            system=system_prompt,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI call failed: {e}")
    cards = _parse_json_array(raw)
    if cards is None:
        cards = [{"front": "Note", "back": raw}]
    return {"cards": cards, "sources": sources}
