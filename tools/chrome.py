"""What the tools that run the game share: hooking into its start line, driving it past the start screen and a
component's card, and running it in headless Chrome. Imported by same_pixels.py, bench.py, fight_makes.py, smoke.py,
test_pages.py, prof.py and levi_budget.py; nothing to run on its own.

Chrome is the Mac one unless CHROME is set to its path.
"""
import html, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = os.environ.get('CHROME', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')

# The game's last line inside start(): the first frame is asked for here, after everything is defined. A tool's hook
# goes just before it, so the hook sees the game's internals before any frame runs.
START_LINE = 'requestAnimationFrame(t => { last = t; frame(t); });'


def inject(game, code, who, anchor=START_LINE):
    """The game's source with `code` on its own line just before `anchor` (the start line unless a tool needs another).
    Stops the tool (exit 1, naming it) unless the anchor is there exactly once: a tool that hooked in at the wrong
    place, or not at all, would measure or test something else and might still say OK (CODING.md rule 13)."""
    n = game.count(anchor)
    if n != 1:
        sys.exit(f'{who}: stopped. The line {anchor!r} is in the game {n} times, not once, so the tool cannot hook '
                 f'in. If the game\'s start-up changed, change the anchor in tools/chrome.py (or in {who}) to match.')
    return game.replace(anchor, code + '\n' + anchor)


# Helpers for the pages' driver scripts, as window.__tools; put this in a page before its driver.
#   cardUp()            a component's card is up (a Leviathan escaped): the confirm dialog showing its picture
#   continueCard()      answers that card with Continue, as a player would; true if it did
#   skipSplash(moon, toMenu)
#                       from the start screen to the menu: choose the moon (default: the game's own), start, skip the
#                       intro film, then press the clean menu's Start unless toMenu is false (undefined: unless the
#                       address has ?clean=1). An old build with a splashSkip button gets that button instead.
#   jumpIn()            the menu's Jump in, then its card's Dive!
HELPERS = r"""<script>
window.__tools = {
  cardUp() { const g = id => document.getElementById(id); return g('confirmDlg').open && !g('confirmPic').hidden; },
  continueCard() { if (!this.cardUp()) return false; document.getElementById('confirmYes').click(); return true; },
  skipSplash(moon, toMenu) {
    const g = id => document.getElementById(id);
    if (g('splashSkip')) { g('splashSkip').click(); return; }
    g('chooseBtn').click();
    document.querySelector('.splash-moon[data-moon="' + (moon || window.__mf.moon || 'dust') + '"]').click();
    g('splashBtn').click(); g('introSkip').click();
    if (toMenu === undefined) toMenu = !new URLSearchParams(location.search).get('clean');
    if (toMenu && g('menuStart')) g('menuStart').click();
  },
  jumpIn() { const g = id => document.getElementById(id); g('startBtn').click(); if (g('confirmDlg').open) g('confirmYes').click(); },
};
</script>"""


def need_chrome(who):
    """Stops the tool with exit 2 (could not run) when Chrome isn't there."""
    if not os.path.exists(CHROME):
        print(f'{who}: Chrome not found at {CHROME}; set CHROME to its path')
        sys.exit(2)


def dump_dom(url, profile, budget_ms, timeout, size=None, files=True):
    """Opens `url` in headless Chrome with its own profile folder, lets the page run for `budget_ms` of virtual time
    and returns the page as it then is. `size` is the window ('390,844'); `files` lets a file:// page read others."""
    args = [CHROME, '--headless=new', '--disable-gpu', '--no-first-run', '--user-data-dir=' + profile]
    if files:
        args.append('--allow-file-access-from-files')
    if size:
        args.append('--window-size=' + size)
    args += ['--virtual-time-budget=' + str(budget_ms), '--dump-dom', url]
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout).stdout


def result(dom):
    """The JSON a driver left in <pre id="out">, or None when the page never got that far."""
    m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
    return json.loads(html.unescape(m.group(1))) if m else None


def moons(game):
    """Every moon the game has, in the order of its LEVI_SETS table."""
    m = re.search(r'const LEVI_SETS = \{(.*?)\};', game, re.S)
    if not m:
        sys.exit('tools: stopped. No LEVI_SETS table in the game, so the moons are unknown.')
    return re.findall(r"(\w+): ", m.group(1))
