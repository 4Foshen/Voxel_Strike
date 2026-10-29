/* Service worker Voxel Strike: офлайн-запуск и быстрая загрузка.
   При каждом обновлении игры поднимайте VERSION - старый кэш удалится сам. */
const VERSION = 'vs-v1';
const LOCAL = [
  './', './index.html', './manifest.json',
  './assets/models/soldier_glb.js',
  './icons/icon-192.png', './icons/icon-512.png', './icons/icon-maskable-512.png', './icons/apple-touch-icon.png'
];
const CDN = [
  'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js',
  'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js',
  'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/utils/SkeletonUtils.js'
];
const CDN_HOSTS = ['cdnjs.cloudflare.com', 'cdn.jsdelivr.net'];

self.addEventListener('install', e => {
  e.waitUntil((async () => {
    const c = await caches.open(VERSION);
    await c.addAll(LOCAL);
    // внешние скрипты кладём по одному: недоступный CDN не должен ломать установку
    await Promise.all(CDN.map(u => fetch(u, { mode: 'cors' }).then(r => r.ok && c.put(u, r)).catch(() => {})));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k !== VERSION) await caches.delete(k);
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  const same = url.origin === self.location.origin;
  if (!same && !CDN_HOSTS.includes(url.hostname)) return;     // всё прочее (WebRTC, аналитика) - мимо кэша

  // страница: сначала сеть (чтобы обновления доходили сразу), без сети - из кэша
  if (req.mode === 'navigate' || (same && /\/(index\.html)?$/.test(url.pathname))) {
    e.respondWith((async () => {
      try {
        const r = await fetch(req.url, { cache: 'no-cache' });     // мимо HTTP-кэша GitHub Pages: обновления приходят сразу
        if (r.ok) (await caches.open(VERSION)).put('./index.html', r.clone());
        return r;
      } catch (_) {
        return (await caches.match('./index.html')) || (await caches.match('./')) || Response.error();
      }
    })());
    return;
  }
  // остальное: из кэша, если нет - сеть и запоминаем
  e.respondWith((async () => {
    const hit = await caches.match(req, { ignoreSearch: same });
    if (hit) return hit;
    try {
      const r = await fetch(req);
      if (r.ok && (r.type === 'basic' || r.type === 'cors')) (await caches.open(VERSION)).put(req, r.clone());
      return r;
    } catch (_) {
      return Response.error();
    }
  })());
});
