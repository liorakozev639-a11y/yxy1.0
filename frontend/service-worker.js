const CACHE_NAME = 'free-time-agent-pwa-v2';
const APP_SHELL = [
  './',
  './index.html',
  './styles.css?v=pixel-v8',
  './config.js?v=pwa-v1',
  './api.js?v=pixel-v8',
  './flow.js?v=pixel-v8',
  './app.js?v=pixel-v8',
  './pixel-companions.png',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './manifest.json?v=pwa-v1',
];

function networkOnly(request) {
  return fetch(request);
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)),
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)),
    )),
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET' || request.url.includes('/api/v1/') || request.url.endsWith('/health')) {
    event.respondWith(networkOnly(request));
    return;
  }
  event.respondWith(
    caches.match(request).then((cached) => cached || fetch(request).then((response) => {
      const copy = response.clone();
      caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
      return response;
    })),
  );
});
