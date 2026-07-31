const chat = document.getElementById("chat");
const welcome = document.getElementById("welcome");
const question = document.getElementById("question");
const sendBtn = document.getElementById("send");
const attach = document.getElementById("attach");
const fileChip = document.getElementById("file-chip");
const fileName = document.getElementById("file-name");
const clearFile = document.getElementById("clear-file");
const errorBox = document.getElementById("error");
const classNameEl = document.getElementById("class-name");

let attachedFile = null;

async function fetchClassName() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    classNameEl.textContent = data.app || "Textbook Tutor";
  } catch (e) {
    /* ignore */
  }
}

function addBubble(text, cls) {
  welcome.classList.add("hidden");
  const div = document.createElement("div");
  div.className = "bubble " + cls;
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

function showError(el, msg) {
  el.textContent = msg;
  el.classList.remove("hidden");
}

function clearError(el) {
  el.classList.add("hidden");
}

function addSources(container, sources) {
  if (!sources || !sources.length) return;
  const details = document.createElement("details");
  details.className = "sources";
  const summary = document.createElement("summary");
  summary.textContent = `Read from ${sources.length} part(s) of the textbook`;
  details.appendChild(summary);
  for (const s of sources) {
    const item = document.createElement("div");
    item.className = "source-item";
    const page = s.page ? ` — page ${s.page}` : "";
    item.innerHTML =
      `<div class="source-book">📖 ${escapeHtml(s.book)}${page}</div>` +
      `<div class="source-text">${escapeHtml(s.text)}</div>`;
    details.appendChild(item);
  }
  container.appendChild(details);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

document.querySelectorAll("#student-tabs .tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll("#student-tabs .tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".student-panel").forEach((p) => p.classList.add("hidden"));
    tab.classList.add("active");
    document.getElementById("tab-" + tab.dataset.tab).classList.remove("hidden");
  });
});

attach.addEventListener("change", () => {
  if (attach.files.length) {
    attachedFile = attach.files[0];
    fileName.textContent = attachedFile.name;
    fileChip.classList.remove("hidden");
  }
});

clearFile.addEventListener("click", () => {
  attachedFile = null;
  attach.value = "";
  fileChip.classList.add("hidden");
});

question.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});

async function send() {
  const text = question.value.trim();
  if (!text && !attachedFile) {
    showError(errorBox, "Type a question or attach a file first.");
    return;
  }
  clearError(errorBox);
  sendBtn.disabled = true;
  const typing = addBubble("Thinking…", "assistant typing");

  const form = new FormData();
  if (text) form.append("question", text);
  if (attachedFile) form.append("file", attachedFile);

  try {
    const res = await fetch("/api/ask", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Something went wrong.");
    }
    typing.classList.remove("typing");
    typing.textContent = data.answer;
    addSources(typing, data.sources);
  } catch (err) {
    typing.remove();
    showError(errorBox, err.message);
  } finally {
    sendBtn.disabled = false;
    question.value = "";
    attachedFile = null;
    attach.value = "";
    fileChip.classList.add("hidden");
  }
}

sendBtn.addEventListener("click", send);

const paperText = document.getElementById("paper-text");
const paperAttach = document.getElementById("paper-attach");
const paperChip = document.getElementById("paper-chip");
const paperFileName = document.getElementById("paper-file-name");
const clearPaperFile = document.getElementById("clear-paper-file");
const genSheet = document.getElementById("gen-sheet");
const sheetOutput = document.getElementById("sheet-output");
const sheetError = document.getElementById("sheet-error");

let paperFile = null;

paperAttach.addEventListener("change", () => {
  if (paperAttach.files.length) {
    paperFile = paperAttach.files[0];
    paperFileName.textContent = paperFile.name;
    paperChip.classList.remove("hidden");
  }
});

clearPaperFile.addEventListener("click", () => {
  paperFile = null;
  paperAttach.value = "";
  paperChip.classList.add("hidden");
});

genSheet.addEventListener("click", async () => {
  const text = paperText.value.trim();
  if (!text && !paperFile) {
    showError(sheetError, "Paste a question paper or attach a file first.");
    return;
  }
  clearError(sheetError);
  genSheet.disabled = true;
  genSheet.textContent = "Working…";
  sheetOutput.innerHTML = "";

  const form = new FormData();
  if (text) form.append("question", text);
  if (paperFile) form.append("file", paperFile);

  try {
    const res = await fetch("/api/answer-sheet", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Something went wrong.");
    }
    for (const item of data.items || []) {
      const block = document.createElement("div");
      block.className = "sheet-item";
      const q = document.createElement("div");
      q.className = "sheet-question";
      q.textContent = `${item.number}. ${item.question || ""}`;
      const a = document.createElement("div");
      a.className = "sheet-answer";
      a.textContent = item.answer || "";
      block.appendChild(q);
      block.appendChild(a);
      sheetOutput.appendChild(block);
    }
    const src = document.createElement("div");
    addSources(src, data.sources);
    sheetOutput.appendChild(src);
  } catch (err) {
    showError(sheetError, err.message);
  } finally {
    genSheet.disabled = false;
    genSheet.textContent = "Create answer sheet";
  }
});

