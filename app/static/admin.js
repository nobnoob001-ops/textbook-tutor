const TOKEN_KEY = "tt_admin_password";

const loginSection = document.getElementById("login");
const panelSection = document.getElementById("panel");
const loginBtn = document.getElementById("login-btn");
const password = document.getElementById("password");
const loginError = document.getElementById("login-error");
const logoutBtn = document.getElementById("logout");
const appName = document.getElementById("app-name");

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const pickFile = document.getElementById("pick-file");
const uploadProgress = document.getElementById("upload-progress");
const progressLabel = document.getElementById("progress-label");
const uploadError = document.getElementById("upload-error");

const libraryList = document.getElementById("library-list");

const paperDropzone = document.getElementById("paper-dropzone");
const paperInput = document.getElementById("paper-input");
const pickPaper = document.getElementById("pick-paper");
const paperUploadError = document.getElementById("paper-upload-error");
const papersList = document.getElementById("papers-list");

const settingsError = document.getElementById("settings-error");
const settingsOk = document.getElementById("settings-ok");

let pollingTimer = null;

function auth() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

function setAuth(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

async function api(path, options = {}) {
  const headers = { "X-Admin-Password": auth(), ...(options.headers || {}) };
  const res = await fetch(path, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.detail || "Request failed");
    err.status = res.status;
    throw err;
  }
  return data;
}

function showError(el, msg) {
  el.textContent = msg;
  el.classList.remove("hidden");
}

function clearError(el) {
  el.classList.add("hidden");
}

loginBtn.addEventListener("click", async () => {
  const form = new FormData();
  form.append("password", password.value);
  try {
    const res = await fetch("/api/admin/login", { method: "POST", body: form });
    if (!res.ok) {
      throw new Error("Wrong password");
    }
    setAuth(password.value);
    showPanel();
  } catch (e) {
    showError(loginError, e.message);
  }
});

logoutBtn.addEventListener("click", () => {
  localStorage.removeItem(TOKEN_KEY);
  location.reload();
});

function showPanel() {
  loginSection.classList.add("hidden");
  panelSection.classList.remove("hidden");
  logoutBtn.style.display = "";
  loadLibrary();
  loadSettings();
}

function init() {
  fetch("/api/health")
    .then((r) => r.json())
    .then((d) => (appName.textContent = d.app || ""))
    .catch(() => {});
  if (auth()) {
    showPanel();
  } else {
    loginSection.classList.remove("hidden");
  }
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.add("hidden"));
    tab.classList.add("active");
    document.getElementById("tab-" + tab.dataset.tab).classList.remove("hidden");
    if (tab.dataset.tab === "library") loadLibrary();
    if (tab.dataset.tab === "papers") loadPapers();
    if (tab.dataset.tab === "insights") loadInsights();
    if (tab.dataset.tab === "syllabus") loadSyllabi();
    if (tab.dataset.tab === "settings") loadSettings();
  });
});

dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("dragging");
});

dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragging"));

dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragging");
  if (e.dataTransfer.files.length) upload(e.dataTransfer.files[0]);
});

pickFile.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
  if (fileInput.files.length) upload(fileInput.files[0]);
});

async function upload(file) {
  clearError(uploadError);
  dropzone.classList.add("hidden");
  uploadProgress.classList.remove("hidden");
  progressLabel.textContent = "Reading your file…";
  const form = new FormData();
  form.append("file", file);
  const cls = document.getElementById("book-class").value.trim();
  const classes = document.getElementById("book-classes").value.trim();
  const sectors = document.getElementById("book-sectors").value.trim();
  if (cls) form.append("class_name", cls);
  if (classes) form.append("classes", classes);
  if (sectors) form.append("sectors", sectors);
  try {
    const data = await api("/api/admin/books", { method: "POST", body: form });
    pollStatus(data.id, file.name);
  } catch (e) {
    dropzone.classList.remove("hidden");
    uploadProgress.classList.add("hidden");
    showError(uploadError, e.message);
  }
}

