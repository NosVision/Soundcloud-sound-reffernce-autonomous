"use strict";

// PWA: register service worker
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () =>
    navigator.serviceWorker.register("/sw.js").catch(() => {}));
}

let MODE = "urls";
let ROWS = [];
let sortKey = "matched_seeds";
let sortDir = -1;
let HARMONIC = false;
let CAM_FILTER = "";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmt = (n) => (n || 0).toLocaleString();
const icon = (name) => `<svg class="ic" viewBox="0 0 24 24"><use href="#i-${name}"></use></svg>`;

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

// ================= theme (dark / light) =================
setTheme(localStorage.getItem("scTheme") || "dark");
[$("themeBtn"), $("themeBtnM")].forEach((b) => b && b.addEventListener("click", () =>
  setTheme(document.body.dataset.theme === "dark" ? "light" : "dark")));
function setTheme(t) {
  document.body.dataset.theme = t;
  document.querySelectorAll("#themeBtn use, #themeBtnM use").forEach((u) =>
    u.setAttribute("href", t === "dark" ? "#i-sun" : "#i-moon"));
  localStorage.setItem("scTheme", t);
}

// ================= view router (sidebar เดสก์ท็อป / bottom-nav มือถือ — state เดียวกัน) =================
let currentView = "search";
function showView(name) {
  currentView = name;
  document.querySelectorAll(".view").forEach((v) =>
    v.classList.toggle("active", v.id === "view-" + name));
  document.querySelectorAll("[data-nav] button").forEach((b) =>
    b.classList.toggle("active", b.dataset.view === name));
  const c = document.querySelector(".content");
  if (c) c.scrollTop = 0;
  if (name === "swipe") openSwipe(); else stopPlayer();
  if (name === "taste") refreshTaste();
  if (name === "history") loadHistory();
}
document.querySelectorAll("[data-nav] button").forEach((b) =>
  b.addEventListener("click", () => showView(b.dataset.view)));

// ================= seed mode =================
document.querySelectorAll("#seedMode button").forEach((b) => {
  b.addEventListener("click", () => {
    document.querySelectorAll("#seedMode button").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    MODE = b.dataset.mode;
    $("urlsBox").classList.toggle("hidden", MODE === "likes");
    $("profileBox").classList.toggle("hidden", MODE === "urls");
  });
});

// ================= run =================
$("runBtn").addEventListener("click", run);
async function run() {
  const btn = $("runBtn");
  btn.disabled = true;
  $("status").innerHTML = "กำลังทำงาน… (ดึง related ของแต่ละ seed)";
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
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    $("log").textContent = (data.logs || []).join("\n");
    if (!data.ok) {
      $("status").innerHTML = `<span class="err">ผิดพลาด:</span> ${esc(data.error || "error")}`;
      return;
    }
    ROWS = data.results || [];
    sortKey = "matched_seeds"; sortDir = -1; HARMONIC = false; CAM_FILTER = "";
    SWIPE_READY = false;
    render();
    const demo = data.demo ? '<span class="badge">DEMO</span>' : "";
    $("status").innerHTML = `<span class="ok">ได้ ${data.count} เพลง</span> ${demo}`;
    const has = ROWS.length > 0;
    ["dlBtn", "dlMik", "dlM3u", "harmonicBtn", "lineBtn", "swipeBtn", "rerankBtn"].forEach((id) =>
      $(id).classList.toggle("hidden", !has));
    if (has) showView("results");
  } catch (e) {
    $("status").innerHTML = `<span class="err">ผิดพลาด:</span> ${esc(String(e))}`;
  } finally {
    btn.disabled = false;
  }
}

// ================= results table =================
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
  $("status").innerHTML = "กำลังส่งเข้า LINE…";
  try {
    const d = await (await fetch("/api/notify", { method: "POST" })).json();
    $("status").innerHTML = d.ok
      ? `<span class="ok">ส่งเข้า LINE แล้ว</span> ${esc(d.info || "")}`
      : `<span class="err">${esc(d.info || "ส่งไม่สำเร็จ")}</span>`;
  } catch (e) { $("status").innerHTML = `<span class="err">${esc(String(e))}</span>`; }
});