const loadFocus = document.getElementById("load-focus");
const focusOutput = document.getElementById("focus-output");
const focusError = document.getElementById("focus-error");

loadFocus.addEventListener("click", async () => {
  clearError(focusError);
  loadFocus.disabled = true;
  loadFocus.textContent = "Working…";
  focusOutput.innerHTML = "";
  try {
    const res = await fetch("/api/exam-focus");
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Something went wrong.");
    }
    if (data.prediction) {
      const box = document.createElement("div");
      box.className = "focus-prediction";
      box.textContent = data.prediction;
      focusOutput.appendChild(box);
    }
    for (const t of data.topics || []) {
      const row = document.createElement("div");
      row.className = "topic-row";
      const meta = document.createElement("div");
      meta.className = "topic-meta";
      const page = t.page ? ` · page ${t.page}` : "";
      meta.textContent = `${t.book}${page}`;
      const count = document.createElement("span");
      count.className = "badge";
      count.textContent = `${t.count}× in past papers`;
      const text = document.createElement("div");
      text.className = "topic-text";
      text.textContent = t.text;
      row.appendChild(meta);
      row.appendChild(count);
      row.appendChild(text);
      focusOutput.appendChild(row);
    }
  } catch (err) {
    showError(focusError, err.message);
  } finally {
    loadFocus.disabled = false;
    loadFocus.textContent = "Load exam focus";
  }
});

const revisionTopic = document.getElementById("revision-topic");
const genRevision = document.getElementById("gen-revision");
const revisionOutput = document.getElementById("revision-output");
const revisionError = document.getElementById("revision-error");

revisionTopic.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    genRevision.click();
  }
});

genRevision.addEventListener("click", async () => {
  const topic = revisionTopic.value.trim();
  if (!topic) {
    showError(revisionError, "Enter a topic or chapter name.");
    return;
  }
  clearError(revisionError);
  genRevision.disabled = true;
  genRevision.textContent = "Working…";
  revisionOutput.innerHTML = "";
  try {
    const form = new FormData();
    form.append("topic", topic);
    const res = await fetch("/api/revision-notes", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Something went wrong.");
    }
    const box = document.createElement("div");
    box.className = "bubble assistant";
    box.textContent = data.notes;
    revisionOutput.appendChild(box);
    addSources(revisionOutput, data.sources);
  } catch (err) {
    showError(revisionError, err.message);
  } finally {
    genRevision.disabled = false;
    genRevision.textContent = "Make notes";
  }
});

const flashcardTopic = document.getElementById("flashcard-topic");
const genFlashcards = document.getElementById("gen-flashcards");
const flashcardOutput = document.getElementById("flashcard-output");
const flashcardError = document.getElementById("flashcard-error");

flashcardTopic.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    genFlashcards.click();
  }
});

genFlashcards.addEventListener("click", async () => {
  const topic = flashcardTopic.value.trim();
  if (!topic) {
    showError(flashcardError, "Enter a topic or chapter name.");
    return;
  }
  clearError(flashcardError);
  genFlashcards.disabled = true;
  genFlashcards.textContent = "Working…";
  flashcardOutput.innerHTML = "";
  try {
    const form = new FormData();
    form.append("topic", topic);
    const res = await fetch("/api/flashcards", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Something went wrong.");
    }
    const grid = document.createElement("div");
    grid.className = "flashcard-grid";
    for (const card of data.cards || []) {
      const c = document.createElement("div");
      c.className = "flashcard";
      const inner = document.createElement("div");
      inner.className = "flashcard-inner";
      const front = document.createElement("div");
      front.className = "flashcard-face front";
      front.textContent = card.front || "";
      const back = document.createElement("div");
      back.className = "flashcard-face back";
      back.textContent = card.back || "";
      inner.appendChild(front);
      inner.appendChild(back);
      c.appendChild(inner);
      c.addEventListener("click", () => c.classList.toggle("flipped"));
      grid.appendChild(c);
    }
    flashcardOutput.appendChild(grid);
    addSources(flashcardOutput, data.sources);
  } catch (err) {
    showError(flashcardError, err.message);
  } finally {
    genFlashcards.disabled = false;
    genFlashcards.textContent = "Make cards";
  }
});

fetchClassName();