function pollStatus(bookId, name) {
  clearTimeout(pollingTimer);
  const check = async () => {
    try {
      const books = await api("/api/admin/books");
      const book = books.find((b) => b.id === bookId);
      if (!book) {
        finishUpload();
        return;
      }
      if (book.status === "ready") {
        progressLabel.textContent = "Ready! Indexed " + book.chunk_count + " parts.";
        setTimeout(finishUpload, 1500);
      } else if (book.status === "error") {
        showError(uploadError, "Could not process \"" + name + "\": " + book.error);
        finishUpload();
      } else {
        progressLabel.textContent = "Processing… please wait.";
        pollingTimer = setTimeout(check, 1500);
      }
    } catch (e) {
      pollingTimer = setTimeout(check, 2000);
    }
  };
  check();
}

function finishUpload() {
  clearTimeout(pollingTimer);
  uploadProgress.classList.add("hidden");
  dropzone.classList.remove("hidden");
  fileInput.value = "";
  loadLibrary();
}

let allBooks = [];

async function loadLibrary() {
  try {
    allBooks = await api("/api/admin/books");
    populateLibFilters();
    renderLibrary();
  } catch (e) {
    libraryList.innerHTML = `<p class="hint">${escapeHtml(e.message)}</p>`;
  }
}

function populateLibFilters() {
  const classes = [...new Set(allBooks.flatMap((b) => b.classes || []))].sort();
  const sectors = [...new Set(allBooks.flatMap((b) => b.sectors || []))].sort();
  fillSelect(document.getElementById("lib-class-filter"), classes, "All classes");
  fillSelect(document.getElementById("lib-sector-filter"), sectors, "All subjects");
}

function fillSelect(sel, values, allLabel) {
  const current = sel.value;
  sel.innerHTML = `<option value="">${escapeHtml(allLabel)}</option>`;
  for (const v of values) {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = v;
    sel.appendChild(opt);
  }
  sel.value = values.includes(current) ? current : "";
}

function renderLibrary() {
  const q = document.getElementById("lib-search").value.trim().toLowerCase();
  const cf = document.getElementById("lib-class-filter").value;
  const sf = document.getElementById("lib-sector-filter").value;
  const st = document.getElementById("lib-status-filter").value;
  const books = allBooks.filter((b) => {
    if (st && b.status !== st) return false;
    if (cf && !(b.classes || []).includes(cf)) return false;
    if (sf && !(b.sectors || []).includes(sf)) return false;
    if (q && !b.name.toLowerCase().includes(q)) return false;
    return true;
  });
  if (!allBooks.length) {
    libraryList.innerHTML = '<p class="hint">No textbooks yet. Add one in the "Add Textbook" tab.</p>';
    return;
  }
  if (!books.length) {
    libraryList.innerHTML = '<p class="hint">No books match those filters.</p>';
    return;
  }
  libraryList.innerHTML = "";
  for (const book of books) {
    const card = bookCard(book);
    stagger(card, libraryList.children.length);
    libraryList.appendChild(card);
  }
}

const CARD_GRADS = [
  "linear-gradient(135deg,#7c6bff,#b388ff)",
  "linear-gradient(135deg,#22d3ee,#0ea5e9)",
  "linear-gradient(135deg,#34d399,#0d9488)",
  "linear-gradient(135deg,#f59e0b,#f97316)",
  "linear-gradient(135deg,#ec4899,#8b5cf6)",
  "linear-gradient(135deg,#a3e635,#16a34a)",
];

function cardAccent(book) {
  const seed = [...(book.sectors || []), ...(book.classes || []), book.name || "x"].join("");
  let h = 0;
  for (const ch of seed) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return CARD_GRADS[h % CARD_GRADS.length];
}