function render() {
  const q = $("filterText").value.trim().toLowerCase();
  let rows = ROWS.filter((r) =>
    !q || (r.title || "").toLowerCase().includes(q) || (r.artist || "").toLowerCase().includes(q));
  if (CAM_FILTER) rows = rows.filter((r) => isCompatible(CAM_FILTER, r.camelot));

  if (HARMONIC) rows = harmonicOrder(rows);
  else rows.sort((a, b) => {
    const x = a[sortKey], y = b[sortKey];
    if (typeof x === "number" && typeof y === "number") return (x - y) * sortDir;
    return String(x).localeCompare(String(y)) * sortDir;
  });

  const chip = $("camChip");
  chip.classList.toggle("hidden", !CAM_FILTER);
  if (CAM_FILTER) chip.textContent = `key เข้ากับ ${CAM_FILTER} · ล้าง`;

  const maxMs = Math.max(1, ...ROWS.map((r) => r.matched_seeds || 0));
  const tb = $("tbl").querySelector("tbody");
  tb.innerHTML = rows.map((r, i) => {
    const w = Math.round(((r.matched_seeds || 0) / maxMs) * 56);
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
      <td><a href="${r.url}" target="_blank" rel="noopener">เปิด ${icon("external")}</a></td>
    </tr>`;
  }).join("");

  tb.querySelectorAll(".cam[data-cam]").forEach((el) =>
    el.addEventListener("click", () => { CAM_FILTER = el.dataset.cam; HARMONIC = false; render(); }));

  $("tbl").classList.toggle("hidden", rows.length === 0);
  $("empty").classList.toggle("hidden", rows.length !== 0);
  document.querySelectorAll("#tbl th[data-k]").forEach((th) => {
    const base = th.dataset.k === "rank" ? "#" : th.dataset.k;
    th.textContent = base + (!HARMONIC && th.dataset.k === sortKey ? (sortDir < 0 ? " ↓" : " ↑") : "");
  });
}

// ================= volume (จำไว้ใน localStorage) =================
let scWidget = null;
let lastVol = 40;
function curVol() {
  const v = parseInt(localStorage.getItem("swVol"), 10);
  return Number.isFinite(v) ? v : 40;
}
function setVol(v) {
  v = Math.max(0, Math.min(100, Math.round(v)));
  if (v > 0) lastVol = v;
  localStorage.setItem("swVol", v);
  if ($("swVol")) $("swVol").value = v;
  const u = $("swMute") && $("swMute").querySelector("use");
  if (u) u.setAttribute("href", v === 0 ? "#i-volume-x" : "#i-volume");
  if (scWidget) { try { scWidget.setVolume(v); } catch (_) {} }
}
function toggleMute() { setVol(curVol() > 0 ? 0 : (lastVol || 40)); }
function applyVolToWidget() {
  if (!(window.SC && SC.Widget)) return;
  try {
    scWidget = SC.Widget($("swPlayer"));
    scWidget.bind(SC.Widget.Events.READY, () => { try { scWidget.setVolume(curVol()); } catch (_) {} });
  } catch (_) {}
}
setVol(curVol());

// ================= swipe deck =================
let DECK = [], DECK_I = 0, SW_LIKE = 0, SW_NOPE = 0, RATED = new Set();
let SWIPE_READY = false;

$("swipeBtn").addEventListener("click", () => showView("swipe"));
$("rerankBtn").addEventListener("click", rerank);
$("btnLike").addEventListener("click", () => swipe(true));
$("btnNope").addEventListener("click", () => swipe(false));
$("swVol").addEventListener("input", (e) => setVol(parseInt(e.target.value, 10)));
$("swMute").addEventListener("click", toggleMute);
document.addEventListener("keydown", (e) => {
  if (currentView !== "swipe") return;
  if (e.key === "ArrowRight") swipe(true);
  else if (e.key === "ArrowLeft") swipe(false);
  else if (e.key === "ArrowUp") { setVol(curVol() + 10); e.preventDefault(); }
  else if (e.key === "ArrowDown") { setVol(curVol() - 10); e.preventDefault(); }
});

function stopPlayer() { if ($("swPlayer") && $("swPlayer").src) $("swPlayer").src = ""; }

async function openSwipe() {
  if (SWIPE_READY) return;            // เก็บความคืบหน้าไว้ตอนสลับหน้าไปมา
  try {
    const p = await (await fetch("/api/profile")).json();
    RATED = new Set(p.rated || []);
    renderTaste(p);
  } catch (_) { RATED = new Set(); }
  DECK = ROWS.filter((r) => !RATED.has(r.track_id));
  DECK_I = 0; SW_LIKE = 0; SW_NOPE = 0;
  SWIPE_READY = true;
  const hasDeck = DECK.length > 0, noRows = ROWS.length === 0;
  $("swipeEmpty").classList.toggle("hidden", !noRows);
  $("swipeDone").classList.toggle("hidden", hasDeck || noRows);
  $("swipeCard").classList.toggle("hidden", !hasDeck);
  if (hasDeck) showCard();
}

// ลากการ์ดซ้าย/ขวา = ไม่ชอบ/ชอบ (Tinder-style + ป้าย LIKE/NOPE)
const THRESHOLD = 95;
(function enableCardDrag() {
  const card = $("swipeCard");
  if (!card) return;
  const likeS = card.querySelector(".stamp-like");
  const nopeS = card.querySelector(".stamp-nope");
  let startX = 0, dx = 0, dragging = false;
  const setStamps = () => {
    if (likeS) likeS.style.opacity = Math.max(0, Math.min(1, dx / THRESHOLD));
    if (nopeS) nopeS.style.opacity = Math.max(0, Math.min(1, -dx / THRESHOLD));
  };
  card.addEventListener("pointerdown", (e) => {
    if (DECK_I >= DECK.length) return;
    if (e.target.closest(".vol-row, .card-actions")) return;  // ปล่อยให้กดปุ่ม/สไลเดอร์ได้
    dragging = true; startX = e.clientX; dx = 0;
    card.style.transition = "none";
    try { card.setPointerCapture(e.pointerId); } catch (_) {}
  });
  card.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    dx = e.clientX - startX;
    card.style.transform = `translateX(${dx}px) rotate(${dx / 22}deg)`;
    card.style.opacity = String(1 - Math.min(Math.abs(dx) / 600, 0.25));
    setStamps();
  });
  const release = () => {
    if (!dragging) return;
    dragging = false;
    card.style.transition = "";
    if (likeS) likeS.style.opacity = 0;
    if (nopeS) nopeS.style.opacity = 0;
    if (dx > THRESHOLD) swipe(true);
    else if (dx < -THRESHOLD) swipe(false);
    else { card.style.transform = ""; card.style.opacity = ""; }   // เด้งกลับกลาง
  };
  card.addEventListener("pointerup", release);
  card.addEventListener("pointercancel", release);
})();

function showCard() {
  // รีเซ็ตการ์ดกลับกลางทันที (ไม่ให้ไหลมาจากตำแหน่งที่บินออก)
  const cardEl = $("swipeCard");
  cardEl.classList.remove("fly-right", "fly-left");
  cardEl.style.transition = "none";
  cardEl.style.transform = "";
  cardEl.style.opacity = "";
  void cardEl.offsetWidth;                 // force reflow
  cardEl.style.transition = "";
  cardEl.querySelectorAll(".stamp").forEach((s) => (s.style.opacity = 0));

  $("swLike").textContent = SW_LIKE;
  $("swNope").textContent = SW_NOPE;
  $("swipeProg").textContent = `${Math.min(DECK_I + 1, DECK.length)}/${DECK.length}`;
  if (DECK_I >= DECK.length) {
    $("swipeCard").classList.add("hidden");
    $("swipeDone").classList.remove("hidden");
    stopPlayer();
    return;
  }
  const r = DECK[DECK_I];
  $("swTitle").textContent = r.title || "(ไม่มีชื่อ)";
  $("swArtist").textContent = r.artist || "";
  const tags = [];
  if (r.camelot) tags.push(`<span class="cam">${r.camelot}</span>`);
  if (r.bpm) tags.push(`<span class="t">${r.bpm} bpm</span>`);
  if (r.genre) tags.push(`<span class="t">${esc(r.genre)}</span>`);
  tags.push(`<span class="t">${r.matched_seeds} seeds</span>`);
  $("swTags").innerHTML = tags.join("");
  const u = encodeURIComponent(r.url);
  $("swPlayer").src = `https://w.soundcloud.com/player/?url=${u}` +
    `&color=%23ff5a1f&auto_play=true&hide_related=true&show_comments=false&visual=false`;
  applyVolToWidget();
}

async function swipe(liked) {
  if (DECK_I >= DECK.length) return;
  const r = DECK[DECK_I];
  liked ? SW_LIKE++ : SW_NOPE++;
  RATED.add(r.track_id);
  const card = $("swipeCard");
  card.style.transition = "";                       // ใช้ transition ของ .card
  card.classList.add(liked ? "fly-right" : "fly-left");   // บินออกข้าง
  try {
    const res = await fetch("/api/feedback", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ track: r, liked }),
    });
    renderTaste(await res.json());
  } catch (_) {}
  DECK_I++;
  setTimeout(showCard, 260);                         // รอบินออกก่อนค่อยโชว์ใบถัดไป
}

