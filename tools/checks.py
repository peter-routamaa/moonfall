"""Quick checks on the game's source that need no browser, and fail if something has drifted out of step.

    python3 tools/checks.py [game.html] [--server=index.ts] [--list]
        (defaults: src/moonfall.html and supabase/functions/scores/index.ts; the commit hook passes the staged copies;
        --list also prints every line the ratchets below count, for a tidy-up)

Runs in a moment, from the commit hook (tools/hooks/pre-commit) and the website build (tools/build_site.py). Needs Node
(as the build does): the script is read by the JavaScript parser that ships inside Node (acorn), so the checks below see
real declarations, scopes and comments rather than guessing from the text. Checks:
  - the rude initials: BAD_INITIALS in the game and BAD in the scores function (supabase/functions/scores/index.ts)
    hold exactly the same set, so the game never accepts initials the server refuses, or the other way round;
  - the code map (CODING.md rule 1): every "// ---------- name" section header is named, in order, in the SECTIONS list
    at the top of the script, so a new section can't be added without the map knowing;
  - no history in comments (CODING.md rule 4): no "version N", version tag (v197, v197-200, v0.224), "no longer",
    "used to", "was replaced" or "previously" in a comment, in the script, the CSS or the HTML. A comment that must
    name a version for another reason (how the version number is shown) says so with "history-ok" in it;
  - no hidden globals (CODING.md rule 5): no local binding (parameter, declaration, any name in a list or a
    destructuring, loop variable, catch parameter, inner function or class) named like a global everyone relies on
    (PROTECTED below); each of those must still be a global, or the list is out of date;
  - lines a reader can follow (CODING.md rule 6), as ratchets: script lines over 160 characters that aren't data rows
    (a data row is only literals, names and the brackets and commas of a table, as sprite rows and palettes are) may
    not number more than LONG_LINES_MAX, and ternaries nested more than two deep not more than DEEP_TERNARIES_MAX. A
    change can lower the count, never raise it; lower the constant when the count drops;
  - sounds are freed (CODING.md rule 11): every oscillator or buffer source the game makes is passed to freeAfter within
    the next 12 lines, or its line says why not with a comment naming freeAfter (one that plays for good, or is freed
    elsewhere).
Add a check here whenever a rule can be checked by reading the files (CLAUDE.md: "When a new rule can be checked by a
script, add it to those gates rather than only writing it down"). Exits 1 naming what is out of step.
"""
import json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chrome

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Globals no local may take the name of (CODING.md rule 5): the palettes, the size and scale of the world, the canvas
# and the context drawn on, the clock, and the game's main state.
PROTECTED = ['S', 'P', 'W', 'H', 'sc', 'cv', 'c', 'clock', 'moon', 'state', 'save', 'player', 'boss', 'camY']
MAX_LINE = 160
# Ratchets (CODING.md rule 6): today's counts. The check fails above them; when a tidy-up brings a count down, lower the
# constant to match so it can't creep back up.
LONG_LINES_MAX = 221
DEEP_TERNARIES_MAX = 0

# Exactly these lines (their text, stripped) would be let through. Both are empty: the code tidy-up fixed every line
# found when the checks were made stricter. Never add one; fix the line instead.
HIDDEN_ALLOWED = set()
HISTORY_ALLOWED = set()

HISTORY = re.compile(r"\bversion\s+\d|(?<![\w.'\"-])v\d+(?:\.\d+)*(?:\s*[-–]\s*v?\d+(?:\.\d+)*)?\b"
                     r"|\bno longer\b|\bused to\b|\bwas replaced\b|\bpreviously\b", re.I)

