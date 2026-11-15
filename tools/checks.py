"""Quick checks on the game's source that need no browser, and fail if something has drifted out of step.

    python3 tools/checks.py [game.html]        (default: src/moonfall.html)

Runs in a moment, from the commit hook (tools/hooks/pre-commit) and the website build (tools/build_site.py). Checks:
  - the rude initials: BAD_INITIALS in the game and BAD in the scores function (supabase/functions/scores/index.ts)
    hold exactly the same set, so the game never accepts initials the server refuses, or the other way round
    (version 216; the two lists were kept the same by hand before).
Add a check here whenever a rule can be checked by reading the files (CLAUDE.md: "When a new rule can be checked by a
script, add it to those gates rather than only writing it down"). Exits 1 naming what is out of step.
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def initials(text, name):
    m = re.search(r'const ' + name + r' = new Set\(\[(.*?)\]\)', text, re.S)
    if not m:
        return None
    return set(re.findall(r"'([A-Z]{3})'", m.group(1)))


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'src', 'moonfall.html')
    game = open(src, encoding='utf-8').read()
    server = open(os.path.join(ROOT, 'supabase', 'functions', 'scores', 'index.ts'), encoding='utf-8').read()
    problems = []

    g, s = initials(game, 'BAD_INITIALS'), initials(server, 'BAD')
    if g is None or s is None:
        problems.append('rude initials: could not find BAD_INITIALS in the game or BAD in the scores function')
    elif g != s:
        if g - s: problems.append('rude initials only in the game: ' + ', '.join(sorted(g - s)))
        if s - g: problems.append('rude initials only in the scores function: ' + ', '.join(sorted(s - g)))

    for p in problems: print('FAIL', p)
    print('FAIL: the source checks found problems' if problems else f'OK: source checks passed (rude initials: {len(g)} in both lists)')
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
