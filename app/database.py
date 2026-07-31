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
    added_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    chunk_index INTEGER,
    content TEXT NOT NULL,
    embedding TEXT,
    FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
);
"""


def init_db():
    conn = _connect()
    try:
        conn.executescript(SCHEMA)
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


def add_book(name: str, file_type: str) -> int:
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO books (name, file_type) VALUES (?, ?)", (name, file_type)
        )
        conn.commit()
        return cur.lastrowid
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
        return [dict(r) for r in rows]
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


def add_chunks(book_id: int, contents: list[str], embeddings: list[list[float]]):
    conn = _connect()
    try:
        rows = [
            (book_id, i, content, json.dumps(emb))
            for i, (content, emb) in enumerate(zip(contents, embeddings))
        ]
        conn.executemany(
            "INSERT INTO chunks (book_id, chunk_index, content, embedding) VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def get_all_chunks() -> list[tuple]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT c.id, b.name AS book, c.content, c.embedding "
            "FROM chunks c JOIN books b ON b.id = c.book_id "
            "WHERE b.status = 'ready'"
        ).fetchall()
        return [(r["id"], r["book"], r["content"], r["embedding"]) for r in rows]
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
