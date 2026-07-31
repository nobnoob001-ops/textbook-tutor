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

function showError(msg) {
  errorBox.textContent = msg;
  errorBox.classList.remove("hidden");
}

function clearError() {
  errorBox.classList.add("hidden");
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
    item.innerHTML =
      `<div class="source-book">📖 ${escapeHtml(s.book)}</div>` +
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
    showError("Type a question or attach a file first.");
    return;
  }
  clearError();
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
    showError(err.message);
  } finally {
    sendBtn.disabled = false;
    question.value = "";
    attachedFile = null;
    attach.value = "";
    fileChip.classList.add("hidden");
  }
}

sendBtn.addEventListener("click", send);

fetchClassName();
