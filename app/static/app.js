const appNameEl = document.getElementById("app-name");
const classSelect = document.getElementById("class-select");
const studentBadge = document.getElementById("student-badge");
const studentNameEl = document.getElementById("student-name");
const logoutBtn = document.getElementById("logout");

const chat = document.getElementById("chat");
const welcome = document.getElementById("welcome");
const question = document.getElementById("question");
const sendBtn = document.getElementById("send");
const micBtn = document.getElementById("mic");
const attach = document.getElementById("attach");
const fileChip = document.getElementById("file-chip");
const fileName = document.getElementById("file-name");
const clearFile = document.getElementById("clear-file");
const errorBox = document.getElementById("error");
const modeToggle = document.getElementById("mode-toggle");
const clearChatBtn = document.getElementById("clear-chat");

const loginModal = document.getElementById("login-modal");
const loginName = document.getElementById("login-name");
const loginPin = document.getElementById("login-pin");
const loginBtn = document.getElementById("login-btn");
const registerBtn = document.getElementById("register-btn");
const skipBtn = document.getElementById("skip-btn");
const loginError = document.getElementById("login-error");

const STUDENT_KEY = "tt_student";
const CLASS_KEY = "tt_class";
const MODE_KEY = "tt_mode";

let attachedFile = null;
let currentClass = localStorage.getItem(CLASS_KEY) || "";
let mode = localStorage.getItem(MODE_KEY) || "short";

function getStudent() {
  try {
    return JSON.parse(localStorage.getItem(STUDENT_KEY) || "null");
  } catch (e) {
    return null;
  }
}

function setStudent(s) {
  if (s) localStorage.setItem(STUDENT_KEY, JSON.stringify(s));
  else localStorage.removeItem(STUDENT_KEY);
  renderStudentBadge();
}

function renderStudentBadge() {
  const s = getStudent();
  if (s) {
    studentNameEl.textContent = s.name;
    studentBadge.classList.remove("hidden");
  } else {
    studentBadge.classList.add("hidden");
  }
}

logoutBtn.addEventListener("click", () => {
  setStudent(null);
});

function showError(el, msg) {
  el.textContent = msg;
  el.classList.remove("hidden");
}

function clearError(el) {
  el.classList.add("hidden");
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function baseForm() {
  const form = new FormData();
  if (currentClass) form.append("class_name", currentClass);
  return form;
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

function addListen(container, text) {
  if (!("speechSynthesis" in window)) return;
  const btn = document.createElement("button");
  btn.className = "ghost small listen";
  btn.textContent = "🔊 Listen";
  btn.addEventListener("click", () => {
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "bn-BD";
    speechSynthesis.speak(u);
  });
  container.appendChild(btn);
}

/* ---------------- classes ---------------- */

async function loadClasses() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    appNameEl.textContent = data.app || "Textbook Tutor";
    const classes = data.classes || [];
    if (classes.length > 1) {
      classSelect.innerHTML = "";
      for (const c of classes) {
        const opt = document.createElement("option");
        opt.value = c;
        opt.textContent = c;
        classSelect.appendChild(opt);
      }
      classSelect.value = classes.includes(currentClass) ? currentClass : classes[0];
      classSelect.classList.remove("hidden");
    } else {
      classSelect.classList.add("hidden");
    }
    if (classes.length) {
      currentClass = classSelect.value || classes[0];
      localStorage.setItem(CLASS_KEY, currentClass);
    }
  } catch (e) {
    /* ignore */
  }
  onClassChange();
}

classSelect.addEventListener("change", () => {
  currentClass = classSelect.value;
  localStorage.setItem(CLASS_KEY, currentClass);
  onClassChange();
});

function onClassChange() {
  renderChatHistory();
}

/* ---------------- tabs ---------------- */

document.querySelectorAll("#student-tabs .tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll("#student-tabs .tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".student-panel").forEach((p) => p.classList.add("hidden"));
    tab.classList.add("active");
    document.getElementById("tab-" + tab.dataset.tab).classList.remove("hidden");
  });
});

/* ---------------- login ---------------- */

function showLogin() {
  loginModal.classList.remove("hidden");
}

