/* Bump the version whenever the app shell changes. API data is never cached here. */
"use strict";
const CACHE = 'gc-shell-20261031-3';
const CORE = ['/', '/index.html', '/styles.css', '/mission.css', '/experience.css', '/driver.css',
  '/theme-init.js', '/future-model.js', '/pwa.js', '/app.js', '/map-scene.js', '/route-math.js', '/driver-mode.js',
  '/vendor/leaflet.js', '/vendor/leaflet.css', '/vendor/maplibre-gl.js', '/vendor/maplibre-gl.css',
  '/manifest.webmanifest', '/icons/icon.svg', '/icons/icon-192.png', '/icons/icon-512.png', '/icons/maskable-512.png', '/icons/apple-touch-icon.png',
  '/data/campus.geojson'];
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(CORE))));
self.addEventListener('activate', event => event.waitUntil((async () => {
  await Promise.all((await caches.keys()).filter(key => key.startsWith('gc-shell-') && key !== CACHE).map(key => caches.delete(key)));
  await self.clients.claim();
})()));
self.addEventListener('message', event => { if(event.data?.type === 'ACTIVATE_UPDATE') self.skipWaiting(); });
self.addEventListener('fetch', event => {
  const req = event.request, url = new URL(req.url);
  if(req.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/') || url.pathname === '/health') return;
  if(req.mode === 'navigate') {
    event.respondWith((async () => {
      const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 4000);
      try { const response = await fetch(req, {signal:controller.signal}); if(response.ok) return response; }
      catch { /* Open the installed shell with its explicit offline state. */ }
      finally { clearTimeout(timer); }
      return await caches.match('/') || Response.error();
    })());
    return;
  }
  if(!CORE.includes(url.pathname) && url.pathname !== '/data/trabzon-buildings.geojson') return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE), saved = await cache.match(url.pathname);
    if(saved) return saved;
    const response = await fetch(req);
    if(response.ok && response.type === 'basic') await cache.put(url.pathname,response.clone());
    return response;
  })());
});
