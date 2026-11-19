"""Builds the website copy of the game, docs/index.html (served by GitHub Pages), from src/moonfall.html.

    python3 tools/build_site.py              # with the online board (the project's Supabase function)
    python3 tools/build_site.py --offline    # without it: scores stay on the device, no stats are sent
    python3 tools/build_site.py --dirty      # a local try: build even with uncommitted changes (never release this)

src/moonfall.html is the game exactly as published on claude.ai, where SCORES_URL is empty. This wraps it in a normal
web page (doctype, head, the same base styles the claude.ai page adds), fills in SCORES_URL, and copies the voice clips
(src/voices/) to docs/voices/. It also fills in UPDATE_URL and writes docs/version.json ({"v": VERSION}), which
open pages ask to find out a newer version is out and reload.

It refuses to build a game that should not go live, so a release cannot skip these checks whoever runs it:
  - src/, tools/ and supabase/ must have no uncommitted changes (or untracked files), so what is built and checked is
    what the commit holds; --dirty allows them for a local try;
  - TEST_START_M must be 0 (a test copy that starts deep in the moon must never reach the website);
  - VERSION must be greater than the one in docs/version.json: open pages only reload when it goes up, so a changed
    game under the same number would never reach them. The same number is allowed only when the page built is
    exactly the docs/index.html already there (a rebuild that changes nothing);
  - tools/levi_budget.py must say OK (every Leviathan inside the drawing budgets in PERFORMANCE.md);
  - tools/fight_makes.py must say OK (no canvas made in the middle of a Leviathan fight, and no burst of them in a
    frame while he is moving; it plays all the fights, about a minute).
  - tools/checks.py must say OK (quick source checks from CODING.md: rude initials in step, code map, no history in
    comments, no hidden names, long lines and deep ternaries within their ratchets, every sound freed);
  - tools/smoke.py must say OK (every screen and state played on every moon with no error; about 20 seconds);
  - node tools/test_function.mjs must pass (the scores function against a pretend database; needs Node 22.13+);
  - tools/test_reports.py must say OK (the game and the scores function together: an offline dive and a continued
    dive must both reach the online board; a few seconds).
Each stops the build (exit 1) before anything in docs/ is touched.
"""
import json, os, re, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCORES_URL = 'https://ukjajizsnowmdjziqkof.supabase.co/functions/v1/scores'   # public; it's in the built page anyway

SITE = 'https://peter-routamaa.github.io/moonfall/'   # where GitHub Pages serves it; link previews need full addresses
FLAGS = {'--offline', '--dirty'}


def stop(why):
    sys.exit('build_site: stopped. ' + why)


unknown = [a for a in sys.argv[1:] if a not in FLAGS]
if unknown:
    stop('unknown option ' + ' '.join(unknown) + ' (it takes ' + ', '.join(sorted(FLAGS)) + ').')
url = '' if '--offline' in sys.argv else SCORES_URL

# Uncommitted changes: the build checks and publishes the working copy, which must be what the commit holds.
st = subprocess.run(['git', '-C', ROOT, 'status', '--porcelain', '--untracked-files=all', '--', 'src', 'tools', 'supabase'],
                    capture_output=True, text=True)
if st.returncode != 0:
    stop('git status failed, so it is unknown whether src/, tools/ and supabase/ are committed:\n' + st.stderr.strip())
# Python's own caches (made by running the tools) don't count.
dirty = [line[3:] for line in st.stdout.splitlines() if line.strip() and '__pycache__/' not in line]
if dirty and '--dirty' not in sys.argv:
    stop('These files have uncommitted changes; commit them first (or pass --dirty for a local try, never a '
         'release):\n  ' + '\n  '.join(dirty))
if dirty:
    print(f'build_site: --dirty, building with {len(dirty)} uncommitted file(s); do not release this build')

game = open(os.path.join(ROOT, 'src', 'moonfall.html'), encoding='utf-8').read()
if not re.search(r'^const TEST_START_M = 0;', game, re.M):
    stop('TEST_START_M is not 0 in src/moonfall.html; set it back to 0 before a release.')
ver = re.search(r'^const VERSION = (\d+);', game, re.M)
if not ver:
    stop('no "const VERSION = <number>;" line in src/moonfall.html.')
version = int(ver.group(1))

cut = game.index('</style>') + len('</style>')
head, body = game[:cut], game[cut:].lstrip('\n')
if url:
    assert re.fullmatch(r'https://[a-z0-9-]+\.supabase\.co/functions/v1/scores', url), url
    assert body.count("const SCORES_URL = '';") == 1, 'SCORES_URL should be empty in src/moonfall.html'
    body = body.replace("const SCORES_URL = '';", f"const SCORES_URL = '{url}';", 1)
