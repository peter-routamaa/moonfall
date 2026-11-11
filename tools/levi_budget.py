"""Checks every Leviathan against the budgets in PERFORMANCE.md, on both moons, and fails if one is over.

    python3 tools/levi_budget.py [game.html]        (default: src/moonfall.html)

Run it before publishing any change to a Leviathan (its background shape, fight art, scars, anything in LEVI_DRAW,
BOSS_GEO or BOSS_ART) or anything else it draws through. It exits with 1 and says which creature and which number when
something is over, so a heavier creature can't reach the test link unnoticed (version 140: a reshaped Gnashbloom went
to 839 rectangles + 92 stamps a frame against a budget of 735 because nobody counted).

What it measures, for each creature, averaged over 30 moments of its animation (it also prints the worst moment):
  background  one frame of its far-off shape (LEVI_DRAW, as drawn in the shaft and behind a cafe): rectangles + stamps
  paint       one full fight paint, the three bossStage steps, in a settled rock colour: rectangles, stamps
  fading      the same while it fades in from its silhouette (every colour new, so nothing is stamped): rectangles
The page runs the real game code headless in Chrome (set CHROME to its path if it isn't the Mac one); counts are exact
and repeat run to run, so a change shows up as a number, not a feeling.
"""
import json, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = os.environ.get('CHROME', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')

# The budgets: the top of each range in PERFORMANCE.md's Leviathan table. Change them there and here together.
# (Version 141: background 735 -> 750 and stamps 190 -> 195, the numbers this script measures for the Mantis and the
# Nautilus, accepted since versions 131 and 110; the old table was counted with a different throwaway page.)
BUDGET = {'background': 750, 'paint_rect': 2172, 'paint_img': 195, 'fading_rect': 3334}

HOOK = """window.__lb = { LEVI_DRAW, LEVI_SETS, bossBuf, bossStage, applyMoon, palAt, setC(g) { const w = c; c = g; return w; },
  setBossTmp(cv) { bossTmp = cv; bossTmpG = cv.getContext('2d'); },
  setClock(v) { clock = v; }, setDirect(v) { stampDirect = v; }, get camY() { return camY; } };"""

PAGE = r"""<script>
window.addEventListener('load', () => setTimeout(() => {
  const L = window.__lb, out = { rows: [], errors: [] };
  const P = CanvasRenderingContext2D.prototype, n = { rect: 0, img: 0 }, fr = P.fillRect, di = P.drawImage;
  P.fillRect = function (...a) { n.rect++; return fr.apply(this, a); };
  P.drawImage = function (...a) { n.img++; return di.apply(this, a); };
  const test = document.createElement('canvas'); test.width = 480; test.height = 600; const tg = test.getContext('2d');
  const N = 30, avg = a => Math.round(a.reduce((s, v) => s + v, 0) / a.length), max = a => Math.max(...a);
  for (const moon of ['dust', 'jungle']) {
    L.applyMoon(moon);
    for (const kind of L.LEVI_SETS[moon]) {
      try {
        const bg = [], pr = [], pi = [], fd = [];
        L.setClock(0); let was = L.setC(tg); L.LEVI_DRAW[kind](240, 360, 1, 2, '#2B3A44'); L.setC(was);   // fills the disc store once
        for (let i = 0; i < N; i++) {
          L.setClock(i * 0.41); tg.clearRect(0, 0, 480, 600); n.rect = 0; n.img = 0;
          was = L.setC(tg); L.LEVI_DRAW[kind](240, 360, 1, 2, '#2B3A44'); L.setC(was);
          bg.push(n.rect + n.img);
        }
        const buf = L.bossBuf(kind), y = 6000 - L.camY;   // 750 m down: the middle of a rock layer, a settled colour
        const tmp = document.createElement('canvas'); tmp.width = buf.w; tmp.height = buf.h; L.setBossTmp(tmp);   // as bossBufs does in the thin shaft
        const paint = (fading, i) => {
          const b = { kind, k2: 2, dir: 1, rot: 0, t: 2 + i * 0.37, phase: fading ? 'enter' : 'fight', pt: fading ? 0.3 : 3, x: 160, y, sil: '#101418', d: 0 };
          L.setClock(i * 0.41); buf.stage = 0; n.rect = 0; n.img = 0;
          L.bossStage(b, buf); L.bossStage(b, buf); L.bossStage(b, buf);
          return [n.rect, n.img];
        };
        paint(false, 0);   // the first paint makes its colour images
        for (let i = 0; i < N; i++) { const [r, m] = paint(false, i); pr.push(r); pi.push(m); }
        for (let i = 0; i < N; i++) fd.push(paint(true, i)[0]);
        out.rows.push({ moon, kind, background: avg(bg), backgroundMax: max(bg), paint_rect: avg(pr), paint_img: avg(pi), paintMax: max(pr), fading_rect: avg(fd), fadingMax: max(fd) });
      } catch (e) { out.errors.push(moon + ' ' + kind + ': ' + e); }
    }
  }
  const pre = document.createElement('pre'); pre.id = 'out'; pre.textContent = JSON.stringify(out); document.body.append(pre);
  document.title = 'done';
}, 400));
</script>"""


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'src', 'moonfall.html')
    game = open(src, encoding='utf-8').read()
    anchor = 'window.claude?.hot?.ready ? window.claude.hot.ready(start)'
    if game.count(anchor) != 1:
        sys.exit('levi_budget: could not find the start line in ' + src)
    page = game.replace(anchor, HOOK + '\n' + anchor) + PAGE
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'levi-budget.html')
        open(path, 'w', encoding='utf-8').write(page)
        dom = subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--no-first-run', '--user-data-dir=' + os.path.join(tmp, 'chrome'),
                              '--allow-file-access-from-files', '--virtual-time-budget=60000', '--dump-dom', 'file://' + path],
                             capture_output=True, text=True, timeout=300).stdout
    m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
    if not m:
        sys.exit('levi_budget: the page did not finish (no result); open the game in a browser and check the console')
    res = json.loads(m.group(1).replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>'))
    over = []
    print(f"{'moon':7} {'kind':10} {'background':>16} {'paint rects':>16} {'stamps':>7} {'fading rects':>16}")
    for r in res['rows']:
        flags = []
        if r['background'] > BUDGET['background']: flags.append(f"background {r['background']} > {BUDGET['background']}")
        if r['paint_rect'] > BUDGET['paint_rect']: flags.append(f"paint {r['paint_rect']} > {BUDGET['paint_rect']}")
        if r['paint_img'] > BUDGET['paint_img']: flags.append(f"stamps {r['paint_img']} > {BUDGET['paint_img']}")
        if r['fading_rect'] > BUDGET['fading_rect']: flags.append(f"fading {r['fading_rect']} > {BUDGET['fading_rect']}")
        mark = '  OVER: ' + '; '.join(flags) if flags else ''
        print(f"{r['moon']:7} {r['kind']:10} {r['background']:>6} (max {r['backgroundMax']:>4}) {r['paint_rect']:>6} (max {r['paintMax']:>4}) "
              f"{r['paint_img']:>7} {r['fading_rect']:>6} (max {r['fadingMax']:>4}){mark}")
        if flags: over.append(r['moon'] + ' ' + r['kind'])
    print(f"\nbudgets (PERFORMANCE.md): background {BUDGET['background']} calls, paint {BUDGET['paint_rect']} rectangles and "
          f"{BUDGET['paint_img']} stamps, fading {BUDGET['fading_rect']} rectangles")
    for e in res['errors']: print('ERROR', e)
    if res['errors'] or over or len(res['rows']) < 12:
        print('FAIL' + (': over budget: ' + ', '.join(over) if over else '') + (f" ({len(res['rows'])} of 12 measured)" if len(res['rows']) < 12 else ''))
        sys.exit(1)
    print('OK: all 12 Leviathans inside the budgets')


if __name__ == '__main__':
    main()
