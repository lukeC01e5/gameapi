self.addEventListener('fetch', function(event) {
    if (event.request.url.startsWith('http://')) {
        const httpsUrl = event.request.url.replace('http://', 'https://');
        event.respondWith(fetch(httpsUrl));
    } else {
        event.respondWith(fetch(event.request));
    }
});