// ================= taste =================
async function refreshTaste() {
  try { renderTaste(await (await fetch("/api/profile")).json()); } catch (_) {}
}
function renderTaste(p) {
  if (!p || !p.profile) return;
  const c = p.counts || {};
  const labels = { genre: "แนว", camelot: "คีย์", bpm: "BPM", artist: "ศิลปิน" };
  const blocks = [];
  for (const k of ["genre", "camelot", "bpm", "artist"]) {
    const arr = (p.profile[k] || []).filter((x) => x.n > 0).slice(0, 4);
    if (!arr.length) continue;
    const items = arr.map((x) =>
      `<span class="tp ${x.like_rate >= 0.5 ? "up" : "down"}">${esc(x.value)} ${Math.round(x.like_rate * 100)}%</span>`).join("");
    blocks.push(`<div class="tp-row"><b>${labels[k]}</b>${items}</div>`);
  }
  $("tasteProfile").innerHTML =
    `<div class="tp-head">ชอบ ${c.likes || 0} · ไม่ชอบ ${c.dislikes || 0}</div>` +
    (blocks.join("") || `<span class="muted">ปัดเพลงเพื่อเริ่มเรียนรู้…</span>`);
}

async function rerank() {
  $("status").innerHTML = "กำลังจัดอันดับใหม่ตามรสนิยม…";
  try {
    const d = await (await fetch("/api/rerank", { method: "POST" })).json();
    if (!d.ok) { $("status").innerHTML = `<span class="muted">${esc(d.info || "")}</span>`; return; }
    ROWS = d.results || [];
    HARMONIC = false; CAM_FILTER = ""; sortKey = "rank"; sortDir = 1;
    render();
    showView("results");
    $("status").innerHTML = `<span class="ok">จัดอันดับใหม่ตามรสนิยมแล้ว</span> (co-occurrence ยังนำ)`;
  } catch (e) { $("status").innerHTML = `<span class="err">${esc(String(e))}</span>`; }
}

