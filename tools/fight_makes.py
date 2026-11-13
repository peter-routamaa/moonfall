"""Finds what a Leviathan fight builds in the middle of play: every canvas made from the moment the fight starts, when
it was made (before the first shot, during the first volleys, later) and which function made it.

    python3 tools/fight_makes.py [game.html] [moon ...] [--fp=3]     (defaults: src/moonfall.html, every moon)

A phone stutters when a frame has to build something (PERFORMANCE.md rule 1). The profiler's totals hide when in a
fight the building happens; this lists it against the fight's own clock. It plays the real game headless in Chrome on
the profiler's seeded run (every cafe landed on, each of the moon's Leviathans fought in turn, the pilot unhurt) and
prints, for each fight, the canvases made per stretch of the fight and their makers. Exits 1 if any fight makes a
canvas after it has started (the thin shaft before it is where a fight's images belong), or if any frame of the run
in which the pilot is moving makes more than BURST canvases (version 180: one new disc or ring image a frame; before,
a creature or hazard seen for the first time made up to 21 at once). Standing at a cafe counter doesn't count.

It also prints what a settled fight costs a frame (rectangles and stamps, on screen and into the paint canvases), to
compare with another build: python3 tools/fight_makes.py /tmp/old.html. With --fp=3 it fingerprints the picture every
3rd frame of the whole run and prints one line per moon; two builds that print the same line drew the same pictures
(the lists are written to tools/out/fight-fp-<moon>.json, to find where two builds part).
"""
import json, os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import same_pixels, test_pages

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BURST = 6   # canvases in one frame while he is moving (version 180 makes at most 5)
CHROME = os.environ.get('CHROME', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')

HOOK = "window.__fm = { kinds() { return leviSet(); }, bossAt, get warm() { return typeof bossWarm === 'undefined' ? null : bossWarm; } };"

DRIVER = r"""<script>
(async () => {
  const M = window.__mf, X = window.__fm, P = M.player, q = new URLSearchParams(location.search);
  const wait = ms => new Promise(f => setTimeout(f, ms)), $ = id => document.getElementById(id);
  const moon = q.get('moon') || 'dust', FP = +(q.get('fp') || 0), out = { moon, fights: [], errors: [], fp: [], burst: { n: 0 }, busy: 0 };
  const fpOf = () => { let h = 2166136261; for (const id of ['cv', 'ov']) { const cv = $(id), d = new Uint32Array(cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data.buffer);
    for (let i = 0; i < d.length; i++) { h ^= d[i]; h = Math.imul(h, 16777619); } } return (h >>> 0).toString(36); };
  window.addEventListener('error', e => out.errors.push(String(e.message)));
  try {
    if (document.fonts) await document.fonts.ready; await wait(300);
    let t = performance.now() + 1000, made = [];
    const mk = document.createElement.bind(document);
    document.createElement = function (tag) {
      if (tag === 'canvas') {
        const names = new Error().stack.split('\n').slice(2).map(l => { const m = /at (?:Object\.|new )?([A-Za-z0-9_$.]+) \(/.exec(l); return m ? m[1] : ''; }).filter(Boolean);
        made.push((names[0] || '?') + ' < ' + (names.slice(1).find(n => !/^(disc|ring|checks|sprite|mk|frame|step|run|render|update)$/.test(n)) || '?'));
      }
      return mk(tag);
    };
    // What a fight's frames cost once it has settled (3 s in): rectangles and stamps, on screen and into other canvases.
    const C = CanvasRenderingContext2D.prototype, fr = C.fillRect, di = C.drawImage, n = { rect: 0, img: 0, offRect: 0, offImg: 0 };
    C.fillRect = function (x, y, w, h) { if (this.canvas.id) n.rect++; else n.offRect++; fr.call(this, x, y, w, h); };
    C.drawImage = function (...a) { if (this.canvas.id) n.img++; else n.offImg++; return di.apply(this, a); };
    const step = () => { t += 1000 / 60; M.frame(t); };
    for (let i = 0; i < 60; i++) step();
    if (M.applyMoon) { M.applyMoon(moon); M.save.moon = moon; }
    ($('splashSkip') || { click() { $('chooseBtn').click(); document.querySelector('.splash-moon[data-moon="' + moon + '"]').click(); $('splashBtn').click(); $('introSkip').click(); } }).click(); await wait(300);
    for (let i = 0; i < 120; i++) step();
    $('startBtn').click(); await wait(100);
    const kinds = X.kinds(), fights = kinds.length;
    for (let i = 0; i < fights; i++) M.setLevi(2 * (2 * i + 1), kinds[i]);
    let cafeK = 1, atCafe = 0, fought = 0, cur = null, guard = 0, shaft = [], shaftFrames = 0, shaftMax = 0; const sc = { rect: 0, img: 0, offRect: 0, offImg: 0 };
    while (fought < fights && guard++ < 120000) {
      P.inv = 1; P.hp = 5;
      while (M.cafeInfo(cafeK).Dl < P.y - 40) cafeK++;
      const C = M.cafeInfo(cafeK), e = M.edgeAt(P.y + 40);
      if (M.state === 'play' && C.Dl - P.y < 500 && C.Dl - P.y > 0) { P.x = C.padX; P.aim = P.x; P.vx = 0; }
      else P.aim = e.iR ? (P.x < (e.iL + e.iR) / 2 ? (e.L + e.iL) / 2 : (e.iR + e.R) / 2) : (e.L + e.R) / 2;
      if (M.state === 'cafe') { if (++atCafe > 300) { $('shopGo').click(); atCafe = 0; } }
      made = []; n.rect = n.img = n.offRect = n.offImg = 0;
      const before = M.bossShots.length, was = M.state;
      step();
      if (was !== 'cafe' && made.length > out.burst.n) out.burst = { n: made.length, m: Math.round(P.y / 8), state: was, who: made.slice() };
      if (was !== 'cafe' && made.length >= 3) out.busy++;
      const b = M.boss;
      if (b && !cur) cur = { kind: b.kind, shaft, shaftFrames, shaftMax, shaftCost: { ...sc }, warm: X.warm ? X.warm.paints : -1, cost: { frames: 0, rect: 0, img: 0, offRect: 0, offImg: 0 }, first: -1, volleys: [], makes: [], secs: 0 };
      if (!b && X.bossAt(P.y + 200)) { shaft = shaft.concat(made); shaftFrames++; shaftMax = Math.max(shaftMax, made.length); for (const k in n) sc[k] += n[k]; }   // the thin shaft before it: where its images belong
      if (!X.bossAt(P.y + 200)) { shaft = []; shaftFrames = 0; shaftMax = 0; for (const k in sc) sc[k] = 0; }
      if (cur && b) {
        cur.secs = b.t;
        if (b.t >= 3 && b.phase !== 'crash') { cur.cost.frames++; for (const k in n) cur.cost[k] += n[k]; }
        if (M.bossShots.length > before) { if (cur.first < 0) cur.first = b.t; if (!cur.volleys.length || b.t - cur.volleys[cur.volleys.length - 1] > 0.25) cur.volleys.push(+b.t.toFixed(2)); }
        for (const who of made) cur.makes.push({ t: +b.t.toFixed(2), phase: b.phase, who });
      }
      if (cur && !b) { out.fights.push(cur); cur = null; fought++; shaft = []; shaftFrames = 0; shaftMax = 0; for (const k in sc) sc[k] = 0; }
      if (FP && guard % FP === 0) out.fp.push(guard + '|' + (b ? b.kind + ' ' + b.t.toFixed(2) : M.state) + '|' + Math.round(P.y) + '|' + fpOf());
      if (guard % 240 === 0) await wait(0);
    }
    out.reached = Math.round(P.y / 8);
  } catch (e) { out.errors.push(String(e && e.stack || e)); }
  const pre = document.createElement('pre'); pre.id = 'out'; pre.textContent = JSON.stringify(out); document.body.append(pre);
  document.title = 'done';
})();
</script>"""


def page(game):
    anchor = 'requestAnimationFrame(t => { last = t; frame(t); });'
    if game.count(anchor) != 1:
        sys.exit('fight_makes: could not find the start line')
    return test_pages.HEAD + same_pixels.SEEDED + game.replace(anchor, test_pages.HOOK + '\n' + HOOK + '\n' + anchor) + DRIVER + '</body></html>'


def run(src, moon, fp=0):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'fight-makes.html')
        open(path, 'w', encoding='utf-8').write(page(open(src, encoding='utf-8').read()))
        dom = subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--no-first-run', '--user-data-dir=' + os.path.join(tmp, 'chrome'),
                              '--allow-file-access-from-files', '--window-size=390,844', '--virtual-time-budget=900000', '--dump-dom',
                              'file://' + path + '?moon=' + moon + ('&fp=' + str(fp) if fp else '')], capture_output=True, text=True, timeout=900).stdout
    m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
    if not m:
        sys.exit('fight_makes: the page did not finish for ' + moon)
    return json.loads(m.group(1).replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>'))


def main():
    args = sys.argv[1:]
    fp = next((int(a[5:]) for a in args if a.startswith('--fp=')), 0)
    args = [a for a in args if not a.startswith('--')]
    src = args.pop(0) if args and args[0].endswith('.html') else os.path.join(ROOT, 'src', 'moonfall.html')
    game = open(src, encoding='utf-8').read()
    moons = args or re.findall(r"(\w+): ", re.search(r'const LEVI_SETS = \{(.*?)\};', game, re.S).group(1))
    if not os.path.exists(CHROME):
        print('fight_makes: Chrome not found at ' + CHROME + '; set CHROME to its path'); sys.exit(2)
    bad = burst = 0
    for moon in moons:
        res = run(src, moon, fp)
        if fp:
            import hashlib
            os.makedirs(os.path.join(ROOT, 'tools', 'out'), exist_ok=True)
            json.dump(res['fp'], open(os.path.join(ROOT, 'tools', 'out', 'fight-fp-' + moon + '.json'), 'w'))
            print(f"{moon}: picture fingerprint {hashlib.sha1(json.dumps(res['fp']).encode()).hexdigest()[:12]} over {len(res['fp'])} frames")
        for e in res['errors']: print('ERROR', moon, e)
        print(f"\n{moon}: {len(res['fights'])} fights, reached {res.get('reached')} m")
        b = res['burst']; burst = max(burst, b['n'])
        if b['n']:
            who = {}
            for w in b['who']: who[w] = who.get(w, 0) + 1
            print(f"  most canvases in one moving frame: {b['n']} (at {b['m']} m, {b['state']}: " + ', '.join(f'{n} x {k}' for k, n in who.items()) + f"); frames with 3 or more: {res['busy']}")
        for f in res['fights']:
            first = f['first']
            enter = [m for m in f['makes'] if first < 0 or m['t'] < first]
            v1 = [m for m in f['makes'] if first >= 0 and first <= m['t'] < first + 2]
            later = [m for m in f['makes'] if first >= 0 and m['t'] >= first + 2]
            bad += len(f['makes'])
            warm = '' if f.get('warm', -1) < 0 else f"   ({f['warm']} warm-up paints)"
            print(f"  {f['kind']:10} thin shaft {len(f['shaft']):3}   before first shot ({first:.2f} s) {len(enter):3}   first 2 s of shots {len(v1):3}   later {len(later):3}   ({f['secs']:.0f} s){warm}")
            sc, sf = f.get('shaftCost'), f.get('shaftFrames')
            if sc and sf:
                print(f"      approach ({sf} frames): at most {f['shaftMax']} canvases in one frame; per frame: paint rectangles {sc['offRect'] / sf:.0f}, paint stamps {sc['offImg'] / sf:.0f}, screen rectangles {sc['rect'] / sf:.0f}, screen stamps {sc['img'] / sf:.0f}")
            k = f.get('cost')
            if k and k['frames']:
                print('      settled, per frame: ' + ', '.join(f"{name} {k[key] / k['frames']:.0f}" for name, key in (('screen rectangles', 'rect'), ('screen stamps', 'img'), ('paint rectangles', 'offRect'), ('paint stamps', 'offImg'))))
            who = {}
            for m in f['makes']: who[m['who']] = who.get(m['who'], 0) + 1
            for k, n in sorted(who.items(), key=lambda kv: -kv[1])[:6]: print(f"      {n:3} x {k}")
            if f['makes']:
                times = sorted(set(m['t'] for m in f['makes']))
                print('      at ' + ' '.join(f'{t:g}' for t in times[:24]) + (' ...' if len(times) > 24 else ''))
    print(f"\n{'FAIL' if bad or burst > BURST else 'OK'}: {bad} canvases made after a fight started; at most {burst} in one moving frame (limit {BURST})")
    sys.exit(1 if bad or burst > BURST else 0)


if __name__ == '__main__':
    main()
