"""Makes local test pages from src/moonfall.html in tools/out/ (not committed):

    test.html        the game with a debug handle, window.__mf, for poking at it from the browser console
    test-board.html  the same with a pretend online board (window.__board), so no real scores or stats are sent
    shot.html        drives the game into a scene for screenshots (see tools/shoot.sh)
    frame.html       shows a page at an exact phone size inside an iframe

Serve the folder and open a page:   python3 -m http.server 8766 -d tools/out   then http://localhost:8766/test.html
"""
import os, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'tools', 'out')

# The debug handle: the game's internals that the tests and screenshots reach for.
HOOK = """window.__mf = { gameOver, depthM, startLaunch, save, player, Sfx, Music, get state() { return state; }, set state(v) { state = v; }, update, render, get openT() { return openT; }, cafeInfo, get flags() { return flags; }, get rocks() { return rocks; }, get items() { return items; }, get hazards() { return hazards; }, nearMiss, collect, buyPerk, openShop, get shopOffer() { return shopOffer; }, get hitStop() { return hitStop; }, get flyers() { return flyers; }, hurt, buildFlags, get cafeT() { return cafeT; }, set cafeT(v) { cafeT = v; }, get camY() { return camY; }, edgeAt, checkCafe, prepaint, frame, DROPS, dropList, set clock(v) { clock = v; }, get shopDone() { return shopDone; } };"""

# A pretend scoreboard: answers the game's requests to fake-scores.test from memory. B.mode = 'down' fails them.
FAKE_BOARD = """window.__board = { rows: [], next: 1, mode: 'ok', calls: [] };
const __realFetch = window.fetch;
window.fetch = async (url, init = {}) => {
  if (!String(url).startsWith('https://fake-scores.test/')) return __realFetch(url, init);
  const B = window.__board; B.calls.push((init.method || 'GET') + (init.body ? ' ' + init.body : ''));
  await new Promise(r => setTimeout(r, 150));
  if (B.mode === 'down') throw new TypeError('Failed to fetch');
  const top = () => B.rows.slice().sort((a, b) => b.depth - a.depth || a.id - b.id).slice(0, 10).map(({ id, initials, depth }) => ({ id, initials, depth }));
  if ((init.method || 'GET') === 'POST') {
    const b = JSON.parse(init.body);
    if (!/^[A-Z]{3}$/.test(b.initials)) return new Response('{"error":"bad"}', { status: 400 });
    const row = { id: B.next++, initials: b.initials, depth: b.depth }; B.rows.push(row);
    const rank = B.rows.filter(r => r.depth > row.depth || (r.depth === row.depth && r.id < row.id)).length + 1;
    return new Response(JSON.stringify({ top: top(), rank, id: row.id }));
  }
  return new Response(JSON.stringify({ top: top() }));
};"""

