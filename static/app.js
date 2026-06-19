"use strict";

let MODE = "urls";
let ROWS = [];
let sortKey = "matched_seeds";
let sortDir = -1;
let HARMONIC = false;     // โหมดเรียงลำดับ mix ต่อกัน
let CAM_FILTER = "";      // กรองเฉพาะ key ที่เข้ากับ Camelot นี้

const $ = (id) => document.getElementById(id);

// ---- Camelot harmonic logic (ตรงกับ scfinder/camelot.py) ----
function compatibleCamelot(code) {
  const m = /^(\d{1,2})([AB])$/.exec(code || "");
  if (!m) return [];
  const n = +m[1], l = m[2];
  if (n < 1 || n > 12) return [];
  const other = l === "A" ? "B" : "A";
  const up = (n % 12) + 1, down = ((n - 2 + 12) % 12) + 1;
  return [`${n}${l}`, `${n}${other}`, `${up}${l}`, `${down}${l}`];
}
function isCompatible(a, b) { return !!a && compatibleCamelot(a).includes(b); }

// เรียงแบบ greedy nearest-harmonic (พอร์ตจาก mixset.py) ไว้ดูลำดับ mix
function harmonicOrder(rows) {
  const pool = rows.slice();
  if (!pool.length) return pool;
  const gap = (a, b) => (!a.bpm || !b.bpm ? 999 : Math.abs(a.bpm - b.bpm));
  const out = [pool.shift()];
  while (pool.length) {
    const cur = out[out.length - 1];
    const compat = new Set(cur.camelot ? compatibleCamelot(cur.camelot) : []);
    let cand = pool.filter((t) => t.camelot && compat.has(t.camelot));
    if (!cand.length) cand = pool;
    let best = cand[0];
    for (const t of cand) if (gap(cur, t) < gap(cur, best)) best = t;
    pool.splice(pool.indexOf(best), 1);
    out.push(best);
  }
  return out;
}

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
    bpm_min: $("bpm_min").value,
    bpm_max: $("bpm_max").value,
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
    HARMONIC = false; CAM_FILTER = "";
    render();
    const demo = data.demo ? '<span class="badge">DEMO</span>' : "";
    $("status").innerHTML = `✅ ได้ ${data.count} เพลง ` + demo;
    const has = ROWS.length > 0;
    ["dlBtn", "dlMik", "dlM3u", "harmonicBtn", "lineBtn", "swipeBtn", "rerankBtn"].forEach((id) =>
      $(id).classList.toggle("hidden", !has));
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

$("harmonicBtn").addEventListener("click", () => {
  HARMONIC = !HARMONIC;
  $("harmonicBtn").classList.toggle("on", HARMONIC);
  render();
});

$("camChip").addEventListener("click", () => { CAM_FILTER = ""; render(); });

$("lineBtn").addEventListener("click", async () => {
  $("status").textContent = "กำลังส่งเข้า LINE…";
  try {
    const res = await fetch("/api/notify", { method: "POST" });
    const d = await res.json();
    $("status").innerHTML = (d.ok ? "✅ ส่งเข้า LINE แล้ว " : "❌ ") + esc(d.info || "");
  } catch (e) {
    $("status").textContent = "❌ " + e;
  }
});

function render() {
  const q = $("filterText").value.trim().toLowerCase();
  let rows = ROWS.filter((r) =>
    !q || (r.title || "").toLowerCase().includes(q) || (r.artist || "").toLowerCase().includes(q));

  // กรอง harmonic ตาม Camelot ที่คลิก
  if (CAM_FILTER) rows = rows.filter((r) => isCompatible(CAM_FILTER, r.camelot));

  if (HARMONIC) {
    rows = harmonicOrder(rows);          // ลำดับ mix ต่อกัน
  } else {
    rows.sort((a, b) => {
      const x = a[sortKey], y = b[sortKey];
      if (typeof x === "number" && typeof y === "number") return (x - y) * sortDir;
      return String(x).localeCompare(String(y)) * sortDir;
    });
  }

  // chip แสดงตัวกรอง Camelot
  const chip = $("camChip");
  chip.classList.toggle("hidden", !CAM_FILTER);
  if (CAM_FILTER) chip.textContent = `🎚 key เข้ากับ ${CAM_FILTER} ✕`;

  const maxMs = Math.max(1, ...ROWS.map((r) => r.matched_seeds || 0));
  const tb = $("tbl").querySelector("tbody");
  tb.innerHTML = rows.map((r, i) => {
    const w = Math.round(((r.matched_seeds || 0) / maxMs) * 60);
    const cam = r.camelot
      ? `<span class="cam" data-cam="${r.camelot}" title="คลิกเพื่อกรองเพลงที่ mix เข้ากัน">${r.camelot}</span>`
      : `<span class="cam none">–</span>`;
    const key = r.key ? ` <small>${esc(r.key)}</small>` : "";
    return `<tr>
      <td>${i + 1}</td>
      <td><span class="ms">${r.matched_seeds}</span><span class="bar" style="width:${w}px"></span></td>
      <td>${esc(r.title)}</td>
      <td>${esc(r.artist)}</td>
      <td>${r.bpm ? r.bpm : "–"}</td>
      <td>${cam}${key}</td>
      <td>${esc(r.genre)}</td>
      <td>${fmt(r.plays)}</td>
      <td>${fmt(r.likes)}</td>
      <td>${r.duration_min}</td>
      <td><a href="${r.url}" target="_blank" rel="noopener">เปิด ↗</a></td>
    </tr>`;
  }).join("");

  // คลิก Camelot -> กรองเพลงที่ mix เข้ากัน
  tb.querySelectorAll(".cam[data-cam]").forEach((el) =>
    el.addEventListener("click", () => { CAM_FILTER = el.dataset.cam; HARMONIC = false; render(); }));

  $("tbl").classList.toggle("hidden", rows.length === 0);
  $("empty").classList.toggle("hidden", rows.length !== 0);
  document.querySelectorAll("#tbl th[data-k]").forEach((th) => {
    th.textContent = th.dataset.k === "rank" ? "#"
      : th.dataset.k + (!HARMONIC && th.dataset.k === sortKey ? (sortDir < 0 ? " ▼" : " ▲") : "");
  });
}

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmt = (n) => (n || 0).toLocaleString();

