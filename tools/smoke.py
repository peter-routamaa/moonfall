"""Smoke test: plays every screen and state of the game headless, on every moon, and fails on any error.

    python3 tools/smoke.py [game.html] [moon ...]        (defaults: src/moonfall.html, every moon)

Version 216 (code review: "no tests of game logic"). The other tools each look at one thing (budgets, canvases made in
a fight, pixels); this one only asks "does anything throw?", everywhere a player can go, in about half a minute:
the start screen, the intro film, the main menu and every card on it, a run (intro, falling with hazards, pause and
resume, a cafe landing, the shop, the jump back out, a death, game over, the high score table), a long fall through
the deeper layers, the self-test started and quit, the launch and the ending, and back to the menu.
It runs the real game in Chrome with the same seeded random numbers and stepped frames as tools/same_pixels.py, and
counts every uncaught error and rejected promise (the frame loop throws its errors on, see frame()). It also fails
if a step doesn't reach the state it should, which means the script or the game's flow broke, not that all is well,
and on every problem the game's own load-time checks found in its tables (window.__mfProblems, filled by
checkHazards and checkLeviathans: a hazard or Leviathan entry missing a field, or naming an attack that doesn't exist).
Exits 1 listing what failed, 2 if Chrome is missing. The website build runs it (tools/build_site.py).
"""
import json, os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import same_pixels, test_pages

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = os.environ.get('CHROME', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')

HOOK = ("window.__smoke = { setCard, openMenu, pause, resume, toTitle, leaveCafe, openShop, showEnd, perfStart, cafeCard, "
        "get perfOn() { return perfOn; }, get cardSide() { return cardSide; }, get wakeWant() { return typeof wakeWant === 'undefined' ? false : wakeWant; } };")

DRIVER = r"""<script>
(async () => {
  const M = window.__mf, S = window.__smoke, P = M.player, $ = id => document.getElementById(id);
  const out = { errors: [], steps: [], moon: new URLSearchParams(location.search).get('moon') || 'dust' };
  addEventListener('error', e => out.errors.push(String(e.message || e.error)));
  addEventListener('unhandledrejection', e => out.errors.push('promise: ' + String(e.reason && e.reason.message || e.reason)));
  document.addEventListener('visibilitychange', e => e.stopImmediatePropagation(), true);
  const wait = ms => new Promise(f => setTimeout(f, ms));
  const seen = new Set();   // every state the run passed through, frame by frame
  let t = performance.now() + 1000;
  const run = (n, keep) => { for (let i = 0; i < n; i++) { t += 1000 / 60; if (keep) keep(); try { M.frame(t); } catch (e) { out.errors.push('frame: ' + (e && e.message || e)); } seen.add(M.state); } };
  const safe = () => { P.inv = 1; P.hp = P.max; };
  // A step does something, plays some frames, and says which state it should end in ('' for any).
  const step = async (name, want, fn, frames, keep) => {
    try { await fn(); } catch (e) { out.errors.push(name + ': ' + (e && e.message || e)); }
    run(frames || 0, keep);
    const ok = !want || want.split('|').includes(M.state);
    out.steps.push({ name, state: M.state, ok });
  };
  if (document.fonts) await document.fonts.ready; await wait(200);
  out.problems = (window.__mfProblems || []).slice();   // what the game's own load-time checks found (checkHazards, checkLeviathans)
  await step('splash', 'splash', () => {}, 30);
  await step('choose moon', 'splash', () => { $('chooseBtn').click(); document.querySelector('.splash-moon[data-moon="' + out.moon + '"]').click(); }, 20);
  await step('intro film', 'opening', () => $('splashBtn').click(), 60 * 6);
  await step('skip film', 'title', () => $('introSkip').click(), 30);
  await step('menu', 'title', () => S.openMenu(), 30);
  for (const card of ['settings', 'how', 'news', 'levi', 'badges', 'unlocks', 'moons', 'kid'])
    await step('card ' + card, 'title', () => S.setCard(card, true), 20);
  await step('cards closed', 'title', () => S.setCard(null, true), 10);
  await step('start', 'intro|play', () => $('startBtn').click(), 60 * 4);
  await step('falling', 'play', () => {}, 60 * 20, safe);
  await step('pause', 'paused', () => S.pause(), 10);
  await step('resume', 'play', () => S.resume(), 10, safe);
  if (!S.wakeWant) out.errors.push('screen awake: not asked for during a run');
  // The phone's back gesture mid-run pauses instead of leaving (see phones in the game).
  await step('back gesture', 'paused', () => dispatchEvent(new PopStateEvent('popstate', { state: null })), 10);
  await step('resume after back', 'play', () => S.resume(), 10, safe);
  await step('cafe landing', 'cafe', () => { P.y = M.cafeInfo(1).Dl - 400; }, 60 * 12, () => { safe(); P.x = M.cafeInfo(1).padX; P.aim = P.x; });
  await step('shop', 'cafe', () => S.openShop(), 20);
  for (const face of ['shop', 'tips', 'repair']) await step('cafe card ' + face, 'cafe', () => S.cafeCard(face, true), 20);
  await step('cafe card closed', 'cafe', () => S.cafeCard(null, true), 10);
  await step('leave cafe', 'cafeJump|play', () => S.leaveCafe(), 60 * 3, safe);
  await step('deep fall', 'play|landing|cafe|cafeJump', () => {}, 60 * 90, safe);
  await step('back to falling', 'play', () => { if (M.state === 'cafe') S.leaveCafe(); }, 60 * 4, safe);   // the deep fall may end at a cafe
  await step('death', 'over|dying', () => { P.inv = 0; P.shield = 0; P.hp = 1; M.rocks.length = 0; M.rocks.push({ d: P.y + 14, x0: P.x, x: P.x, size: 1, rr: 9, amp: 0, ph: 0, sp: 1, hot: true, isMine: true, dead: false }); }, 60 * 4);
  await step('high scores', '', () => M.openTable && M.openTable(), 30);
  await step('back to menu', 'title', () => S.toTitle(), 30);
  if (S.wakeWant) out.errors.push('screen awake: still asked for on the menu');
  await step('self-test', 'intro|play', () => S.perfStart(), 60 * 3);
  await step('self-test quit', 'title', () => S.toTitle(), 20);
  if (S.perfOn) out.errors.push('self-test still on after quitting it');
  await step('launch', 'launch', () => M.startLaunch(), 60 * 20);
  await step('ending', 'launch|ended', () => S.showEnd(), 30);
  await step('menu again', 'title', () => S.toTitle(), 30);
  out.seen = [...seen];
  const pre = document.createElement('pre'); pre.id = 'out'; pre.textContent = JSON.stringify(out); document.body.appendChild(pre);
})();
</script>"""


def page(game):
    anchor = 'requestAnimationFrame(t => { last = t; frame(t); });'
    if game.count(anchor) != 1:
        sys.exit('smoke: could not find the start line')
    return test_pages.HEAD + same_pixels.SEEDED + game.replace(anchor, test_pages.HOOK + '\n' + HOOK + '\n' + anchor) + DRIVER + '</body></html>'


def run(src, moon):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'smoke.html')
        open(path, 'w', encoding='utf-8').write(page(open(src, encoding='utf-8').read()))
        dom = subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--no-first-run', '--user-data-dir=' + os.path.join(tmp, 'chrome'),
                              '--allow-file-access-from-files', '--window-size=390,844', '--virtual-time-budget=300000', '--dump-dom',
                              'file://' + path + '?moon=' + moon], capture_output=True, text=True, timeout=600).stdout
    m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
    if not m:
        return None
    return json.loads(m.group(1).replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>'))


def main():
    args = sys.argv[1:]
    src = args.pop(0) if args and args[0].endswith('.html') else os.path.join(ROOT, 'src', 'moonfall.html')
    if not os.path.exists(CHROME):
        print('smoke: Chrome not found at ' + CHROME + '; set CHROME to its path'); sys.exit(2)
    game = open(src, encoding='utf-8').read()
    moons = args or re.findall(r"(\w+): ", re.search(r'const LEVI_SETS = \{(.*?)\};', game, re.S).group(1))
    fails = 0
    for moon in moons:
        res = run(src, moon)
        if res is None:
            print(f'FAIL {moon}: the page did not finish (it stopped before the last step)'); fails += 1; continue
        bad = [s for s in res['steps'] if not s['ok']]
        probs = res.get('problems', [])
        for p in probs: print(f'PROBLEM {moon}: {p}')
        for e in res['errors']: print(f'ERROR {moon}: {e}')
        for s in bad: print(f"FAIL {moon}: step '{s['name']}' ended in state '{s['state']}'")
        print(f"{moon}: {len(res['steps'])} steps, {len(res['errors'])} errors, {len(bad)} steps off course, {len(probs)} problems from the game's own checks")
        unseen = sorted(set(re.findall(r"setState\('(\w+)'\)", game)) - set(res.get('seen', [])))
        for st in unseen: print(f"FAIL {moon}: the game can enter state '{st}' but the smoke test never reached it; add a step for it")
        fails += len(res['errors']) + len(bad) + len(unseen) + len(probs)
    print('FAIL: the smoke test found problems (above)' if fails else 'OK: every screen played on every moon, no errors')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
