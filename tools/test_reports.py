"""Run reports and scores end to end: the real game in headless Chrome, sending to the real scores function
(supabase/functions/scores/index.ts, types stripped by Node) over the pretend database in tools/fake_supabase.js.

    python3 tools/test_reports.py [game.html]       (needs Chrome, and Node 22.13+ for stripTypeScriptTypes)

Two cases from the code review of 19 November 2026, each a genuine player's score that must reach the online board:
  offline     a dive played with no network: its start and end reports and its score wait on the phone, then all go,
              reports first, when the network is back. The score must be saved (not refused because the server never
              heard of the run, nor because the reports arrived only just now), shown to its player at once, and on the
              board for everyone once its depth's time at the fastest fall has passed.
  continue    Save and quit at a cafe, then Continue dive: the continued dive names the run it carries on, the server
              credits it with that run's depth, and its score (the whole dive's depth) is on the board straight away.
The server's clock is moved on between steps (the pretend database's later()), as real time would pass while playing;
the game's own frames are stepped, so they take no real time. Exits 1 listing what failed, 2 if Chrome is missing.
"""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chrome, same_pixels, smoke, test_pages

ROOT = chrome.ROOT
FAKE_URL = 'https://fake-scores.test/functions/v1/scores'

HOOK = ("window.__rep = { syncOnline, sendPings, get hsBusy() { return hsBusy; }, get hsErr() { return hsErr; }, "
        "get hsOnline() { return hsOnline; }, get scoreOpen() { return scoreOpen; } };")

# The function as a script in the page: types stripped, wrapped so its names don't meet the game's, and its board's
# season set to a past moment so the test's scores count.
STRIP = ("import { stripTypeScriptTypes } from 'node:module'; import { readFileSync } from 'node:fs';"
         "process.stdout.write(stripTypeScriptTypes(readFileSync(process.argv[1], 'utf8')));")

# Sends the game's requests to the function (window.__board.down: as if there were no network) and records each one.
ROUTER = """window.__board = { down: false, calls: [] };
window.__fake = window.fakeSupabase();
const __toDb = window.fetch;
window.fetch = async (url, init = {}) => {
  if (!String(url).startsWith('%s')) return __toDb(url, init);
  const B = window.__board, body = init.body ? JSON.parse(init.body) : null;
  const call = { what: body ? (body.event || 'score') : 'board', run: body && body.run, status: 0 };
  B.calls.push(call);
  if (B.down) throw new TypeError('Failed to fetch');
  const res = await window.__fake.handler(new Request(url, init));
  call.status = res.status;
  return res;
};""" % FAKE_URL

