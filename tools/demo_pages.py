"""Builds three demo copies of the game, each a few seconds from one of the three ways to finish, for trying them on a
phone (published as private claude.ai pages, each with its own save, so the real one is never touched).

    python3 tools/demo_pages.py [--check]        writes tools/out/demo-fall.html, demo-cafe.html, demo-cave.html

  fall  the ship is one plate short; a plate falls straight at him a second into the dive and finishes the repair. He
        has 1 health, so the next hit ends the dive: the congratulations card, the ending, then the drone card.
  cafe  the ship is repaired and every component fitted; the dive starts just above cafe 1. At the cafe, the Ship
        repair card's launch flies home: initials, the ending.
  cave  a fresh save; the dive starts above the deep cave (as the escape preview does) but counts for real: the chest,
        the drone, the portal, initials, the ending.
Publish each with src/voices/*.mp3 as supporting files at voices/ (the voice clips load from there; without them the
death, hurt and other voice lines are silent). Every load starts the demo again from the same save (the page's own save
is reset when it opens). The title shows
"v0.N DEMO". With --check, each demo is played headless far enough to show its setup works, and the script exits 1 if
one doesn't.
"""
import json, os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chrome

SRC = os.path.join(chrome.ROOT, 'src', 'moonfall.html')
OUT = os.path.join(chrome.ROOT, 'tools', 'out')

# Per demo: the save set up after the game has loaded and repaired it, the start depth, and what happens as play begins.
DEMOS = {
    'fall': {
        'setup': "for (const pt of PARTS) save.parts[pt.id] = pt.need; save.parts.plate = PARTS.find(pt => pt.id === 'plate').need - 1;"
                 " save.compsGot = COMPONENTS.map(cp => cp.id);",
        'start': '400',
        'play': "player.hp = 1; setHP(); items.push({ d: player.y + PILOT_CY + 300, x: player.x, kind: 'part', "
                "part: PARTS.find(pt => pt.id === 'plate'), dead: false }); showCoach('CATCH THE PLATE, THEN HIT A WALL', 4000);",
    },
    'cafe': {
        'setup': "for (const pt of PARTS) save.parts[pt.id] = pt.need; save.compsGot = COMPONENTS.map(cp => cp.id);",
        'start': '960',
        'play': "showCoach('AT THE CAFE: SHIP REPAIR, THEN LAUNCH', 4000);",
    },
    'cave': {
        'setup': '',
        'start': 'previewStartM()',
        'play': "showCoach('THE DEEP CAVE IS JUST BELOW', 4000);",
    },
}


def build(game, name):
    d = DEMOS[name]
    reps = [
        # A fresh save on every load: the page's own copy of the real save key, never the player's.
        ('<script>\n', "<script>\ntry { localStorage.removeItem('moonfall.v1'); } catch (e) {}\n"),
        ("if (!Array.isArray(save.compsNew)) save.compsNew = [];",
         "if (!Array.isArray(save.compsNew)) save.compsNew = [];\n" + d['setup']),
        ("  let startM = TEST_START_M;", "  let startM = " + d['start'] + ";"),
        ("  showCoach('TAP A SIDE, OR DRAG', 2600);", "  " + d['play']),
        ("(TEST_START_M ? ' TEST' : '')", "' DEMO'"),
        ('<title>MoonFall</title>', f'<title>MoonFall {name.capitalize()} Demo</title>'),
    ]
    for a, b in reps:
        if game.count(a) != 1:
            sys.exit(f"demo_pages: '{a.strip()[:50]}' found {game.count(a)} times in the game, not once; update DEMOS")
        game = game.replace(a, b, 1)
    return game


CHECK = r"""<script>
(async () => {
  const out = {}, T = window.__tools, M = window.__mf, wait = ms => new Promise(r => setTimeout(r, ms));
  let t = performance.now() + 1000;
  const run = n => { for (let i = 0; i < n; i++) { t += 1000 / 60; M.frame(t); } };   // stepped frames, as tools/smoke.py
  try {
    await wait(300); T.skipSplash('dust', true); run(30); T.jumpIn();
    for (let i = 0; i < 40 && !['play', 'cafe', 'cave', 'landing'].includes(M.state); i++) run(15);
    out.start = M.state; out.depth = M.depthM();
    for (let i = 0; i < 120 && !['cafe', 'cave'].includes(M.state) && !(NAME === 'fall' && M.canLaunch()); i++) run(15);
    out.end = M.state; out.ready = M.canLaunch(); out.hp = M.player.hp;
  } catch (e) { out.err = String(e); }
  const p = document.createElement('pre'); p.id = 'out'; p.textContent = JSON.stringify(out); document.body.appendChild(p);
})();
</script>"""


def check(name, page):
    import same_pixels, test_pages
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'd.html')
        body = chrome.inject(page, test_pages.HOOK, 'demo_pages')
        open(path, 'w', encoding='utf-8').write(test_pages.MUTE + test_pages.HEAD + same_pixels.SEEDED + chrome.HELPERS + body
                                                + CHECK.replace('NAME', repr(name)) + '</body></html>')
        res = chrome.result(chrome.dump_dom(chrome.file_url(path), os.path.join(tmp, 'chrome'), 120000, 300, size='390,844'))
    res = res or {'err': 'no result'}
    want = {'fall': res.get('ready') is True and res.get('hp') == 1, 'cafe': res.get('end') == 'cafe' and res.get('ready') is True,
            'cave': res.get('end') == 'cave'}[name]
    print(('OK  ' if want else 'FAIL') + f' {name}: {res}')
    return want


def main():
    game = open(SRC, encoding='utf-8').read()
    os.makedirs(OUT, exist_ok=True)
    ok = True
    for name in DEMOS:
        page = build(game, name)
        open(os.path.join(OUT, f'demo-{name}.html'), 'w', encoding='utf-8').write(page)
        print(f'tools/out/demo-{name}.html')
        if '--check' in sys.argv:
            chrome.need_chrome('demo_pages')
            ok = check(name, page) and ok
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
