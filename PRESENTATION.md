# Textbook Tutor — Presentation

## 1. One-liner (30-second pitch)
> "An AI teacher that answers students' questions **only from their own class textbook** — so every answer is correct and traceable, in Bengali or English, on any phone."

---

## 2. The problem
- Students use Google / ChatGPT and get **generic or wrong** answers — not what's in their actual textbook.
- Teachers can't give every student 1-on-1 help.
- Bengali textbooks are **not well supported** by most AI tools (weak OCR + weak search).

## 3. What I built
A web app called **Textbook Tutor** where a student:
- Types a question (or speaks it, or takes a photo of the question paper)
- Gets an answer written **from their class textbook**, with **sources cited**
- If the answer is NOT in the book, the app says so — it never makes things up

**Extra study tools (all generated from the textbook):**
- Practice quizzes (auto-graded, progress saved)
- Answer sheets for past question papers
- Flashcards & revision notes
- Exam focus — predicts likely exam topics from past papers
- Study path, question bank, quick formula sheet
- My Notes — student's own notes get mixed into answers
- Multi-class + subject support, student accounts

## 4. How it works (the tech behind it)
```
Textbook pages (photos/PDF)
      ↓ 1. OCR — turns Bengali pages into text  (EasyOCR, 2026)
      ↓ 2. Chunking + Embeddings — meaning stored as numbers
Student question
      ↓ 3. Hybrid search — semantic (vector) + keyword (BM25), fused with RRF
      ↓ 4. DeepSeek V4 Pro (2026) writes the answer using only matched passages
   → Answer with citations
```
1. **OCR**: scans Bengali textbook pages into searchable text (EasyOCR, near-perfect Bengali accuracy)
2. **Indexing**: text is split into passages, each converted to a mathematical "embedding" that captures meaning
3. **Hybrid retrieval**: finds the best passages two ways at once — by meaning (embeddings) and by exact keywords (BM25) — then merges the results (Reciprocal Rank Fusion) for the best matches
4. **Answer generation**: the AI model writes the answer **using only those passages**, so it can't drift from the textbook

## 5. Tech stack (latest, 2026)
| Layer | Technology |
|---|---|
| Backend | Python + FastAPI + SQLite |
| Bengali OCR | EasyOCR 1.7.2 (PyTorch CPU) |
| Search | Hybrid: FTS5 BM25 + vector embeddings, RRF fusion |
| AI chat | DeepSeek V4 Pro (NVIDIA free API) |
| Embeddings | multilingual nv-embedqa-e5-v5 |
| Frontend | Modern, mobile-friendly web UI |

## 6. Why it's special
- **No hallucination** — a "minimum match" gate refuses questions that aren't in the book
- **Real Bengali support** — OCR + search + answers all work in Bengali
- **Cross-references** multiple books when an answer spans them
- **Free AI** — uses NVIDIA's free API, no API bill
- **Always-on** — students can use it from anywhere via a secure link; admin stays private

## 7. Verified results
- Bengali page OCR is near-perfect (tested on real scanned pages)
- Hybrid search finds the exact passage for a question (tested end-to-end)
- Answers come out in Bengali with textbook citations
- Works on any phone, no app install

## 8. What's next (optional)
- Own permanent domain (no more random link)
- More classes & subjects, analytics for teachers, offline mode
