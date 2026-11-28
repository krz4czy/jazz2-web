/* Touch controls for the Jazz² Resurrection web port.
   The engine (SDL, via Emscripten) reads real keyboard state. Default binds:
   arrows move / look / crouch, V jumps, Space fires, C runs, X changes weapon,
   Enter confirms a menu, Escape is back / pause.

   The old analog stick stuck on Right: pointerup was listened for only on the
   stick element, and iOS often drops that event when the thumb lifts outside
   the circle or when another finger is down. Direction changes also postponed
   keyup, so Right could stay down across a slide. Fingers are now tracked by
   touch identifier (and pointer id) on the window, including touchcancel,
   pointercancel and lost capture, and a direction is released as soon as the
   finger leaves it. */
(function () {
	'use strict';

	var KEYS = {
		left:   { key: 'ArrowLeft',  code: 'ArrowLeft',  keyCode: 37, arrow: true },
		right:  { key: 'ArrowRight', code: 'ArrowRight', keyCode: 39, arrow: true },
		up:     { key: 'ArrowUp',    code: 'ArrowUp',    keyCode: 38, arrow: true },
		down:   { key: 'ArrowDown',  code: 'ArrowDown',  keyCode: 40, arrow: true },
		fire:   { key: ' ',          code: 'Space',      keyCode: 32 },
		jump:   { key: 'v',          code: 'KeyV',       keyCode: 86 },
		run:    { key: 'c',          code: 'KeyC',       keyCode: 67 },
		weapon: { key: 'x',          code: 'KeyX',       keyCode: 88 },
		esc:    { key: 'Escape',     code: 'Escape',     keyCode: 27 },
		enter:  { key: 'Enter',      code: 'Enter',      keyCode: 13 }
	};
	var ACT = {
		up: KEYS.up, down: KEYS.down, left: KEYS.left, right: KEYS.right,
		ok: KEYS.enter, enter: KEYS.enter, back: KEYS.esc, pause: KEYS.esc,
		jump: KEYS.jump, fire: KEYS.fire, run: KEYS.run, weapon: KEYS.weapon
	};
	var BY_CODE = {};
	Object.keys(KEYS).forEach(function (name) { BY_CODE[KEYS[name].code] = KEYS[name]; });
	var DIRS = ['left', 'right', 'up', 'down'];
	/* A tap can go down and up before the next game frame samples the keyboard.
	   Action keys stay down at least this long. Arrows do not: a slide from
	   right to left must keyup Right immediately or it sticks. */
	var MIN_HOLD_MS = 110;
	var DEAD = 0.2;

	var held = {};
	var real = {};
	var latch = {};
	var owners = {};
	var pendingPointers = [];
	var trace = [];
	var booted = false;
	var gameOn = false;
	/* inLevel: a level is running (possibly paused). pauseDepth is how many
	   menu screens are stacked on that pause. 1 is the pause list itself. */
	var inLevel = false;
	var pauseDepth = 0;
	var pauseMoved = false;
	var root, menuPane, playPane;

	var origAdd = EventTarget.prototype.addEventListener;
	var origRemove = EventTarget.prototype.removeEventListener;
	var wrapped = new WeakMap();

	function svg(body) {
		return '<svg viewBox="0 0 24 24" aria-hidden="true">' + body + '</svg>';
	}
	var ICONS = {
		up: svg('<path class="fill" d="M12 3.5l8.2 14.2H3.8z"/>'),
		down: svg('<path class="fill" d="M12 20.5L3.8 6.3h16.4z"/>'),
		left: svg('<path class="fill" d="M3.5 12l14.2-8.2v16.4z"/>'),
		right: svg('<path class="fill" d="M20.5 12L6.3 3.8v16.4z"/>'),
		jump: svg('<path class="stroke" d="M12 18.5V7"/><path class="stroke" d="M7 11.2L12 6.2l5 5"/><path class="stroke" d="M4 19.2c2.4-3.4 13.6-3.4 16 0"/>'),
		fire: svg('<circle class="stroke" cx="12" cy="12" r="3.1"/><path class="stroke" d="M12 2.4v4.1M12 17.5v4.1M2.4 12h4.1M17.5 12h4.1"/>'),
		run: svg('<path class="stroke" d="M3.5 6.5l6.2 5.5-6.2 5.5"/><path class="stroke" d="M12.2 6.5l6.3 5.5-6.3 5.5"/>'),
		weapon: svg('<path class="stroke" d="M19.2 8.2A7.2 7.2 0 0 0 6.4 6.4"/><path class="stroke" d="M6.2 3.2v4.2h4.2"/><path class="stroke" d="M4.8 15.8a7.2 7.2 0 0 0 12.8 1.8"/><path class="stroke" d="M17.8 20.8v-4.2h-4.2"/>'),
		menu: svg('<path class="stroke" d="M8 4v16M16 4v16"/>'),
		ok: svg('<path class="stroke" d="M4.2 12.4l5.1 5.1L19.8 6.6"/>'),
		back: svg('<path class="stroke" d="M9.2 15.2L4 10l5.2-5.2"/><path class="stroke" d="M4 10h9.2a5.6 5.6 0 0 1 0 11.2H11"/>'),
		play: svg('<path class="fill" d="M8 4.8l11.2 7.2L8 19.2z"/>')
	};

	function proxied(ev, spec) {
		return new Proxy(ev, {
			get: function (target, prop) {
				if (prop === 'keyCode' || prop === 'which') return spec.keyCode;
				if (prop === 'charCode') return 0;
				if (prop === 'key') return spec.key;
				if (prop === 'code') return spec.code;
				if (prop === 'repeat') return false;
				var value = Reflect.get(target, prop, target);
				return typeof value === 'function' ? value.bind(target) : value;
			}
		});
	}

	function wrapListener(fn) {
		var w = wrapped.get(fn);
		if (w) return w;
		w = function (ev) {
			if (ev && ev.__jazzSpec) return fn.call(this, proxied(ev, ev.__jazzSpec));
			return fn.call(this, ev);
		};
		wrapped.set(fn, w);
		return w;
	}

	function installBridge() {
		EventTarget.prototype.addEventListener = function (type, fn, opts) {
			if ((type === 'keydown' || type === 'keyup' || type === 'keypress') && typeof fn === 'function') {
				return origAdd.call(this, type, wrapListener(fn), opts);
			}
			return origAdd.call(this, type, fn, opts);
		};
		EventTarget.prototype.removeEventListener = function (type, fn, opts) {
			if ((type === 'keydown' || type === 'keyup' || type === 'keypress') && typeof fn === 'function') {
				return origRemove.call(this, type, wrapListener(fn), opts);
			}
			return origRemove.call(this, type, fn, opts);
		};
		origAdd.call(window, 'keydown', onRealKey, true);
		origAdd.call(window, 'keyup', onRealKey, true);
	}

	function onRealKey(e) {
		if (!e.isTrusted) return;
		if (e.type === 'keydown') {
			real[e.code] = true;
			return;
		}
		real[e.code] = false;
		var spec = BY_CODE[e.code];
		if (!spec || !wanted(spec.code)) {
			held[e.code] = false;
			return;
		}
		queueMicrotask(function () {
			if (wanted(spec.code) && !real[spec.code]) {
				held[spec.code] = true;
				dispatch('keydown', spec);
			}
		});
	}

	function dispatch(type, spec) {
		var ev;
		try {
			ev = new KeyboardEvent(type, {
				key: spec.key,
				code: spec.code,
				keyCode: spec.keyCode,
				which: spec.keyCode,
				bubbles: true,
				cancelable: true,
				composed: true,
				repeat: false
			});
		} catch (err) {
			ev = document.createEvent('Event');
			ev.initEvent(type, true, true);
		}
		ev.__jazzSpec = spec;
		try {
			if (ev.keyCode !== spec.keyCode) {
				Object.defineProperty(ev, 'keyCode', { configurable: true, get: function () { return spec.keyCode; } });
				Object.defineProperty(ev, 'which', { configurable: true, get: function () { return spec.keyCode; } });
			}
		} catch (err2) { /* the listener proxy covers this */ }
		window.dispatchEvent(ev);
		trace.push({ type: type, code: spec.code, key: spec.key, keyCode: spec.keyCode });
		if (trace.length > 64) trace.shift();
	}

	function wanted(code) {
		var spec = BY_CODE[code];
		if (!spec) return false;
		var fromFinger = false;
		Object.keys(owners).forEach(function (id) {
			var o = owners[id];
			if (o.kind === 'pad') {
				DIRS.forEach(function (d) {
					if (o.dirs[d] && KEYS[d].code === code) fromFinger = true;
				});
			} else if (o.spec && o.spec.code === code) {
				fromFinger = true;
			}
		});
		if (fromFinger) return true;
		/* Arrows are never latched: leaving a direction releases that key now. */
		if (spec.arrow) return false;
		return (latch[code] || 0) > Date.now();
	}

	function recompute() {
		var codes = Object.keys(BY_CODE);
		var i;
		for (i = 0; i < codes.length; i++) {
			var code = codes[i];
			if (held[code] && !wanted(code)) {
				held[code] = false;
				latch[code] = 0;
				if (!real[code]) dispatch('keyup', BY_CODE[code]);
			}
		}
		for (i = 0; i < codes.length; i++) {
			var downCode = codes[i];
			if (!held[downCode] && wanted(downCode)) {
				held[downCode] = true;
				if (!real[downCode]) dispatch('keydown', BY_CODE[downCode]);
				if (inLevel && htmlOverlayOpen() && BY_CODE[downCode].arrow) pauseMoved = true;
			}
		}
		paint();
	}

	function releaseAll() {
		owners = {};
		pendingPointers = [];
		latch = {};
		Object.keys(held).forEach(function (code) {
			if (!held[code]) return;
			held[code] = false;
			if (!real[code] && BY_CODE[code]) dispatch('keyup', BY_CODE[code]);
		});
		paint();
	}

	function releaseOwner(id) {
		var o = owners[id];
		if (!o) return;
		delete owners[id];
		if (o.go) {
			var spec = o.spec;
			var go = o.go;
			var wait = spec && !spec.arrow ? Math.max(0, MIN_HOLD_MS - (Date.now() - o.downAt)) : 0;
			if (spec && wait > 0) latch[spec.code] = Date.now() + wait;
			recompute();
			var finish = function () {
				if (spec) latch[spec.code] = 0;
				recompute();
				if (go === 'native') enableNative();
				else if (go === 'menu') showMenuPad();
				else setMode(go);
			};
			if (wait === 0) finish();
			else setTimeout(finish, wait);
			return;
		}
		if (o.kind === 'hold' && o.spec && !o.spec.arrow) {
			var remain = MIN_HOLD_MS - (Date.now() - o.downAt);
			if (remain > 0) {
				latch[o.spec.code] = Date.now() + remain;
				(function (code, due) {
					setTimeout(function () {
						if ((latch[code] || 0) <= Date.now()) {
							latch[code] = 0;
							recompute();
						}
					}, due);
				})(o.spec.code, remain);
			}
		}
		recompute();
		if (o.spec === KEYS.enter) scheduleMenuCommand('ok');
		else if (o.spec === KEYS.esc) scheduleMenuCommand('back');
	}

	/* On the pause list, Back resumes and OK on the first item is Resume.
	   OK after moving, or Back from a screen we opened, stays on the pad. */
	function scheduleMenuCommand(kind) {
		if (!inLevel || useHtmlOverlay()) return;
		setTimeout(function () {
			if (!htmlOverlayOpen()) return;
			if (kind === 'back') {
				if (pauseDepth <= 1) enableNative();
				else { pauseDepth--; pauseMoved = false; }
			} else if (kind === 'ok') {
				if (pauseDepth <= 1 && !pauseMoved) enableNative();
				else { pauseDepth++; pauseMoved = false; }
			}
		}, MIN_HOLD_MS + 40);
	}

	function paint() {
		if (!root) return;
		var pads = root.querySelectorAll('.jt-pad');
		for (var i = 0; i < pads.length; i++) {
			var pad = pads[i];
			var dirs = { left: false, right: false, up: false, down: false };
			Object.keys(owners).forEach(function (id) {
				var o = owners[id];
				if (o.kind === 'pad' && o.pad === pad) {
					DIRS.forEach(function (d) { if (o.dirs[d]) dirs[d] = true; });
				}
			});
			var cells = pad.querySelectorAll('[data-dir]');
			for (var c = 0; c < cells.length; c++) {
				var d = cells[c].getAttribute('data-dir');
				cells[c].classList.toggle('is-down', !!dirs[d]);
			}
		}
		var holds = root.querySelectorAll('[data-hold]');
		for (var h = 0; h < holds.length; h++) {
			var el = holds[h];
			var down = false;
			Object.keys(owners).forEach(function (id) {
				if (owners[id].el === el) down = true;
			});
			el.classList.toggle('is-down', down);
			el.setAttribute('aria-pressed', down ? 'true' : 'false');
		}
	}

	function focusGame() {
		var canvas = document.getElementById('canvas');
		if (canvas && canvas.focus) {
			try { canvas.focus({ preventScroll: true }); } catch (e) { canvas.focus(); }
		}
	}

	function hitTest(x, y) {
		if (!root || root.hidden) return null;
		var el = document.elementFromPoint(x, y);
		if (!el || !root.contains(el)) return null;
		if (el.closest('[hidden]')) return null;
		var hold = el.closest('[data-hold]');
		if (hold && !hold.closest('[hidden]')) return { kind: 'hold', el: hold };
		var pad = el.closest('.jt-pad');
		if (pad && !pad.closest('[hidden]')) return { kind: 'pad', el: pad };
		return null;
	}

	function applyPad(o, x, y) {
		var r = o.pad.getBoundingClientRect();
		var padX = r.width ? (x - r.left) / r.width : 0.5;
		var padY = r.height ? (y - r.top) / r.height : 0.5;
		var inside = padX >= -0.2 && padX <= 1.2 && padY >= -0.2 && padY <= 1.2;
		var nx = (padX - 0.5) * 2;
		var ny = (padY - 0.5) * 2;
		o.dirs.left = inside && nx <= -DEAD;
		o.dirs.right = inside && nx >= DEAD;
		o.dirs.up = inside && ny <= -DEAD;
		o.dirs.down = inside && ny >= DEAD;
	}

	function linkedPointer(pid) {
		var ids = Object.keys(owners);
		for (var i = 0; i < ids.length; i++) {
			if (owners[ids[i]].pointerId === pid) return ids[i];
		}
		return null;
	}

	function claimAt(x, y, id, pointerId) {
		if (owners[id]) return;
		var hit = hitTest(x, y);
		if (!hit) return;
		if (hit.kind === 'pad') {
			owners[id] = {
				kind: 'pad', pad: hit.el, pointerId: pointerId,
				dirs: { left: false, right: false, up: false, down: false },
				downAt: Date.now()
			};
			applyPad(owners[id], x, y);
		} else {
			var act = hit.el.getAttribute('data-act');
			owners[id] = {
				kind: 'hold', el: hit.el,
				spec: act ? ACT[act] : null,
				go: hit.el.getAttribute('data-go'),
				pointerId: pointerId,
				downAt: Date.now()
			};
		}
		focusGame();
		recompute();
	}

	function moveOwner(id, x, y) {
		var o = owners[id];
		if (!o || o.kind !== 'pad') return;
		applyPad(o, x, y);
		recompute();
	}

	function takePendingPointer(x, y) {
		var best = null;
		var bestD = 56;
		var now = Date.now();
		for (var i = pendingPointers.length - 1; i >= 0; i--) {
			var p = pendingPointers[i];
			if (now - p.time > 100 || linkedPointer(p.id) || owners['p' + p.id]) {
				if (now - p.time > 100) pendingPointers.splice(i, 1);
				continue;
			}
			var d = Math.hypot(p.x - x, p.y - y);
			if (d < bestD) { bestD = d; best = p.id; }
		}
		return best;
	}

	function fromCheats(e) {
		var n = e.target;
		while (n && n !== document) {
			if (n.id === 'jt-cheats-btn' || n.id === 'jt-cheats-panel' || n.id === 'jt-cheats-toast') return true;
			n = n.parentNode;
		}
		return false;
	}

	function onPointerDown(e) {
		if (fromCheats(e)) return;
		if (!htmlOverlayOpen()) return;
		if (e.pointerType === 'touch') {
			pendingPointers.push({ id: e.pointerId, x: e.clientX, y: e.clientY, time: Date.now() });
			var pid = e.pointerId;
			var x = e.clientX;
			var y = e.clientY;
			requestAnimationFrame(function () {
				if (linkedPointer(pid) || owners['p' + pid]) return;
				claimAt(x, y, 'p' + pid, pid);
			});
			return;
		}
		if (e.button != null && e.button !== 0) return;
		claimAt(e.clientX, e.clientY, 'p' + e.pointerId, e.pointerId);
		var o = owners['p' + e.pointerId];
		var cap = o && (o.pad || o.el);
		if (cap && cap.setPointerCapture) {
			try { cap.setPointerCapture(e.pointerId); } catch (err) {}
		}
	}

	function onPointerMove(e) {
		if (e.pointerType === 'touch') return;
		moveOwner('p' + e.pointerId, e.clientX, e.clientY);
	}

	function onPointerUp(e) {
		if (e.type === 'lostpointercapture' && e.pointerType === 'touch') return;
		if (e.pointerType === 'touch') {
			var tid = linkedPointer(e.pointerId);
			if (tid) releaseOwner(tid);
			releaseOwner('p' + e.pointerId);
			return;
		}
		releaseOwner('p' + e.pointerId);
	}

	function onTouchStart(e) {
		/* preventDefault does not stop the event. In native mode the canvas is the
		   target, so SDL still receives the touch after this capture listener.
		   The cheat list is allowed to scroll, so those touches are left alone. */
		if (fromCheats(e)) return;
		if (gestureLocked() && e.cancelable) e.preventDefault();
		if (!htmlOverlayOpen()) return;
		for (var i = 0; i < e.changedTouches.length; i++) {
			var t = e.changedTouches[i];
			var id = 't' + t.identifier;
			var link = takePendingPointer(t.clientX, t.clientY);
			var pointerOwner = link != null ? owners['p' + link] : null;
			if (pointerOwner) {
				delete owners['p' + link];
				pointerOwner.pointerId = link;
				owners[id] = pointerOwner;
				if (pointerOwner.kind === 'pad') applyPad(pointerOwner, t.clientX, t.clientY);
				recompute();
				continue;
			}
			claimAt(t.clientX, t.clientY, id, link);
		}
	}

	function onTouchMove(e) {
		if (fromCheats(e)) return;
		if (gestureLocked() && e.cancelable) e.preventDefault();
		for (var i = 0; i < e.changedTouches.length; i++) {
			var t = e.changedTouches[i];
			moveOwner('t' + t.identifier, t.clientX, t.clientY);
		}
	}

	function onTouchEnd(e) {
		var i;
		for (i = 0; i < e.changedTouches.length; i++) {
			releaseOwner('t' + e.changedTouches[i].identifier);
		}
		/* Any tracked touch that is no longer on the screen is released, even
		   when this event's identifier did not match the one we stored. */
		var alive = {};
		for (i = 0; i < e.touches.length; i++) alive['t' + e.touches[i].identifier] = true;
		var stale = [];
		Object.keys(owners).forEach(function (id) {
			if (id.charAt(0) === 't' && !alive[id]) stale.push(id);
		});
		stale.forEach(releaseOwner);
	}

	function gestureLocked() {
		var rootEl = document.documentElement;
		return rootEl.classList.contains('jt-lock') || rootEl.classList.contains('jt-native');
	}

	/* The engine draws its own touch controls and reads canvas touch events.
	   The HTML pad is only a fallback (?overlay=1, or the preview pages). */
	function useHtmlOverlay() {
		try {
			var q = new URLSearchParams(location.search);
			if (q.get('overlay') === '1') return true;
			var previewMode = q.get('preview') || '';
			return previewMode === 'menu' || previewMode === 'play';
		} catch (e) {
			return false;
		}
	}

	function htmlOverlayOpen() {
		return !!(root && !root.hidden);
	}

	function wantsTouchControls() {
		var touch = (navigator.maxTouchPoints || 0) > 0 || 'ontouchstart' in window;
		var coarse = false;
		var noHover = false;
		try {
			coarse = window.matchMedia('(pointer: coarse)').matches;
			noHover = window.matchMedia('(hover: none)').matches;
		} catch (e) {}
		return touch && (coarse || noHover);
	}

	function btn(icon, opts) {
		var el = document.createElement('button');
		el.type = 'button';
		el.className = opts.cls || '';
		el.innerHTML = ICONS[icon];
		el.setAttribute('data-hold', '');
		if (opts.act) el.setAttribute('data-act', opts.act);
		if (opts.go) el.setAttribute('data-go', opts.go);
		el.setAttribute('aria-label', opts.label);
		el.setAttribute('aria-pressed', 'false');
		return el;
	}

	function buildPad(parent, extraClass, label) {
		var pad = document.createElement('div');
		pad.className = 'jt-pad jt-cross' + (extraClass ? ' ' + extraClass : '');
		pad.setAttribute('role', 'group');
		pad.setAttribute('aria-label', label);
		[['up', 'Góra'], ['left', 'Lewo'], ['right', 'Prawo'], ['down', 'Dół']].forEach(function (pair) {
			var cell = document.createElement('div');
			cell.className = 'jt-' + pair[0];
			cell.setAttribute('data-dir', pair[0]);
			cell.setAttribute('aria-label', pair[1]);
			cell.innerHTML = ICONS[pair[0]];
			pad.appendChild(cell);
		});
		parent.appendChild(pad);
		return pad;
	}

	function setMode(mode) {
		releaseAll();
		if (!root) return;
		root.dataset.mode = mode;
		if (menuPane) menuPane.hidden = mode !== 'menu';
		if (playPane) playPane.hidden = mode !== 'play';
	}

	function show(mode) {
		document.documentElement.classList.remove('jt-native');
		document.documentElement.classList.add('jt-lock');
		root.hidden = false;
		setMode(mode || 'menu');
		var go = root.querySelector('.jt-go');
		if (go) go.hidden = !inLevel;
		focusGame();
	}

	function showMenuPad() {
		show('menu');
	}

	function enableNative() {
		pauseDepth = 0;
		pauseMoved = false;
		releaseAll();
		if (root) root.hidden = true;
		document.documentElement.classList.remove('jt-lock');
		document.documentElement.classList.add('jt-native');
		focusGame();
	}

	function enterPausePad() {
		if (useHtmlOverlay() || !inLevel) return;
		pauseDepth = 1;
		pauseMoved = false;
		showMenuPad();
	}

	function noteLog(text) {
		var line = String(text || '');
		engineLog.push(line);
		if (engineLog.length > 80) engineLog.shift();
		if (pendingCheat) pendingCheat(line);
		if (!gameOn) return;
		var back = /Going to main menu/i.test(line);
		var loaded = /Level ".+" \(from ".+\.j2l"\) loaded/i.test(line) || /Level ".+" initialized/i.test(line);
		if (!back && !loaded) return;
		inLevel = !back;
		pauseDepth = 0;
		pauseMoved = false;
		syncCheats();
		/* ?overlay=1 keeps the HTML pad for the whole session. inLevel still tracks
		   the level so the cheat button can show, without swapping that pad away. */
		if (useHtmlOverlay()) return;
		if (!wantsTouchControls() && !gestureLocked()) return;
		if (back) showMenuPad();
		else enableNative();
	}

	function hide() {
		releaseAll();
		if (root) root.hidden = true;
		document.documentElement.classList.remove('jt-lock');
		document.documentElement.classList.remove('jt-native');
	}

	function build() {
		root = document.createElement('div');
		root.id = 'jazz-touch';
		root.hidden = true;

		menuPane = document.createElement('div');
		menuPane.className = 'pane jt-menu';
		buildPad(menuPane, '', 'Kierunki menu');
		var actions = document.createElement('div');
		actions.className = 'jt-menu-actions';
		actions.appendChild(btn('play', { cls: 'jt-go', go: 'native', label: 'Wróć do sterowania w grze' }));
		actions.appendChild(btn('back', { cls: 'jt-back', act: 'back', label: 'Wstecz' }));
		actions.appendChild(btn('ok', { cls: 'jt-ok', act: 'ok', label: 'Potwierdź' }));
		menuPane.appendChild(actions);

		playPane = document.createElement('div');
		playPane.className = 'pane jt-play';
		playPane.hidden = true;
		var sys = document.createElement('div');
		sys.className = 'jt-sys';
		sys.appendChild(btn('menu', { act: 'pause', go: 'menu', label: 'Menu' }));
		sys.appendChild(btn('ok', { act: 'enter', label: 'Potwierdź' }));
		playPane.appendChild(sys);
		buildPad(playPane, 'jt-playpad', 'Ruch');

		var pad = document.createElement('div');
		pad.className = 'jt-actions';
		pad.appendChild(btn('run', { cls: 'jt-run', act: 'run', label: 'Bieg' }));
		pad.appendChild(btn('weapon', { cls: 'jt-weapon', act: 'weapon', label: 'Zmiana broni' }));
		pad.appendChild(btn('jump', { cls: 'jt-jump jt-primary', act: 'jump', label: 'Skok' }));
		pad.appendChild(btn('fire', { cls: 'jt-fire jt-primary', act: 'fire', label: 'Strzał' }));
		playPane.appendChild(pad);

		root.appendChild(menuPane);
		root.appendChild(playPane);
		root.addEventListener('contextmenu', function (e) { e.preventDefault(); });
		document.body.appendChild(root);
	}

	function installGestures() {
		window.addEventListener('pointerdown', onPointerDown, true);
		window.addEventListener('pointermove', onPointerMove, true);
		window.addEventListener('pointerup', onPointerUp, true);
		window.addEventListener('pointercancel', onPointerUp, true);
		window.addEventListener('lostpointercapture', onPointerUp, true);
		window.addEventListener('touchstart', onTouchStart, { capture: true, passive: false });
		window.addEventListener('touchmove', onTouchMove, { capture: true, passive: false });
		window.addEventListener('touchend', onTouchEnd, { capture: true, passive: false });
		window.addEventListener('touchcancel', onTouchEnd, { capture: true, passive: false });
		function block(e) {
			if (!gestureLocked()) return;
			if (e.cancelable) e.preventDefault();
		}
		document.addEventListener('gesturestart', block, { capture: true, passive: false });
		document.addEventListener('gesturechange', block, { capture: true, passive: false });
		document.addEventListener('gestureend', block, { capture: true, passive: false });
		document.addEventListener('selectstart', function (e) {
			if (gestureLocked()) e.preventDefault();
		}, true);
		window.addEventListener('touchstart', function (e) {
			if (useHtmlOverlay() || htmlOverlayOpen() || !inLevel) return;
			if (!document.documentElement.classList.contains('jt-native')) return;
			var canvas = document.getElementById('canvas');
			if (!canvas) return;
			var rect = canvas.getBoundingClientRect();
			if (!rect.width || !rect.height) return;
			for (var i = 0; i < e.changedTouches.length; i++) {
				var t = e.changedTouches[i];
				var x = (t.clientX - rect.left) / rect.width;
				var y = (t.clientY - rect.top) / rect.height;
				if (x >= 0.70 && y <= 0.24) {
					enterPausePad();
					return;
				}
			}
		}, false);
		origAdd.call(window, 'keydown', function (e) {
			if (!e.isTrusted || e.code !== 'Escape') return;
			if (useHtmlOverlay() || !inLevel || htmlOverlayOpen()) return;
			enterPausePad();
		}, true);
		document.addEventListener('visibilitychange', function () {
			if (document.hidden) releaseAll();
		});
		window.addEventListener('blur', releaseAll);
		window.addEventListener('pagehide', releaseAll);
	}

	function ensureDemo() {
		if (document.getElementById('jt-demo')) return;
		var d = document.createElement('div');
		d.id = 'jt-demo';
		d.className = 'jt-demo';
		d.innerHTML = '<div class="cap">Podgląd układu</div><ul><li class="on">Nowa gra</li><li>Opcje</li><li>Wybór poziomu</li><li>Wyniki</li></ul>';
		root.appendChild(d);
	}

	function prepareStage() {
		var ui = document.getElementById('ui');
		if (ui) ui.style.display = 'none';
		var canvas = document.getElementById('canvas');
		if (canvas) {
			canvas.style.display = 'block';
			canvas.style.background = '#071018';
		}
		gameOn = true;
	}

	function preview(mode) {
		prepareStage();
		inLevel = mode === 'play';
		show(mode === 'play' ? 'play' : 'menu');
		ensureDemo();
		syncCheats();
	}

	function previewNative() {
		prepareStage();
		inLevel = true;
		enableNative();
		syncCheats();
	}

	function previewCheats() {
		prepareStage();
		inLevel = true;
		enableNative();
		syncCheats();
		openCheats();
	}

	/* Every row is one entry of LevelHandler::ApplyCheat CheatCommands, including aliases.
	   Activation types the canonical code into the in-game console. The page always
	   passes /cheats, which sets PreferencesCache::AllowCheats, so TryInvokeCheat
	   applies it instead of reporting that cheats are not allowed. T opens the
	   console (default bind, same keyCode scheme as jump/fire). Letters are keypress
	   text, Enter submits, Escape closes the console (Menu hides it while it is open). */
	var CHEATS = [
		{ code: 'jjkill', alias: 'jjk', desc: 'Zabija postać' },
		{ code: 'jjgod', desc: 'Nieśmiertelność' },
		{ code: 'jjnext', alias: 'jjnxt', desc: 'Następny poziom' },
		{ code: 'jjguns', alias: 'jjammo', desc: 'Pełna amunicja' },
		{ code: 'jjrush', desc: 'Przyspieszenie' },
		{ code: 'jjgems', desc: 'Dodaje klejnoty' },
		{ code: 'jjbird', desc: 'Przywołuje ptaka' },
		{ code: 'jjlife', desc: 'Dodaje życia' },
		{ code: 'jjpower', desc: 'Ulepszenia broni' },
		{ code: 'jjcoins', desc: 'Dodaje monety' },
		{ code: 'jjmorph', desc: 'Zmienia postać' },
		{ code: 'jjshield', desc: 'Zmienia tarczę' },
		{ code: 'jjfly', desc: 'Lot' }
	];
	var CONSOLE_KEY = { key: 't', code: 'KeyT', keyCode: 84 };
	var BACKSPACE_KEY = { key: 'Backspace', code: 'Backspace', keyCode: 8 };
	var engineLog = [];
	var pendingCheat = null;
	var cheatBusy = false;
	var cheatBtn, cheatPanel, cheatToast, toastTimer;

	function sleep(ms) {
		return new Promise(function (resolve) { setTimeout(resolve, ms); });
	}

	function pulseKey(spec) {
		focusGame();
		dispatch('keydown', spec);
		return sleep(200).then(function () { dispatch('keyup', spec); });
	}

	function typeChar(ch) {
		var code = ch.charCodeAt(0);
		var ev;
		try {
			ev = new KeyboardEvent('keypress', {
				key: ch,
				bubbles: true,
				cancelable: true
			});
		} catch (err) {
			ev = document.createEvent('Event');
			ev.initEvent('keypress', true, true);
		}
		try {
			Object.defineProperty(ev, 'charCode', { configurable: true, get: function () { return code; } });
			Object.defineProperty(ev, 'keyCode', { configurable: true, get: function () { return code; } });
			Object.defineProperty(ev, 'which', { configurable: true, get: function () { return code; } });
		} catch (err2) {}
		window.dispatchEvent(ev);
	}

	function typeLine(text) {
		var i = 0;
		function step() {
			if (i >= text.length) return Promise.resolve();
			typeChar(text.charAt(i));
			i++;
			return sleep(40).then(step);
		}
		return step();
	}

	function engineLooksPaused() {
		if (!inLevel || !root || root.hidden) return false;
		if (useHtmlOverlay()) return root.dataset.mode === 'menu';
		return true;
	}

	function ensurePlaying() {
		if (!engineLooksPaused()) return Promise.resolve();
		/* The pause button latches Menu for a moment, so Escape sent immediately
		   is swallowed and the following Enter would confirm Resume instead of
		   the console. Wait that out, then resume once. */
		var taps = useHtmlOverlay() ? 1 : Math.max(1, pauseDepth || 1);
		var chain = sleep(450);
		var n;
		for (n = 0; n < taps; n++) {
			chain = chain.then(function () { return pulseKey(KEYS.esc); }).then(function () { return sleep(180); });
		}
		return chain.then(function () {
			if (!useHtmlOverlay()) enableNative();
			else setMode('play');
			/* The pause menu resumes on the frame that sees Escape. The console
			   toggle is ignored until that menu is gone, so wait a moment. */
			return sleep(400);
		});
	}

	function toast(text) {
		if (!cheatToast) return;
		cheatToast.textContent = text;
		cheatToast.hidden = false;
		if (toastTimer) clearTimeout(toastTimer);
		toastTimer = setTimeout(function () { cheatToast.hidden = true; }, 2200);
	}

	function cheatUiWanted() {
		if (!gameOn || !inLevel) return false;
		if (wantsTouchControls()) return true;
		/* Layout previews have no touch sensor, but they are the phone layouts. */
		try {
			var p = new URLSearchParams(location.search).get('preview') || '';
			return p === 'play' || p === 'native' || p === 'cheats';
		} catch (e) {
			return false;
		}
	}

	function syncCheats() {
		if (!cheatBtn) return;
		var show = cheatUiWanted();
		cheatBtn.hidden = !show || (cheatPanel && !cheatPanel.hidden);
	}

	function closeCheats() {
		if (!cheatPanel) return;
		cheatPanel.hidden = true;
		document.documentElement.classList.remove('jt-cheats-open');
		syncCheats();
	}

	function openCheats() {
		if (!cheatPanel) return;
		if (!gameOn || !inLevel) {
			toast('Kody działają tylko w grze');
			return;
		}
		cheatPanel.hidden = false;
		document.documentElement.classList.add('jt-cheats-open');
		var list = document.getElementById('jt-cheats-list');
		if (list) list.scrollTop = 0;
		syncCheats();
	}

	function runCheat(entry) {
		var saw = { echo: false, denied: false, unknown: false };
		pendingCheat = function (line) {
			if (line.indexOf(entry.code) >= 0) saw.echo = true;
			if (/not allowed in current context/i.test(line)) saw.denied = true;
			if (/Unknown command/i.test(line)) saw.unknown = true;
		};
		return ensurePlaying().then(function () {
			return pulseKey(CONSOLE_KEY);
		}).then(function () {
			return sleep(200);
		}).then(function () {
			return pulseKey(BACKSPACE_KEY);
		}).then(function () {
			return sleep(40);
		}).then(function () {
			return typeLine(entry.code);
		}).then(function () {
			return sleep(80);
		}).then(function () {
			return pulseKey(KEYS.enter);
		}).then(function () {
			return sleep(500);
		}).then(function () {
			pendingCheat = null;
			/* Escape closes the console when it is open, and pauses the game when
			   it is not. Only send it after the console echoed the code. */
			if (saw.echo || saw.denied || saw.unknown) return pulseKey(KEYS.esc);
			return null;
		}).then(function () {
			return saw;
		});
	}

	function activateCheat(entry) {
		if (cheatBusy) return;
		closeCheats();
		if (!gameOn || !inLevel) {
			toast('Kody działają tylko w grze');
			return;
		}
		cheatBusy = true;
		runCheat(entry).then(function (saw) {
			cheatBusy = false;
			if (saw.denied) toast('Kody są wyłączone w tej grze');
			else if (saw.unknown) toast('Silnik nie zna kodu ' + entry.code);
			else if (saw.echo) toast('Aktywowano: ' + entry.code);
			else toast('Wysłano: ' + entry.code);
		}, function () {
			cheatBusy = false;
			toast('Nie udało się wysłać kodu');
		});
	}

	function cheatIcon() {
		return '<svg viewBox="0 0 24 24" aria-hidden="true"><path class="stroke" d="M12 3.2v17.6M3.2 12h17.6M6.2 6.2l11.6 11.6M17.8 6.2L6.2 17.8"/></svg>';
	}

	function buildCheats() {
		cheatBtn = document.createElement('button');
		cheatBtn.type = 'button';
		cheatBtn.id = 'jt-cheats-btn';
		cheatBtn.hidden = true;
		cheatBtn.setAttribute('aria-label', 'Kody');
		cheatBtn.innerHTML = cheatIcon();
		cheatBtn.addEventListener('pointerup', function (e) {
			if (e.button != null && e.button !== 0) return;
			e.preventDefault();
			e.stopPropagation();
			openCheats();
		});

		cheatPanel = document.createElement('div');
		cheatPanel.id = 'jt-cheats-panel';
		cheatPanel.hidden = true;
		cheatPanel.setAttribute('role', 'dialog');
		cheatPanel.setAttribute('aria-label', 'Kody');
		var head = document.createElement('header');
		var title = document.createElement('h2');
		title.textContent = 'Kody';
		var close = document.createElement('button');
		close.type = 'button';
		close.className = 'jt-cheats-x';
		close.textContent = 'Zamknij';
		close.addEventListener('pointerup', function (e) {
			e.preventDefault();
			e.stopPropagation();
			closeCheats();
		});
		head.appendChild(title);
		head.appendChild(close);
		var list = document.createElement('div');
		list.id = 'jt-cheats-list';
		CHEATS.forEach(function (entry) {
			var row = document.createElement('button');
			row.type = 'button';
			row.className = 'jt-cheat';
			row.setAttribute('data-code', entry.code);
			var downY = 0;
			row.innerHTML = '<span class="code">' + entry.code +
				(entry.alias ? '<span class="alias">' + entry.alias + '</span>' : '') +
				'</span><span class="desc">' + entry.desc + '</span>';
			row.addEventListener('pointerdown', function (e) { downY = e.clientY; });
			row.addEventListener('pointerup', function (e) {
				if (Math.abs(e.clientY - downY) > 14) return;
				e.preventDefault();
				e.stopPropagation();
				activateCheat(entry);
			});
			list.appendChild(row);
		});
		cheatPanel.appendChild(head);
		cheatPanel.appendChild(list);
		cheatPanel.addEventListener('contextmenu', function (e) { e.preventDefault(); });

		cheatToast = document.createElement('div');
		cheatToast.id = 'jt-cheats-toast';
		cheatToast.hidden = true;
		cheatToast.setAttribute('role', 'status');

		document.body.appendChild(cheatBtn);
		document.body.appendChild(cheatPanel);
		document.body.appendChild(cheatToast);
	}

	function boot() {
		if (booted) return;
		booted = true;
		installBridge();
		installGestures();
		build();
		buildCheats();
		var previewMode = '';
		try { previewMode = new URLSearchParams(location.search).get('preview') || ''; } catch (e) {}
		if (previewMode === 'menu' || previewMode === 'play') preview(previewMode);
		else if (previewMode === 'native') previewNative();
		else if (previewMode === 'cheats') previewCheats();
	}

	function onGameStart() {
		gameOn = true;
		if (!wantsTouchControls()) return;
		if (useHtmlOverlay()) show('menu');
		else showMenuPad();
		syncCheats();
	}

	function onGameStop() {
		gameOn = false;
		inLevel = false;
		closeCheats();
		hide();
		syncCheats();
	}

	function pressed() {
		return Object.keys(held).filter(function (code) { return held[code]; });
	}

	window.JazzTouch = {
		boot: boot,
		onGameStart: onGameStart,
		onGameStop: onGameStop,
		preview: preview,
		noteLog: noteLog,
		setMode: setMode,
		wantsTouchControls: wantsTouchControls,
		pressed: pressed,
		openCheats: openCheats,
		closeCheats: closeCheats,
		activateCheat: activateCheat,
		cheats: CHEATS,
		get trace() { return trace.slice(); },
		get engineLog() { return engineLog.slice(); },
		get inLevel() { return inLevel; },
		get mode() { return root && !root.hidden ? root.dataset.mode : null; }
	};
})();