# Scenes for screenshots: ?scene=splash|title|opening|launch|pause|cafe|sign|haz, plus options (see each branch).
SHOT = """"<style>*{transition:none!important;animation-duration:1ms!important;animation-delay:0s!important}</style><script>
(async () => {
  const q = new URLSearchParams(location.search), M = window.__mf, pl = M.player, wait = ms => new Promise(f => setTimeout(f, ms));
  document.addEventListener('visibilitychange', e => e.stopImmediatePropagation(), true);
  M.save.introSeen = true; M.save.cafeTips = !q.get('first');
  if (document.fonts) await document.fonts.ready;
  await wait(300);
  if (q.get('scene') === 'splash') { M.clock = +(q.get('ft') || 0); M.render(); M.state = 'paused'; document.title = 'ready'; return; }
  document.getElementById('splashSkip').click(); await wait(300);
  if (q.get('scene') === 'launch') {   // the ending at ?t= seconds
    M.startLaunch(); for (let i = 0; i < Math.round(+(q.get('t') || 0) * 60); i++) M.update(1 / 60);
    document.querySelectorAll('.pop').forEach(e => { if (!q.get('pops')) e.remove(); }); M.prepaint(M.camY); M.render(); document.title = 'ready'; return;
  }
  if (q.get('scene') === 'opening') {   // the intro film at ?t= seconds after it starts
    document.getElementById('introBtn').click(); await wait(100);
    for (let i = 0; i < Math.round(+(q.get('t') || 0) * 60); i++) M.update(1 / 60);
    M.render(); M.state = 'paused'; document.title = 'ready'; return;
  }
  if (q.get('scene') === 'title') {
    for (let i = 0; i < 60; i++) M.update(1 / 60);
    if (q.get('card')) { document.getElementById(q.get('card') === 'how' ? 'howBtn' : 'settingsBtn').click(); await wait(800); }
    M.render(); document.title = 'ready'; return;
  }
  document.getElementById('startBtn').click(); await wait(300);
  if (q.get('scene') === 'haz') {   // a contact sheet of the signature hazards; see tools/shoot_hazards.sh
    M.save.hints = { glaze: 1, crumble: 1, column: 1, geyser: 1, gate: 1 };
    const cv = document.getElementById('cv'), ov = document.getElementById('ov');
    const goTo = (kind, minM) => {
      for (let m = minM; m < 4400; m += 20) {
        pl.y = m * 8; const e = M.edgeAt(pl.y + 14); pl.x = (e.L + e.R) / 2; pl.aim = pl.x; pl.vx = 0; pl.inv = 9; M.state = 'play'; M.update(1 / 60);
        const h = M.hazards.find(h => h.kind === kind && h.d > pl.y + 300);
        if (h) return h;
      }
    };
    // the pilot `soon` seconds above hazard h, on the far side from it, for a few frames so its state is natural
    const pose = (h, soon, frames = 20) => {
      for (let i = 0; i < frames; i++) {
        const v = Math.max(60, pl.v || 300), back = frames - i - 1;
        pl.y = h.d - 14 - (soon + back / 60) * v; pl.x = h.side < 0 ? M.edgeAt(h.d).R - 30 : M.edgeAt(h.d).L + 30; pl.aim = pl.x; pl.vx = 0; pl.inv = 9;
        M.state = 'play'; M.update(1 / 60);
      }
      M.render();
    };
    const sheet = document.createElement('canvas'); sheet.width = 640; sheet.height = 800; const g = sheet.getContext('2d');
    g.imageSmoothingEnabled = false; g.fillStyle = '#000'; g.fillRect(0, 0, 640, 800);
    let slot = 0;
    const grab = (h, label) => {
      const y = Math.round(h.d - M.camY) - 100, sx = (slot % 2) * 320, sy = Math.floor(slot / 2) * 200;
      g.drawImage(cv, 0, y, 320, 200, sx, sy, 320, 200); g.drawImage(ov, 0, y, 320, 200, sx, sy, 320, 200);
      g.fillStyle = '#fff'; g.fillRect(sx, sy, 120, 13); g.fillStyle = '#000'; g.font = 'bold 10px monospace'; g.fillText(label, sx + 3, sy + 10);
      g.fillStyle = '#000'; g.fillRect(sx + 319, sy, 1, 200); g.fillRect(sx, sy + 199, 320, 1); slot++;
    };
    let h = goTo('glaze', 120); pose(h, 0.3); grab(h, 'glaze');
    h = goTo('crumble', 520); pose(h, 1.3); grab(h, 'crumble: shaking');
    pose(h, 0.55, 1); grab(h, 'crumble: boulder');
    h = goTo('column', 1020); pose(h, 1.0); grab(h, 'column: warning');
    pose(h, 0.3, 20); grab(h, 'column: out');
    h = goTo('geyser', 1520); { let n = 0; do { pose(h, 0.6, 1); n++; } while (!(h.on && h.p > 1.95) && n < 400); } grab(h, 'geyser: spraying');
    h = goTo('gate', 2020); pose(h, 1.15); grab(h, 'gate: growing');
    pose(h, 0.3, 20); grab(h, 'gate: solid');
    document.body.innerHTML = ''; document.body.style.cssText = 'margin:0;background:#000';
    sheet.style.cssText = 'display:block;width:640px;height:800px;image-rendering:pixelated'; document.body.appendChild(sheet);
    document.title = 'ready'; return;
  }
  if (q.get('scene') === 'pause') { for (let i = 0; i < 150; i++) M.update(1 / 60); M.render(); document.getElementById('pauseBtn').click(); await wait(300); document.title = 'ready'; return; }
  for (let i = 0; i < 150; i++) M.update(1 / 60);
  if (q.get('scene') === 'sign') {
    let k = 1; const want = +(q.get('side') || -1); while (M.cafeInfo(k).side !== want) k++;
    const C = M.cafeInfo(k); pl.y = C.Dl - 800 - 150; pl.x = 160; pl.aim = 160; pl.vx = 0;
    for (let i = 0; i < 8; i++) { pl.inv = 1; pl.x = 160; M.update(1 / 60); }
    M.rocks.length = 0; await wait(500); M.render(); M.state = 'paused'; document.title = 'ready:' + k; return;
  }
  if (q.get('scene') === 'cafe') {
    const C = M.cafeInfo(1); pl.spare = +(q.get('spare') || 5); pl.hp = 4;
    pl.y = C.Dl - 28 - 120; pl.x = C.padX; pl.aim = pl.x; pl.vx = 0; M.checkCafe();
    for (let i = 0; i < 60 * 3.2; i++) M.update(1 / 60);
    await wait(700);
    const face = q.get('face');
    if (face === 'shop') document.getElementById('shopBtn').click();
    if (face === 'tips') document.getElementById('tipsBtn').click();
    if (q.get('buy')) { await wait(600); document.querySelector('.perk:not(:disabled)').click(); }
  }
  await wait(700); document.title = 'ready:' + M.state + ':' + document.getElementById('shop').hidden + ':' + document.getElementById('hud').className;
})();
</script>"""

