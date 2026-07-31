# Textbook Tutor

An AI teacher for a class, powered by your own textbook.

A student asks a question → the app searches your class textbook → an AI (any provider you choose) writes a teacher-style answer, step by step, based on that material.

## How it works

```
You upload the class textbook (PDF / photos / text)
   ↓  app reads it, cuts it into parts, indexes it
Student asks a question (typed, or photo/PDF of a question paper)
   ↓  app finds the relevant parts of the textbook
   ↓  sends those parts + the question to the AI
Teacher-style answer appears, with the textbook sources shown
```

The AI never gets stuck: if the textbook doesn't cover a question, it still explains from its own knowledge — like a teacher would.

## Features

- Student page — ask questions by typing or by uploading a photo/PDF of a question paper
- Admin page — add/remove textbooks, manage the library
- Settings — plug in any OpenAI-compatible API (OpenAI, Gemini, DeepSeek, Groq, Mistral, OpenRouter, ...)
- RAG search — answers are grounded in the class textbook
- OCR — reads printed PDFs and photos of pages

## Requirements

- Python 3.10+
- `tesseract-ocr` and `poppler-utils` installed on the system:
  - Ubuntu/Debian: `sudo apt install tesseract-ocr poppler-utils`
- An OpenAI-compatible API key (chat + embeddings)

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python run.py
```

Open http://localhost:8080 in your browser.

Default admin password is `admin123`. **Change it** in Admin → Settings (or set `ADMIN_PASSWORD` env var before first run).

## Admin setup (once)

1. Open http://localhost:8080/admin
2. Log in with the admin password
3. Go to **Settings** and fill in:
   - Chat: API base URL, API key, model (e.g. OpenAI `https://api.openai.com/v1`, `gpt-4o-mini`)
   - Embeddings: API base URL, API key, model (e.g. `text-embedding-3-small`)
4. Go to **Add Textbook** and upload the class book

Some providers and how they map:

| Provider | Chat base URL | Chat model example | Embeddings model example |
|---|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` | `text-embedding-3-small` |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.5-flash` | `gemini-embedding-001` |

> **Notes:**
> - Google's OpenAI-compatible URL handles chat only — it does not expose `/embeddings` (you'll get a 404). The app detects the Gemini URL and calls Google's native `batchEmbedContents` endpoint instead, so the same base URL works for both fields.
> - Use `gemini-embedding-001` for embeddings. The old `text-embedding-004` is deprecated and returns 404.
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` | needs a separate embedding provider |
| Mistral | `https://api.mistral.ai/v1` | `mistral-small-latest` | `mistral-embed` |

If your chat provider has no embeddings API (DeepSeek, Groq), use a free/cheap OpenAI-compatible embeddings provider (e.g. Jina `https://api.jina.ai/v1`, model `jina-embeddings-v3`) for the embedding fields.

## Serving it to students

Same device / same Wi-Fi: open `http://<your-device-ip>:8080` (find it with `hostname -I`).

For students outside your network, use a free tunnel (e.g. Cloudflare Tunnel) or port-forwarding.

## Project structure

```
app/
  main.py         FastAPI server + routes
  database.py     SQLite storage (books, chunks, settings)
  text_extract.py PDF/image/text reading + OCR + chunking
  ai.py           OpenAI-compatible chat + embeddings calls
  search.py       similarity search over the book chunks
  static/         student page + admin page (no build step)
run.py            entry point
```

## Scaling later

The design is RAG-first and provider-agnostic: swap a bigger model, move to a cloud server, or add accounts — without rewriting.