// ================= history (ประวัติ like/dislike) =================
let HIST = [], HIST_F = "all";
document.querySelectorAll("#histFilter button").forEach((b) =>
  b.addEventListener("click", () => {
    document.querySelectorAll("#histFilter button").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    HIST_F = b.dataset.f;
    renderHistory();
  }));

async function loadHistory() {
  try {
    const d = await (await fetch("/api/history")).json();
    HIST = d.records || [];
    const c = d.counts || {};
    $("histCounts").textContent =
      `ทั้งหมด ${c.total || 0} · ชอบ ${c.likes || 0} · ไม่ชอบ ${c.dislikes || 0}`;
    renderHistory();
  } catch (_) {}
}
function renderHistory() {
  const list = HIST.filter((r) =>
    HIST_F === "all" || (HIST_F === "like" ? r.liked : !r.liked));
  if (!list.length) {
    $("historyList").innerHTML = `<span class="muted">ยังไม่มีรายการในหมวดนี้</span>`;
    return;
  }
  $("historyList").innerHTML = list.map((r) => {
    const f = r.features || {};
    const tags = [f.genre, f.camelot, f.bpm, f.artist].filter(Boolean).join(" · ");
    const mark = r.liked ? "like" : "nope";
    const ic = r.liked ? "heart" : "x";
    const next = r.liked ? "เปลี่ยนเป็นไม่ชอบ" : "เปลี่ยนเป็นชอบ";
    return `<div class="hist-item">
      <span class="hist-mark ${mark}">${icon(ic)}</span>
      <div class="hist-main">
        <div class="hist-title">${esc(r.title || "(ไม่มีชื่อ)")}</div>
        <div class="hist-tags">${esc(tags || "—")}</div>
      </div>
      <button class="hist-toggle" data-id="${r.track_id}">${next}</button>
    </div>`;
  }).join("");
  $("historyList").querySelectorAll(".hist-toggle").forEach((btn) =>
    btn.addEventListener("click", () => reRate(btn.dataset.id)));
}
async function reRate(id) {
  try {
    await fetch("/api/rate_toggle", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ track_id: id }),
    });
    SWIPE_READY = false;     // rating เปลี่ยน -> deck/อันดับอาจต้องอัปเดต
    await loadHistory();
  } catch (_) {}
}