function bookIcon(book) {
  const s = (book.sectors || []).join(" ").toLowerCase();
  const n = (book.name || "").toLowerCase();
  if (/bio|জীব|জীববিজ্ঞান/.test(s) || /জীববিজ্ঞান|biology/.test(n)) return "🧬";
  if (/phys|পদার্থ/.test(s) || /পদার্থবিজ্ঞান|physics/.test(n)) return "⚡";
  if (/chem|রসায়ন/.test(s) || /রসায়ন|chemistry/.test(n)) return "🧪";
  if (/math|গণিত/.test(s) || /গণিত|math/.test(n)) return "📐";
  if (/english|ইংরেজি/.test(s) || /ইংরেজি/.test(n)) return "🔤";
  return "📖";
}

function statusLabel(book) {
  if (book.status === "ready")
    return `<span class="scope-pill ok"><span class="dot ok"></span> Ready · ${book.chunk_count || 0} parts</span>`;
  if (book.status === "error")
    return `<span class="scope-pill bad"><span class="dot bad"></span> Failed</span>`;
  return `<span class="scope-pill spin"><span class="spinner"></span> Processing…</span>`;
}

function bookCard(book) {
  const card = document.createElement("div");
  card.className = "book-card";
  const accent = cardAccent(book);
  card.style.setProperty("--accent", accent);
  const classes = book.classes && book.classes.length
    ? book.classes.map((c) => `<span class="scope-pill">${escapeHtml(c)}</span>`).join(" ")
    : `<span class="scope-pill all">All classes</span>`;
  const sectors = book.sectors && book.sectors.length
    ? book.sectors.map((s) => `<span class="scope-pill sector">${escapeHtml(s)}</span>`).join(" ")
    : `<span class="scope-pill all">All subjects</span>`;
  card.innerHTML =
    `<div class="book-card-top">` +
    `<div class="book-icon">${bookIcon(book)}</div>` +
    `<div class="book-title">${escapeHtml(book.name)}</div>` +
    `</div>` +
    `<div class="book-scopes">${classes}${sectors}</div>` +
    `<div class="book-status">${statusLabel(book)}</div>` +
    `<div class="book-meta">${escapeHtml(book.added_at || "")} · ${book.file_type || "file"}</div>` +
    `<div class="book-actions">` +
    `<button class="ghost small" data-act="edit">Edit</button>` +
    `<button class="danger small" data-act="del">Delete</button>` +
    `</div>`;
  card.querySelector('[data-act="edit"]').addEventListener("click", () => openEdit(book));
  card.querySelector('[data-act="del"]').addEventListener("click", () => removeBook(book.id, book.name));
  return card;
}

function stagger(el, i) {
  el.style.setProperty("--i", i);
}

async function removeBook(id, name) {
  if (!confirm('Delete "' + name + '" from the library?')) return;
  try {
    await api("/api/admin/books/" + id, { method: "DELETE" });
    loadLibrary();
  } catch (e) {
    alert(e.message);
  }
}

["lib-search", "lib-class-filter", "lib-sector-filter", "lib-status-filter"].forEach((id) => {
  document.getElementById(id).addEventListener("input", renderLibrary);
});

/* ---------------- edit book ---------------- */

let editingId = null;

function openEdit(book) {
  editingId = book.id;
  document.getElementById("edit-title").textContent = "Edit book";
  document.getElementById("edit-name").value = book.name || "";
  document.getElementById("edit-classes").value = (book.classes || []).join(", ");
  document.getElementById("edit-sectors").value = (book.sectors || []).join(", ");
  document.getElementById("edit-error").classList.add("hidden");
  document.getElementById("edit-modal").classList.remove("hidden");
}

document.getElementById("edit-cancel").addEventListener("click", () => {
  document.getElementById("edit-modal").classList.add("hidden");
});

document.getElementById("edit-save").addEventListener("click", async () => {
  clearError(document.getElementById("edit-error"));
  const form = new FormData();
  form.append("name", document.getElementById("edit-name").value.trim());
  form.append("classes", document.getElementById("edit-classes").value);
  form.append("sectors", document.getElementById("edit-sectors").value);
  try {
    await api("/api/admin/books/" + editingId, { method: "PATCH", body: form });
    document.getElementById("edit-modal").classList.add("hidden");
    loadLibrary();
  } catch (e) {
    showError(document.getElementById("edit-error"), e.message);
  }
});