DRIVER = r"""<script>
(async () => {
  const M = window.__mf, S = window.__smoke, R = window.__rep, F = window.__fake, B = window.__board, P = M.player;
  const $ = id => document.getElementById(id);
  const out = { errors: [], fails: [] }, fail = m => out.fails.push(m);
  addEventListener('error', e => out.errors.push(String(e.message || e.error)));
  addEventListener('unhandledrejection', e => out.errors.push('promise: ' + String(e.reason && e.reason.message || e.reason)));
  document.addEventListener('visibilitychange', e => e.stopImmediatePropagation(), true);
  const wait = ms => new Promise(f => setTimeout(f, ms));
  let t = performance.now() + 1000;
  const run = (n, keep) => {
    for (let i = 0; i < n; i++) {
      t += 1000 / 60; if (keep) keep(); __tools.continueCard();
      try { M.frame(t); } catch (e) { out.errors.push('frame: ' + (e && e.message || e)); }
    }
  };
  const until = (done, max, keep) => { for (let i = 0; i < max && !done(); i++) run(1, keep); };
  const settle = async () => { for (let i = 0; i < 200 && R.hsBusy; i++) await wait(20); await R.sendPings(); };
  const safe = () => { P.inv = 1; P.hp = P.max; };
  const die = () => {
    P.inv = 0; P.shield = 0; P.hp = 1; M.rocks.length = 0;
    M.rocks.push({ d: P.y + 14, x0: P.x, x: P.x, size: 1, rr: 9, amp: 0, ph: 0, sp: 1, hot: true, isMine: true, dead: false });
    until(() => M.state === 'over', 60 * 6);
  };
  // The board as anyone else sees it (no score of theirs in the answer).
  const board = async () => (await (await F.handler(new Request('%s'))).json()).top.map(r => r.id);
  // Game over, then the initials (as typed) saved: the score goes into the outbox and the game tries to send it.
  const saveInitials = async what => {
    if (M.state !== 'over' || !R.scoreOpen || $('hsEntry').hidden) { fail(what + ': no initials to enter after the death (state ' + M.state + ')'); return false; }
    $('hsSave').click(); await wait(0); await settle();
    return true;
  };
  // A new dive; its start report reaches the server (when there's a network) before the clock is moved on.
  const dive = async () => { __tools.jumpIn(); until(() => M.state === 'play', 60 * 6); await R.sendPings(); };
  if (document.fonts) await document.fonts.ready; await wait(200);
  __tools.skipSplash();
  run(30);

  // ---- offline: a whole dive and its score with no network, sent later.
  B.down = true;
  await dive();
  run(60 * 4, safe);
  const run1 = M.save.pings.length ? M.save.pings[0].run : '';
  die();
  const m1 = M.depthM();
  if (!(await saveInitials('offline'))) return finish();
  const waiting = M.save.pings.map(p => p.event + ':' + (p.run === run1 ? 'run' : p.run)).join(' ');
  if (waiting !== 'play:run end:run') fail('offline: the run\'s reports are not waiting on the phone (' + waiting + ')');
  if (M.save.outbox.length !== 1 || M.save.outbox[0].r !== run1) fail('offline: the score is not waiting with its run: ' + JSON.stringify(M.save.outbox));
  if (!R.hsErr) fail('offline: no word that the board could not be reached');
  $('hsDone').click(); run(10);
  S.toTitle(); run(10);
  F.later(3600);   // an hour later, the network is back
  B.down = false;
  await R.syncOnline(); await settle();
  const row1 = F.db.plays.find(r => r.run === run1), score1 = F.db.scores.find(r => r.run === run1);
  if (!row1 || row1.depth !== m1) fail('offline: the server has no report of the run, or the wrong depth: ' + JSON.stringify(row1));
  if (!score1 || score1.depth !== m1) fail('offline: the score never reached the server');
  if (M.save.outbox.length || M.save.pings.length) fail('offline: still waiting on the phone: ' + JSON.stringify({ outbox: M.save.outbox, pings: M.save.pings }));
  if (score1 && !(R.hsOnline && R.hsOnline.top.some(r => r.id === score1.id))) fail('offline: the player is not shown their score on the online board');
  if (score1 && m1 > 75 && (await board()).includes(score1.id)) fail('offline: on the board before its depth\'s time had passed');
  F.later(m1 / 75 + 1);
  if (score1 && !(await board()).includes(score1.id)) fail('offline: not on the board once its time had passed');

  // ---- continue: Save and quit at a cafe, then Continue dive, and a score for the whole dive.
  await dive();
  const C = M.cafeInfo(1);
  M.save.compsNew = [];
  P.y = C.Dl - 400;
  until(() => M.state === 'cafe' && M.cafeT > 1.7, 60 * 12, () => { safe(); P.x = C.padX; P.aim = P.x; });
  if (M.state !== 'cafe') { fail('continue: never reached the cafe (state ' + M.state + ')'); return finish(); }
  F.later(300);   // the dive down to the cafe took five minutes
  $('diveSaveBtn').click(); run(10);
  const kept = M.save.dive && M.save.dive.run;
  await R.sendPings();
  const first = F.db.plays.find(r => r.run === kept);
  if (!first || first.how !== 'quit') fail('continue: the saved dive\'s run is not on the server as quit: ' + JSON.stringify(first));
  $('continueBtn').click(); run(10);
  if (M.state !== 'cafe') fail('continue: Continue dive did not land at the cafe (state ' + M.state + ')');
  await R.sendPings();
  const second = F.db.plays.at(-1);
  if (!second || second.prev !== kept || !first || second.start_m !== first.depth) fail('continue: the continued run is not credited with the dive so far: ' + JSON.stringify(second));
  S.leaveCafe(); run(60 * 4, safe);
  F.later(2);   // a few seconds more of falling
  die();
  const m2 = M.depthM();
  if (!(await saveInitials('continue'))) return finish();
  const score2 = second && F.db.scores.find(r => r.run === second.run);
  if (!score2 || score2.depth !== m2) fail('continue: the whole dive\'s score (' + m2 + ' m) never reached the server');
  else if (!(await board()).includes(score2.id)) fail('continue: the whole dive\'s score is not on the board straight away');

  const refused = B.calls.filter(c => c.status === 400);
  if (refused.length) fail('the server refused ' + refused.map(c => c.what).join(', ') + ' (400)');
  finish();
  function finish() {
    out.calls = B.calls.map(c => c.what + ' ' + c.status).join(', ');
    const pre = document.createElement('pre'); pre.id = 'out'; pre.textContent = JSON.stringify(out); document.body.appendChild(pre);
  }
})();
</script>""" % FAKE_URL


def page(game, function_js):
    assert game.count("const SCORES_URL = '';") == 1, 'SCORES_URL should be empty in the game'
    game = game.replace("const SCORES_URL = '';", f"const SCORES_URL = '{FAKE_URL}';", 1)
    game = chrome.inject(game, test_pages.HOOK + '\n' + smoke.HOOK + '\n' + HOOK, 'test_reports')
    fake = open(os.path.join(ROOT, 'tools', 'fake_supabase.js'), encoding='utf-8').read()
    function_js = function_js.replace(function_js[function_js.index("const BOARD_FROM = '"):].split('\n')[0],
                                      "const BOARD_FROM = '2026-11-05T00:00:00Z';", 1)
    server = '<script>' + fake + '\n' + ROUTER + '\n(() => {\n' + function_js + '\n})();</script>'
    return test_pages.HEAD + test_pages.MUTE + same_pixels.SEEDED + server + chrome.HELPERS + game + DRIVER + '</body></html>'


def main():
    args = sys.argv[1:]
    src = args[0] if args else os.path.join(ROOT, 'src', 'moonfall.html')
    chrome.need_chrome('test_reports')
    fn = os.path.join(ROOT, 'supabase', 'functions', 'scores', 'index.ts')
    function_js = chrome.run_text(['node', '--no-warnings', '--input-type=module', '-e', STRIP, fn], check=True)[1]
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'reports.html')
        open(path, 'w', encoding='utf-8').write(page(open(src, encoding='utf-8').read(), function_js))
        dom = chrome.dump_dom(chrome.file_url(path), os.path.join(tmp, 'chrome'), 120000, 300, size='390,844')
    res = chrome.result(dom)
    if res is None:
        print('FAIL: the page did not finish (it stopped before the last step)')
        sys.exit(1)
    for e in res['errors']: print('ERROR', e)
    for f in res['fails']: print('FAIL', f)
    print('requests:', res.get('calls', ''))
    bad = len(res['errors']) + len(res['fails'])
    print('FAIL: run reports and scores (above)' if bad else 'OK: an offline dive and a continued dive both reached the online board')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
