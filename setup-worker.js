// Converts the user's original Jazz Jackrabbit 2 files into the Jazz² Resurrection web content, entirely in the
// browser, with the official AssetPacker compiled to WebAssembly. Nothing is uploaded anywhere.
/* global createAssetPacker */
importScripts('assetpacker/AssetPacker.js');

function post(type, data) { self.postMessage(Object.assign({ type }, data || {})); }

function walk(FS, dir, out) {
	for (const name of FS.readdir(dir)) {
		if (name === '.' || name === '..') continue;
		const p = dir + '/' + name;
		const st = FS.stat(p);
		if (FS.isDir(st.mode)) walk(FS, p, out); else out.push(p);
	}
	return out;
}

self.onmessage = async (e) => {
	const files = e.data.files;
	try {
		post('log', { text: 'Wybrano plików: ' + files.length });
		const m = await createAssetPacker({
			locateFile: (p) => 'assetpacker/' + p,
			print: (t) => post('log', { text: t }),
			printErr: (t) => post('log', { text: t, error: true }),
			preRun: [(mod) => {
				const FS = mod.FS;
				FS.mkdir('/src');
				FS.mount(FS.filesystems.WORKERFS, { files: files }, '/src');
				FS.mkdir('/out');
			}]
		});
		post('status', { text: 'Konwersja plików gry…' });
		const rc = m.callMain(['convert', '--source=/src', '--content=/Content', '--target=emscripten', '/out']);
		if (rc !== 0) { post('failed', { text: 'AssetPacker zakończył się kodem ' + rc }); return; }

		const FS = m.FS;
		const paths = walk(FS, '/out', []).sort();
		const parts = [], meta = [];
		let offset = 0, hasEpisodes = [];
		for (const p of paths) {
			const data = FS.readFile(p);
			const rel = '/Content' + p.substring(4);
			meta.push({ filename: rel, start: offset, end: offset + data.length });
			parts.push(data);
			offset += data.length;
			const mm = /^\/Content\/Episodes\/([^/]+)\.j2e$/.exec(rel);
			if (mm) hasEpisodes.push(mm[1]);
		}
		if (!paths.some((p) => /Prebaked\.pak$/.test(p)) || hasEpisodes.length === 0) {
			post('failed', { text: 'Nie znaleziono epizodów – czy wybrałeś WSZYSTKIE pliki z katalogu gry (Anims.j2a, Data.j2d, *.j2l, *.j2t, *.j2b…)?' });
			return;
		}
		const blob = new Blob(parts, { type: 'application/octet-stream' });
		post('done', { blob, meta: { files: meta, remote_package_size: offset, episodes: hasEpisodes } });
	} catch (err) {
		post('failed', { text: String(err && err.message ? err.message : err) });
	}
};