/* ---------------- upload scope preview ---------------- */

function parseList(raw) {
  return raw
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
}

function updateScopePreview() {
  const el = document.getElementById("scope-preview");
  const classes = parseList(document.getElementById("book-classes").value);
  const sectors = parseList(document.getElementById("book-sectors").value);
  if (!classes.length && !sectors.length) {
    el.classList.add("hidden");
    return;
  }
  const pills = [];
  if (!classes.length) pills.push('<span class="scope-pill all">All classes</span>');
  else for (const c of classes) pills.push(`<span class="scope-pill">${escapeHtml(c)}</span>`);
  if (!sectors.length) pills.push('<span class="scope-pill all">All subjects</span>');
  else for (const s of sectors) pills.push(`<span class="scope-pill sector">${escapeHtml(s)}</span>`);
  el.innerHTML = pills.join(" ");
  el.classList.remove("hidden");
}

document.getElementById("book-classes").addEventListener("input", updateScopePreview);
document.getElementById("book-sectors").addEventListener("input", updateScopePreview);

paperDropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  paperDropzone.classList.add("dragging");
});

paperDropzone.addEventListener("dragleave", () => paperDropzone.classList.remove("dragging"));

paperDropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  paperDropzone.classList.remove("dragging");
  if (e.dataTransfer.files.length) uploadPaper(e.dataTransfer.files[0]);
});

pickPaper.addEventListener("click", () => paperInput.click());

paperInput.addEventListener("change", () => {
  if (paperInput.files.length) uploadPaper(paperInput.files[0]);
});

async function uploadPaper(file) {
  paperUploadError.classList.add("hidden");
  paperDropzone.classList.add("hidden");
  const form = new FormData();
  form.append("file", file);
  try {
    await api("/api/admin/papers", { method: "POST", body: form });
    paperDropzone.classList.remove("hidden");
    paperInput.value = "";
    loadPapers();
  } catch (e) {
    paperDropzone.classList.remove("hidden");
    showError(paperUploadError, e.message);
  }
}

async function loadPapers() {
  try {
    const papers = await api("/api/admin/papers");
    if (!papers.length) {
      papersList.innerHTML = '<p class="hint">No papers yet. Upload past exam papers so Exam Focus can predict topics.</p>';
      return;
    }
    papersList.innerHTML = "";
    for (const paper of papers) {
      const item = document.createElement("div");
      item.className = "book-row";
      const statusClass = paper.status === "ready" ? "ok" : paper.status === "error" ? "bad" : "";
      let matches = 0;
      try {
        matches = Object.keys(JSON.parse(paper.matches || "{}")).length;
      } catch (e) {
        /* ignore */
      }
      item.innerHTML =
        `<div class="book-info">` +
        `<div class="book-name">${escapeHtml(paper.name)}</div>` +
        `<div class="book-meta"><span class="badge ${statusClass}">${paper.status}</span>` +
        ` &middot; ${matches} topic match(es) &middot; ${escapeHtml(paper.added_at || "")}</div>` +
        `</div>` +
        `<button class="danger" data-id="${paper.id}">Delete</button>`;
      item.querySelector(".danger").addEventListener("click", () => removePaper(paper.id, paper.name));
      papersList.appendChild(item);
    }
  } catch (e) {
    papersList.innerHTML = `<p class="hint">${escapeHtml(e.message)}</p>`;
  }
}

async function removePaper(id, name) {
  if (!confirm('Delete paper "' + name + '"?')) return;
  try {
    await api("/api/admin/papers/" + id, { method: "DELETE" });
    loadPapers();
  } catch (e) {
    alert(e.message);
  }
}

