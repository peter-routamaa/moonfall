"""Quick checks on the game's source that need no browser, and fail if something has drifted out of step.

    python3 tools/checks.py [game.html]        (default: src/moonfall.html)

Runs in a moment, from the commit hook (tools/hooks/pre-commit) and the website build (tools/build_site.py). Checks:
  - the rude initials: BAD_INITIALS in the game and BAD in the scores function (supabase/functions/scores/index.ts)
    hold exactly the same set, so the game never accepts initials the server refuses, or the other way round;
  - the code map (CODING.md rule 1): every "// ---------- name" section header is named, in order, in the SECTIONS list
    at the top of the script, so a new section can't be added without the map knowing;
  - no history in comments (CODING.md rule 4): no "version N" in a comment (history goes in the notes and commits);
  - no hidden globals (CODING.md rule 5): no local variable or parameter named like a global everyone relies on
    (S, P, W, H, c, clock, moon, state, save, player, boss, camY).
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

    script = game[game.index('<script>\n'):game.rindex('</script>')]
    lines = script.split('\n')

    # The code map names every section header, in the same order.
    m = re.search(r'^// SECTIONS, in order.*?(?=^// [A-Z][A-Z ]+:)', script, re.S | re.M)
    if not m:
        problems.append('code map: no "// SECTIONS, in order" list at the top of the script')
    else:
        smap = ' '.join(l.lstrip('/ ').strip() for l in m.group(0).split('\n')).lower()
        at = 0
        for l in lines:
            if not l.startswith('// ---------- '):
                continue
            name = re.split(r':| \(', l[len('// ---------- '):].replace(' ----------', ''))[0].strip().lower()
            k = smap.find(name, at)
            if k < 0:
                problems.append(f'code map: section "{name}" is not in the SECTIONS list at the top of the script (or not in order)')
            else:
                at = k + len(name)

    # No version history in comments: line comments (not "://" in addresses) and /* */ comments, CSS included.
    comments = [(i + 1, c) for i, l in enumerate(game.split('\n')) for c in re.findall(r'(?:^|[^:\'"])//(.*)$', l)]
    comments += [(game.count('\n', 0, mm.start()) + 1, mm.group(1)) for mm in re.finditer(r'/\*(.*?)\*/', game, re.S)]
    for n, c in comments:
        if re.search(r'\bversion\s+\d', c, re.I):
            problems.append(f'history in a comment, line {n}: "{c.strip()[:70]}" (history goes in MOONFALL-NOTES.md and the commit)')

    # No local (indented) declaration or parameter that hides a global.
    GLOBALS = 'S|P|W|H|c|clock|moon|state|save|player|boss|camY'
    decl = re.compile(r'^\s+(?:const|let|var)\s+(?:[^;=]*?,\s*)?(' + GLOBALS + r')\s*=(?!=)')
    params = re.compile(r'(?:function\s*\w*\s*\(([^)]*)\)|\(([^()]*)\)\s*=>|(?<![\w.])(\w+)\s*=>)')
    base = game.count('\n', 0, game.index('<script>\n')) + 1
    for i, l in enumerate(lines):
        code = re.sub(r"'(?:[^'\\]|\\.)*'|`[^`]*`|//.*$", "''", l)
        hit = decl.search(code)
        names = [hit.group(1)] if hit else []
        for mm in params.finditer(code):
            for grp in mm.groups():
                if grp:
                    for part in grp.split(','):   # each parameter's own name, not its default value
                        pm = re.match(r'\s*[{\[]?\s*\.{0,3}(\w+)', part)
                        if pm and re.fullmatch(GLOBALS, pm.group(1)): names.append(pm.group(1))
        for n in names:
            problems.append(f'hidden global, line {base + i}: a local "{n}" hides the global {n} (CODING.md rule 5)')

    for p in problems: print('FAIL', p)
    print('FAIL: the source checks found problems' if problems else f'OK: source checks passed (rude initials: {len(g)} in both lists; code map, comments, names)')
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
