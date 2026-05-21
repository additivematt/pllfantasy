const CACHE_VERSION = 'interrogata-v1';
const DATA_CACHE = 'interrogata-data-v1';

// App shell assets — cache on install, serve cache-first
const APP_SHELL = [
    './',
    'index.html',
    'style.css',
    'app.js',
    'https://cdn.jsdelivr.net/npm/chart.js',
    'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap',
];

// ── Install: pre-cache the app shell and initial data ────────────────────────
self.addEventListener('install', event => {
    event.waitUntil(
        Promise.all([
            caches.open(CACHE_VERSION).then(cache => {
                console.log('[SW] Pre-caching app shell');
                return Promise.allSettled(
                    APP_SHELL.map(url => cache.add(url).catch(err => {
                        console.warn('[SW] Failed to cache asset:', url, err);
                    }))
                );
            }),
            caches.open(DATA_CACHE).then(cache => {
                console.log('[SW] Pre-caching player stats data');
                return cache.add('all_players_stats.json').catch(err => {
                    console.warn('[SW] Failed to pre-cache player stats data:', err);
                });
            })
        ]).then(() => self.skipWaiting())
    );
});


// ── Activate: clean up old caches ─────────────────────────────────────────────
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys
                    .filter(key => key !== CACHE_VERSION && key !== DATA_CACHE)
                    .map(key => {
                        console.log('[SW] Deleting old cache:', key);
                        return caches.delete(key);
                    })
            )
        ).then(() => self.clients.claim())
    );
});

// ── Fetch: route requests to the right strategy ───────────────────────────────
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);

    // Strategy 1: all_players_stats.json → Stale-While-Revalidate
    // Serve the cached copy immediately (fast), update in background when online
    if (url.pathname.endsWith('/all_players_stats.json')) {
        event.respondWith(staleWhileRevalidate(event.request, DATA_CACHE));
        return;
    }


    // Strategy 2: App shell & CDN assets → Cache-First
    // Never hit the network if we have it cached
    if (
        url.hostname === self.location.hostname ||
        url.hostname === 'cdn.jsdelivr.net' ||
        url.hostname === 'fonts.googleapis.com' ||
        url.hostname === 'fonts.gstatic.com'
    ) {
        event.respondWith(cacheFirst(event.request, CACHE_VERSION));
        return;
    }

    // Everything else: network only (don't interfere)
});

// ── Strategy: Cache-First ─────────────────────────────────────────────────────
async function cacheFirst(request, cacheName) {
    const cached = await caches.match(request);
    if (cached) return cached;

    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(cacheName);
            cache.put(request, response.clone());
        }
        return response;
    } catch {
        return new Response('', { status: 408, statusText: 'Network Error' });
    }
}

// ── Strategy: Stale-While-Revalidate ─────────────────────────────────────────
async function staleWhileRevalidate(request, cacheName) {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(request);

    // Kick off a background network fetch to refresh the cache
    const networkFetch = fetch(request).then(response => {
        if (response.ok) {
            cache.put(request, response.clone());
            console.log('[SW] Updated cache for:', request.url);
            // Notify clients: server is reachable
            self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clients => {
                clients.forEach(client => client.postMessage({ type: 'SERVER_REACHABLE' }));
            });
        }
        return response;
    }).catch(() => {
        // Network fetch failed — server is genuinely unreachable
        self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clients => {
            clients.forEach(client => client.postMessage({ type: 'SERVER_UNREACHABLE' }));
        });
        return null;
    });

    // Return cached immediately if available, otherwise wait for network
    return cached || networkFetch;
}
