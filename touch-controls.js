/* Touch controls for the Jazz² Resurrection web port.
   The engine (SDL, via Emscripten) reads real keyboard state. Default binds:
   arrows move / look / crouch, V jumps, Space fires, C runs, X changes weapon,
   Enter confirms a menu, Escape is back / pause. Menus auto-repeat a held arrow.
   These buttons dispatch those keys. A real keyboard or gamepad is left alone. */
(function () {
	'use strict';

	var KEYS = {
		left:   { key: 'ArrowLeft',  code: 'ArrowLeft',  keyCode: 37 },
		right:  { key: 'ArrowRight', code: 'ArrowRight', keyCode: 39 },
		up:     { key: 'ArrowUp',    code: 'ArrowUp',    keyCode: 38 },
		down:   { key: 'ArrowDown',  code: 'ArrowDown',  keyCode: 40 },
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

	var want = {};
	var held = {};
	var real = {};
	/* A tap can go down and up before the next game frame samples the keyboard.
	   Keep every press down long enough for that sample, without holding long
	   enough to trip the menu's auto-repeat. */
	var MIN_HOLD_MS = 110;
	var trace = [];
	var booted = false;
	var gameOn = false;
	var root, menuPane, playPane, stick, knob;
	var stickId = null;
	var stickDir = { left: false, right: false, up: false, down: false };

	var origAdd = EventTarget.prototype.addEventListener;
	var origRemove = EventTarget.prototype.removeEventListener;
	var wrapped = new WeakMap();

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
		if (!spec || !(want[e.code] > 0)) {
			held[e.code] = false;
			return;
		}
		/* Let the physical keyup finish, then press the key again if a finger is still down. */
		queueMicrotask(function () {
			if (want[spec.code] > 0 && !real[spec.code]) {
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
		if (trace.length > 48) trace.shift();
	}

	function releaseKey(spec) {
		if (!held[spec.code]) return;
		held[spec.code] = false;
		if (!real[spec.code]) dispatch('keyup', spec);
	}

	function setWant(spec, down) {
		var code = spec.code;
		var prev = want[code] || 0;
		var next = Math.max(0, prev + (down ? 1 : -1));
		want[code] = next;
		if (next > 0 && !held[code]) {
			held[code] = true;
			spec._until = Date.now() + MIN_HOLD_MS;
			if (!real[code]) dispatch('keydown', spec);
		} else if (next === 0 && held[code]) {
			var wait = (spec._until || 0) - Date.now();
			if (wait > 0) {
				setTimeout(function () {
					if ((want[code] || 0) === 0) releaseKey(spec);
				}, wait);
			} else {
				releaseKey(spec);
			}
		}
	}

	function releaseAll() {
		var captured = stickId;
		stickId = null;
		Object.keys(want).forEach(function (code) { want[code] = 0; });
		Object.keys(BY_CODE).forEach(function (code) {
			if (BY_CODE[code]) BY_CODE[code]._until = 0;
		});
		Object.keys(held).forEach(function (code) {
			if (!held[code]) return;
			held[code] = false;
			if (!real[code] && BY_CODE[code]) dispatch('keyup', BY_CODE[code]);
		});
		stickDir = { left: false, right: false, up: false, down: false };
		if (knob) knob.style.transform = 'translate(-50%, -50%)';
		if (stick) {
			stick.classList.remove('is-down');
			if (captured != null) {
				try { stick.releasePointerCapture(captured); } catch (e) {}
			}
		}
		if (root) {
			var down = root.querySelectorAll('.is-down');
			for (var i = 0; i < down.length; i++) down[i].classList.remove('is-down');
		}
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

	function btn(label, opts) {
		var el = document.createElement('button');
		el.type = 'button';
		el.textContent = label;
		if (opts.cls) el.className = opts.cls;
		if (opts.act) el.setAttribute('data-act', opts.act);
		if (opts.go) el.setAttribute('data-go', opts.go);
		if (opts.label) el.setAttribute('aria-label', opts.label);
		el.setAttribute('aria-pressed', 'false');
		bindHold(el, opts.act ? ACT[opts.act] : null, opts.go || null);
		return el;
	}

	function bindHold(el, spec, go) {
		var ids = new Set();
		function down(e) {
			if (e.button != null && e.button !== 0) return;
			e.preventDefault();
			e.stopPropagation();
			try { el.setPointerCapture(e.pointerId); } catch (err) {}
			var was = ids.size;
			ids.add(e.pointerId);
			if (was === 0) {
				el.classList.add('is-down');
				el.setAttribute('aria-pressed', 'true');
				if (spec) setWant(spec, true);
				focusGame();
			}
		}
		function up(e) {
			if (!ids.has(e.pointerId)) return;
			ids.delete(e.pointerId);
			if (ids.size === 0) {
				el.classList.remove('is-down');
				el.setAttribute('aria-pressed', 'false');
				if (spec) setWant(spec, false);
				if (go) setMode(go);
			}
		}
		el.addEventListener('pointerdown', down);
		el.addEventListener('pointerup', up);
		el.addEventListener('pointercancel', up);
		el.addEventListener('contextmenu', function (e) { e.preventDefault(); });
	}

	function focusGame() {
		var canvas = document.getElementById('canvas');
		if (canvas && canvas.focus) {
			try { canvas.focus({ preventScroll: true }); } catch (e) { canvas.focus(); }
		}
	}

	function setMode(mode) {
		releaseAll();
		if (!root) return;
		root.dataset.mode = mode;
		if (menuPane) menuPane.hidden = mode !== 'menu';
		if (playPane) playPane.hidden = mode !== 'play';
	}

	function show(mode) {
		document.documentElement.classList.add('jt-lock');
		root.hidden = false;
		setMode(mode || 'menu');
		focusGame();
	}

	function hide() {
		releaseAll();
		if (root) root.hidden = true;
		document.documentElement.classList.remove('jt-lock');
	}

	function moveStick(e) {
		var rect = stick.getBoundingClientRect();
		var cx = rect.left + rect.width / 2;
		var cy = rect.top + rect.height / 2;
		var radius = rect.width / 2;
		var dx = e.clientX - cx;
		var dy = e.clientY - cy;
		var dist = Math.hypot(dx, dy);
		var nx = dist ? dx / dist : 0;
		var ny = dist ? dy / dist : 0;
		var clamped = Math.min(dist, radius * 0.62);
		knob.style.transform = 'translate(calc(-50% + ' + (nx * clamped) + 'px), calc(-50% + ' + (ny * clamped) + 'px))';
		var next = { left: false, right: false, up: false, down: false };
		if (dist > radius * 0.22) {
			if (nx <= -0.38) next.left = true;
			if (nx >= 0.38) next.right = true;
			if (ny <= -0.38) next.up = true;
			if (ny >= 0.38) next.down = true;
		}
		['left', 'right', 'up', 'down'].forEach(function (dir) {
			if (stickDir[dir] !== next[dir]) {
				stickDir[dir] = next[dir];
				setWant(KEYS[dir], next[dir]);
			}
		});
	}

	function endStick(e) {
		if (e.pointerId !== stickId) return;
		stickId = null;
		stick.classList.remove('is-down');
		['left', 'right', 'up', 'down'].forEach(function (dir) {
			if (stickDir[dir]) {
				stickDir[dir] = false;
				setWant(KEYS[dir], false);
			}
		});
		knob.style.transform = 'translate(-50%, -50%)';
	}

	function buildStick(parent) {
		stick = document.createElement('div');
		stick.className = 'jt-stick';
		stick.setAttribute('role', 'group');
		stick.setAttribute('aria-label', 'Ruch');
		stick.innerHTML = '<div class="jt-knob"></div><span class="n">▲</span><span class="e">▶</span><span class="s">▼</span><span class="w">◀</span>';
		knob = stick.querySelector('.jt-knob');
		stick.addEventListener('pointerdown', function (e) {
			if (stickId != null) return;
			if (e.button != null && e.button !== 0) return;
			e.preventDefault();
			e.stopPropagation();
			stickId = e.pointerId;
			stick.classList.add('is-down');
			try { stick.setPointerCapture(e.pointerId); } catch (err) {}
			focusGame();
			moveStick(e);
		});
		stick.addEventListener('pointermove', function (e) {
			if (e.pointerId !== stickId || (playPane && playPane.hidden)) return;
			moveStick(e);
		});
		stick.addEventListener('pointerup', endStick);
		stick.addEventListener('pointercancel', endStick);
		stick.addEventListener('contextmenu', function (e) { e.preventDefault(); });
		parent.appendChild(stick);
	}

	function build() {
		root = document.createElement('div');
		root.id = 'jazz-touch';
		root.hidden = true;

		menuPane = document.createElement('div');
		menuPane.className = 'pane jt-menu';
		var cross = document.createElement('div');
		cross.className = 'jt-cross';
		cross.appendChild(btn('▲', { cls: 'jt-up', act: 'up', label: 'Góra' }));
		cross.appendChild(btn('◀', { cls: 'jt-left', act: 'left', label: 'Lewo' }));
		cross.appendChild(btn('▶', { cls: 'jt-right', act: 'right', label: 'Prawo' }));
		cross.appendChild(btn('▼', { cls: 'jt-down', act: 'down', label: 'Dół' }));
		menuPane.appendChild(cross);

		var actions = document.createElement('div');
		actions.className = 'jt-menu-actions';
		actions.appendChild(btn('W GRZE', { cls: 'jt-go', go: 'play', label: 'Pokaż sterowanie w grze' }));
		actions.appendChild(btn('WSTECZ', { cls: 'jt-back', act: 'back', label: 'Wstecz' }));
		actions.appendChild(btn('OK', { cls: 'jt-ok', act: 'ok', label: 'Potwierdź' }));
		menuPane.appendChild(actions);

		playPane = document.createElement('div');
		playPane.className = 'pane jt-play';
		playPane.hidden = true;
		var sys = document.createElement('div');
		sys.className = 'jt-sys';
		sys.appendChild(btn('MENU', { act: 'pause', go: 'menu', label: 'Menu' }));
		sys.appendChild(btn('OK', { cls: 'jt-ok', act: 'enter', label: 'Potwierdź' }));
		playPane.appendChild(sys);
		buildStick(playPane);

		var pad = document.createElement('div');
		pad.className = 'jt-actions';
		pad.appendChild(btn('BIEG', { cls: 'jt-run', act: 'run', label: 'Bieg' }));
		pad.appendChild(btn('BROŃ', { cls: 'jt-weapon', act: 'weapon', label: 'Zmiana broni' }));
		pad.appendChild(btn('SKOK', { cls: 'jt-jump jt-primary', act: 'jump', label: 'Skok' }));
		pad.appendChild(btn('STRZAŁ', { cls: 'jt-fire jt-primary', act: 'fire', label: 'Strzał' }));
		playPane.appendChild(pad);

		root.appendChild(menuPane);
		root.appendChild(playPane);
		root.addEventListener('contextmenu', function (e) { e.preventDefault(); });
		document.body.appendChild(root);
	}

	function installGestures() {
		function block(e) {
			if (!document.documentElement.classList.contains('jt-lock')) return;
			if (e.cancelable) e.preventDefault();
		}
		document.addEventListener('touchstart', block, { capture: true, passive: false });
		document.addEventListener('touchmove', block, { capture: true, passive: false });
		document.addEventListener('gesturestart', block, { capture: true, passive: false });
		document.addEventListener('gesturechange', block, { capture: true, passive: false });
		document.addEventListener('gestureend', block, { capture: true, passive: false });
		document.addEventListener('selectstart', function (e) {
			if (document.documentElement.classList.contains('jt-lock')) e.preventDefault();
		}, true);
		document.addEventListener('touchstart', function () {
			if (gameOn && root && root.hidden) show('menu');
		}, { capture: true, passive: true });
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

	function preview(mode) {
		var ui = document.getElementById('ui');
		if (ui) ui.style.display = 'none';
		var canvas = document.getElementById('canvas');
		if (canvas) {
			canvas.style.display = 'block';
			canvas.style.background = '#071018';
		}
		gameOn = true;
		show(mode === 'play' ? 'play' : 'menu');
		ensureDemo();
	}

	function boot() {
		if (booted) return;
		booted = true;
		installBridge();
		installGestures();
		build();
		var previewMode = '';
		try { previewMode = new URLSearchParams(location.search).get('preview') || ''; } catch (e) {}
		if (previewMode === 'menu' || previewMode === 'play') preview(previewMode);
	}

	function onGameStart() {
		gameOn = true;
		if (wantsTouchControls()) show('menu');
	}

	function onGameStop() {
		gameOn = false;
		hide();
	}

	window.JazzTouch = {
		boot: boot,
		onGameStart: onGameStart,
		onGameStop: onGameStop,
		preview: preview,
		setMode: setMode,
		wantsTouchControls: wantsTouchControls,
		get trace() { return trace.slice(); },
		get mode() { return root && !root.hidden ? root.dataset.mode : null; }
	};
})();
