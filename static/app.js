"use strict";

// PWA: register service worker (ติดตั้งเป็นแอปบนมือถือได้)
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () =>
    navigator.serviceWorker.register("/sw.js").catch(() => {}));
}

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
  themeBtn.textContent = t === "dark" ? "☀️" : "🌙";
  localStorage.setItem("scTheme", t);
}

// ================= mobile tab pager (เลื่อนซ้ายขวา / แตะเมนูล่าง) =================
const TABS = ["search", "results", "swipe", "taste"];
const pager = $("pager");
let SWIPE_READY = false;          // กันไม่ให้ deck รีเซ็ตเองตอนสไลด์กลับมา

function activeTabIndex() {
  return Math.max(0, Math.min(TABS.length - 1,
    Math.round(pager.scrollLeft / Math.max(1, pager.clientWidth))));
}
function setActiveTab(name) {
  document.querySelectorAll(".tabbar button").forEach((b) =>
    b.classList.toggle("active", b.dataset.go === name));
}
function goTab(name) {
  const i = TABS.indexOf(name);
  if (i < 0) return;
  pager.scrollTo({ left: i * pager.clientWidth, behavior: "smooth" });
  setActiveTab(name);
  if (name === "swipe") openSwipe();
}
document.querySelectorAll(".tabbar button").forEach((b) =>
  b.addEventListener("click", () => goTab(b.dataset.go)));

let _scrollSync;
pager.addEventListener("scroll", () => {
  clearTimeout(_scrollSync);
  _scrollSync = setTimeout(() => {
    const name = TABS[activeTabIndex()];
    setActiveTab(name);
    if (name === "swipe") openSwipe();
    else if (typeof stopPlayer === "function") stopPlayer();   // ออกจากหน้าปัด = หยุดเสียง
  }, 90);
});
// แตะหน้าใหม่หลังหมุนจอ ให้ snap ตรงหน้าเดิม
window.addEventListener("resize", () => {
  pager.scrollTo({ left: activeTabIndex() * pager.clientWidth });
});

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
    SWIPE_READY = false;          // ผลใหม่ -> สร้าง deck ปัดใหม่
    render();
    const demo = data.demo ? '<span class="badge">DEMO</span>' : "";
    $("status").innerHTML = `✅ ได้ ${data.count} เพลง ` + demo;
    const has = ROWS.length > 0;
    ["dlBtn", "dlMik", "dlM3u", "harmonicBtn", "lineBtn", "swipeBtn", "rerankBtn"].forEach((id) =>
      $(id).classList.toggle("hidden", !has));
    if (has) goTab("results");    // พาไปดูผลลัพธ์เลย
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

// ----- ระดับเสียง (จำไว้ใน localStorage) -----
let scWidget = null;            // SoundCloud Widget API ของการ์ดปัจจุบัน
let lastVol = 40;
function curVol() {
  const v = parseInt(localStorage.getItem("swVol"), 10);
  return Number.isFinite(v) ? v : 40;   // default 40 (ไม่ดังเกิน)
}
function setVol(v) {
  v = Math.max(0, Math.min(100, Math.round(v)));
  if (v > 0) lastVol = v;
  localStorage.setItem("swVol", v);
  if ($("swVol")) $("swVol").value = v;
  if ($("swMute")) $("swMute").textContent = v === 0 ? "🔇" : (v < 50 ? "🔉" : "🔊");
  if (scWidget) { try { scWidget.setVolume(v); } catch (_) {} }
}
function toggleMute() { setVol(curVol() > 0 ? 0 : (lastVol || 40)); }
function applyVolToWidget() {
  // ผูก widget ของการ์ดปัจจุบัน แล้วตั้งเสียงตามที่จำไว้
  if (!(window.SC && SC.Widget)) return;
  try {
    scWidget = SC.Widget($("swPlayer"));
    scWidget.bind(SC.Widget.Events.READY, () => { try { scWidget.setVolume(curVol()); } catch (_) {} });
  } catch (_) {}
}

$("swipeBtn").addEventListener("click", () => goTab("swipe"));
$("rerankBtn").addEventListener("click", rerank);
$("btnLike").addEventListener("click", () => swipe(true));
$("btnNope").addEventListener("click", () => swipe(false));
if ($("swVol")) $("swVol").addEventListener("input", (e) => setVol(parseInt(e.target.value, 10)));
if ($("swMute")) $("swMute").addEventListener("click", toggleMute);
setVol(curVol());               // ตั้งสไลเดอร์/ไอคอนให้ตรงค่าที่จำไว้

document.addEventListener("keydown", (e) => {
  if (TABS[activeTabIndex()] !== "swipe") return;   // ทำงานเฉพาะตอนอยู่หน้าปัด
  if (e.key === "ArrowRight") swipe(true);
  else if (e.key === "ArrowLeft") swipe(false);
  else if (e.key === "ArrowUp") { setVol(curVol() + 10); e.preventDefault(); }
  else if (e.key === "ArrowDown") { setVol(curVol() - 10); e.preventDefault(); }
});

function stopPlayer() { if ($("swPlayer").src) $("swPlayer").src = ""; }   // หยุดเสียง

async function openSwipe() {
  if (SWIPE_READY) return;        // มี deck อยู่แล้ว -> เก็บความคืบหน้าไว้ (กันรีเซ็ตตอนสไลด์กลับมา)
  try {
    const p = await (await fetch("/api/profile")).json();
    RATED = new Set(p.rated || []);
    renderTaste(p);
  } catch (_) { RATED = new Set(); }
  DECK = ROWS.filter((r) => !RATED.has(r.track_id));
  DECK_I = 0; SW_LIKE = 0; SW_NOPE = 0;
  SWIPE_READY = true;
  const hasDeck = DECK.length > 0;
  const noRows = ROWS.length === 0;
  $("swipeEmpty").classList.toggle("hidden", !noRows);
  $("swipeDone").classList.toggle("hidden", hasDeck || noRows);
  $("swipeCard").classList.toggle("hidden", !hasDeck);
  if (hasDeck) showCard();
}

// ----- ลากการ์ดซ้าย/ขวา = ไม่ชอบ/ชอบ (เหมือน Tinder) -----
(function enableCardDrag() {
  const card = $("swipeCard");
  if (!card) return;
  let startX = 0, dx = 0, dragging = false;
  card.addEventListener("pointerdown", (e) => {
    if (DECK_I >= DECK.length) return;
    dragging = true; startX = e.clientX; dx = 0;
    card.style.transition = "none";
    try { card.setPointerCapture(e.pointerId); } catch (_) {}
  });
  card.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    dx = e.clientX - startX;
    card.style.transform = `translateX(${dx}px) rotate(${dx / 28}deg)`;
    card.style.opacity = String(1 - Math.min(Math.abs(dx) / 380, 0.45));
  });
  const release = () => {
    if (!dragging) return;
    dragging = false;
    card.style.transition = ""; card.style.transform = ""; card.style.opacity = "";
    if (dx > 80) swipe(true);
    else if (dx < -80) swipe(false);
  };
  card.addEventListener("pointerup", release);
  card.addEventListener("pointercancel", release);
})();

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
  applyVolToWidget();           // ตั้งระดับเสียงตามที่ผู้ใช้เลือกไว้
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