// ================= Phase 4: Tinder-style swipe =================
let DECK = [];
let DECK_I = 0;
let SW_LIKE = 0, SW_NOPE = 0;
let RATED = new Set();

const ov = $("swipeOverlay");

$("swipeBtn").addEventListener("click", openSwipe);
$("rerankBtn").addEventListener("click", rerank);
$("swipeClose").addEventListener("click", closeSwipe);
$("btnLike").addEventListener("click", () => swipe(true));
$("btnNope").addEventListener("click", () => swipe(false));
document.addEventListener("keydown", (e) => {
  if (ov.classList.contains("hidden")) return;
  if (e.key === "ArrowRight") swipe(true);
  else if (e.key === "ArrowLeft") swipe(false);
  else if (e.key === "Escape") closeSwipe();
});

async function openSwipe() {
  // ข้ามเพลงที่เคยปัดแล้ว
  try {
    const p = await (await fetch("/api/profile")).json();
    RATED = new Set(p.rated || []);
    renderTaste(p);
  } catch (_) { RATED = new Set(); }
  DECK = ROWS.filter((r) => !RATED.has(r.track_id));
  DECK_I = 0; SW_LIKE = 0; SW_NOPE = 0;
  ov.classList.remove("hidden");
  $("swipeDone").classList.toggle("hidden", DECK.length > 0);
  $("swipeCard").classList.toggle("hidden", DECK.length === 0);
  showCard();
}

function closeSwipe() {
  ov.classList.add("hidden");
  $("swPlayer").src = "";          // หยุดเสียง
}

function showCard() {
  $("swLike").textContent = SW_LIKE;
  $("swNope").textContent = SW_NOPE;
  $("swipeProg").textContent = `${Math.min(DECK_I + 1, DECK.length)}/${DECK.length}`;
  if (DECK_I >= DECK.length) {
    $("swipeCard").classList.add("hidden");
    $("swipeDone").classList.remove("hidden");
    $("swPlayer").src = "";
    return;
  }
  const r = DECK[DECK_I];
  $("swTitle").textContent = r.title || "(ไม่มีชื่อ)";
  $("swArtist").textContent = r.artist || "";
  const tags = [];
  if (r.camelot) tags.push(`<span class="cam">${r.camelot}</span>`);
  if (r.bpm) tags.push(`<span class="t">${r.bpm} bpm</span>`);
  if (r.genre) tags.push(`<span class="t">${esc(r.genre)}</span>`);
  tags.push(`<span class="t">×${r.matched_seeds} seeds</span>`);
  $("swTags").innerHTML = tags.join("");
  const u = encodeURIComponent(r.url);
  $("swPlayer").src = `https://w.soundcloud.com/player/?url=${u}` +
    `&color=%23ff5a1f&auto_play=true&hide_related=true&show_comments=false&visual=false`;
}

async function swipe(liked) {
  if (DECK_I >= DECK.length) return;
  const r = DECK[DECK_I];
  liked ? SW_LIKE++ : SW_NOPE++;
  RATED.add(r.track_id);
  // animation เล็กน้อย
  const card = $("swipeCard");
  card.classList.add(liked ? "fly-right" : "fly-left");
  setTimeout(() => card.classList.remove("fly-right", "fly-left"), 220);
  try {
    const res = await fetch("/api/feedback", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ track: r, liked }),
    });
    renderTaste(await res.json());
  } catch (_) {}
  DECK_I++;
  setTimeout(showCard, 120);
}

function renderTaste(p) {
  if (!p || !p.profile) return;
  const c = p.counts || {};
  const blocks = [];
  const labels = { genre: "แนว", camelot: "คีย์", bpm: "BPM", artist: "ศิลปิน" };
  for (const k of ["genre", "camelot", "bpm", "artist"]) {
    const arr = (p.profile[k] || []).filter((x) => x.n > 0).slice(0, 3);
    if (!arr.length) continue;
    const items = arr.map((x) =>
      `<span class="tp ${x.like_rate >= 0.5 ? "up" : "down"}">${esc(x.value)} ${Math.round(x.like_rate * 100)}%</span>`).join("");
    blocks.push(`<div class="tp-row"><b>${labels[k]}</b>${items}</div>`);
  }
  $("tasteProfile").innerHTML =
    `<div class="tp-head">รสนิยมที่เรียนรู้ · ❤️${c.likes || 0} 💔${c.dislikes || 0}</div>` +
    (blocks.join("") || `<span class="muted">ปัดเพลงเพื่อเริ่มเรียนรู้…</span>`);
}

async function rerank() {
  $("status").textContent = "กำลังจัดอันดับใหม่ตามรสนิยม…";
  try {
    const res = await fetch("/api/rerank", { method: "POST" });
    const d = await res.json();
    if (!d.ok) { $("status").innerHTML = "ℹ️ " + esc(d.info || ""); return; }
    ROWS = d.results || [];
    HARMONIC = false; CAM_FILTER = ""; sortKey = "rank"; sortDir = 1;
    render();
    $("status").innerHTML = "✨ จัดอันดับใหม่ตามรสนิยมแล้ว (co-occurrence ยังนำ)";
  } catch (e) { $("status").textContent = "❌ " + e; }
}
