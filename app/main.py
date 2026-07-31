import asyncio
import json
import threading

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
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

_CHAT_LOCK = threading.Lock()


def _ensure_defaults():
    for key, value in DEFAULT_SETTINGS.items():
        if db.get_setting(key) is None:
            db.set_setting(key, value)


db.init_db()
_ensure_defaults()
db.backfill_book_classes(db.get_setting("class_name") or "this class")


def _get_classes() -> list[str]:
    classes = db.get_classes()
    default = db.get_setting("class_name")
    if default and default not in classes:
        classes.insert(0, default)
    return classes


def _resolve_class(class_name: str | None) -> str | None:
    if class_name:
        return class_name
    classes = _get_classes()
    return classes[0] if classes else None


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
    return {
        "status": "ok",
        "app": APP_NAME,
        "books": len(db.list_books()),
        "classes": _get_classes(),
        "sectors": db.get_sectors(),
    }


@app.get("/api/classes")
def classes():
    return {"classes": _get_classes()}


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
    class_name: str = Form(default=""),
    classes: str = Form(default=""),
    sectors: str = Form(default=""),
    x_admin_password: str = Header(default=""),
):
    if not _check_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="Not authorized")
    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if not class_name.strip():
        class_name = db.get_setting("class_name") or "this class"
    classes_list = _split_list(classes) or [class_name.strip()]
    sectors_list = _split_list(sectors)
    book_id = db.add_book(
        file.filename or "untitled",
        _file_type(file.filename or ""),
        class_name.strip(),
        classes_list,
        sectors_list,
    )
    settings = db.get_all_settings()
    thread = threading.Thread(
        target=_process_book,
        args=(book_id, file.filename or "untitled", data, settings),
        daemon=True,
    )
    thread.start()
    return {
        "id": book_id,
        "name": file.filename,
        "class_name": class_name.strip(),
        "classes": classes_list,
        "sectors": sectors_list,
    }


def _split_list(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


@app.get("/api/admin/books")
def list_books(x_admin_password: str = Header(default="")):
    if not _check_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="Not authorized")
    return db.list_books()


@app.patch("/api/admin/books/{book_id}")
def update_book(
    book_id: int,
    name: str = Form(default=""),
    classes: str = Form(default=""),
    sectors: str = Form(default=""),
    x_admin_password: str = Header(default=""),
):
    if not _check_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="Not authorized")
    book = db.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    db.update_book(
        book_id,
        name=name if name.strip() else book["name"],
        classes=_split_list(classes),
        sectors=_split_list(sectors),
    )
    return {"ok": True, "id": book_id}


@app.delete("/api/admin/books/{book_id}")
def remove_book(book_id: int, x_admin_password: str = Header(default="")):
    if not _check_admin(x_admin_password):
        raise HTTPException(status_code=401, detail="Not authorized")
    db.delete_book(book_id)
    return {"ok": True}


def _get_chunks(class_name: str | None, sector: str | None = None) -> list[tuple]:
    chunks = db.get_all_chunks(class_name, sector)
    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="No textbook has been added yet. Ask your admin to add the class textbook first.",
        )
    return chunks


def _system_prompt(settings: dict, mode: str = "short") -> str:
    if mode == "detailed":
        detail = (
            " Explain thoroughly, step by step, like a good teacher in class."
            " Include reasons, examples, and background where helpful."
            " Use headings or bullet points to stay organised."
        )
    else:
        detail = (
            " Give a short, direct answer first. Do NOT add extra information,"
            " examples, background, or follow-up suggestions unless the question"
            " asks for them."
        )
    return (
        f"You are an expert teacher for {settings['class_name']}."
        f" Answer exactly the question that was asked.{detail}"
        " Never greet, introduce yourself, or write filler such as"
        " 'Sure!' or 'Here is your answer:'."
        " If the answer comes from the class textbook material, briefly"
        " mention the textbook. Always answer in the same language the"
        " student used in their question."
    )


