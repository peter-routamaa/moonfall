"""Builds the website copy of the game, docs/index.html (served by GitHub Pages), from src/moonfall.html.

    python3 tools/build_site.py              # with the online board (the project's Supabase function)
    python3 tools/build_site.py --offline    # without it: scores stay on the device, no stats are sent

src/moonfall.html is the game exactly as published on claude.ai, where SCORES_URL is empty. This wraps it in a normal
web page (doctype, head, the same base styles the claude.ai page adds), fills in SCORES_URL, and copies the voice clips
(src/voices/*.wav) to docs/voices/.

It refuses to build a game that should not go live, so a release cannot skip these checks whoever runs it:
  - TEST_START_M must be 0 (a test copy that starts deep in the moon must never reach the website);
  - tools/levi_budget.py must say OK (every Leviathan inside the drawing budgets in PERFORMANCE.md);
  - tools/fight_makes.py must say OK (no canvas made in the middle of a Leviathan fight; it plays all of them, about
    a minute).
"""
import os, re, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCORES_URL = 'https://ukjajizsnowmdjziqkof.supabase.co/functions/v1/scores'   # public; it's in the built page anyway

SITE = 'https://peter-routamaa.github.io/moonfall/'   # where GitHub Pages serves it; link previews need full addresses
url = '' if '--offline' in sys.argv else SCORES_URL
game = open(os.path.join(ROOT, 'src', 'moonfall.html')).read()

# The release gates (see the top of this file). Each stops the build before anything in docs/ is touched.
if not re.search(r'^const TEST_START_M = 0;', game, re.M):
    sys.exit('build_site: stopped. TEST_START_M is not 0 in src/moonfall.html; set it back to 0 before a release.')
budget = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'levi_budget.py')], capture_output=True, text=True)
if budget.returncode != 0:
    print(budget.stdout + budget.stderr)
    sys.exit('build_site: stopped. tools/levi_budget.py did not pass (above); bring the Leviathan back inside the '
             'budgets in PERFORMANCE.md, or fix the check if it could not run, then build again.')
print(budget.stdout.strip().splitlines()[-1])
makes = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'fight_makes.py')], capture_output=True, text=True)
if makes.returncode != 0:
    print(makes.stdout + makes.stderr)
    sys.exit('build_site: stopped. tools/fight_makes.py did not pass (above): something makes a canvas in the middle '
             'of a Leviathan fight. Make it in the thin shaft instead (PERFORMANCE.md, rule 11), then build again.')
print(makes.stdout.strip().splitlines()[-1])
cut = game.index('</style>') + len('</style>')
head, body = game[:cut], game[cut:].lstrip('\n')
if url:
    assert re.fullmatch(r'https://[a-z0-9-]+\.supabase\.co/functions/v1/scores', url), url
    assert body.count("const SCORES_URL = '';") == 1, 'SCORES_URL should be empty in src/moonfall.html'
    body = body.replace("const SCORES_URL = '';", f"const SCORES_URL = '{url}';", 1)
# Favicon: a little cratered moon.
icon = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' shape-rendering='crispEdges'%3E"
        "%3Crect width='16' height='16' fill='%231A1E2C'/%3E%3Ccircle cx='8' cy='8' r='6' fill='%23EEE8D8'/%3E"
        "%3Ccircle cx='6' cy='6' r='1.5' fill='%23B7B0A1'/%3E%3Ccircle cx='10' cy='10' r='1.2' fill='%23B7B0A1'/%3E%3C/svg%3E")
page = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
        '<meta name="theme-color" content="#1A1E2C">\n'
        '<meta name="description" content="MoonFall: fall through a moon, dodge the walls, repair your ship.">\n'
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
os.makedirs(os.path.join(ROOT, 'docs'), exist_ok=True)
open(os.path.join(ROOT, 'docs', 'index.html'), 'w').write(page)
shutil.copytree(os.path.join(ROOT, 'src', 'voices'), os.path.join(ROOT, 'docs', 'voices'), dirs_exist_ok=True)
shutil.copy(os.path.join(ROOT, 'src', 'share.png'), os.path.join(ROOT, 'docs', 'share.png'))   # the link preview picture
print(f'docs/index.html {len(page) // 1024} KB, scores URL: {url or "(none: offline)"}')