function hideLogin() {
  loginModal.classList.add("hidden");
}

async function authCall(path, name, pin) {
  const form = new FormData();
  form.append("name", name);
  form.append("pin", pin);
  const res = await fetch(path, { method: "POST", body: form });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Something went wrong.");
  return data;
}

loginBtn.addEventListener("click", async () => {
  clearError(loginError);
  try {
    const s = await authCall("/api/login", loginName.value, loginPin.value);
    setStudent({ id: s.id, name: s.name });
    hideLogin();
  } catch (e) {
    showError(loginError, e.message);
  }
});

registerBtn.addEventListener("click", async () => {
  clearError(loginError);
  try {
    const s = await authCall("/api/register", loginName.value, loginPin.value);
    setStudent({ id: s.id, name: s.name });
    hideLogin();
  } catch (e) {
    showError(loginError, e.message);
  }
});

skipBtn.addEventListener("click", () => {
  setStudent(null);
  hideLogin();
});

/* ---------------- chat history ---------------- */

function historyKey() {
  return "tt_hist_" + currentClass;
}

function getHistory() {
  try {
    return JSON.parse(localStorage.getItem(historyKey()) || "[]");
  } catch (e) {
    return [];
  }
}

function setHistory(h) {
  localStorage.setItem(historyKey(), JSON.stringify(h.slice(-20)));
}

function renderChatHistory() {
  chat.innerHTML = "";
  welcome.classList.remove("hidden");
  for (const m of getHistory()) {
    addBubble(m.content, m.role === "user" ? "user" : "assistant");
  }
}

clearChatBtn.addEventListener("click", () => {
  if (!confirm("Clear this conversation?")) return;
  setHistory([]);
  renderChatHistory();
});

/* ---------------- mode toggle ---------------- */

modeToggle.querySelectorAll("button").forEach((b) => {
  b.addEventListener("click", () => {
    modeToggle.querySelectorAll("button").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    mode = b.dataset.mode;
    localStorage.setItem(MODE_KEY, mode);
  });
});

/* ---------------- mic (voice question) ---------------- */

let recognition = null;

micBtn.addEventListener("click", () => {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    alert("Voice input is not supported in this browser. Try Google Chrome.");
    return;
  }
  if (!recognition) {
    recognition = new SR();
    recognition.interimResults = true;
    recognition.onresult = (e) => {
      let t = "";
      for (let i = 0; i < e.results.length; i++) t += e.results[i][0].transcript;
      question.value = t;
    };
    recognition.onend = () => micBtn.classList.remove("recording");
    recognition.onerror = () => micBtn.classList.remove("recording");
  }
  if (micBtn.classList.contains("recording")) {
    recognition.stop();
    micBtn.classList.remove("recording");
  } else {
    micBtn.classList.add("recording");
    try {
      recognition.start();
    } catch (e) {
      /* already running */
    }
  }
});

/* ---------------- ask / chat ---------------- */

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

  const history = getHistory();
  const form = baseForm();
  if (text) form.append("question", text);
  if (attachedFile) form.append("file", attachedFile);
  form.append("history", JSON.stringify(history.slice(-6)));
  form.append("mode", mode);

  if (text) {
    addBubble(text, "user");
    welcome.classList.add("hidden");
  }
  const typing = addBubble("", "assistant typing");

  let answerText = "";
  try {
    const res = await fetch("/api/ask/stream", { method: "POST", body: form });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "Something went wrong.");
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const events = buf.split("\n\n");
      buf = events.pop();
      for (const ev of events) {
        for (const line of ev.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          let d;
          try {
            d = JSON.parse(line.slice(6));
          } catch (e) {
            continue;
          }
          if (d.token) {
            answerText += d.token;
            typing.textContent = answerText;
            chat.scrollTop = chat.scrollHeight;
          } else if (d.sources) {
            addSources(typing, d.sources);
          } else if (d.error) {
            showError(errorBox, d.error);
          }
        }
      }
    }
    if (answerText) {
      typing.classList.remove("typing");
      addListen(typing, answerText);
      history.push({ role: "user", content: text });
      history.push({ role: "assistant", content: answerText });
      setHistory(history);
    } else {
      typing.remove();
    }
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

