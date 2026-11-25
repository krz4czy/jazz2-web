/* Elektronika sprites.
   Jazz² Resurrection asks for Enemy/Skeleton and the other original names, and
   those strings live in the engine with a fixed length. While a Plyta level is
   opening — and only then — the same-length names below are written over them,
   so this episode loads Metadata/Rezystor/… from the imported add-on. Leaving
   the level writes the original names back, and other episodes keep their art. */
(function () {
	'use strict';

	var SWAPS = [
		['Enemy/Skeleton', 'Rezystor/WalkX'],
		['Enemy/Sparks', 'Mosfet/Spark'],
		['Enemy/Fencer', 'Trybik/GearX'],
		['Enemy/Dragonfly', 'Cewka/Dragonfly'],
		['Enemy/Bee', 'Cewka/Bee'],
		['Enemy/FatChick', 'Kondens/Attack'],
		['Enemy/Rapier', 'Cewka/Charge'],
		['Boss/Robot', 'Trafo/Boss']
	];
	var offsets = null;
	var applied = false;

	function findOffsets(heap) {
		var found = [];
		for (var s = 0; s < SWAPS.length; s++) {
			var from = SWAPS[s][0];
			var at = -1;
			for (var i = 0; i < heap.length - from.length; i++) {
				var ok = true;
				for (var k = 0; k < from.length; k++) {
					if (heap[i + k] !== from.charCodeAt(k)) { ok = false; break; }
				}
				if (ok && heap[i + from.length] === 0) { at = i; break; }
			}
			if (at < 0) return null;
			found.push(at);
		}
		return found;
	}

	function writeAt(heap, at, text) {
		for (var i = 0; i < text.length; i++) heap[at + i] = text.charCodeAt(i);
	}

	function apply(Module, on) {
		if (!Module || !Module.HEAPU8) return false;
		if (!offsets) offsets = findOffsets(Module.HEAPU8);
		if (!offsets) {
			console.warn('Elektronika: nie znaleziono nazw wrogów w silniku');
			return false;
		}
		if (applied === on) return true;
		var heap = Module.HEAPU8;
		for (var i = 0; i < SWAPS.length; i++) writeAt(heap, offsets[i], on ? SWAPS[i][1] : SWAPS[i][0]);
		applied = on;
		console.log(on ? 'Elektronika: własne duszki włączone' : 'Elektronika: przywrócono oryginalne duszki');
		return true;
	}

	function isElektroLevel(path) {
		if (typeof path !== 'string') return false;
		var p = path.toLowerCase();
		return p.indexOf('plyta.j2l') >= 0 || p.indexOf('plyta2.j2l') >= 0;
	}

	function isOtherLevel(path) {
		if (typeof path !== 'string') return false;
		var p = path.toLowerCase();
		return p.endsWith('.j2l') && !isElektroLevel(p);
	}

	function consider(Module, path) {
		if (isElektroLevel(path)) apply(Module, true);
		else if (isOtherLevel(path)) apply(Module, false);
	}

	function hook(Module) {
		if (!Module || !Module.FS || Module.FS.__elektroHook) {
			console.log('Elektronika: hook pominiety', !Module, !(Module && Module.FS));
			return;
		}
		console.log('Elektronika: hook zalozony');
		var open = Module.FS.open;
		Module.FS.open = function (path, flags, mode) {
			consider(Module, path);
			return open.call(this, path, flags, mode);
		};
		if (Module.FS.lookupPath) {
			var lookup = Module.FS.lookupPath;
			Module.FS.lookupPath = function (path, opts) {
				consider(Module, path);
				return lookup.call(this, path, opts);
			};
		}
		Module.FS.__elektroHook = true;
	}

	window.JazzAddon = { hook: hook, apply: apply };
})();
