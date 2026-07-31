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
  if (cls) form.append("class_name", cls);
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

async function loadLibrary() {
  try {
    const books = await api("/api/admin/books");
    if (!books.length) {
      libraryList.innerHTML = '<p class="hint">No textbooks yet. Add one in the "Add Textbook" tab.</p>';
      return;
    }
    libraryList.innerHTML = "";
    for (const book of books) {
      const item = document.createElement("div");
      item.className = "book-row";
      const statusClass = book.status === "ready" ? "ok" : book.status === "error" ? "bad" : "";
      item.innerHTML =
        `<div class="book-info">` +
        `<div class="book-name">${escapeHtml(book.name)}</div>` +
        `<div class="book-meta"><span class="badge ${statusClass}">${book.status}</span>` +
        ` &middot; ${escapeHtml(book.class_name || "")}` +
        ` &middot; ${book.chunk_count || 0} parts &middot; ${escapeHtml(book.added_at || "")}</div>` +
        `</div>` +
        `<button class="danger" data-id="${book.id}">Delete</button>`;
      item.querySelector(".danger").addEventListener("click", () => removeBook(book.id, book.name));
      libraryList.appendChild(item);
    }
  } catch (e) {
    libraryList.innerHTML = `<p class="hint">${escapeHtml(e.message)}</p>`;
  }
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

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

init();
