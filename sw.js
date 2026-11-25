// blober offline: the pages come from the network when there is one (so updates show up), from the cache when there isn't.
const CACHE = "blober-v4";
const SHELL = ["./", "index.html", "blobslinger.html", "manifest.webmanifest?v=3", "icon.svg", "fonts/BagelFatOne.woff2", "icon-192.png?v=3", "icon-512.png?v=3", "icon-maskable-192.png?v=3", "icon-maskable-512.png?v=3", "apple-touch-icon.png?v=3"];

self.addEventListener("install", e => { e.waitUntil(caches.open(CACHE).then(c => Promise.all(SHELL.map(u => c.add(u).catch(() => {})))).then(() => self.skipWaiting()));   // a missing file never blocks the rest
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const r = e.request;
  if (r.method !== "GET") return;
  const keep = res => { if (res && (res.ok || res.type === "opaque")) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(r, copy)); } return res; };
  if (r.mode === "navigate") {                            // pages: network first
    e.respondWith(fetch(r).then(keep).catch(() => caches.match(r, { ignoreSearch: true }).then(m => m || caches.match("index.html"))));
    return;
  }
  e.respondWith(caches.match(r).then(m => {                // the rest (icons, the font): cache first, refreshed behind
    const net = fetch(r).then(keep).catch(() => m);
    return m || net;
  }));
});
