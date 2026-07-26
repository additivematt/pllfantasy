// Self-unregistering Service Worker to clean up legacy offline caches
self.addEventListener('install', event => {
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(keys.map(key => caches.delete(key)));
        }).then(() => {
            return self.registration.unregister();
        }).then(() => {
            console.log('[SW] Service worker unregistered and all legacy caches purged.');
        })
    );
});
