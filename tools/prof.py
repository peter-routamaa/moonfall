"""Builds a profiling page that plays the whole game on a scripted, seeded run and reports, scene by scene, what each
frame costs: time, drawing calls, pixels touched, page changes and the game's own functions.

    python3 tools/prof.py [game.html] [name]     (defaults: src/moonfall.html, prof)

Writes tools/out/<name>.html. Serve tools/out and open it at a phone size, e.g.
http://localhost:8770/frame.html?w=390&h=844&page=prof.html (add &moon=jungle for the Jungle moon, &km=6 for the
length of the fall, &fp=4 to fingerprint the picture every 4th frame: run two builds that way and compare their
window.__prof.fp lists, which are also kept in localStorage as "fp:/<name>.html:<moon>"). When the tab's title says "done", the result is in window.__prof (inside the iframe) and in a
<pre id=out>. To compare a change, build the old source under another name (python3 tools/prof.py /tmp/old.html
prof-old) and read both.

The run: splash, main menu, the intro film, the leap, then a fall with every cafe landed on and each of the moon's
Leviathans fought in turn, a death, the high score screen, and the repair-and-launch ending. The pilot can't be hurt
and steers down the middle. Each frame is filed under a scene (the rock layer, a hazard on screen, a void, near a
cafe, at a cafe, the thin shaft before a Leviathan, each Leviathan's fight ...).

What to trust: the counts (rectangles, images, pixels) are exact and repeat run to run; times on a desktop are tiny
and noisy, so load the page two or three times and compare. "px" columns are the pixels the calls cover, the best
stand-in here for what a phone's graphics chip has to do. It doesn't run headless (see bench.py), and it is silent,
so the cost of sound isn't in it.
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import same_pixels, test_pages

# The game's functions that get a timer (time inside them, including what they call).
TIMED = """update render prepaint updateFace drawCinema cineCaps drawSky drawShaft drawProps drawFireworks dropList life motes
speedLines critters drawFlags drawCafeSigns drawCafe drawHazards drawDrops drawIntroPilot drawBoss drawBossShots drawFlyers
drawManSquashed drawBack drawSpurs drawAshVent dustSkyline machineSkyline drawMachineHazard leviathans paintTile readyTile backTile paintMid paintFar wedgeImg spurImg wallArt wallTile
bossStage bossBuf updateBoss updateBossShots bossFire updateHazards collide genSeg passFlags checkCafe updateCafe
updateOpening updateLaunch updateFireworks drawOpeningBridge drawIntroSpace drawSpace drawPullback drawBridge repairScene
drawRepairTools paintHills paintProps jungleTrees drawPlanet drawMoonAt drawShipAt cafeLayers cafeSignArt flagArt setDepth
setHP tapDir stepSquash drawJungleHazard elderFrame bossHides drawCanopy shipDamage shipShine placeSay renderRunParts
showCoach pop fly""".split()
# Small helpers that are only counted (a timer on these would cost more than they do).
COUNTED = """mix hash disc ring sprite spriteRows drawRow fillPoly fillEllipse ellipseIn edgeAt edgesRaw palAt pmap bline tile
spans shaftHalfW shaftCentreX cavernAt voidAt bossAt cafeInfo bossShape splitAt ledge laneX discRows drawMine drawRock
drawOrb drawBubble drawPart drawMan drawFlame burst sparks""".split()

# Loaded before the game: counts what is drawn and what the page is asked to do.
PROBE = r"""<script>
(() => {
  window.__raf = window.__raf0;
  const zero = () => ({ rect: 0, rectPx: 0, img: 0, imgPx: 0, offRect: 0, offRectPx: 0, offImg: 0, offImgPx: 0, clearPx: 0, path: 0, text: 0,
    style: 0, alpha: 0, comp: 0, pixels: 0, canvas: 0, dom: 0, layout: 0, heap: 0 });
  const PR = window.__P = { cur: null, phases: {}, frameFn: {}, zero,
    phase(name) { PR.cur = PR.phases[name] || (PR.phases[name] = { n: 0, times: [], c: zero(), fn: {}, calls: {} }); },
    wrap(name, f) {
      return function () {
        const t = performance.now();
        try { return f.apply(this, arguments); }
        finally { const d = performance.now() - t, e = PR.cur.fn[name] || (PR.cur.fn[name] = [0, 0]); e[0] += d; e[1]++; PR.frameFn[name] = (PR.frameFn[name] || 0) + d; }
      };
    },
    count(name, f) { return function () { PR.cur.calls[name] = (PR.cur.calls[name] || 0) + 1; return f.apply(this, arguments); }; },
  };
  PR.phase('load');
  const C = CanvasRenderingContext2D.prototype, on = g => g.canvas.id !== '';
  // Written out argument by argument: an `arguments` object per call would add garbage of the probe's own.
  const fr = C.fillRect, di = C.drawImage, cr = C.clearRect;
  C.fillRect = function (x, y, w, h) { const c = PR.cur.c, px = Math.abs(w * h); if (on(this)) { c.rect++; c.rectPx += px; } else { c.offRect++; c.offRectPx += px; } fr.call(this, x, y, w, h); };
  C.drawImage = function (im, a, b, d, e, f, g, h, i) {
    const c = PR.cur.c, n = arguments.length, px = Math.abs(n >= 9 ? h * i : n >= 5 ? d * e : im.width * im.height);
    if (on(this)) { c.img++; c.imgPx += px; } else { c.offImg++; c.offImgPx += px; }
    if (n >= 9) di.call(this, im, a, b, d, e, f, g, h, i); else if (n >= 5) di.call(this, im, a, b, d, e); else di.call(this, im, a, b);
  };
  C.clearRect = function (x, y, w, h) { PR.cur.c.clearPx += Math.abs(w * h); cr.call(this, x, y, w, h); };
  const patch = (name, key) => { const o = C[name]; C[name] = function () { PR.cur.c[key]++; return o.apply(this, arguments); }; };
  patch('fill', 'path'); patch('stroke', 'path'); patch('fillText', 'text'); patch('getImageData', 'pixels'); patch('putImageData', 'pixels');
  const prop = (name, key) => { const d = Object.getOwnPropertyDescriptor(C, name); Object.defineProperty(C, name, { get: d.get, set(v) { PR.cur.c[key]++; d.set.call(this, v); }, configurable: true }); };
  prop('fillStyle', 'style'); prop('globalAlpha', 'alpha'); prop('globalCompositeOperation', 'comp');
  // With &fp= every canvas is kept in memory (not on the graphics chip), so reading the picture back is quick.
  if (/[?&]fp=/.test(location.search)) { const gc = HTMLCanvasElement.prototype.getContext; HTMLCanvasElement.prototype.getContext = function (t, o) { return gc.call(this, t, Object.assign({ willReadFrequently: true }, o)); }; }
  const mk = document.createElement.bind(document);
  PR.makers = {};   // which of the game's functions made each new canvas
  document.createElement = function (tag) {
    if (tag === 'canvas') {
      PR.cur.c.canvas++;
      const names = new Error().stack.split('\n').slice(2).map(l => { const m = /at (?:Object\.|new )?([A-Za-z0-9_$.]+) \(/.exec(l); return m ? m[1] : ''; }).filter(Boolean);
      const who = (names[0] || '?') + ' < ' + (names.slice(1).find(n => !/^(disc|ring|checks|sprite|mk|frame|step|run)$/.test(n)) || '?');
      PR.makers[who] = (PR.makers[who] || 0) + 1;
    }
    return mk(tag);
  };
  // Reads that make the browser lay the page out on the spot.
  const E = Element.prototype, gb = E.getBoundingClientRect;
  E.getBoundingClientRect = function () { PR.cur.c.layout++; return gb.call(this); };
  for (const k of ['offsetWidth', 'offsetHeight', 'offsetTop', 'offsetLeft']) {
    const d = Object.getOwnPropertyDescriptor(HTMLElement.prototype, k);
    Object.defineProperty(HTMLElement.prototype, k, { get() { PR.cur.c.layout++; return d.get.call(this); }, configurable: true });
  }
  addEventListener('DOMContentLoaded', () => { PR.mo = new MutationObserver(() => {}); PR.mo.observe(document.documentElement, { subtree: true, childList: true, attributes: true, characterData: true }); });
})();
</script>"""

# Inside the game, just before it starts: put the timers on, and hand out a few more of its internals.
def inside(game):
    has = lambda n: re.search(r'\bfunction ' + n + r'\(', game)
    lines = ['{ const PR = window.__P;']
    lines += [f'{n} = PR.wrap("{n}", {n});' for n in TIMED if has(n)]
    lines += [f'{n} = PR.count("{n}", {n});' for n in COUNTED if has(n)]
    opt = lambda n: f"typeof {n} === 'undefined' ? undefined : {n}"
    lines.append('window.__px = { get launchT() { return ' + opt('launchT') + '; }, get particles() { return particles; }, '
                 'bossAt: ' + opt('bossAt') + ', voidAt: ' + opt('voidAt') + ', matI: ' + opt('matI') + ', cafeD: ' + opt('cafeD') +
                 ', OPEN: ' + opt('OPEN') + ', LAUNCH: ' + opt('LAUNCH') + ', REPAIR: ' + opt('REPAIR') +
                 ', kinds() { return ' + ("leviSet()" if 'leviSet' in game else "LEVI_KINDS") + '; }, version: VERSION }; }')
    return '\n'.join(lines)

DRIVER = r"""<script>
(async () => {
  const M = window.__mf, X = window.__px, PR = window.__P, P = M.player, q = new URLSearchParams(location.search);
  const wait = ms => new Promise(f => setTimeout(f, ms)), $ = id => document.getElementById(id);
  document.addEventListener('visibilitychange', e => e.stopImmediatePropagation(), true);
  const moon = q.get('moon') || 'dust', KM = +(q.get('km') || 0), HITCH = +(q.get('hitch') || 3), REAL = !!q.get('real'), FP = +(q.get('fp') || 0);
  // &fp=4: a fingerprint of both canvases every 4th frame, kept in localStorage under the page's name, to check that
  // two builds draw the same thing over the whole run (see the docstring). Don't read timings off such a run.
  // &shot=3198,4902: the two canvases at those frames, kept in localStorage as PNGs ("shot:/<name>.html:<moon>:<frame>:cv").
  const SHOTS = new Set((q.get('shot') || '').split(',').filter(Boolean).map(Number));
  const fps = [], fpOf = () => { let h = 2166136261; for (const id of ['cv', 'ov']) { const cv = $(id), d = new Uint32Array(cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data.buffer);
    for (let i = 0; i < d.length; i++) { h ^= d[i]; h = Math.imul(h, 16777619); } } return (h >>> 0).toString(36); };
  if (document.fonts) await document.fonts.ready; await wait(300);
  let t = performance.now() + 1000, total = 0, lastHeap = 0;
  const hitches = [], late = [], mem = performance.memory;
  let shown = 0, gaps = 0, gapN = 0;
  // One frame, filed under `name`. With &real=1 each waits for the screen's next frame, so the browser draws every one
  // as it would in play (the content is the same: the game clock still steps 1/60 s). `late` lists the frames the
  // screen had to wait for (a gap of more than 1.6 of the usual).
  const step = async name => {
    if (REAL) {
      const ts = await new Promise(f => window.__raf(f));
      if (shown) { const gap = ts - shown; if (gapN > 30 && gap > 1.6 * gaps / gapN) late.push({ scene: name, gap: +gap.toFixed(1), m: Math.round(P.y / 8) }); else { gaps += gap; gapN++; } }
      shown = ts;
    }
    PR.phase(name); const ph = PR.cur; for (const k in PR.frameFn) PR.frameFn[k] = 0;
    t += 1000 / 60;
    const a = performance.now(); M.frame(t); const ms = performance.now() - a;
    ph.n++; ph.times.push(ms); total++;
    if (SHOTS.has(total)) for (const id of ['cv', 'ov']) localStorage.setItem('shot:' + location.pathname + ':' + moon + ':' + total + ':' + id, $(id).toDataURL());
    if (FP && total % FP === 0) fps.push(total + '|' + name + '|' + Math.round(P.y) + '|' + fpOf());
    if (PR.mo) ph.c.dom += PR.mo.takeRecords().length;
    if (mem) { const h = mem.usedJSHeapSize; if (h > lastHeap && lastHeap) ph.c.heap += h - lastHeap; lastHeap = h; }
    if (ms >= HITCH) {
      const top = Object.entries(PR.frameFn).filter(e => e[0] !== 'update' && e[0] !== 'render').sort((x, y) => y[1] - x[1]).slice(0, 3).map(e => e[0] + ' ' + e[1].toFixed(1));
      hitches.push({ scene: name, ms: +ms.toFixed(1), m: Math.round(P.y / 8), frame: ph.n, top });
    }
    PR.phase('between');
  };
  const run = async (n, name, until) => { for (let i = 0; i < n && !(until && until()); i++) { await step(typeof name === 'function' ? name() : name); if (total % 240 === 0) { document.title = 'frame ' + total; if (!REAL) await wait(0); } } };
  const skipSplash = () => ($('splashSkip') || { click() { $('chooseBtn').click(); document.querySelector('.splash-moon[data-moon="' + moon + '"]').click(); $('splashBtn').click(); $('introSkip').click(); } }).click();

  await run(120, 'splash');
  if (M.applyMoon) { M.applyMoon(moon); M.save.moon = moon; }
  skipSplash(); await wait(300);
  await run(240, 'menu');
  // The intro film.
  if ($('introBtn')) $('introBtn').click(); else M.startOpening();   // the menu's Watch the intro button went in version 124
  await wait(100);
  await run(60 * 30, () => M.state !== 'opening' ? 'menu' : M.openT < X.OPEN.coffee ? 'intro: bridge' : M.openT - X.OPEN.pre < X.OPEN.dive ? 'intro: space' : 'intro: crash');
  if (M.state === 'opening') { $('introSkip').click(); await wait(100); }
  await run(60, 'menu');
  // The fall.
  $('startBtn').click(); await wait(100);
  const kinds = X.kinds(), fights = kinds.length, H = M.H;
  let cafeK = 1, atCafe = 0, fought = 0, lastBoss = null;
  for (let i = 0; i < fights; i++) M.setLevi(2 * (2 * i + 1), kinds[i]);   // cafe 1, 3, 5 ... each get the next kind
  const scene = () => {
    const s = M.state, y = P.y;
    if (s === 'intro') return 'leap';
    if (s === 'landing' || s === 'cafeJump') return 'cafe: landing and leaving';
    if (s === 'cafe') return 'cafe: at the counter';
    if (M.boss) return 'fight: ' + M.boss.kind;
    if (X.bossAt && X.bossAt(y)) return 'thin shaft and funnel';
    const C = M.cafeInfo(cafeK);
    if (C.Dl > M.camY - 200 && C.Dl < M.camY + H + 300) return 'cafe in view';
    if (X.voidAt && X.voidAt(y)) return 'void';
    const hz = M.hazards.find(h => h.d > M.camY - 150 && h.d < M.camY + H + 50);
    if (hz) return 'hazard: ' + hz.kind;
    return 'fall: layer ' + (X.matI ? X.matI(Math.floor(y / 8 / 500)) : 0);
  };
  const done = () => KM ? P.y / 8 >= KM * 1000 : fought >= fights && !M.boss && !(X.bossAt && X.bossAt(P.y));
  let guard = 0;
  while (!done() && guard++ < 90000) {
    P.inv = 1; P.hp = 5;
    while (M.cafeInfo(cafeK).Dl < P.y - 40) cafeK++;
    const C = M.cafeInfo(cafeK), e = M.edgeAt(P.y + 40);
    if (M.state === 'play' && C.Dl - P.y < 500 && C.Dl - P.y > 0) { P.x = C.padX; P.aim = P.x; P.vx = 0; }
    else P.aim = e.iR ? (P.x < (e.iL + e.iR) / 2 ? (e.L + e.iL) / 2 : (e.iR + e.R) / 2) : (e.L + e.R) / 2;
    if (M.state === 'cafe') { if (++atCafe > 300) { $('shopGo').click(); atCafe = 0; } }
    if (M.boss) lastBoss = M.boss.kind; else if (lastBoss) { fought++; lastBoss = null; }
    await step(scene());
    if (total % 240 === 0) { document.title = 'frame ' + total + ' ' + Math.round(P.y / 8) + ' m'; if (!REAL) await wait(0); }
  }
  const reached = Math.round(P.y / 8);
  // A death and the high score screen.
  P.inv = 0; P.shield = 0; P.hp = 1; M.rocks.length = 0;
  M.rocks.push({ d: P.y + 14, x0: P.x, x: P.x, size: 1, rr: 9, amp: 0, ph: 0, sp: 1, hot: true, isMine: true, dead: false });
  await run(200, () => M.state === 'over' ? 'game over screen' : 'dying');
  await wait(300); await run(120, 'game over screen');
  // The ending.
  M.startLaunch();
  let endedFor = 0;
  await run(60 * 60, () => {
    const T = X.launchT, L = X.LAUNCH;
    if (M.state === 'ended') endedFor++;
    return M.state === 'ended' ? 'ending: mission complete' : T < X.REPAIR.done ? 'ending: repair' : T < L.space ? 'ending: lift-off' : 'ending: space';
  }, () => endedFor > 120);

  const out = { version: X.version, moon, screen: 320 + 'x' + H, frames: total, reached, real: REAL, usualGap: gapN ? +(gaps / gapN).toFixed(2) : 0, scenes: {}, hitches, late, makers: PR.makers };
  for (const [name, ph] of Object.entries(PR.phases)) {
    if (!ph.n) continue;
    const ts = ph.times.slice().sort((a, b) => a - b), n = ph.n, r = v => +(v / n).toFixed(1), c = ph.c;
    out.scenes[name] = {
      frames: n, ms: +(ts.reduce((s, x) => s + x, 0) / n).toFixed(3), p95: +ts[Math.floor(n * 0.95)].toFixed(2), worst: +ts[n - 1].toFixed(1),
      rect: r(c.rect), rectKpx: r(c.rectPx / 1000), img: r(c.img), imgKpx: r(c.imgPx / 1000), offRect: r(c.offRect), offKpx: r((c.offRectPx + c.offImgPx) / 1000), offImg: r(c.offImg),
      clearKpx: r(c.clearPx / 1000), path: r(c.path), text: r(c.text), style: r(c.style), alpha: r(c.alpha), comp: r(c.comp), pixels: r(c.pixels),
      canvases: c.canvas, dom: r(c.dom), layout: r(c.layout), heapKB: r(c.heap / 1024),
      fn: Object.entries(ph.fn).sort((a, b) => b[1][0] - a[1][0]).slice(0, 14).map(([k, v]) => k + ' ' + (v[0] / n).toFixed(3) + 'ms x' + +(v[1] / n).toFixed(1)),
      calls: Object.entries(ph.calls).sort((a, b) => b[1] - a[1]).slice(0, 12).map(([k, v]) => k + ' x' + +(v / n).toFixed(1)),
    };
  }
  window.__prof = out;
  if (FP) { out.fp = fps; try { localStorage.setItem('fp:' + location.pathname + ':' + moon, JSON.stringify(fps)); } catch (e) {} }
  const pre = document.createElement('pre'); pre.id = 'out'; pre.textContent = JSON.stringify(out);
  pre.style.cssText = 'position:fixed;left:0;top:0;right:0;bottom:0;z-index:99;margin:0;padding:6px;overflow:auto;background:#fff;color:#000;font:9px monospace;white-space:pre-wrap';
  document.body.appendChild(pre); document.title = 'done';
})();
</script>"""

def page(src_path):
    game = open(src_path).read()
    anchor = 'requestAnimationFrame(t => { last = t; frame(t); });'
    assert game.count(anchor) == 1, 'start-up line not found'
    body = game.replace(anchor, inside(game) + '\n' + test_pages.HOOK + '\n' + anchor)
    return (test_pages.HEAD + '<script>window.__raf0 = window.requestAnimationFrame.bind(window);</script>' + same_pixels.SEEDED + PROBE +
            body + DRIVER + '</body></html>')

if __name__ == '__main__':
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(same_pixels.ROOT, 'src', 'moonfall.html')
    name = sys.argv[2] if len(sys.argv) > 2 else 'prof'
    out = os.path.join(same_pixels.ROOT, 'tools', 'out', name + '.html')
    open(out, 'w').write(page(src))
    print('wrote', out)
