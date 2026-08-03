# Textbook Tutor

An AI teacher for a class, powered by your own textbook.

A student asks a question → the app finds the exact part of the textbook → an AI writes a teacher-style answer based on that material, with the sources shown.

## What it does

- **Ask anything** — type a question, speak it, or upload a photo/PDF of a question paper
- **Answer sheet** — paste or upload a past question paper, get every question answered from the textbook
- **Exam focus** — studies past papers and predicts which textbook topics are most likely on the next exam
- **Revision notes** — 5-minute quick notes for any topic or chapter
- **Flashcards** — tap-to-flip study cards made from the textbook
- **Practice quizzes** — auto-graded multiple-choice quizzes with explanations; scores saved to student progress
- **Question bank** — practice questions with model answers, downloadable
- **Study path** — a step-by-step learning roadmap built from the book
- **Quick sheet** — one-page formula / definition cheat sheet
- **My notes** — students upload their own notes and they get blended into answers
- **Student accounts** — login (no email), streaks, progress; guests can use it too
- **Classes & subjects** — books are scoped to classes and subject sectors, so a Class 10 Biology student only sees their material
- **Chat with memory** — follow-up questions work; answers stream word-by-word and can be read aloud
- **Short / Detailed** answer modes

## How it works

```
Textbook pages (PDF / photos)
   ↓  OCR reads the pages into text (Bengali + English)
   ↓  text is split into parts and indexed by meaning
Student asks a question
   ↓  hybrid search finds the best parts (meaning + keywords)
   ↓  AI writes the answer using only those parts
Answer appears, with the textbook sources shown
```

## Key design choices

- **No hallucination** — the app only answers from the textbook. If a question's topic is not in the book, it says so instead of guessing.
- **Hybrid search** — meaning-based search and keyword search are combined, so a question works even when the student rephrases it differently.
- **Bengali-first** — OCR, search, and answers all work in Bengali.
- **Cross-referencing** — when an answer spans several books, the app pulls from all of them.

## Stack

Python · FastAPI · SQLite · EasyOCR (PyTorch) · hybrid retrieval (FTS5 BM25 + embeddings, RRF fusion) · DeepSeek V4 Pro · multilingual embeddings · mobile-friendly web UI.

## Status

In development. Available to students from a live link; admin is password-protected.

## Run on Google Colab (free, just your Gmail)

The full app — including Bengali OCR (EasyOCR) — runs in Google Colab. Login with Gmail only, no credit card. Your database and OCR models are saved to Google Drive, so nothing is lost between sessions.

### Steps

1. Open the notebook: **https://colab.research.google.com/github/nobnoob001-ops/textbook-tutor/blob/master/run_in_colab.ipynb**
2. Runtime menu → **Run all**
3. Choose your Gmail and **Allow** Drive access when asked
4. The last cell prints a shareable link. Share it with students.
5. Manage at `LINK/admin` (default password `admin123` — change it in Settings)

The first run downloads the OCR models (~2 min); afterwards they load from Drive instantly. Every 60s the database is backed up to Drive.

Free Colab limits: a session lasts at most ~12 hours and ends if the tab is closed. To restart, reopen the notebook and Run all again — data is restored from Drive.

### Local dev

```bash
python run.py        # serves on http://localhost:8080
```