FRAME = """<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:#000}iframe{border:0;display:block;position:absolute;left:50%;top:50%;transform:translate(-50%,-50%)}</style></head>
<body><script>
const q = new URLSearchParams(location.search), w = +q.get('w') || 375, h = +q.get('h') || 667;
q.delete('w'); q.delete('h');
const f = document.createElement('iframe'); f.width = w; f.height = h; f.src = (q.get("page") || "shot.html") + "?" + q.toString();
document.body.append(f);
</script></body></html>
"""

HEAD = ('<!doctype html><html><head><meta charset=utf8><meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top);padding-bottom:env(safe-area-inset-bottom)}'
        'body{margin:0;font:14px system-ui}img{max-width:100%}[hidden]{display:none!important}</style></head><body>')

if __name__ == '__main__':
    game = open(os.path.join(ROOT, 'src', 'moonfall.html')).read()
    anchor = 'requestAnimationFrame(t => { last = t; frame(t); });'
    assert game.count(anchor) == 1, 'start-up line not found'
    game = game.replace(anchor, HOOK + '\n' + anchor)
    board = game.replace("const SCORES_URL = '';", "const SCORES_URL = 'https://fake-scores.test/functions/v1/scores';", 1)
    os.makedirs(OUT, exist_ok=True)
    pages = {
        'test.html': HEAD + '<script>' + FAKE_BOARD + '</script>' + game + '</body></html>',
        'test-board.html': HEAD + '<script>' + FAKE_BOARD + '</script>' + board + '</body></html>',
        'frame.html': FRAME,
    }
    local = pages['test.html']
    pages['shot.html'] = local[:local.rindex('</body>')] + SHOT + '</body></html>'
    shutil.copytree(os.path.join(ROOT, 'src', 'voices'), os.path.join(OUT, 'voices'), dirs_exist_ok=True)
    for name, html in pages.items():
        open(os.path.join(OUT, name), 'w').write(html)
    print('tools/out:', ', '.join(pages))