# The update check: the page asks version.json (written below) whether a newer version is out.
assert body.count("const UPDATE_URL = '';") == 1, 'UPDATE_URL should be empty in src/moonfall.html'
body = body.replace("const UPDATE_URL = '';", "const UPDATE_URL = 'version.json';", 1)
# Favicon: a little cratered moon.
icon = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' shape-rendering='crispEdges'%3E"
        "%3Crect width='16' height='16' fill='%231A1E2C'/%3E%3Ccircle cx='8' cy='8' r='6' fill='%23EEE8D8'/%3E"
        "%3Ccircle cx='6' cy='6' r='1.5' fill='%23B7B0A1'/%3E%3Ccircle cx='10' cy='10' r='1.2' fill='%23B7B0A1'/%3E%3C/svg%3E")
page = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
        '<meta name="theme-color" content="#1A1E2C">\n'
        '<meta name="description" content="MoonFall: fall through three moons, dodge the walls, escape the Leviathans and repair your ship.">\n'
        # Link previews (WhatsApp, iMessage, Slack, X and so on): title, line and the picture from src/share.png.
        '<meta property="og:type" content="website">\n'
        '<meta property="og:site_name" content="MoonFall">\n'
        '<meta property="og:title" content="MoonFall">\n'
        '<meta property="og:description" content="Dodge. Collect. Repair. Escape. A free pixel-art phone game by PermaFrost Productions.">\n'
        f'<meta property="og:url" content="{SITE}">\n'
        f'<meta property="og:image" content="{SITE}share.png">\n'
        '<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">\n'
        '<meta property="og:image:alt" content="MoonFall: a pixel-art pilot falling down a moon shaft past a giant jellyfish, and a cafe stop">\n'
        '<meta name="twitter:card" content="summary_large_image">\n'
        f'<link rel="icon" href="{icon}">\n'
        # Same base styles the claude.ai artifact page gets, so the game looks identical.
        '<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top);padding-bottom:env(safe-area-inset-bottom)}'
        'body{margin:0;font:14px system-ui}img{max-width:100%}[hidden]{display:none!important}</style>\n'
        + head + '\n</head>\n<body>\n' + body.rstrip() + '\n</body>\n</html>\n')

# The version must go up (see the top of this file).
docs = os.path.join(ROOT, 'docs')
try:
    published = json.load(open(os.path.join(docs, 'version.json'), encoding='utf-8'))['v']
except FileNotFoundError:
    published = None   # nothing built yet
except (ValueError, KeyError, TypeError) as e:
    stop(f'docs/version.json could not be read ({e!r}), so it is unknown whether VERSION went up.')
if published is not None:
    if not isinstance(published, int):
        stop(f'docs/version.json holds {published!r}, not a version number.')
    old_page = open(os.path.join(docs, 'index.html'), encoding='utf-8').read() if os.path.exists(os.path.join(docs, 'index.html')) else None
    if version < published or (version == published and page != old_page):
        stop(f'VERSION is {version} in src/moonfall.html and the website is already at {published}: open pages only '
             f'reload when it goes up. Add one to VERSION, then build again.')

# The release gates (see the top of this file). Each stops the build before docs/ is touched.
GATES = (
    ('tools/levi_budget.py', 'bring the Leviathan back inside the budgets in PERFORMANCE.md, or fix the check if it could not run'),
    ('tools/fight_makes.py', 'something makes a canvas in the middle of a Leviathan fight, or several in one frame of the '
                             'fall; see PERFORMANCE.md, rules 11 and 12'),
    ('tools/checks.py', 'the game and the scores function are out of step, or a code rule is broken (CODING.md)'),
    ('tools/smoke.py', 'something throws an error, or a screen no longer goes where it should'),
    ('tools/test_function.mjs', 'the scores function gives a wrong answer to the pretend database'),
    ('tools/test_reports.py', 'a genuine score (an offline dive, or a dive continued from a cafe) no longer reaches the online board'),
)
for tool, why in GATES:
    cmd = ['node' if tool.endswith('.mjs') else sys.executable, os.path.join(ROOT, tool)]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
    except OSError as e:
        stop(f'{tool} could not run ({e}); a gate that cannot run fails.')
    if res.returncode != 0:
        print(res.stdout + res.stderr)
        stop(f'{tool} did not pass (above): {why}. Fix it, then build again.')
    last = res.stdout.strip().splitlines()
    if not last:
        stop(f'{tool} printed nothing, so it is unknown whether it checked anything.')
    print(last[-1])

os.makedirs(os.path.join(ROOT, 'docs'), exist_ok=True)
open(os.path.join(ROOT, 'docs', 'index.html'), 'w').write(page)
shutil.copytree(os.path.join(ROOT, 'src', 'voices'), os.path.join(ROOT, 'docs', 'voices'), dirs_exist_ok=True)
shutil.copy(os.path.join(ROOT, 'src', 'share.png'), os.path.join(ROOT, 'docs', 'share.png'))   # the link preview picture
open(os.path.join(ROOT, 'docs', 'version.json'), 'w').write('{"v": %d}\n' % version)   # what open pages ask
print(f'docs/index.html {len(page) // 1024} KB, scores URL: {url or "(none: offline)"}')