def _parse_history(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        history = json.loads(raw)
    except Exception:
        return []
    messages = []
    for item in history[-6:]:
        role = item.get("role")
        content = str(item.get("content", "")).strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    return messages


def _ask_messages(
    combined: str, sources: list[dict], settings: dict, history: list[dict], mode: str
) -> list[dict]:
    context = "\n\n".join(_format_source(source) for source in sources)
    messages = [{"role": "system", "content": _system_prompt(settings, mode)}]
    messages.extend(history)
    messages.append(
        {
            "role": "user",
            "content": (
                "Class textbook material:\n"
                f"{context}\n\n"
                f"Student question:\n{combined}"
            ),
        }
    )
    return messages


@app.post("/api/ask")
async def ask(
    question: str = Form(default=""),
    file: UploadFile | None = None,
    class_name: str = Form(default=""),
    sector: str = Form(default=""),
    history: str = Form(default=""),
    mode: str = Form(default="short"),
):
    class_name = _resolve_class(class_name)
    sector = sector.strip() or None
    chunks = _get_chunks(class_name, sector)

    file_text = ""
    if file is not None and file.filename:
        file_text = _extract_text(file.filename, await file.read())

    combined = "\n\n".join(part for part in (question.strip(), file_text.strip()) if part)
    if not combined:
        raise HTTPException(status_code=400, detail="No question given.")

    settings = db.get_all_settings()
    try:
        query_embedding = await asyncio.to_thread(_embed_query, combined, settings)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Search failed: {e}")

    sources = search.rank_chunks(chunks, query_embedding)
    messages = _ask_messages(combined, sources, settings, _parse_history(history), mode)

    try:
        answer = await asyncio.to_thread(_chat_messages, messages, settings)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI call failed: {e}")

    return {
        "answer": answer,
        "sources": sources,
        "class": class_name,
    }


@app.post("/api/ask/stream")
async def ask_stream(
    question: str = Form(default=""),
    file: UploadFile | None = None,
    class_name: str = Form(default=""),
    sector: str = Form(default=""),
    history: str = Form(default=""),
    mode: str = Form(default="short"),
):
    class_name = _resolve_class(class_name)
    sector = sector.strip() or None
    chunks = _get_chunks(class_name, sector)

    file_text = ""
    if file is not None and file.filename:
        file_text = _extract_text(file.filename, await file.read())

    combined = "\n\n".join(part for part in (question.strip(), file_text.strip()) if part)
    if not combined:
        raise HTTPException(status_code=400, detail="No question given.")

    settings = db.get_all_settings()
    try:
        query_embedding = await asyncio.to_thread(_embed_query, combined, settings)
    except Exception as e:
        return StreamingResponse(
            iter([_sse({"error": f"Search failed: {e}"})]),
            media_type="text/event-stream",
        )

    sources = search.rank_chunks(chunks, query_embedding)
    messages = _ask_messages(combined, sources, settings, _parse_history(history), mode)

    async def generate():
        queue: asyncio.Queue = asyncio.Queue()

        def worker():
            try:
                with _CHAT_LOCK:
                    for token in ai.chat_completion_stream(
                        messages,
                        settings["chat_base_url"],
                        settings["chat_api_key"],
                        settings["chat_model"],
                    ):
                        queue.put_nowait(("token", token))
                queue.put_nowait(("done", {"sources": sources, "class": class_name}))
            except Exception as e:
                queue.put_nowait(("error", f"AI call failed: {e}"))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        while True:
            kind, payload = await queue.get()
            if kind == "token":
                yield _sse({"token": payload})
            elif kind == "done":
                yield _sse(payload)
                return
            else:
                yield _sse({"error": payload})
                return

    return StreamingResponse(generate(), media_type="text/event-stream")


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


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
    return _chat_messages(messages, settings)


def _chat_messages(messages: list[dict], settings: dict) -> str:
    with _CHAT_LOCK:
        return ai.chat_completion(
            messages,
            settings["chat_base_url"],
            settings["chat_api_key"],
            settings["chat_model"],
        )


def _parse_json_array(text: str | None) -> list | None:
    if not isinstance(text, str):
        return None
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
    class_name: str = Form(default=""),
    sector: str = Form(default=""),
    mode: str = Form(default="short"),
):
    class_name = _resolve_class(class_name)
    sector = sector.strip() or None
    chunks = _get_chunks(class_name, sector)
    file_text = ""
    if file is not None and file.filename:
        file_text = _extract_text(file.filename, await file.read())
    combined = "\n\n".join(part for part in (question.strip(), file_text.strip()) if part)
    if not combined:
        raise HTTPException(status_code=400, detail="No question paper given.")

    settings = db.get_all_settings()
    try:
        query_embedding = await asyncio.to_thread(_embed_query, combined, settings)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Search failed: {e}")
    sources = search.rank_chunks(chunks, query_embedding, top_k=8)
    context = "\n\n".join(_format_source(s) for s in sources)

    detail = (
        " For each question give a thorough, step-by-step answer."
        if mode == "detailed"
        else " Answer each question concisely, directly, with no extra detail."
    )
    system_prompt = (
        f"You are an expert teacher for {settings['class_name']}."
        " You are given a question paper and textbook material."
        " Answer every question on the paper, in order, numbered."
        " Use only the textbook material when it covers the question;"
        " otherwise answer from your own knowledge at the class level."
        f"{detail}"
        " Respond with ONLY a JSON array, no other text, in this format:"
        ' [{"number": 1, "question": "...", "answer": "..."}]'
        " Answer in the language the paper is written in."
    )
    try:
        raw = await asyncio.to_thread(
            _chat,
            "Question paper:\n" + combined + "\n\nClass textbook material:\n" + context,
            settings,
            system_prompt,
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
async def exam_focus(class_name: str = "", sector: str = ""):
    class_name = _resolve_class(class_name)
    sector = sector.strip() or None
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

    all_chunks = db.get_all_chunks(class_name, sector)
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
        summary = await asyncio.to_thread(
            _chat,
            summary_text
            + "\nWrite a short exam-focus prediction for students: which 3 topics are"
            " most likely to appear next and why, based only on these. Be concise.",
            settings,
            f"You are an expert teacher for {settings['class_name']}. Be concise.",
        )
    except Exception as e:
        summary = f"Prediction unavailable: {e}"
    return {"topics": topics, "prediction": summary}


@app.post("/api/revision-notes")
async def revision_notes(
    topic: str = Form(default=""),
    class_name: str = Form(default=""),
    sector: str = Form(default=""),
):
    topic = topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Enter a topic or chapter name.")
    class_name = _resolve_class(class_name)
    sector = sector.strip() or None
    chunks = _get_chunks(class_name, sector)
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
        notes = await asyncio.to_thread(
            _chat,
            "Topic: " + topic + "\n\nClass textbook material:\n" + context,
            settings,
            system_prompt,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI call failed: {e}")
    return {"notes": notes, "sources": sources}


@app.post("/api/flashcards")
async def flashcards(
    topic: str = Form(default=""),
    class_name: str = Form(default=""),
    sector: str = Form(default=""),
):
    topic = topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Enter a topic or chapter name.")
    class_name = _resolve_class(class_name)
    sector = sector.strip() or None
    chunks = _get_chunks(class_name, sector)
    settings = db.get_all_settings()
    try:
        query_embedding = await asyncio.to_thread(_embed_query, topic, settings)
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
        raw = await asyncio.to_thread(
            _chat,
            "Topic: " + topic + "\n\nClass textbook material:\n" + context,
            settings,
            system_prompt,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI call failed: {e}")
    cards = _parse_json_array(raw)
    if cards is None:
        cards = [{"front": "Note", "back": raw}]
    return {"cards": cards, "sources": sources}


@app.post("/api/register")
def register(name: str = Form(...), pin: str = Form(...)):
    name = name.strip()
    pin = pin.strip()
    if not name or not pin:
        raise HTTPException(status_code=400, detail="Name and PIN are required.")
    if len(pin) < 4 or len(pin) > 8:
        raise HTTPException(status_code=400, detail="PIN must be 4-8 characters.")
    if db.login_student(name, pin):
        return {"id": db.login_student(name, pin)["id"], "name": name, "new": False}
    return {**db.register_student(name, pin), "new": True}


@app.post("/api/login")
def login(name: str = Form(...), pin: str = Form(...)):
    student = db.login_student(name.strip(), pin.strip())
    if not student:
        raise HTTPException(status_code=401, detail="Wrong name or PIN.")
    return student


@app.get("/api/profile")
def profile(student_id: int = 0):
    if not student_id:
        raise HTTPException(status_code=401, detail="Not logged in.")
    student = db.get_student(student_id)
    if not student:
        raise HTTPException(status_code=401, detail="Not logged in.")
    attempts = db.get_quiz_progress(student_id)
    dates = {a["created_at"][:10] for a in attempts}
    streak = 0
    from datetime import date, timedelta

    day = date.today()
    while str(day) in dates:
        streak += 1
        day -= timedelta(days=1)
    quizzes_done = len(attempts)
    avg_score = 0
    if attempts:
        avg_score = round(
            sum(a["score"] / a["total"] for a in attempts if a["total"]) / len(attempts) * 100
        )
    return {
        "name": student["name"],
        "streak": streak,
        "quizzes_done": quizzes_done,
        "avg_score": avg_score,
        "attempts": attempts[:20],
    }


def _retrieve_context(
    query: str, settings: dict, class_name: str, sector: str | None = None, top_k: int = 12
) -> list[dict]:
    chunks = _get_chunks(class_name, sector)
    try:
        query_embedding = _embed_query(query, settings)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Search failed: {e}")
    return search.rank_chunks(chunks, query_embedding, top_k=top_k)


@app.post("/api/quiz")
async def quiz(
    topic: str = Form(default=""),
    count: int = Form(default=5),
    class_name: str = Form(default=""),
    sector: str = Form(default=""),
):
    topic = topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Enter a topic or chapter name.")
    count = min(max(int(count), 3), 15)
    class_name = _resolve_class(class_name)
    sector = sector.strip() or None
    settings = db.get_all_settings()
    sources = await asyncio.to_thread(_retrieve_context, topic, settings, class_name, sector, 15)
    context = "\n\n".join(_format_source(s) for s in sources)
    system_prompt = (
        f"You are an expert teacher for {settings['class_name']}."
        " Create a multiple-choice quiz from the textbook material."
        f" Make exactly {count} questions. Each question must have 4 options and"
        " exactly one correct answer index (0-3). Add a short explanation."
        " Respond with ONLY a JSON array, no other text:"
        ' [{"question": "...", "options": ["a","b","c","d"], "answer": 0,'
        ' "explanation": "..."}]'
        " Questions and options in the same language as the topic."
    )
    try:
        raw = await asyncio.to_thread(
            _chat,
            "Topic: " + topic + "\n\nClass textbook material:\n" + context,
            settings,
            system_prompt,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI call failed: {e}")
    questions = _parse_json_array(raw) or []
    return {"questions": questions, "topic": topic, "class": class_name}


@app.post("/api/quiz/submit")
async def quiz_submit(
    student_id: int = Form(...),
    class_name: str = Form(default=""),
    topic: str = Form(default=""),
    questions: str = Form(default="[]"),
    answers: str = Form(default="[]"),
):
    if not db.get_student(student_id):
        raise HTTPException(status_code=401, detail="Not logged in.")
    try:
        qs = json.loads(questions)
        ans = json.loads(answers)
    except Exception:
        raise HTTPException(status_code=400, detail="Bad quiz payload.")
    score = 0
    results = []
    for i, q in enumerate(qs):
        correct = q.get("answer") if isinstance(q.get("answer"), int) else -1
        chosen = ans[i] if i < len(ans) else None
        ok = chosen == correct
        if ok:
            score += 1
        results.append(
            {
                "question": q.get("question", ""),
                "options": q.get("options", []),
                "correct": correct,
                "chosen": chosen,
                "ok": ok,
                "explanation": q.get("explanation", ""),
            }
        )
    db.add_quiz_attempt(student_id, class_name or None, topic, score, len(qs))
    return {"score": score, "total": len(qs), "results": results}


@app.post("/api/question-bank")
async def question_bank(
    topic: str = Form(default=""),
    count: int = Form(default=10),
    class_name: str = Form(default=""),
    sector: str = Form(default=""),
):
    topic = topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Enter a topic or chapter name.")
    count = min(max(int(count), 5), 30)
    class_name = _resolve_class(class_name)
    sector = sector.strip() or None
    settings = db.get_all_settings()
    sources = await asyncio.to_thread(_retrieve_context, topic, settings, class_name, sector, 15)
    context = "\n\n".join(_format_source(s) for s in sources)
    system_prompt = (
        f"You are an expert teacher for {settings['class_name']}."
        " Create a practice question bank from the textbook material."
        f" Make exactly {count} questions mixing short-answer and long-answer"
        " (mark 'type' as 'short' or 'long'). Give a concise model answer for each."
        " Respond with ONLY a JSON array, no other text:"
        ' [{"type": "short", "question": "...", "answer": "..."}]'
        " Questions and answers in the same language as the topic."
    )
    try:
        raw = await asyncio.to_thread(
            _chat,
            "Topic: " + topic + "\n\nClass textbook material:\n" + context,
            settings,
            system_prompt,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI call failed: {e}")
    questions = _parse_json_array(raw)
    if not questions:
        if not raw:
            raise HTTPException(
                status_code=503,
                detail="The AI returned an empty response (likely a rate limit). Please wait a minute and try again.",
            )
        questions = []
    return {"questions": questions, "topic": topic, "class": class_name}


@app.get("/api/study-path")
async def study_path(class_name: str = "", sector: str = ""):
    class_name = _resolve_class(class_name)
    sector = sector.strip() or None
    if not class_name:
        raise HTTPException(
            status_code=400,
            detail="No textbook has been added yet. Ask your admin to add the class textbook first.",
        )
    cache_key = f"{class_name}|{sector or ''}"
    cached = db.get_study_path(cache_key)
    if cached:
        return {"topic": class_name, "steps": cached["path"], "cached": True, "sector": sector}

    chunks = _get_chunks(class_name, sector)
    settings = db.get_all_settings()
    step_size = max(1, len(chunks) // 14)
    sampled = [c[2][:600] for c in chunks[::step_size][:14]]
    overview = "\n\n".join(
        f"[Section {i + 1}]\n{s}" for i, s in enumerate(sampled)
    )
    system_prompt = (
        f"You are an expert teacher for {settings['class_name']}."
        " These are sample sections of the class textbook, in book order."
        " Build a step-by-step study path: an ordered list of 5-10 study steps"
        " (topics/chapters a student should study, in the right order)."
        " Respond with ONLY a JSON array, no other text:"
        ' [{"step": 1, "title": "...", "what": "one line on what to learn"}]'
        " Use the same language as the book."
    )
    try:
        raw = await asyncio.to_thread(
            _chat,
            "Textbook sections:\n" + overview,
            settings,
            system_prompt,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not build study path: {e}")
    steps = _parse_json_array(raw) or []
    db.set_study_path(cache_key, steps)
    return {"topic": class_name, "steps": steps, "cached": False, "sector": sector}


@app.post("/api/quick-sheet")
async def quick_sheet(
    topic: str = Form(default=""),
    class_name: str = Form(default=""),
    sector: str = Form(default=""),
):
    topic = topic.strip()
    class_name = _resolve_class(class_name)
    sector = sector.strip() or None
    settings = db.get_all_settings()
    sources = await asyncio.to_thread(
        _retrieve_context,
        topic or "all key formulas and definitions",
        settings,
        class_name,
        sector,
        12,
    )
    context = "\n\n".join(_format_source(s) for s in sources)
    scope = f"for the topic '{topic}'" if topic else "for the whole class"
    system_prompt = (
        f"You are an expert teacher for {settings['class_name']}."
        f" Create a one-page quick sheet of the key formulas and definitions {scope}."
        " Use short bullet points. Label each with 'Formula:' or 'Definition:'."
        " Be concise. No filler, no greetings."
        " Write it in the same language as the book."
    )
    try:
        sheet = await asyncio.to_thread(
            _chat,
            "Class textbook material:\n" + context,
            settings,
            system_prompt,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI call failed: {e}")
    return {"sheet": sheet, "sources": sources, "class": class_name}
