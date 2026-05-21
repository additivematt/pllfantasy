const CACHE_VERSION = 'predicta-v1';
const DATA_CACHE = 'predicta-data-v1';

// App shell assets — cache on install, serve cache-first
const APP_SHELL = [
    './',
    'index.html',
    'style.css',
    'app.js?v=3',
    'https://cdn.plot.ly/plotly-2.32.0.min.js',
    'https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap'
];

// ── Install: pre-cache the app shell and initial data ────────────────────────
self.addEventListener('install', event => {
    event.waitUntil(
        Promise.all([
            caches.open(CACHE_VERSION).then(cache => {
                console.log('[SW] Pre-caching Predicta app shell');
                return Promise.allSettled(
                    APP_SHELL.map(url => cache.add(url).catch(err => {
                        console.warn('[SW] Failed to cache asset:', url, err);
                    }))
                );
            }),
            caches.open(DATA_CACHE).then(async cache => {
                console.log('[SW] Pre-caching all available predictions');
                try {
                    const response = await fetch('predictions/available');
                    if (response.ok) {
                        // Cache the available list itself
                        await cache.put('predictions/available', response.clone());
                        
                        const available = await response.json();
                        // Cache each week's predictions dynamically
                        const fetchPromises = available.map(period => {
                            const url = `predictions/${period.year}/${period.week}`;
                            return cache.add(url).catch(err => {
                                console.warn('[SW] Failed to cache prediction period:', url, err);
                            });
                        });
                        await Promise.all(fetchPromises);
                        console.log('[SW] Successfully pre-cached all available prediction periods!');
                    }
                } catch (err) {
                    console.warn('[SW] Failed to pre-cache predictions data:', err);
                }
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

    // Strategy 1: predictions/available or predictions/YYYY/W → Stale-While-Revalidate
    if (url.pathname.includes('/predictions/')) {
        event.respondWith(staleWhileRevalidate(event.request, DATA_CACHE));
        return;
    }


    // Strategy 2: App shell & Plotly CDN & Google Fonts → Cache-First
    if (
        url.hostname === self.location.hostname ||
        url.hostname === 'cdn.plot.ly' ||
        url.hostname === 'fonts.googleapis.com' ||
        url.hostname === 'fonts.gstatic.com'
    ) {
        event.respondWith(cacheFirst(event.request, CACHE_VERSION));
        return;
    }
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
                clients.forEach(client => client.postMessage({ type: 'SERVER_REACHABLE', url: request.url }));
            });
        }
        return response;
    }).catch(() => {
        // Network fetch failed — server is genuinely unreachable
        self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clients => {
            clients.forEach(client => client.postMessage({ type: 'SERVER_UNREACHABLE', url: request.url }));
        });
        return null;
    });

    // Return cached immediately if available, otherwise wait for network
    return cached || networkFetch;
}
