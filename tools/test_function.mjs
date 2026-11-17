// Tests the scoreboard and stats function (supabase/functions/scores/index.ts) without Supabase: it runs under Node
// with a stand-in for Deno and a small in-memory copy of the database API, then checks the answers.
//   node tools/test_function.mjs            (needs Node 22.13 or newer, for stripTypeScriptTypes)
import { stripTypeScriptTypes } from 'node:module';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const src = stripTypeScriptTypes(readFileSync(process.argv[2] || root + 'supabase/functions/scores/index.ts', 'utf8'));
mkdirSync(root + 'tools/out', { recursive: true });
// The board's start time (BOARD_FROM) is set to a fixed past moment here, so scores saved during the test are on the board.
writeFileSync(root + 'tools/out/function.mjs', src.replace(/const BOARD_FROM = '[^']*'/, "const BOARD_FROM = '2026-11-05T00:00:00Z'"));

// Fake Deno (env and serve) and a fake PostgREST for the `scores` and `plays` tables: just enough of GET with filters,
// POST, PATCH and count=exact for what the function uses.
let handler; const db = { scores: [], plays: [] }; let nextId = 1;
let failNext = '';   // 'count': the first count after the next score insert fails, as a database error then would
globalThis.Deno = { env: { get: k => ({ SUPABASE_URL: 'https://x.supabase.co', SUPABASE_SERVICE_ROLE_KEY: 'eyJfake' })[k] }, serve: f => { handler = f; } };
globalThis.fetch = async (url, init = {}) => {
  const u = new URL(url), q = u.searchParams, h = init.headers || {}, table = u.pathname.split('/').pop();
  if (h.apikey !== 'eyJfake') return new Response('no auth', { status: 401 });
  if (!db[table]) return new Response('no table ' + table, { status: 404 });
  if (failNext === 'armed' && h.Prefer === 'count=exact') { failNext = ''; return new Response('database down', { status: 503 }); }
  if (failNext === 'count' && init.method === 'POST' && table === 'scores') failNext = 'armed';
  if ((init.method || 'GET') === 'POST' && table === 'scores' && JSON.parse(init.body).run && db.scores.some(x => x.run === JSON.parse(init.body).run)) return new Response('duplicate key', { status: 409 });
  if ((init.method || 'GET') === 'POST') { const b = JSON.parse(init.body); const row = { id: nextId++, ...b, created_at: new Date().toISOString() }; db[table].push(row); return new Response(h.Prefer === 'return=minimal' ? '' : JSON.stringify([row]), { status: 201 }); }
  if (init.method === 'PATCH') { const b = JSON.parse(init.body); const hit = db[table].filter(x => x.player === q.get('player').slice(3) && x.run === q.get('run').slice(3)); hit.forEach(x => Object.assign(x, b)); return new Response(JSON.stringify(hit), { status: 200 }); }
  let r = db[table].slice();
  for (const col of ['who', 'player', 'run']) if (q.get(col)) r = r.filter(x => x[col] === q.get(col).slice(3));
  if (table === 'scores' && q.get('kid')) r = r.filter(x => !!x.kid === (q.get('kid') === 'eq.true'));   // version 197
  for (const c of q.getAll('created_at')) r = r.filter(x => x.created_at > c.slice(3));   // gt. only; the board's season and the spam check
  if (q.get('or')) { const m = q.get('or').match(/depth\.gt\.(\d+),and\(depth\.eq\.(\d+),id\.lt\.(\d+)\)/); r = r.filter(x => x.depth > +m[1] || (x.depth === +m[2] && x.id < +m[3])); }
  if (h.Prefer === 'count=exact') return new Response('[]', { headers: { 'content-range': r.length ? `0-0/${r.length}` : `*/0` } });
  r.sort((a, b) => b.depth - a.depth || a.id - b.id);
  const cols = (q.get('select') || 'id,initials,depth,escaped,moon').split(',');
  return new Response(JSON.stringify(r.slice(0, +q.get('limit')).map(x => Object.fromEntries(cols.map(c => [c, x[c] ?? null])))));
};
await import(root + 'tools/out/function.mjs');

const call = async (method, body, ip = '1.2.3.4') => {
  const res = await handler(new Request('https://fn/scores', { method, headers: { 'x-forwarded-for': ip, 'content-type': 'application/json' }, body: body && JSON.stringify(body) }));
  return [res.status, await res.json().catch(() => null)];
};
let failed = 0, passed = 0;
const check = (name, ok, got) => { if (ok) passed++; else { failed++; console.log('FAIL', name, JSON.stringify(got)); } };

// Scoreboard
check('empty board', JSON.stringify(await call('GET')) === JSON.stringify([200, { top: [] }]), await call('GET'));
const s1 = await call('POST', { initials: 'abc', depth: 500 });
check('score saved at rank 1', s1[0] === 200 && s1[1].rank === 1 && s1[1].top[0].initials === 'ABC', s1);
const s2 = await call('POST', { initials: 'ESC', depth: 400, escaped: true }, 'e');
check('escaped stored and returned', s2[0] === 200 && s2[1].top.find(t => t.initials === 'ESC').escaped === true && s1[1].top[0].escaped === null, [s1, s2]);
const s3 = await call('POST', { initials: 'JNK', depth: 300, escaped: 'yes' }, 'j');
check('junk escaped stored as null', s3[0] === 200 && db.scores.find(x => x.initials === 'JNK').escaped === null, db.scores);
const s4 = await call('POST', { initials: 'JGL', depth: 350, moon: 'jungle' }, 'm');
check('moon stored and returned', s4[0] === 200 && s4[1].top.find(t => t.initials === 'JGL').moon === 'jungle' && db.scores.find(x => x.initials === 'ESC').moon === null, s4);
const s5 = await call('POST', { initials: 'MCH', depth: 345, moon: 'machine' }, 'q');
check('machine moon stored', s5[0] === 200 && db.scores.find(x => x.initials === 'MCH').moon === 'machine', s5);
await call('POST', { initials: 'MNX', depth: 340, moon: 'mars' }, 'n');
check('unknown moon stored as null', db.scores.find(x => x.initials === 'MNX').moon === null, db.scores);
check('rude initials refused', (await call('POST', { initials: 'ass', depth: 300 }, 'b'))[0] === 400, null);
check('bad depth refused', (await call('POST', { initials: 'ABC', depth: -5 }, 'c'))[0] === 400, null);
db.scores.push({ id: 99, initials: 'FUK', depth: 900, who: null, created_at: '2026-11-06' });
const masked = (await call('GET'))[1].top.map(t => t.initials + t.depth).join(' ');
check('rude names already stored show as ???', masked === '???900 ABC500 ESC400 JGL350 MCH345 MNX340 JNK300', masked);
const burst = []; for (let k = 0; k < 8; k++) burst.push((await call('POST', { initials: 'SPM', depth: 5 }, 'spam'))[0]);
check('6 scores a minute per connection, then 429', burst.join(',') === '200,200,200,200,200,200,429,429', burst);

// Play stats
const P = '00112233aabbccdd', RUN = '1111222233334444';
check('play ping', (await call('POST', { event: 'play', player: P, run: RUN, ver: 106, moon: 'jungle', hard: true, droneOpen: true, drone: false }))[0] === 200, null);
check('hard and drone flags stored on the start ping', (r => r.hard === true && r.drone_open === true && r.drone === false)(db.plays.find(x => x.run === RUN)), db.plays);
check('moon stored on the start ping', db.plays.find(x => x.run === RUN).moon === 'jungle', db.plays);
check('version stored on the start ping', db.plays.find(x => x.run === RUN).ver === 106, db.plays);
await call('POST', { event: 'play', player: P, run: RUN });
check('repeat ping within 5 s ignored', db.plays.filter(x => x.player === P).length === 1, db.plays);
check('bad player id refused', (await call('POST', { event: 'play', player: 'nope' }))[0] === 400, null);
const end = { event: 'end', player: P, run: RUN, depth: 812, secs: 95, how: 'mine', orbs: 7, parts: 2, cafes: 0, initials: 'PJR',
  fps: 89.67, worst: 41, device: 'phone', os: 'android', screen: '412x915@2.63', treats: ['Magnet', 'Bubble to go'], streak: 17, sound: true, music: false, repair: 53, intro: 'skipped', ver: 107, moon: 'dust', hard: false, droneOpen: true, drone: true,
  errors: 2, error: 'TypeError: x is undefined @5100:12', leviFought: ['whale', 'jelly'], leviEscaped: ['whale'], missions: 3, suit: 2, badges: 7, nav: 40,
  cafesPassed: 4, droneCaught: 6, installed: true, browser: 'safari', pauses: 1, hz: 120, fpsFight: 93.04, slowPct: 18.26 };
check('end ping', (await call('POST', end))[0] === 200, null);
await call('POST', { ...end, depth: 900, secs: 120, how: 'rock' });
const row = db.plays.find(x => x.run === RUN);
check('second end updates the same run', row.depth === 900 && row.how === 'rock' && db.plays.filter(x => x.run === RUN).length === 1, row);
check('extras stored', row.fps === 89.7 && row.device === 'phone' && row.treats.join() === 'Magnet,Bubble to go' && row.intro === 'skipped' && row.repair === 53 && row.ver === 107 && row.moon === 'dust' && row.hard === false && row.drone_open === true && row.drone === true, row);
check('version 192 extras stored', row.errors === 2 && row.error === 'TypeError: x is undefined @5100:12' && row.levi_fought.join() === 'whale,jelly' && row.levi_escaped.join() === 'whale' && row.missions === 3 && row.suit === 2 && row.badges === 7 && row.nav === 40 && row.cafes_passed === 4 && row.drone_caught === 6 && row.installed === true && row.browser === 'safari' && row.pauses === 1, row);
check('frame-rate figures stored', row.hz === 120 && row.fps_fight === 93 && row.slow_pct === 18.3, row);
await call('POST', { ...end, run: '5555666677778888', depth: 40, how: 'left' });
check('end without a start makes the row', !!db.plays.find(x => x.run === '5555666677778888'), db.plays);
const { ver: _v, ...old } = end;
await call('POST', { ...old, run: '9999aaaa9999bbbb' });
check('older copies without a version still save', db.plays.find(x => x.run === '9999aaaa9999bbbb')?.ver === null, db.plays);
const { hard: _h, droneOpen: _o, drone: _d, ...noFlags } = end;
await call('POST', { ...noFlags, run: '9999cccc9999dddd' });
check('older copies without hard/drone save them empty', (r => r && r.hard === null && r.drone_open === null && r.drone === null)(db.plays.find(x => x.run === '9999cccc9999dddd')), db.plays);
check('bad how refused', (await call('POST', { ...end, how: 'boom' }))[0] === 400, null);
check('bad run id refused', (await call('POST', { ...end, run: 'zz' }))[0] === 400, null);
await call('POST', { ...end, run: '0000aaaa0000bbbb', fps: 'fast', device: 'fridge', screen: '<b>', treats: ['<x>'], repair: 140, intro: 'maybe', initials: 'ASS', ver: '106', moon: 'Jungle', hard: 'yes', droneOpen: 1, drone: 'on', kid: 'on', errors: -1, error: 'x'.repeat(201), leviFought: ['<b>'], leviEscaped: 'whale', missions: 1.5, suit: 'red', badges: null, nav: -3, cafesPassed: 'many', droneCaught: 1e9, installed: 'yes', browser: 'netscape', pauses: -1, hz: 10, fpsFight: 'fast', slowPct: 101 });
const junk = db.plays.find(x => x.run === '0000aaaa0000bbbb');
check('junk extras stored as empty, run kept', junk.how === 'mine' && [junk.fps, junk.device, junk.screen, junk.treats, junk.repair, junk.intro, junk.initials, junk.ver, junk.moon, junk.hard, junk.drone_open, junk.drone, junk.kid, junk.errors, junk.error, junk.levi_fought, junk.levi_escaped, junk.missions, junk.suit, junk.badges, junk.nav, junk.cafes_passed, junk.drone_caught, junk.installed, junk.browser, junk.pauses, junk.hz, junk.fps_fight, junk.slow_pct].every(v => v === null), junk);

// Kid mode board (version 197): its own top 10 and rank; the normal board never shows kid scores, and the other way round.
const normalTop = (await call('GET'))[1].top.map(t => t.id).join();
const k1 = await call('POST', { initials: 'KID', depth: 99999, kid: true }, '9.9.9.1');
check('kid score at rank 1 of its own board', k1[0] === 200 && k1[1].rank === 1 && k1[1].top.length === 1 && k1[1].top[0].initials === 'KID' && db.scores.find(x => x.initials === 'KID').kid === true, k1);
check('normal board unchanged by a kid score', (await call('GET'))[1].top.map(t => t.id).join() === normalTop, null);
const kidGet = async () => { const res = await handler(new Request('https://fn/scores?kid=1')); return res.json(); };
check('GET ?kid=1 gives the kid board', (await kidGet()).top.map(t => t.initials).join() === 'KID', await kidGet());
const k2 = await call('POST', { initials: 'TOT', depth: 5, kid: true }, '9.9.9.2');
check('kid rank counts only kid scores', k2[1].rank === 2 && k2[1].top.length === 2, k2);
const n1 = await call('POST', { initials: 'NRM', depth: 5, kid: 'yes' }, '9.9.9.3');
check('kid other than true is a normal score', db.scores.find(x => x.initials === 'NRM').kid === false && !n1[1].top.some(t => t.initials === 'KID'), n1);
await call('POST', { event: 'play', player: 'abcdefabcdef0197', run: '0197019701970197', kid: true });
check('kid flag on a run', db.plays.find(x => x.run === '0197019701970197').kid === true, db.plays.at(-1));

// Fresh boards (version 213): scores from before BOARD_FROM stay in the table but aren't on either board or counted in ranks.
db.scores.push({ id: 500, initials: 'OLD', depth: 99000, who: null, created_at: '2026-11-01T10:00:00.000Z', kid: false },
  { id: 501, initials: 'OLK', depth: 99000, who: null, created_at: '2026-11-04T10:00:00.000Z', kid: true });
check('old score not on the board', !(await call('GET'))[1].top.some(t => t.initials === 'OLD'), (await call('GET'))[1]);
check('old kid score not on the kid board', !(await kidGet()).top.some(t => t.initials === 'OLK'), await kidGet());
const f1 = await call('POST', { initials: 'NEW', depth: 98000 }, '9.9.9.4');
check('rank ignores old scores', f1[0] === 200 && f1[1].rank === 1 && f1[1].top[0].initials === 'NEW', f1);
check('old rows kept', db.scores.some(x => x.initials === 'OLD') && db.scores.some(x => x.initials === 'OLK'), null);

// Each score tied to its run: one row per run, checked against the run's play ping (checkRun).
const RP = 'abcabcabcabcabc0', R1 = '1234123412341234';
await call('POST', { event: 'play', player: RP, run: R1 }, '7.7.7.1');
const fast = await call('POST', { initials: 'RUN', depth: 5000, player: RP, run: R1 }, '7.7.7.1');
check('score deeper than the time since its run started refused', fast[0] === 400 && /too deep/.test(fast[1].error), fast);
db.plays.find(x => x.run === R1).created_at = new Date(Date.now() - 10 * 60_000).toISOString();
const ok1 = await call('POST', { initials: 'RUN', depth: 5000, player: RP, run: R1 }, '7.7.7.1');
check('score with its run saved', ok1[0] === 200 && db.scores.filter(x => x.run === R1).length === 1 && db.scores.find(x => x.run === R1).player === RP, ok1);
const again = await call('POST', { initials: 'RUN', depth: 5000, player: RP, run: R1 }, '7.7.7.2');
check('the same run sent again: same answer, no second row', again[0] === 200 && again[1].id === ok1[1].id && again[1].rank === ok1[1].rank && db.scores.filter(x => x.run === R1).length === 1, again);
check('a run nobody started refused', (await call('POST', { initials: 'RUN', depth: 50, player: RP, run: 'ffff0000ffff0000' }, '7.7.7.3'))[0] === 400, null);
const R2 = '2222000022220000';
db.plays.push({ id: nextId++, player: RP, run: R2, created_at: new Date(Date.now() - 3600_000).toISOString(), depth: 800, how: 'mine' });
check('score deeper than its run ended refused', (await call('POST', { initials: 'RUN', depth: 900, player: RP, run: R2 }, '7.7.7.4'))[0] === 400, null);
db.plays.find(x => x.run === R2).how = 'left';
check('a run last seen hidden mid-run may have gone deeper', (await call('POST', { initials: 'RUN', depth: 900, player: RP, run: R2 }, '7.7.7.4'))[0] === 200, null);
// The case behind duplicate scores: the row is saved, then the database fails before the answer, so the phone keeps the
// score in its outbox and sends it again.
const R3 = '3333000033330000';
db.plays.push({ id: nextId++, player: RP, run: R3, created_at: new Date(Date.now() - 3600_000).toISOString(), depth: null, how: null });
failNext = 'count';
const lost = await call('POST', { initials: 'LST', depth: 700, player: RP, run: R3 }, '7.7.7.5');
check('database failure after the insert answers 500', lost[0] === 500 && db.scores.filter(x => x.run === R3).length === 1, lost);
const retry = await call('POST', { initials: 'LST', depth: 700, player: RP, run: R3 }, '7.7.7.5');
check('the retry finds the saved row instead of adding one', retry[0] === 200 && db.scores.filter(x => x.run === R3).length === 1, retry);
// The connection is the last x-forwarded-for entry (the platform's); anything in front of it is the caller's to set.
const spoof = []; for (let k = 0; k < 7; k++) spoof.push((await call('POST', { initials: 'SPF', depth: 5 }, `${k}.0.0.${k}, 8.8.8.8`))[0]);
check('a made-up first hop doesn\'t escape the score limit', spoof.join(',') === '200,200,200,200,200,200,429', spoof);
// Play pings: 30 new runs a minute per connection.
const pings = []; for (let k = 0; k < 32; k++) pings.push((await call('POST', { event: 'play', player: (1e15 + k).toString(16).padStart(16, '0'), run: R1 }, '6.6.6.6'))[0]);
check('30 new runs a minute per connection, then 429', pings.filter(x => x === 200).length === 30 && pings.at(-1) === 429, pings.join());
const endOnly = []; for (let k = 0; k < 2; k++) endOnly.push((await call('POST', { ...end, run: (5e15 + k).toString(16).padStart(16, '0') }, '6.6.6.6'))[0]);
check('an end ping that makes a new row counts too', endOnly.join() === '429,429', endOnly);
check('a launch and the cave are endings', (await call('POST', { ...end, how: 'launch' }, '5.5.5.5'))[0] === 200 && (await call('POST', { ...end, how: 'cave' }, '5.5.5.5'))[0] === 200, null);

console.log(failed ? `${failed} failed, ${passed} passed` : `all ${passed} checks passed`);
process.exit(failed ? 1 : 0);