# Run by Node on the game's script (stdin), with the settings as its last argument; prints what it found as JSON.
SCAN_JS = r"""
let acorn;
try { acorn = require('internal/deps/acorn/acorn/dist/acorn'); } catch (e) {
  console.error('the acorn parser inside Node could not be loaded (' + e.message + ')'); process.exit(3);
}
const { protectedNames, maxLen } = JSON.parse(process.argv[process.argv.length - 1]);
const PROTECTED = new Set(protectedNames);
const src = require('fs').readFileSync(0, 'utf8');
const comments = [];
const opts = { ecmaVersion: 'latest', sourceType: 'script', locations: true };
let ast;
try { ast = acorn.parse(src, { ...opts, onComment: (block, text, s, e, loc) => comments.push([loc.line, text]) }); } catch (e) {
  console.log(JSON.stringify({ error: e.message, line: e.loc ? e.loc.line : 0 })); process.exit(0);
}

const isFn = n => n.type === 'FunctionDeclaration' || n.type === 'FunctionExpression' || n.type === 'ArrowFunctionExpression';
const children = n => {
  const out = [];
  for (const k in n) {
    if (k === 'loc' || k === 'type' || k === 'start' || k === 'end') continue;
    const v = n[k];
    if (Array.isArray(v)) { for (const x of v) if (x && typeof x.type === 'string') out.push(x); }
    else if (v && typeof v.type === 'string') out.push(v);
  }
  return out;
};
// The names a binding pattern declares: a, { a, b: c, ...d }, [e, f = 1, ...g].
const bound = (p, out = []) => {
  if (!p) return out;
  if (p.type === 'Identifier') out.push(p);
  else if (p.type === 'ObjectPattern') for (const q of p.properties) bound(q.type === 'RestElement' ? q.argument : q.value, out);
  else if (p.type === 'ArrayPattern') for (const q of p.elements) bound(q, out);
  else if (p.type === 'AssignmentPattern') bound(p.left, out);
  else if (p.type === 'RestElement') bound(p.argument, out);
  return out;
};

const globals = new Set(), hidden = [], ternaries = [];
const local = ids => { for (const id of ids) if (PROTECTED.has(id.name)) hidden.push([id.loc.start.line, id.name]); };
const declare = (ids, global) => { if (global) for (const id of ids) globals.add(id.name); else local(ids); };
// The deepest chain of ternaries in n, not counting any inside a function there.
const depth = n => {
  let d = 0;
  for (const ch of children(n)) if (!isFn(ch)) d = Math.max(d, depth(ch));
  return n.type === 'ConditionalExpression' ? d + 1 : d;
};
// The script's own scope: the program, or the body of the function it calls at once, (() => { ... })(), that holds the
// whole game. Declarations there are the globals.
const wrap = ast.body.length > 0 && ast.body.every(st => st.type === 'ExpressionStatement') && ast.body.map(st => st.expression)
  .find(e => e.type === 'CallExpression' && isFn(e.callee) && e.callee.body.type === 'BlockStatement');
const topBody = wrap ? wrap.callee.body : ast;
const isTop = parent => parent === ast || parent === topBody;
const walk = (n, parent, inFn, inTernary) => {
  if (wrap && n === wrap.callee) {
    // The wrapper: its body is the global scope, so nothing changes on the way in.
  } else if (isFn(n)) {
    if (n.id) declare([n.id], n.type === 'FunctionDeclaration' && isTop(parent));
    local(n.params.flatMap(p => bound(p)));
    inFn = true;
    inTernary = false;
  } else if (n.type === 'VariableDeclaration') {
    // At the top, or a var hoisted out of a block at the top: a global. Anything else (a for head included): a local.
    declare(n.declarations.flatMap(d => bound(d.id)), isTop(parent) || (n.kind === 'var' && !inFn));
  } else if (n.type === 'ClassDeclaration' || n.type === 'ClassExpression') {
    if (n.id) declare([n.id], n.type === 'ClassDeclaration' && isTop(parent));
  } else if (n.type === 'CatchClause') {
    local(bound(n.param));
  } else if (n.type === 'ConditionalExpression' && !inTernary) {
    const d = depth(n);
    if (d > 2) ternaries.push([n.loc.start.line, d]);
    inTernary = true;
  }
  for (const ch of children(n)) walk(ch, n, inFn, inTernary);
};
walk(ast, null, false, false);

// Long lines. A data row's code (leaving out "const NAME =" in front, and ; or , at the end) has nothing but literals,
// names and the brackets, commas and colons of arrays, objects and calls: no operator, assignment, arrow or keyword.
// A line inside a template literal that spans lines (markup) is data too, unless it holds code.
const lines = src.split('\n');
const DATA = new Set(['string', 'num', 'regexp', 'template', '`', '${', '}', '{', '[', ']', '(', ')', ',', ':', '.', 'name',
  'true', 'false', 'null']);
const onLine = new Map(), inTemplate = new Set();
let prev = null;
for (const t of acorn.tokenizer(src, opts)) {
  const l = t.loc.start.line, label = t.type.label;
  if (!onLine.has(l)) onLine.set(l, []);
  // A minus sign straight after a bracket, comma or colon is a negative number in a table, not a subtraction.
  const negative = label === '+/-' && t.value === '-' && prev && ['[', ',', '(', ':', '{'].includes(prev.type.label);
  onLine.get(l).push(negative ? 'num' : label);
  if (label === 'template') for (let k = l + 1; k <= t.loc.end.line; k++) inTemplate.add(k);
  prev = t;
}
const long = [];
lines.forEach((text, i) => {
  if (text.length <= maxLen) return;
  let toks = (onLine.get(i + 1) || []).slice();
  // "const" and "var" are keywords to the tokenizer; "let" is a name.
  if (toks.length >= 3 && ['const', 'var', 'name'].includes(toks[0]) && toks[1] === 'name' && toks[2] === '=') toks = toks.slice(3);
  while (toks.length && (toks[toks.length - 1] === ';' || toks[toks.length - 1] === ',')) toks.pop();
  const isData = (toks.length > 0 || inTemplate.has(i + 1)) && toks.every(k => DATA.has(k));
  long.push([i + 1, isData]);
});

console.log(JSON.stringify({ protectedGlobals: [...PROTECTED].filter(n => globals.has(n)), hidden, comments, ternaries, long,
  lines: lines.length }));
"""