async function loadSettings() {
  try {
    const s = await api("/api/admin/settings");
    document.getElementById("s-class").value = s.class_name || "";
    document.getElementById("s-chat-base").value = s.chat_base_url || "";
    document.getElementById("s-chat-key").value = s.chat_api_key || "";
    document.getElementById("s-chat-model").value = s.chat_model || "";
    document.getElementById("s-embed-base").value = s.embed_base_url || "";
    document.getElementById("s-embed-key").value = s.embed_api_key || "";
    document.getElementById("s-embed-model").value = s.embed_model || "";
  } catch (e) {
    showError(settingsError, e.message);
  }
}

document.getElementById("save-settings").addEventListener("click", async () => {
  clearError(settingsError);
  settingsOk.classList.add("hidden");
  const payload = {};
  const mapping = {
    "s-class": "class_name",
    "s-chat-base": "chat_base_url",
    "s-chat-key": "chat_api_key",
    "s-chat-model": "chat_model",
    "s-embed-base": "embed_base_url",
    "s-embed-key": "embed_api_key",
    "s-embed-model": "embed_model",
  };
  for (const [elId, key] of Object.entries(mapping)) {
    payload[key] = document.getElementById(elId).value.trim();
  }
  const newPass = document.getElementById("s-admin-pass").value.trim();
  if (newPass) payload.admin_password = newPass;
  try {
    await api("/api/admin/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (newPass) setAuth(newPass);
    settingsOk.textContent = "Settings saved.";
    settingsOk.classList.remove("hidden");
  } catch (e) {
    showError(settingsError, e.message);
  }
});

/* ---------------- insights dashboard ---------------- */

const insightsError = document.getElementById("insights-error");

async function loadInsights() {
  clearError(insightsError);
  try {
    const data = await api("/api/admin/insights");
    renderSummary(data.summary || {});
    renderPopularTopics(data.popular_topics || []);
    renderActivity(data.activity || []);
    renderSectorBreakdown(data.sector_breakdown || []);
    renderLeaderboard(data.leaderboard || []);
    renderLowPerformers(data.low_performers || []);
  } catch (e) {
    showError(insightsError, e.message);
  }
}

function renderSummary(s) {
  const cards = [
    { label: "Students", value: s.students || 0, icon: "👥" },
    { label: "Textbooks", value: s.books || 0, icon: "📚" },
    { label: "Questions (7d)", value: s.questions_7d || 0, icon: "💬" },
    { label: "Quizzes (7d)", value: s.quizzes_7d || 0, icon: "📝" },
    { label: "Avg quiz score", value: (s.avg_score_7d || 0) + "%", icon: "🎯" },
  ];
  const el = document.getElementById("insight-summary");
  el.innerHTML = "";
  for (const c of cards) {
    const card = document.createElement("div");
    card.className = "insight-card";
    card.innerHTML =
      `<div class="insight-icon">${c.icon}</div>` +
      `<div class="insight-value">${escapeHtml(String(c.value))}</div>` +
      `<div class="insight-label">${escapeHtml(c.label)}</div>`;
    el.appendChild(card);
  }
}

function renderPopularTopics(topics) {
  const el = document.getElementById("popular-topics");
  if (!topics.length) {
    el.innerHTML = '<p class="hint">No student questions yet this week. Ask your class to use the app and the struggle topics will appear here.</p>';
    return;
  }
  el.innerHTML = "";
  const max = Math.max(...topics.map((t) => t.count), 1);
  for (const t of topics) {
    const row = document.createElement("div");
    row.className = "topic-bar-row";
    const top = document.createElement("div");
    top.className = "topic-bar-top";
    const word = document.createElement("span");
    word.className = "topic-word";
    word.textContent = t.keyword;
    const meta = document.createElement("span");
    meta.className = "topic-meta";
    meta.textContent = `${t.count} question(s) · ${t.students_pct}% of students`;
    top.appendChild(word);
    top.appendChild(meta);
    const bar = document.createElement("div");
    bar.className = "topic-bar";
    const fill = document.createElement("div");
    fill.className = "topic-bar-fill";
    fill.style.width = Math.round((t.count / max) * 100) + "%";
    bar.appendChild(fill);
    row.appendChild(top);
    row.appendChild(bar);
    el.appendChild(row);
  }
}

function renderActivity(activity) {
  const el = document.getElementById("activity-chart");
  if (!activity.length) {
    el.innerHTML = '<p class="hint">No data yet.</p>';
    return;
  }
  el.innerHTML = "";
  const chart = document.createElement("div");
  chart.className = "bar-chart";
  const max = Math.max(...activity.map((a) => a.count), 1);
  for (const a of activity) {
    const col = document.createElement("div");
    col.className = "bar-col";
    const fill = document.createElement("div");
    fill.className = "bar-fill";
    fill.style.height = Math.max(4, Math.round((a.count / max) * 100)) + "%";
    fill.title = `${a.date}: ${a.count} question(s)`;
    const label = document.createElement("div");
    label.className = "bar-label";
    label.textContent = a.date.slice(5);
    col.appendChild(fill);
    col.appendChild(label);
    chart.appendChild(col);
  }
  el.appendChild(chart);
}

function renderSectorBreakdown(rows) {
  const el = document.getElementById("sector-breakdown");
  if (!rows.length) {
    el.innerHTML = '<p class="hint">No data yet.</p>';
    return;
  }
  el.innerHTML = "";
  for (const r of rows) {
    const pill = document.createElement("span");
    pill.className = "scope-pill sector";
    pill.textContent = `${r.sector}: ${r.count}`;
    el.appendChild(pill);
  }
}

function renderLeaderboard(rows) {
  const el = document.getElementById("leaderboard");
  if (!rows.length) {
    el.innerHTML = '<p class="hint">No activity yet.</p>';
    return;
  }
  el.innerHTML = "";
  for (let i = 0; i < rows.length; i++) {
    const r = rows[i];
    const item = document.createElement("div");
    item.className = "rank-row";
    const medal = i === 0 ? "🥇" : i === 1 ? "🥈" : i === 2 ? "🥉" : `${i + 1}.`;
    item.innerHTML =
      `<span class="rank-medal">${medal}</span>` +
      `<span class="rank-name">${escapeHtml(r.name)}</span>` +
      `<span class="rank-score">${r.questions} Qs · ${r.quizzes} quizzes</span>`;
    el.appendChild(item);
  }
}

function renderLowPerformers(rows) {
  const el = document.getElementById("low-performers");
  if (!rows.length) {
    el.innerHTML = '<p class="hint">No one struggling — everyone averaging 40% or better. 🎉</p>';
    return;
  }
  el.innerHTML = "";
  for (const r of rows) {
    const item = document.createElement("div");
    item.className = "rank-row warn";
    item.innerHTML =
      `<span class="rank-medal">⚠️</span>` +
      `<span class="rank-name">${escapeHtml(r.name)}</span>` +
      `<span class="rank-score">avg ${r.avg}% · ${r.quizzes} quiz(es)</span>`;
    el.appendChild(item);
  }
}

/* ---------------- syllabus gap check ---------------- */

const syllabusDropzone = document.getElementById("syllabus-dropzone");
const syllabusInput = document.getElementById("syllabus-input");
const pickSyllabus = document.getElementById("pick-syllabus");
const syllabusUploadError = document.getElementById("syllabus-upload-error");
const syllabiList = document.getElementById("syllabi-list");

syllabusDropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  syllabusDropzone.classList.add("dragging");
});

