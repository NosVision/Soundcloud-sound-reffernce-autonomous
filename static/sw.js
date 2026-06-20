/* service worker: network-first สำหรับ app shell
   - ออนไลน์: ดึงไฟล์สดเสมอ (deploy ใหม่เห็นทันที) แล้วเก็บสำเนาไว้
   - ออฟไลน์: fallback เป็นสำเนาล่าสุดที่เคยโหลด
   - ไม่แตะ /api ฯลฯ เพื่อให้ข้อมูลสดเสมอ
   เปลี่ยนเลขเวอร์ชันทุกครั้งที่อยากบังคับล้างแคชเก่า */
const CACHE = "scf-v3";
const ASSETS = ["/", "/static/style.css", "/static/app.js",
                "/static/icon.svg", "/static/manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  // ของสด: ไม่แตะ api/export/download/login + ข้ามโดเมน
  if (url.origin !== location.origin ||
      url.pathname.startsWith("/api") || url.pathname.startsWith("/export") ||
      url.pathname === "/download" || url.pathname.startsWith("/login") ||
      url.pathname.startsWith("/logout")) {
    return;
  }
  // network-first: เอาของใหม่ก่อน ถ้าเน็ตล่มค่อยใช้แคช
  e.respondWith(
    fetch(e.request).then((res) => {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(() => {});
      return res;
    }).catch(() => caches.match(e.request))
  );
});
