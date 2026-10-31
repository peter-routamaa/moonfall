"""Checks that a code change didn't change what the game draws: plays the same scripted session (same random numbers,
same frame times) on two versions of the game and compares fingerprints of both canvases at a series of moments.

    python3 tools/same_pixels.py <before.html> [after.html]     (after defaults to src/moonfall.html)

Both files are game sources like src/moonfall.html. Needs Google Chrome (set CHROME to its path if it isn't the Mac one).
The session covers the title, falling, mine hits, a café landing and shop, dying, the high score screen, the opening film
and the launch.
"""
import json, os, re, subprocess, sys, tempfile, http.server, threading, functools, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = os.environ.get('CHROME', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
sys.path.insert(0, os.path.join(ROOT, 'tools'))

SEEDED = """<script>window.requestAnimationFrame = () => 0;  // the script steps frames itself
Math.random = (s => () => { s |= 0; s = s + 0x6D2B79F5 | 0; let t = Math.imul(s ^ s >>> 15, 1 | s);
t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; })(12345);</script>"""

# Works with the old and new names (pl/player, ft/clock, hot/isMine), so it can compare across a rename.
DRIVER = r"""<script>
(async () => {
  const M = window.__mf, wait = ms => new Promise(f => setTimeout(f, ms)), out = [];
  document.addEventListener('visibilitychange', e => e.stopImmediatePropagation(), true);
  const P = M.player || M.pl;
  const fp = name => { for (const id of ['cv', 'ov']) { const cv = document.getElementById(id), d = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data;
    let h = 2166136261; for (let i = 0; i < d.length; i += 3) { h ^= d[i]; h = Math.imul(h, 16777619); } out.push(name + ':' + id + ':' + (h >>> 0).toString(16)); } };
  let t = performance.now() + 1000;
  const run = (n, keep) => { for (let i = 0; i < n; i++) { t += 1000 / 60; if (keep) keep(); M.frame(t); } };
  const mine = () => M.rocks.push({ d: P.y + 14, x0: P.x, x: P.x, size: 1, rr: 9, amp: 0, ph: 0, sp: 1, hot: true, isMine: true, dead: false });
  if (document.fonts) await document.fonts.ready; await wait(300);
  run(30); fp('splash');
  document.getElementById('splashSkip').click(); await wait(300); run(30); fp('title');
  document.getElementById('startBtn').click(); await wait(100);
  run(300, () => { P.inv = 1; }); fp('falling');
  M.rocks.length = 0; P.inv = 0; P.shield = 0; P.hp = 5; mine(); run(1); run(20); fp('mine');
  run(90 * 30, () => { P.inv = 1; P.hp = 5; }); out.push('depth:' + Math.round(P.y) + ':state:' + M.state); fp('later');
  P.y = M.cafeInfo(1).Dl - 400; run(60 * 12, () => { P.inv = 1; P.hp = 5; P.x = M.cafeInfo(1).padX; P.aim = P.x; }); out.push('cafe:' + M.state); fp('cafe');
  const shop = document.getElementById('shopBtn'); if (shop) shop.click(); await wait(800); run(10); fp('shop');
  document.getElementById('shopGo').click(); await wait(100); run(120, () => { P.inv = 1; P.hp = 5; }); fp('leftCafe');
  P.inv = 0; P.shield = 0; P.hp = 1; M.rocks.length = 0; mine(); run(200); out.push('over:' + M.state); fp('dead');
  await wait(400); document.getElementById('introBtn').click(); await wait(100); run(60 * 9); fp('opening');
  run(60 * 12); out.push('afterOpening:' + M.state);
  M.startLaunch(); run(60 * 6); fp('launch1'); run(60 * 12); fp('launch2'); out.push('end:' + M.state);
  const pre = document.createElement('pre'); pre.id = 'out'; pre.textContent = JSON.stringify(out); document.body.appendChild(pre);
})();
</script>"""

def page(src_path, hook):
    import test_pages
    game = open(src_path).read()
    anchor = 'requestAnimationFrame(t => { last = t; frame(t); });'
    game = game.replace(anchor, hook + '\n' + anchor)
    return test_pages.HEAD + SEEDED + game + DRIVER + '</body></html>'

def run(html_text, tmp, name, port):
    open(os.path.join(tmp, name), 'w').write(html_text)
    r = subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--no-first-run', '--user-data-dir=' + os.path.join(tmp, 'prof'),
                        '--window-size=412,915', '--virtual-time-budget=60000', '--dump-dom', f'http://localhost:{port}/{name}'],
                       capture_output=True, text=True, timeout=240)
    m = re.search(r'<pre id="out">(.*?)</pre>', r.stdout, re.S)
    return json.loads(html.unescape(m.group(1))) if m else ['NO RESULT']

if __name__ == '__main__':
    import test_pages
    before = sys.argv[1]; after = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'src', 'moonfall.html')
    old_hook = os.environ.get('OLD_HOOK')   # the debug handle for the old names, if they differ
    tmp = tempfile.mkdtemp()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=tmp)
    handler.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler); threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    a = run(page(before, old_hook or test_pages.HOOK), tmp, 'before.html', port)
    b = run(page(after, test_pages.HOOK), tmp, 'after.html', port)
    srv.shutdown()
    diff = [(x, y) for x, y in zip(a, b) if x != y]
    for x in a: print(('  ' if x in b else '≠ ') + x)
    print('SAME' if a == b and 'NO RESULT' not in a else f'DIFFERENT ({len(diff)} of {len(a)})')
    sys.exit(0 if a == b else 1)