syllabusDropzone.addEventListener("dragleave", () => syllabusDropzone.classList.remove("dragging"));

syllabusDropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  syllabusDropzone.classList.remove("dragging");
  if (e.dataTransfer.files.length) uploadSyllabus(e.dataTransfer.files[0]);
});

pickSyllabus.addEventListener("click", () => syllabusInput.click());

syllabusInput.addEventListener("change", () => {
  if (syllabusInput.files.length) uploadSyllabus(syllabusInput.files[0]);
});

async function uploadSyllabus(file) {
  clearError(syllabusUploadError);
  syllabusDropzone.classList.add("hidden");
  const form = new FormData();
  form.append("file", file);
  try {
    await api("/api/admin/syllabi", { method: "POST", body: form });
    syllabusDropzone.classList.remove("hidden");
    syllabusInput.value = "";
    loadSyllabi();
  } catch (e) {
    syllabusDropzone.classList.remove("hidden");
    showError(syllabusUploadError, e.message);
  }
}

async function loadSyllabi() {
  try {
    const items = await api("/api/admin/syllabi");
    if (!items.length) {
      syllabiList.innerHTML = '<p class="hint">No syllabus uploaded yet. Upload the official syllabus to find missing topics.</p>';
      return;
    }
    syllabiList.innerHTML = "";
    for (const item of items) {
      const row = document.createElement("div");
      row.className = "book-row";
      const info = document.createElement("div");
      info.className = "book-info";
      const name = document.createElement("div");
      name.className = "book-name";
      name.textContent = item.name;
      const meta = document.createElement("div");
      meta.className = "book-meta";
      if (item.status === "ready") {
        let stats = "";
        try {
          const report = JSON.parse(item.report || "{}");
          const s = report.stats || {};
          stats = ` · <span class="badge ok">${s.covered || 0} covered</span> <span class="badge">${s.partial || 0} partial</span> <span class="badge bad">${s.missing || 0} missing</span>`;
        } catch (e) {
          /* ignore */
        }
        meta.innerHTML = `<span class="badge ok">Ready</span> · ${escapeHtml(item.added_at || "")}${stats}`;
      } else if (item.status === "error") {
        meta.innerHTML = `<span class="badge bad">Failed</span> · ${escapeHtml(item.error || "")}`;
      } else {
        meta.innerHTML = `<span class="badge">Checking…</span> · ${escapeHtml(item.added_at || "")}`;
      }
      info.appendChild(name);
      info.appendChild(meta);
      const actions = document.createElement("div");
      actions.className = "book-actions-row";
      if (item.status === "ready") {
        const btn = document.createElement("button");
        btn.className = "ghost";
        btn.textContent = "View report";
        btn.addEventListener("click", () => openReport(item));
        actions.appendChild(btn);
      }
      const del = document.createElement("button");
      del.className = "danger";
      del.textContent = "Delete";
      del.addEventListener("click", () => removeSyllabus(item.id, item.name));
      actions.appendChild(del);
      row.appendChild(info);
      row.appendChild(actions);
      syllabiList.appendChild(row);
    }
  } catch (e) {
    syllabiList.innerHTML = `<p class="hint">${escapeHtml(e.message)}</p>`;
  }
}

