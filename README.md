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
- **Answer sheet** — paste or upload a past question paper, get every question answered from the textbook
- **Exam focus** — the app studies past papers you upload and predicts which textbook topics are most likely on the next exam
- **Revision notes** — type a topic/chapter, get quick 5-minute notes from the textbook
- **Flashcards** — type a topic, get study cards (tap to flip) made from the textbook
- **Practice quizzes** — type a topic, get a multiple-choice quiz (4 questions), answer it, and get instant grading with explanations
- **Question bank** — type a topic, get a set of practice questions you can download as a text file
- **Study path** — a personalized learning roadmap for the class: what to study, in what order (reuse topics in a chapter until done)
- **Quick sheet** — a one-page formula / definition cheat sheet for a topic
- **Student accounts** — students register/login (no email needed, name + password), see their streak, quiz scores and progress; visitors can use the app without an account
- **Classes** — textbooks are tagged with a class (e.g. "Class 10"); students pick their class and everything (search, chat, study path) uses only that class's books
- **Subject sectors / scoped books** — every book can be restricted to specific classes *and* subject sectors (e.g. "Class 10" + "Biology"). A book with no limits is available to all classes and subjects. Students pick a class + subject, and all answers/quizzes/search come only from matching books — so a Class 10 Biology student never sees Class 9 Physics material
- **Library manager** — a visual, filterable library (search, class/subject/status filters), color-coded book cards, and inline editing of each book's name, class scope, and subject scope without re-uploading
- **Chat with memory** — the tutor remembers the conversation (follow-up questions work), streams answers word-by-word, reads answers aloud, and takes voice questions in the browser
- **Answer mode** — toggle between Short and Detailed answers
- Admin page — add/remove textbooks, manage the library, upload past question papers
- Settings — plug in any OpenAI-compatible API (OpenAI, Gemini, DeepSeek, Groq, Mistral, OpenRouter, ...)
- RAG search — answers are grounded in the class textbook, with page citations
- OCR — reads printed PDFs and photos of pages

## Requirements

- Python 3.10+
- `tesseract-ocr` and `poppler-utils` installed on the system:
  - Ubuntu/Debian: `sudo apt install tesseract-ocr poppler-utils`
- An OpenAI-compatible API key (chat + embeddings)
- A budget-friendly AI provider — see the quota warning below

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
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-3.6-flash` | `gemini-embedding-001` |

> **Notes:**
> - Google's OpenAI-compatible URL handles chat only — it does not expose `/embeddings` (you'll get a 404). The app detects the Gemini URL and calls Google's native `batchEmbedContents` endpoint instead, so the same base URL works for both fields.
> - Use `gemini-embedding-001` for embeddings. The old `text-embedding-004` is deprecated and returns 404.
> - Older chat models like `gemini-2.5-flash` return 404 for **new** API keys ("no longer available to new users"). Use the current free flash model, e.g. `gemini-3.6-flash`.
> - ⚠️ **Gemini free tier is extremely limited** — this project's key hit "generate_content_free_tier_requests, limit: 20 per day per project per model" after one day of testing. The app retries 429s with backoff and degrades to a clean error message, but 20 requests/day is not enough for a real class. For production, use a paid Gemini tier or another provider.
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

The design is RAG-first and provider-agnostic: swap a bigger model or move to a cloud server without rewriting. Student accounts, per-class books, quizzes, and a study path are already in.
