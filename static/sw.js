const CACHE_NAME = 'melo-finance-v2';
const OFFLINE_URL = '/login';

const CACHED_URLS = [
  '/',
  '/login',
  '/dashboard',
  '/loans',
  '/clients',
  '/history/movements',
  '/history/loans',
  '/settings/profile',
  '/static/manifest.json',
  '/static/icon.png',
];

// Instalar: cachear recursos clave
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(CACHED_URLS))
  );
  self.skipWaiting();
});

// Activar: limpiar caches viejos
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch: network-first para HTML (siempre datos frescos), cache-first para assets estáticos
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Solo interceptar solicitudes del mismo origen
  if (url.origin !== location.origin) return;

  // Para archivos estáticos: cache-first
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request))
    );
    return;
  }

  // Para rutas HTML: network-first con fallback a cache
  event.respondWith(
    fetch(request)
      .then((response) => {
        // Guardar respuesta exitosa en cache
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        }
        return response;
      })
      .catch(() => caches.match(request).then((cached) => cached || caches.match(OFFLINE_URL)))
  );
});
