/* Chat UI for the Vectra KB assistant.
   Thin by design: it renders what /api/ask returns; no AI logic here. */

"use strict";

const SAMPLE_QUESTIONS = [
  "My account got locked. How long until it unlocks by itself?",
  "What VPN server address should I use when working from home?",
  "What is the resolution target for a P2 ticket?",
  "How do I get a parking pass for the Gurugram office?",
  "ZenTunnel shows error ZT-401 on my laptop. What do I do?",
  "I clicked a suspicious link and then entered my password on an unknown page. What should I do?",
  "My laptop is really slow, what should I do to speed it up?",
  "Hi, I'm Anand Sharma (anand.sharma@vectralogistics.example, +91 9876543210). Company mail doesn't show up in my iPhone's built-in Mail app. How do I fix it?",
];

const HAS_PII = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|(?:\+91[\s-]?)?[6-9]\d{9}/;
const esc = (s) => s.replace(/[&<>"']/g, (c) =>
  ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
// Answers contain tiny markdown (bold, code). Escape first, then format - safe.
const md = (s) => esc(s)
  .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
  .replace(/`([^`]+)`/g, "<code>$1</code>");
const $ = (id) => document.getElementById(id);

const chat = $("chat");
const form = $("ask-form");
const input = $("q");
const askBtn = $("ask-btn");

function addChips() {
  const wrap = $("samples");
  for (const q of SAMPLE_QUESTIONS) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip";
    b.textContent = q.length > 46 ? q.slice(0, 46) + "..." : q;
    b.title = q;
    b.addEventListener("click", () => ask(q));
    wrap.appendChild(b);
  }
}

function bubble(q, maskedQ) {
  chat.querySelector(".empty")?.remove();
  const turn = document.createElement("div");
  turn.className = "turn";
  turn.innerHTML = `
    <div class="q-bubble">${esc(q)}</div>
    ${maskedQ && maskedQ !== q
      ? `<div class="pii-notice"><strong>PII guardrail:</strong> string actually sent to
         OpenAI: <code>${esc(maskedQ)}</code></div>`
      : ""}
    <div class="a-bubble"><div class="loading">Retrieving from pgvector and grounding gpt-4o-mini...</div></div>`;
  chat.appendChild(turn);
  window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
  return turn.querySelector(".a-bubble");
}

function simTrace(retrieved) {
  const max = Math.max(...retrieved.map((r) => r.similarity), 0.001);
  const rows = retrieved.map(
    (r) => `
      <div class="sim-row ${r.similarity < 0.3 ? "low" : ""}" title="${esc(r.section || "")}">
        <span class="sim-doc">${esc(r.doc_id)}</span>
        <span class="sim-track"><span class="sim-fill" style="width:${Math.max(3, (r.similarity / max) * 100)}%"></span></span>
        <span class="sim-val">${r.similarity.toFixed(2)}</span>
      </div>`
  ).join("");
  return `
    <details class="gold"><summary>Retrieval trace &amp; safety checks</summary>
      <div class="trace">${rows}</div>
      <div id="warns" class="warns"></div>
    </details>`;
}

function render(box, data) {
  const abstained = data.abstained;
  const cites = data.citations.length
    ? data.citations.map((c) => `<span class="cite-chip">${esc(c)}</span>`).join(" ")
    : `<span class="cite-chip none">no citations</span>`;

  const warnsHtml = data.warnings?.length
    ? `<div class="warns"><ul>${data.warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul></div>`
    : `<li>No guardrail notes - clean pass.</li>`;

  box.innerHTML = `
    <div class="a-head">
      <span class="badge ${abstained ? "stop" : "ok"}">${abstained ? "ABSTAINED" : "ANSWERED"}</span>
      ${cites}
      <span class="a-meta">${data.latency_ms} ms &middot; pgvector top-4 &middot; gpt-4o-mini &middot; temp 0</span>
    </div>
    <div class="a-body">${md(data.answer)}</div>
    ${abstained
      ? `<div class="a-abstain">The knowledge base does not cover this, so nothing was invented.
         Suggestion: raise a ticket - the service desk will take it from there.</div>`
      : ""}
    ${HAS_PII.test(data.question) && data.masked_question !== data.question
      ? `<div class="pii-notice"><strong>PII masked out before any OpenAI call / log:</strong>
         <code>${esc(data.masked_question)}</code></div>`
      : ""}
    ${simTrace(data.retrieved)}
    <details class="gold"><summary>Guardrail warnings</summary><div class="warns">${warnsHtml}</div></details>`;

  window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
}

async function ask(q) {
  if (!q || askBtn.disabled) return;
  askBtn.disabled = true;
  input.value = q;
  const box = bubble(q, null);
  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    box.closest(".turn").querySelector(".q-bubble").textContent = q;
    // Recompute bubble with the mask notice once we have the masked text.
    render(box, data);
  } catch (err) {
    box.querySelector(".loading").textContent =
      "Request failed - is `uvicorn src.api:app` running? (" + err.message + ")";
  } finally {
    askBtn.disabled = false;
    if (!/^\?q=/.test(location.search)) input.value = "";
    input.focus();
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  ask(input.value.trim());
});

addChips();

// ?q= auto-asks on load: used for tests and for headless screenshots.
const urlQ = new URLSearchParams(location.search).get("q");
if (urlQ) {
  ask(urlQ);
} else {
  input.focus();
}
