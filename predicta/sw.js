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
            console.log('[SW] Service Worker deactivated, caches cleared, and unregistered.');
        })
    );
});