def initials(text, name):
    m = re.search(r'const ' + name + r' = new Set\(\[(.*?)\]\)', text, re.S)
    if not m:
        return None
    return set(re.findall(r"'([A-Z]{3})'", m.group(1)))


def scan(js):
    """What SCAN_JS finds in the script `js`, or (None, why) when Node or its parser can't read it."""
    try:
        # Bytes, not text mode: on Windows text mode would turn every '\n' into '\r\n' and lengthen each line by one.
        code, out, err_text = chrome.run_text(['node', '--expose-internals', '-e', SCAN_JS,
                                               json.dumps({'protectedNames': PROTECTED, 'maxLen': MAX_LINE})],
                                              input_text=js, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, f'could not run Node ({e}); the build needs it too (README)'
    if code != 0:
        err = err_text.strip().split('\n')
        return None, 'Node could not read the script: ' + next((l for l in err if 'rror' in l or 'acorn' in l), err[-1])[:300]
    try:
        return json.loads(out), None
    except ValueError:
        return None, 'Node printed no result'


def main():
    listing = '--list' in sys.argv[1:]
    args = [a for a in sys.argv[1:] if not a.startswith('--server=') and a != '--list']
    server_path = next((a[len('--server='):] for a in sys.argv[1:] if a.startswith('--server=')),
                       os.path.join(ROOT, 'supabase', 'functions', 'scores', 'index.ts'))
    if len(args) > 1 or any(a.startswith('--') for a in args):
        sys.exit('checks: usage: python3 tools/checks.py [game.html] [--server=index.ts] [--list]')
    src = args[0] if args else os.path.join(ROOT, 'src', 'moonfall.html')
    game = open(src, encoding='utf-8').read()
    server = open(server_path, encoding='utf-8').read()
    problems, notes = [], []

    g, s = initials(game, 'BAD_INITIALS'), initials(server, 'BAD')
    if g is None or s is None:
        problems.append('rude initials: could not find BAD_INITIALS in the game or BAD in the scores function')
    elif g != s:
        if g - s: problems.append('rude initials only in the game: ' + ', '.join(sorted(g - s)))
        if s - g: problems.append('rude initials only in the scores function: ' + ', '.join(sorted(s - g)))

    start, end = game.index('<script>\n'), game.rindex('</script>')
    script = game[start:end]
    lines = script.split('\n')
    base = game.count('\n', 0, start) + 1   # the file's line number of lines[0] ("<script>")
    file_lines = game.split('\n')
    # The parser reads the script from just after "<script>", so its line 1 is lines[0] and line k is the file's base + k - 1.
    found, why = scan(script[len('<script>'):])
    if found is not None and 'error' in found:
        found, why = None, f'the script does not parse, line {base + found["line"] - 1}: {re.sub(r" [(][0-9:]+[)]$", "", found["error"])}'
    scanned = found is not None
    if not scanned:
        problems.append('source checks could not run: ' + why)
        found = {'protectedGlobals': PROTECTED, 'hidden': [], 'comments': [], 'ternaries': [], 'long': [], 'lines': 0}
    elif found['lines'] != len(lines) or len(found['comments']) < 500:
        problems.append(f'source checks: the parser saw {found["lines"]} lines and {len(found["comments"])} comments in a '
                        f'script of {len(lines)} lines; it is not reading the game')

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

    # No history in comments: the script's comments as the parser found them, and the CSS's /* */ and the HTML's <!-- -->
    # outside the script.
    comments = [(base + n - 1, text) for n, text in found['comments']]
    for part, offset in ((game[:start], 0), (game[end:], end)):
        for mm in re.finditer(r'/\*(.*?)\*/|<!--(.*?)-->', part, re.S):
            comments.append((game.count('\n', 0, offset + mm.start()) + 1, mm.group(1) if mm.group(1) is not None else mm.group(2)))
    allowed_seen = set()
    for n, text in comments:
        if 'history-ok' in text:
            continue
        for mm in HISTORY.finditer(text):
            at = n + text.count('\n', 0, mm.start())
            line = file_lines[at - 1].strip()
            if line in HISTORY_ALLOWED:
                allowed_seen.add(line)
                continue
            problems.append(f'history in a comment, line {at}: "{mm.group(0)}" in "{line[:90]}" (history goes in '
                            f'MOONFALL-NOTES.md and the commit; CODING.md rule 4)')
    for line in HISTORY_ALLOWED - allowed_seen:
        notes.append(f'history allowed for a line that is gone or fixed; remove it from HISTORY_ALLOWED: "{line[:90]}"')

    # No local binding that hides a global, and every protected name is still a global.
    for n in PROTECTED:
        if n not in found['protectedGlobals']:
            problems.append(f'hidden globals: "{n}" is no longer declared at the top of the script; update PROTECTED in tools/checks.py')
    allowed_seen = set()
    for n, name in found['hidden']:
        line = file_lines[base + n - 2].strip()
        if (name, line) in HIDDEN_ALLOWED:
            allowed_seen.add((name, line))
            continue
        problems.append(f'hidden global, line {base + n - 1}: a local "{name}" hides the global {name} (CODING.md rule 5)')
    for name, line in HIDDEN_ALLOWED - allowed_seen:
        notes.append(f'hidden "{name}" allowed for a line that is gone or fixed; remove it from HIDDEN_ALLOWED: "{line[:90]}"')

    # Ratchets on long lines and deeply nested ternaries.
    long_logic = [base + n - 1 for n, data in found['long'] if not data]
    deep = [(base + n - 1, d) for n, d in found['ternaries']]
    for what, count, limit, const, where in (
            (f'script lines over {MAX_LINE} characters (not data rows)', len(long_logic), LONG_LINES_MAX, 'LONG_LINES_MAX', long_logic),
            ('ternaries nested more than two deep', len(deep), DEEP_TERNARIES_MAX, 'DEEP_TERNARIES_MAX', [n for n, d in deep])):
        if count > limit:
            problems.append(f'{what}: {count}, more than the {limit} allowed (CODING.md rule 6). Split the new ones '
                            f'(python3 tools/checks.py --list names every line counted)')
        elif count < limit:
            notes.append(f'{what}: {count}, below {const} = {limit}; lower it to {count} in tools/checks.py')
        if listing:
            for n in where:
                print(f'LIST {what}, line {n}: {file_lines[n - 1].strip()[:100]}')

    # Every oscillator and buffer source is freed when it ends (freeAfter), so the audio graph can't grow with play time.
    made = re.compile(r'\b(\w+) = ctx\.create(?:Oscillator|BufferSource)\(\)')
    sources = 0
    for i, l in enumerate(lines):
        for name in made.findall(l):
            sources += 1
            if re.search(r'//.*freeAfter', l):
                continue
            freed = re.compile(r'freeAfter\(\[[^\]]*\b' + name + r'\b')
            if not any(freed.search(x) for x in lines[i:i + 13]):
                problems.append(f'sound not freed, line {base + i}: "{name}" is never passed to freeAfter (CODING.md rule 11)')
    if sources < 25:
        problems.append(f'sound not freed: found only {sources} oscillators and buffer sources; the check no longer matches the code')

    for p in problems: print('FAIL', p)
    for p in notes if scanned else []: print('NOTE', p)   # with nothing scanned, every allowance looks unused
    print('FAIL: the source checks found problems' if problems else
          f'OK: source checks passed (rude initials: {len(g)} in both lists; code map, comments, names, '
          f'{len(long_logic)}/{LONG_LINES_MAX} long lines, {len(deep)}/{DEEP_TERNARIES_MAX} deep ternaries, {sources} sounds freed)')
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
