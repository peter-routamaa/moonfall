"""Checks that a code change didn't change what the game draws: plays the same scripted session (same random numbers,
same frame times) on two versions of the game and compares fingerprints of both canvases at a series of moments.

    python3 tools/same_pixels.py <before.html> [after.html]     (after defaults to src/moonfall.html)

Both files are game sources like src/moonfall.html. Needs Google Chrome (set CHROME to its path if it isn't the Mac one).
The session covers the title, falling, mine hits, a café landing and shop, dying, the high score screen, the opening film
and the launch.
"""
import os, sys, tempfile, http.server, threading, functools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chrome

ROOT = chrome.ROOT

SEEDED = """<script>window.requestAnimationFrame = () => 0;  // the script steps frames itself
// No sound: the synthesised voice uses random numbers and the recorded clips load in the background, so with sound on
// the random sequence (and with it every particle) would depend on whether a clip had arrived yet.
window.AudioContext = window.webkitAudioContext = undefined;
Math.random = (s => () => { s |= 0; s = s + 0x6D2B79F5 | 0; let t = Math.imul(s ^ s >>> 15, 1 | s);
t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; })(12345);</script>"""

# Works with the old and new names (pl/player, ft/clock, hot/isMine), so it can compare across a rename.
DRIVER = r"""<script>
(async () => {
  const M = window.__mf, wait = ms => new Promise(f => setTimeout(f, ms)), out = [];
  document.addEventListener('visibilitychange', e => e.stopImmediatePropagation(), true);
  const P = M.player || M.pl;
  // Each pixel's whole RGBA value goes into the hash (as fight_makes.py's fpOf), so a change in one channel of one pixel shows.
  const fp = name => { for (const id of ['cv', 'ov']) { const cv = document.getElementById(id);
    const d = new Uint32Array(cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data.buffer);
    let h = 2166136261; for (let i = 0; i < d.length; i++) { h ^= d[i]; h = Math.imul(h, 16777619); } out.push(name + ':' + id + ':' + (h >>> 0).toString(16)); } };
  let t = performance.now() + 1000;
  const run = (n, keep) => { for (let i = 0; i < n; i++) { t += 1000 / 60; if (keep) keep(); __tools.continueCard(); M.frame(t); } };   // Continue on a component's card, as a player would
  const mine = () => M.rocks.push({ d: P.y + 14, x0: P.x, x: P.x, size: 1, rr: 9, amp: 0, ph: 0, sp: 1, hot: true, isMine: true, dead: false });
  if (document.fonts) await document.fonts.ready; await wait(300);
  run(30); fp('splash');
  __tools.skipSplash(); await wait(300); run(30); fp('title');
  __tools.jumpIn(); await wait(100);
  run(300, () => { P.inv = 1; }); fp('falling');
  M.rocks.length = 0; P.inv = 0; P.shield = 0; P.hp = 5; mine(); run(1); run(20); fp('mine');
  run(90 * 30, () => { P.inv = 1; P.hp = 5; }); out.push('depth:' + Math.round(P.y) + ':state:' + M.state); fp('later');
  P.y = M.cafeInfo(1).Dl - 400; run(60 * 12, () => { P.inv = 1; P.hp = 5; P.x = M.cafeInfo(1).padX; P.aim = P.x; }); out.push('cafe:' + M.state); fp('cafe');
  const shop = document.getElementById('shopBtn'); if (shop) shop.click(); await wait(800); run(10); fp('shop');
  document.getElementById('shopGo').click(); await wait(100); run(120, () => { P.inv = 1; P.hp = 5; }); fp('leftCafe');
  P.inv = 0; P.shield = 0; P.hp = 1; M.rocks.length = 0; mine(); run(200); out.push('over:' + M.state); fp('dead');
  await wait(400); (document.getElementById('introBtn') ? document.getElementById('introBtn').click() : M.startOpening()); await wait(100); run(60 * 9); fp('opening');
  run(60 * 12); out.push('afterOpening:' + M.state);
  M.startLaunch(); run(60 * 6); fp('launch1'); run(60 * 12); fp('launch2'); out.push('end:' + M.state);
  const pre = document.createElement('pre'); pre.id = 'out'; pre.textContent = JSON.stringify(out); document.body.appendChild(pre);
})();
</script>"""

def page(src_path, hook):
    import test_pages
    game = chrome.inject(open(src_path).read(), hook, 'same_pixels')
    return test_pages.HEAD + SEEDED + chrome.HELPERS + game + DRIVER + '</body></html>'

def run(html_text, tmp, name, port):
    open(os.path.join(tmp, name), 'w').write(html_text)
    # Each page gets its own profile: a shared one carried the first run's save (scores, best) into the second.
    dom = chrome.dump_dom(f'http://localhost:{port}/{name}', os.path.join(tmp, 'prof-' + name), 60000, 240, size='412,915', files=False)
    return chrome.result(dom) or ['NO RESULT']

if __name__ == '__main__':
    import test_pages
    before = sys.argv[1]; after = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'src', 'moonfall.html')
    old_hook = os.environ.get('OLD_HOOK')   # the debug handle for the old names, if they differ
    chrome.need_chrome('same_pixels')
    tmp = tempfile.mkdtemp()
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):   # no line per request (the voice clips' 404s are expected: none are copied)
            pass
    handler = functools.partial(Quiet, directory=tmp)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler); threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    a = run(page(before, old_hook or test_pages.HOOK), tmp, 'before.html', port)
    b = run(page(after, test_pages.HOOK), tmp, 'after.html', port)
    srv.shutdown()
    diff = [(x, y) for x, y in zip(a, b) if x != y]
    for x in a: print(('  ' if x in b else '≠ ') + x)
    same = a == b and 'NO RESULT' not in a
    print('SAME' if same else 'NO RESULT' if 'NO RESULT' in a + b else f'DIFFERENT ({len(diff)} of {len(a)})')
    sys.exit(0 if same else 1)