async function removeSyllabus(id, name) {
  if (!confirm('Delete syllabus "' + name + '"?')) return;
  try {
    await api("/api/admin/syllabi/" + id, { method: "DELETE" });
    loadSyllabi();
  } catch (e) {
    alert(e.message);
  }
}

function openReport(item) {
  const body = document.getElementById("report-body");
  body.innerHTML = "";
  let report = null;
  try {
    report = JSON.parse(item.report || "null");
  } catch (e) {
    report = null;
  }
  if (!report || !report.topics || !report.topics.length) {
    body.innerHTML = '<p class="hint">No report available.</p>';
  } else {
    for (const t of report.topics) {
      const block = document.createElement("div");
      block.className = "gap-item " + (t.status || "");
      const status = document.createElement("span");
      status.className = "badge " + (t.status === "missing" ? "bad" : t.status === "partial" ? "" : "ok");
      status.textContent = t.status || "";
      const title = document.createElement("div");
      title.className = "gap-title";
      title.textContent = t.topic || "";
      const note = document.createElement("div");
      note.className = "gap-note";
      note.textContent = t.note || "";
      block.appendChild(title);
      block.appendChild(status);
      if (t.note) block.appendChild(note);
      body.appendChild(block);
    }
  }
  document.getElementById("report-title").textContent = "Gap report: " + item.name;
  document.getElementById("report-modal").classList.remove("hidden");
}

document.getElementById("report-close").addEventListener("click", () => {
  document.getElementById("report-modal").classList.add("hidden");
});

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

init();
