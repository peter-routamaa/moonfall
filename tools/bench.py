"""Builds two benchmark pages that time the game's frames on the same scripted run, so a drawing change can be
compared with the code before it.

    python3 tools/bench.py <before.html> [after.html]     (after defaults to src/moonfall.html)

Both files are game sources like src/moonfall.html. It writes tools/out/bench-before.html and bench-after.html. Serve
tools/out (python3 -m http.server 8766 -d tools/out) and open each in a normal browser: after a few seconds the result
appears at the top. Each page plays the same seeded run (no sound, he can't be hurt, steering down the middle) for
60 seconds of game time, about 2 km through the first four rock layers, timing every frame (update and drawing).
Load each page a few times and compare the best runs. It doesn't run headless: headless Chrome's simulated clock
stands still inside a frame, so every time reads 0.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import same_pixels, test_pages

DRIVER = r"""<script>
(async () => {
  const M = window.__mf, wait = ms => new Promise(f => setTimeout(f, ms)), P = M.player;
  document.addEventListener('visibilitychange', e => e.stopImmediatePropagation(), true);
  if (document.fonts) await document.fonts.ready; await wait(300);
  let t = performance.now() + 1000;
  const step = () => { t += 1000 / 60; M.frame(t); };
  document.getElementById('splashSkip').click(); await wait(300);
  for (let i = 0; i < 60; i++) step();
  document.getElementById('startBtn').click(); await wait(100);
  const times = [];
  for (let i = 0; i < 3600; i++) {
    P.inv = 1; P.hp = 5;
    const e = M.edgeAt(P.y + 40);
    P.aim = e.iR ? (P.x < (e.iL + e.iR) / 2 ? (e.L + e.iL) / 2 : (e.iR + e.R) / 2) : (e.L + e.R) / 2;
    if (M.state === 'cafe') document.getElementById('shopGo').click();
    const a = performance.now(); step(); times.push(performance.now() - a);
  }
  times.sort((x, y) => x - y);
  const b = { avg: times.reduce((s, x) => s + x, 0) / times.length, p95: times[Math.floor(times.length * 0.95)], p99: times[Math.floor(times.length * 0.99)], depth: Math.round(P.y / 8) };
  window.__bench = b;
  const pre = document.createElement('pre'); pre.id = 'out';
  pre.style.cssText = 'position:fixed;left:0;top:0;z-index:99;margin:0;padding:6px;background:#fff;color:#000;font:12px monospace';
  pre.textContent = JSON.stringify(b); document.body.appendChild(pre);
})();
</script>"""

def page(src_path):
    game = open(src_path).read()
    anchor = 'requestAnimationFrame(t => { last = t; frame(t); });'
    game = game.replace(anchor, test_pages.HOOK + '\n' + anchor)
    return test_pages.HEAD + same_pixels.SEEDED + game + DRIVER + '</body></html>'

if __name__ == '__main__':
    before = sys.argv[1]; after = sys.argv[2] if len(sys.argv) > 2 else os.path.join(same_pixels.ROOT, 'src', 'moonfall.html')
    out = os.path.join(same_pixels.ROOT, 'tools', 'out')
    for name, path in (('before', before), ('after', after)):
        open(os.path.join(out, 'bench-' + name + '.html'), 'w').write(page(path))
    print('wrote tools/out/bench-before.html and tools/out/bench-after.html')