/* ---------------- answer sheet ---------------- */

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

  const form = baseForm();
  if (text) form.append("question", text);
  if (paperFile) form.append("file", paperFile);
  form.append("mode", mode);

  try {
    const res = await fetch("/api/answer-sheet", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Something went wrong.");
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
      addListen(block, item.answer || "");
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

/* ---------------- exam focus ---------------- */

const loadFocus = document.getElementById("load-focus");
const focusOutput = document.getElementById("focus-output");
const focusError = document.getElementById("focus-error");

loadFocus.addEventListener("click", async () => {
  clearError(focusError);
  loadFocus.disabled = true;
  loadFocus.textContent = "Working…";
  focusOutput.innerHTML = "";
  try {
    const qs = new URLSearchParams();
    if (currentClass) qs.set("class_name", currentClass);
    const res = await fetch("/api/exam-focus?" + qs.toString());
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Something went wrong.");
    if (data.prediction) {
      const box = document.createElement("div");
      box.className = "focus-prediction";
      box.textContent = data.prediction;
      focusOutput.appendChild(box);
      addListen(box, data.prediction);
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

/* ---------------- study path ---------------- */

const loadPath = document.getElementById("load-path");
const pathOutput = document.getElementById("path-output");
const pathError = document.getElementById("path-error");

loadPath.addEventListener("click", async () => {
  clearError(pathError);
  loadPath.disabled = true;
  loadPath.textContent = "Building…";
  pathOutput.innerHTML = "";
  try {
    const qs = new URLSearchParams();
    if (currentClass) qs.set("class_name", currentClass);
    const res = await fetch("/api/study-path?" + qs.toString());
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Something went wrong.");
    for (const s of data.steps || []) {
      const step = document.createElement("div");
      step.className = "path-step";
      const num = document.createElement("div");
      num.className = "path-num";
      num.textContent = s.step || "";
      const body = document.createElement("div");
      body.className = "path-body";
      const title = document.createElement("div");
      title.className = "path-title";
      title.textContent = s.title || "";
      const what = document.createElement("div");
      what.className = "path-what";
      what.textContent = s.what || "";
      const practice = document.createElement("button");
      practice.className = "ghost small";
      practice.textContent = "Practice this topic";
      practice.addEventListener("click", () => {
        document.querySelector('#student-tabs .tab[data-tab="quiz"]').click();
        document.getElementById("quiz-topic").value = s.title || "";
        document.getElementById("gen-quiz").click();
      });
      body.appendChild(title);
      body.appendChild(what);
      body.appendChild(practice);
      step.appendChild(num);
      step.appendChild(body);
      pathOutput.appendChild(step);
    }
  } catch (err) {
    showError(pathError, err.message);
  } finally {
    loadPath.disabled = false;
    loadPath.textContent = "Show my study path";
  }
});

/* ---------------- revision notes ---------------- */

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
    const form = baseForm();
    form.append("topic", topic);
    const res = await fetch("/api/revision-notes", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Something went wrong.");
    const box = document.createElement("div");
    box.className = "bubble assistant";
    box.textContent = data.notes;
    revisionOutput.appendChild(box);
    addListen(box, data.notes);
    addSources(revisionOutput, data.sources);
  } catch (err) {
    showError(revisionError, err.message);
  } finally {
    genRevision.disabled = false;
    genRevision.textContent = "Make notes";
  }
});

/* ---------------- flashcards ---------------- */

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
    const form = baseForm();
    form.append("topic", topic);
    const res = await fetch("/api/flashcards", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Something went wrong.");
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

/* ---------------- quiz ---------------- */

const quizTopic = document.getElementById("quiz-topic");
const quizCount = document.getElementById("quiz-count");
const genQuiz = document.getElementById("gen-quiz");
const quizOutput = document.getElementById("quiz-output");
const quizError = document.getElementById("quiz-error");

quizTopic.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    genQuiz.click();
  }
});

genQuiz.addEventListener("click", async () => {
  const topic = quizTopic.value.trim();
  if (!topic) {
    showError(quizError, "Enter a topic or chapter name.");
    return;
  }
  clearError(quizError);
  genQuiz.disabled = true;
  genQuiz.textContent = "Making quiz…";
  quizOutput.innerHTML = "";
  try {
    const form = baseForm();
    form.append("topic", topic);
    form.append("count", quizCount.value);
    const res = await fetch("/api/quiz", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Something went wrong.");
    const questions = data.questions || [];
    if (!questions.length) throw new Error("The AI returned no questions. Try another topic.");

    for (let i = 0; i < questions.length; i++) {
      const q = questions[i];
      const block = document.createElement("div");
      block.className = "quiz-q";
      const text = document.createElement("div");
      text.className = "quiz-qtext";
      text.textContent = `${i + 1}. ${q.question || ""}`;
      block.appendChild(text);
      (q.options || []).forEach((opt, j) => {
        const label = document.createElement("label");
        label.className = "quiz-opt";
        const radio = document.createElement("input");
        radio.type = "radio";
        radio.name = "quizq" + i;
        radio.value = j;
        const span = document.createElement("span");
        span.textContent = opt;
        label.appendChild(radio);
        label.appendChild(span);
        block.appendChild(label);
      });
      quizOutput.appendChild(block);
    }

    const submit = document.createElement("button");
    submit.className = "primary";
    submit.id = "submit-quiz";
    submit.textContent = "Check my answers";
    submit.addEventListener("click", () => submitQuiz(questions));
    quizOutput.appendChild(submit);

    const saved = document.createElement("div");
    saved.id = "quiz-result";
    quizOutput.appendChild(saved);
  } catch (err) {
    showError(quizError, err.message);
  } finally {
    genQuiz.disabled = false;
    genQuiz.textContent = "Start quiz";
  }
});

async function submitQuiz(questions) {
  const answers = [];
  for (let i = 0; i < questions.length; i++) {
    const checked = document.querySelector(`input[name="quizq${i}"]:checked`);
    answers.push(checked ? parseInt(checked.value, 10) : null);
  }
  let score = 0;
  const results = questions.map((q, i) => {
    const ok = answers[i] === q.answer;
    if (ok) score++;
    return {
      question: q.question,
      options: q.options,
      correct: q.answer,
      chosen: answers[i],
      ok,
      explanation: q.explanation,
    };
  });

  const student = getStudent();
  if (student && student.id) {
    const form = new FormData();
    form.append("student_id", student.id);
    form.append("class_name", currentClass);
    form.append("topic", quizTopic.value.trim());
    form.append("questions", JSON.stringify(questions));
    form.append("answers", JSON.stringify(answers));
    try {
      await fetch("/api/quiz/submit", { method: "POST", body: form });
    } catch (e) {
      /* progress save failed, results still shown */
    }
  }

  const result = document.getElementById("quiz-result");
  result.innerHTML = "";
  const head = document.createElement("div");
  head.className = "quiz-score";
  head.textContent = `You scored ${score} / ${questions.length}`;
  result.appendChild(head);
  if (score === questions.length) head.textContent += " — perfect! 🎉";
  const pct = Math.round((score / questions.length) * 100);
  const bar = document.createElement("div");
  bar.className = "progress-bar";
  const fill = document.createElement("div");
  fill.className = "progress-fill";
  fill.style.width = pct + "%";
  bar.appendChild(fill);
  result.appendChild(bar);
  if (!student) {
    const hint = document.createElement("p");
    hint.className = "hint";
    hint.textContent = "Log in to save this score to your progress.";
    result.appendChild(hint);
  }

  results.forEach((r, i) => {
    const block = document.createElement("div");
    block.className = "quiz-review " + (r.ok ? "right" : "wrong");
    const q = document.createElement("div");
    q.className = "quiz-qtext";
    q.textContent = `${i + 1}. ${r.question || ""}`;
    block.appendChild(q);
    if (r.ok) {
      const good = document.createElement("div");
      good.className = "quiz-feedback right";
      good.textContent = `✓ ${r.options[r.correct]}`;
      block.appendChild(good);
    } else {
      const wrong = document.createElement("div");
      wrong.className = "quiz-feedback wrong";
      wrong.textContent = `✗ You chose: ${r.chosen != null ? r.options[r.chosen] : "no answer"}`;
      block.appendChild(wrong);
      const good = document.createElement("div");
      good.className = "quiz-feedback right";
      good.textContent = `✓ Correct: ${r.options[r.correct]}`;
      block.appendChild(good);
    }
    if (r.explanation) {
      const exp = document.createElement("div");
      exp.className = "quiz-expl";
      exp.textContent = r.explanation;
      block.appendChild(exp);
    }
    result.appendChild(block);
  });
}

/* ---------------- question bank ---------------- */

const qbTopic = document.getElementById("qb-topic");
const qbCount = document.getElementById("qb-count");
const genQb = document.getElementById("gen-qb");
const qbDownload = document.getElementById("qb-download");
const qbOutput = document.getElementById("qb-output");
const qbError = document.getElementById("qb-error");

qbTopic.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    genQb.click();
  }
});

