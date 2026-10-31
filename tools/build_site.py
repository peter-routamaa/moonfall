"""Builds the website copy of the game, docs/index.html (served by GitHub Pages), from src/moonfall.html.

    python3 tools/build_site.py              # with the online board (the project's Supabase function)
    python3 tools/build_site.py --offline    # without it: scores stay on the device, no stats are sent

src/moonfall.html is the game exactly as published on claude.ai, where SCORES_URL is empty. This wraps it in a normal
web page (doctype, head, the same base styles the claude.ai page adds) and fills in SCORES_URL.
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCORES_URL = 'https://ukjajizsnowmdjziqkof.supabase.co/functions/v1/scores'   # public; it's in the built page anyway

url = '' if '--offline' in sys.argv else SCORES_URL
game = open(os.path.join(ROOT, 'src', 'moonfall.html')).read()
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
        '<meta name="description" content="MoonFall: fall through the moon, dodge the walls, repair your ship.">\n'
        f'<link rel="icon" href="{icon}">\n'
        # Same base styles the claude.ai artifact page gets, so the game looks identical.
        '<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top);padding-bottom:env(safe-area-inset-bottom)}'
        'body{margin:0;font:14px system-ui}img{max-width:100%}[hidden]{display:none!important}</style>\n'
        + head + '\n</head>\n<body>\n' + body.rstrip() + '\n</body>\n</html>\n')
os.makedirs(os.path.join(ROOT, 'docs'), exist_ok=True)
open(os.path.join(ROOT, 'docs', 'index.html'), 'w').write(page)
print(f'docs/index.html {len(page) // 1024} KB, scores URL: {url or "(none: offline)"}')
