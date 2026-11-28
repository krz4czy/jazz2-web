// Offline cache for the app shell (engine, converter, page). The user's converted game data is stored
// separately by the page in the "jj2-userdata" cache and never leaves the device.
const SHELL = 'jj2-shell-v7';
const FILES = ['./', './index.html', './manifest.json', './setup-worker.js', './addon-sprites.js', './touch-controls.js', './touch-controls.css',
	'./engine/jazz2.js', './engine/jazz2.wasm',
	'./assetpacker/AssetPacker.js', './assetpacker/AssetPacker.wasm', './assetpacker/AssetPacker.data',
	'./icons/256px.png', './icons/1024px.png'];
self.addEventListener('install', (e) => { e.waitUntil(caches.open(SHELL).then((c) => c.addAll(FILES)).then(() => self.skipWaiting())); });
self.addEventListener('activate', (e) => {
	e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k.startsWith('jj2-shell-') && k !== SHELL).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', (e) => {
	const url = new URL(e.request.url);
	if (e.request.method !== 'GET' || url.origin !== location.origin) return;
	// Server-side data package (optional) is always fetched fresh when online
	if (/\/jazz2\.data(\.json)?$/.test(url.pathname)) return;
	e.respondWith(caches.match(e.request, { ignoreSearch: true }).then((r) => r || fetch(e.request)));
});