genQb.addEventListener("click", async () => {
  const topic = qbTopic.value.trim();
  if (!topic) {
    showError(qbError, "Enter a topic or chapter name.");
    return;
  }
  clearError(qbError);
  genQb.disabled = true;
  genQb.textContent = "Generating…";
  qbOutput.innerHTML = "";
  qbDownload.classList.add("hidden");
  try {
    const form = baseForm();
    form.append("topic", topic);
    form.append("count", qbCount.value);
    const res = await fetch("/api/question-bank", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Something went wrong.");
    const questions = data.questions || [];
    for (let i = 0; i < questions.length; i++) {
      const q = questions[i];
      const block = document.createElement("div");
      block.className = "qb-item";
      const head = document.createElement("div");
      head.className = "qb-q";
      head.textContent = `${i + 1}. [${q.type || "short"}] ${q.question || ""}`;
      const ans = document.createElement("div");
      ans.className = "qb-a";
      ans.textContent = `Answer: ${q.answer || ""}`;
      block.appendChild(head);
      block.appendChild(ans);
      qbOutput.appendChild(block);
    }
    if (questions.length) {
      qbDownload.classList.remove("hidden");
      qbDownload.onclick = () => downloadQuestionBank(topic, questions);
    }
  } catch (err) {
    showError(qbError, err.message);
  } finally {
    genQb.disabled = false;
    genQb.textContent = "Generate";
  }
});

function downloadQuestionBank(topic, questions) {
  let out = `QUESTION BANK - ${topic}\n\n`;
  questions.forEach((q, i) => {
    out += `${i + 1}. (${q.type || "short"}) ${q.question}\nAnswer: ${q.answer}\n\n`;
  });
  const blob = new Blob([out], { type: "text/plain;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "question-bank-" + topic.replace(/\s+/g, "-").toLowerCase() + ".txt";
  a.click();
  URL.revokeObjectURL(a.href);
}

/* ---------------- quick sheet ---------------- */

const qsTopic = document.getElementById("qs-topic");
const genQs = document.getElementById("gen-qs");
const qsOutput = document.getElementById("qs-output");
const qsError = document.getElementById("qs-error");

qsTopic.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    genQs.click();
  }
});

genQs.addEventListener("click", async () => {
  clearError(qsError);
  genQs.disabled = true;
  genQs.textContent = "Making sheet…";
  qsOutput.innerHTML = "";
  try {
    const form = baseForm();
    form.append("topic", qsTopic.value.trim());
    const res = await fetch("/api/quick-sheet", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Something went wrong.");
    const box = document.createElement("div");
    box.className = "bubble assistant";
    box.textContent = data.sheet;
    qsOutput.appendChild(box);
    addListen(box, data.sheet);
    addSources(qsOutput, data.sources);
  } catch (err) {
    showError(qsError, err.message);
  } finally {
    genQs.disabled = false;
    genQs.textContent = "Make quick sheet";
  }
});

/* ---------------- init ---------------- */

modeToggle.querySelectorAll("button").forEach((b) => {
  if (b.dataset.mode === mode) b.classList.add("active");
  else b.classList.remove("active");
});

renderStudentBadge();
loadClasses();
if (!getStudent()) showLogin();
