"use strict";

let MODE = "urls";
let ROWS = [];
let sortKey = "matched_seeds";
let sortDir = -1;

const $ = (id) => document.getElementById(id);

// ---- theme toggle (ดำ-ส้ม / ขาว-ส้ม) ----
const themeBtn = $("themeBtn");
const savedTheme = localStorage.getItem("scTheme") || "dark";
setTheme(savedTheme);
themeBtn.addEventListener("click", () =>
  setTheme(document.body.dataset.theme === "dark" ? "light" : "dark"));
function setTheme(t) {
  document.body.dataset.theme = t;
  themeBtn.textContent = t === "dark" ? "☀️ ขาว-ส้ม" : "🌙 ดำ-ส้ม";
  localStorage.setItem("scTheme", t);
}

// ---- seed mode segmented control ----
document.querySelectorAll("#seedMode button").forEach((b) => {
  b.addEventListener("click", () => {
    document.querySelectorAll("#seedMode button").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    MODE = b.dataset.mode;
    $("urlsBox").classList.toggle("hidden", MODE === "likes");
    $("profileBox").classList.toggle("hidden", MODE === "urls");
  });
});

// ---- run ----
$("runBtn").addEventListener("click", run);

async function run() {
  const btn = $("runBtn");
  btn.disabled = true;
  $("status").textContent = "กำลังทำงาน… (related ของแต่ละ seed)";
  const payload = {
    seed_mode: MODE,
    seed_urls: $("seed_urls").value,
    profile_url: $("profile_url").value,
    max_seeds: $("max_seeds").value,
    target: $("target").value,
    related_per_seed: $("related_per_seed").value,
    duration_min: $("duration_min").value,
    duration_max: $("duration_max").value,
    dedupe_enabled: $("dedupe_enabled").checked,
    demo_mode: $("demo_mode").checked,
  };
  try {
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    $("log").textContent = (data.logs || []).join("\n");
    if (!data.ok) {
      $("status").innerHTML = "❌ " + (data.error || "error");
      return;
    }
    ROWS = data.results || [];
    sortKey = "matched_seeds"; sortDir = -1;
    render();
    const demo = data.demo ? '<span class="badge">DEMO</span>' : "";
    $("status").innerHTML = `✅ ได้ ${data.count} เพลง ` + demo;
    $("dlBtn").classList.toggle("hidden", ROWS.length === 0);
  } catch (e) {
    $("status").textContent = "❌ " + e;
  } finally {
    btn.disabled = false;
  }
}

// ---- sorting ----
document.querySelectorAll("#tbl th[data-k]").forEach((th) => {
  th.addEventListener("click", () => {
    const k = th.dataset.k;
    if (sortKey === k) sortDir *= -1;
    else { sortKey = k; sortDir = (k === "title" || k === "artist") ? 1 : -1; }
    render();
  });
});

$("filterText").addEventListener("input", render);

function render() {
  const q = $("filterText").value.trim().toLowerCase();
  let rows = ROWS.filter((r) =>
    !q || (r.title || "").toLowerCase().includes(q) || (r.artist || "").toLowerCase().includes(q));

  rows.sort((a, b) => {
    const x = a[sortKey], y = b[sortKey];
    if (typeof x === "number" && typeof y === "number") return (x - y) * sortDir;
    return String(x).localeCompare(String(y)) * sortDir;
  });

  const maxMs = Math.max(1, ...ROWS.map((r) => r.matched_seeds || 0));
  const tb = $("tbl").querySelector("tbody");
  tb.innerHTML = rows.map((r, i) => {
    const w = Math.round(((r.matched_seeds || 0) / maxMs) * 60);
    return `<tr>
      <td>${i + 1}</td>
      <td><span class="ms">${r.matched_seeds}</span><span class="bar" style="width:${w}px"></span></td>
      <td>${esc(r.title)}</td>
      <td>${esc(r.artist)}</td>
      <td>${esc(r.genre)}</td>
      <td>${fmt(r.plays)}</td>
      <td>${fmt(r.likes)}</td>
      <td>${r.duration_min}</td>
      <td><a href="${r.url}" target="_blank" rel="noopener">เปิด ↗</a></td>
    </tr>`;
  }).join("");

  $("tbl").classList.toggle("hidden", rows.length === 0);
  $("empty").classList.toggle("hidden", rows.length !== 0);
  document.querySelectorAll("#tbl th[data-k]").forEach((th) => {
    const base = th.dataset.k === "matched_seeds" ? "matched_seeds" : th.textContent.replace(/[ ▲▼]+$/,"");
    th.textContent = th.dataset.k + (th.dataset.k === sortKey ? (sortDir < 0 ? " ▼" : " ▲") : "");
    if (th.dataset.k === "rank") th.textContent = "#";
  });
}

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmt = (n) => (n || 0).toLocaleString();
