import json
import sqlite3

from app.config import DATA_DIR

_DB_PATH = DATA_DIR / "tutor.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    file_type TEXT,
    status TEXT NOT NULL DEFAULT 'processing',
    error TEXT,
    chunk_count INTEGER DEFAULT 0,
    class_name TEXT,
    added_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    chunk_index INTEGER,
    content TEXT NOT NULL,
    embedding TEXT,
    page TEXT,
    FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    content TEXT,
    status TEXT DEFAULT 'ready',
    matches TEXT,
    added_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    pin TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    class_name TEXT,
    topic TEXT,
    score INTEGER,
    total INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS study_paths (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_name TEXT NOT NULL,
    path TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS book_scopes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    value TEXT NOT NULL,
    UNIQUE(book_id, kind, value),
    FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
);
"""


def init_db():
    conn = _connect()
    try:
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()


def _migrate(conn):
    columns = [row["name"] for row in conn.execute("PRAGMA table_info(chunks)")]
    if "page" not in columns:
        conn.execute("ALTER TABLE chunks ADD COLUMN page TEXT")
    book_columns = [row["name"] for row in conn.execute("PRAGMA table_info(books)")]
    if "class_name" not in book_columns:
        conn.execute("ALTER TABLE books ADD COLUMN class_name TEXT")
    conn.execute(
        """
        INSERT OR IGNORE INTO book_scopes (book_id, kind, value)
        SELECT id, 'class', class_name FROM books
        WHERE class_name IS NOT NULL AND class_name != ''
        """
    )


def backfill_book_classes(default: str):
    conn = _connect()
    try:
        conn.execute(
            "UPDATE books SET class_name = ? WHERE class_name IS NULL OR class_name = ''",
            (default,),
        )
        conn.commit()
    finally:
        conn.close()


def _connect():
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def get_setting(key: str, default: str | None = None) -> str | None:
    conn = _connect()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_setting(key: str, value: str):
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def get_all_settings() -> dict[str, str]:
    conn = _connect()
    try:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {row["key"]: row["value"] for row in rows}
    finally:
        conn.close()


def add_book(
    name: str,
    file_type: str,
    class_name: str | None = None,
    classes: list[str] | None = None,
    sectors: list[str] | None = None,
) -> int:
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO books (name, file_type, class_name) VALUES (?, ?, ?)",
            (name, file_type, class_name),
        )
        book_id = cur.lastrowid
        _replace_scopes(conn, book_id, classes or [], sectors or [])
        conn.commit()
        return book_id
    finally:
        conn.close()


def _clean_values(values: list[str] | None) -> list[str]:
    out = []
    for v in values or []:
        v = (v or "").strip()
        if v and v not in out:
            out.append(v)
    return out


def _replace_scopes(conn, book_id: int, classes: list[str], sectors: list[str]):
    conn.execute("DELETE FROM book_scopes WHERE book_id = ?", (book_id,))
    for kind, values in (("class", _clean_values(classes)), ("sector", _clean_values(sectors))):
        for v in values:
            conn.execute(
                "INSERT OR IGNORE INTO book_scopes (book_id, kind, value) VALUES (?, ?, ?)",
                (book_id, kind, v),
            )


def set_book_scopes(book_id: int, classes: list[str], sectors: list[str]):
    conn = _connect()
    try:
        _replace_scopes(conn, book_id, classes, sectors)
        conn.commit()
    finally:
        conn.close()


def update_book(
    book_id: int,
    name: str | None = None,
    classes: list[str] | None = None,
    sectors: list[str] | None = None,
):
    conn = _connect()
    try:
        if name is not None:
            conn.execute("UPDATE books SET name = ? WHERE id = ?", (name.strip(), book_id))
        if classes is not None or sectors is not None:
            _replace_scopes(conn, book_id, classes or [], sectors or [])
        conn.commit()
    finally:
        conn.close()


def get_book_scopes(book_id: int) -> dict:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT kind, value FROM book_scopes WHERE book_id = ? ORDER BY value", (book_id,)
        ).fetchall()
        scopes: dict = {"classes": [], "sectors": []}
        for r in rows:
            key = "classes" if r["kind"] == "class" else "sectors"
            scopes[key].append(r["value"])
        return scopes
    finally:
        conn.close()


def set_book_status(book_id: int, status: str, error: str | None = None, chunk_count: int | None = None):
    conn = _connect()
    try:
        if chunk_count is None:
            conn.execute(
                "UPDATE books SET status = ?, error = ? WHERE id = ?",
                (status, error, book_id),
            )
        else:
            conn.execute(
                "UPDATE books SET status = ?, error = ?, chunk_count = ? WHERE id = ?",
                (status, error, chunk_count, book_id),
            )
        conn.commit()
    finally:
        conn.close()


def get_book(book_id: int) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_books() -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM books ORDER BY added_at DESC").fetchall()
        books = []
        for r in rows:
            book = dict(r)
            scopes = {"classes": [], "sectors": []}
            for s in conn.execute(
                "SELECT kind, value FROM book_scopes WHERE book_id = ? ORDER BY value", (r["id"],)
            ).fetchall():
                key = "classes" if s["kind"] == "class" else "sectors"
                scopes[key].append(s["value"])
            book.update(scopes)
            books.append(book)
        return books
    finally:
        conn.close()


def delete_book(book_id: int):
    conn = _connect()
    try:
        conn.execute("DELETE FROM chunks WHERE book_id = ?", (book_id,))
        conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
        conn.commit()
    finally:
        conn.close()


def add_chunks(
    book_id: int, contents: list[str], embeddings: list[list[float]], pages: list[str | None] | None = None
):
    conn = _connect()
    try:
        if pages is None:
            pages = [None] * len(contents)
        rows = [
            (book_id, i, content, json.dumps(emb), pages[i])
            for i, (content, emb) in enumerate(zip(contents, embeddings))
        ]
        conn.executemany(
            "INSERT INTO chunks (book_id, chunk_index, content, embedding, page) VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def get_all_chunks(class_name: str | None = None, sector: str | None = None) -> list[tuple]:
    conn = _connect()
    try:
        sql = (
            "SELECT c.id, b.name AS book, c.content, c.embedding, c.page "
            "FROM chunks c JOIN books b ON b.id = c.book_id "
            "WHERE b.status = 'ready'"
        )
        params: list[str] = []
        if class_name:
            sql += (
                " AND (NOT EXISTS (SELECT 1 FROM book_scopes s "
                "WHERE s.book_id = b.id AND s.kind = 'class')"
                " OR EXISTS (SELECT 1 FROM book_scopes s "
                "WHERE s.book_id = b.id AND s.kind = 'class' AND s.value = ?))"
            )
            params.append(class_name)
        if sector:
            sql += (
                " AND (NOT EXISTS (SELECT 1 FROM book_scopes s "
                "WHERE s.book_id = b.id AND s.kind = 'sector')"
                " OR EXISTS (SELECT 1 FROM book_scopes s "
                "WHERE s.book_id = b.id AND s.kind = 'sector' AND s.value = ?))"
            )
            params.append(sector)
        rows = conn.execute(sql, params).fetchall()
        return [
            (r["id"], r["book"], r["content"], r["embedding"], r["page"])
            for r in rows
        ]
    finally:
        conn.close()


def get_classes() -> list[str]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT DISTINCT value AS name FROM book_scopes "
            "WHERE kind = 'class' AND value != '' "
            "AND book_id IN (SELECT id FROM books WHERE status = 'ready') "
            "ORDER BY name"
        ).fetchall()
        return [r["name"] for r in rows]
    finally:
        conn.close()


def get_sectors() -> list[str]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT DISTINCT value AS name FROM book_scopes "
            "WHERE kind = 'sector' AND value != '' "
            "AND book_id IN (SELECT id FROM books WHERE status = 'ready') "
            "ORDER BY name"
        ).fetchall()
        return [r["name"] for r in rows]
    finally:
        conn.close()


def add_paper(name: str, content: str) -> int:
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO papers (name, content) VALUES (?, ?)", (name, content)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def set_paper_matches(paper_id: int, matches: list):
    conn = _connect()
    try:
        conn.execute(
            "UPDATE papers SET matches = ? WHERE id = ?", (json.dumps(matches), paper_id)
        )
        conn.commit()
    finally:
        conn.close()


def list_papers() -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM papers ORDER BY added_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_paper_matches() -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, name, matches FROM papers WHERE matches IS NOT NULL"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_paper(paper_id: int):
    conn = _connect()
    try:
        conn.execute("DELETE FROM papers WHERE id = ?", (paper_id,))
        conn.commit()
    finally:
        conn.close()


def count_chunks(book_id: int) -> int:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM chunks WHERE book_id = ?", (book_id,)
        ).fetchone()
        return int(row["n"])
    finally:
        conn.close()


def register_student(name: str, pin: str) -> dict:
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO students (name, pin) VALUES (?, ?)", (name, pin)
        )
        conn.commit()
        return {"id": cur.lastrowid, "name": name}
    finally:
        conn.close()


def login_student(name: str, pin: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, name FROM students WHERE name = ? AND pin = ?",
            (name, pin),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_student(student_id: int) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, name FROM students WHERE id = ?", (student_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def add_quiz_attempt(
    student_id: int,
    class_name: str | None,
    topic: str,
    score: int,
    total: int,
):
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO quiz_attempts (student_id, class_name, topic, score, total) "
            "VALUES (?, ?, ?, ?, ?)",
            (student_id, class_name, topic, score, total),
        )
        conn.commit()
    finally:
        conn.close()


def get_quiz_progress(student_id: int) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT topic, class_name, score, total, created_at "
            "FROM quiz_attempts WHERE student_id = ? "
            "ORDER BY created_at DESC LIMIT 100",
            (student_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_study_path(class_name: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT path, created_at FROM study_paths WHERE class_name = ? ORDER BY id DESC LIMIT 1",
            (class_name,),
        ).fetchone()
        if not row:
            return None
        try:
            return {"path": json.loads(row["path"]), "created_at": row["created_at"]}
        except Exception:
            return None
    finally:
        conn.close()


def set_study_path(class_name: str, path: list):
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO study_paths (class_name, path) VALUES (?, ?)",
            (class_name, json.dumps(path)),
        )
        conn.commit()
    finally:
        conn.close()
