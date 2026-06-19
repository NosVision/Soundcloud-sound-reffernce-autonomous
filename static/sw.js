/* service worker เบาๆ: cache static shell ให้เปิดเป็นแอปบนมือถือได้
   ไม่ cache /api เพื่อให้ข้อมูลสดเสมอ */
const CACHE = "scf-v1";
const ASSETS = ["/", "/static/style.css", "/static/app.js",
                "/static/icon.svg", "/static/manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) =>
    Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
  self.clients.claim();
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
  e.respondWith(
    caches.match(e.request).then((hit) =>
      hit || fetch(e.request).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(() => {});
        return res;
      }).catch(() => hit))
  );
});
