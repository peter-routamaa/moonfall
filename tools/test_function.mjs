// Tests the scoreboard and stats function (supabase/functions/scores/index.ts) without Supabase: it runs under Node
// with a stand-in for Deno and a small in-memory copy of the database API, then checks the answers.
//   node tools/test_function.mjs            (needs Node 22.13 or newer, for stripTypeScriptTypes)
import { stripTypeScriptTypes } from 'node:module';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const src = stripTypeScriptTypes(readFileSync(process.argv[2] || root + 'supabase/functions/scores/index.ts', 'utf8'));
mkdirSync(root + 'tools/out', { recursive: true });
writeFileSync(root + 'tools/out/function.mjs', src);

// Fake Deno (env and serve) and a fake PostgREST for the `scores` and `plays` tables: just enough of GET with filters,
// POST, PATCH and count=exact for what the function uses.
let handler; const db = { scores: [], plays: [] }; let nextId = 1;
globalThis.Deno = { env: { get: k => ({ SUPABASE_URL: 'https://x.supabase.co', SUPABASE_SERVICE_ROLE_KEY: 'eyJfake' })[k] }, serve: f => { handler = f; } };
globalThis.fetch = async (url, init = {}) => {
  const u = new URL(url), q = u.searchParams, h = init.headers || {}, table = u.pathname.split('/').pop();
  if (h.apikey !== 'eyJfake') return new Response('no auth', { status: 401 });
  if (!db[table]) return new Response('no table ' + table, { status: 404 });
  if ((init.method || 'GET') === 'POST') { const b = JSON.parse(init.body); const row = { id: nextId++, ...b, created_at: new Date().toISOString() }; db[table].push(row); return new Response(h.Prefer === 'return=minimal' ? '' : JSON.stringify([row]), { status: 201 }); }
  if (init.method === 'PATCH') { const b = JSON.parse(init.body); const hit = db[table].filter(x => x.player === q.get('player').slice(3) && x.run === q.get('run').slice(3)); hit.forEach(x => Object.assign(x, b)); return new Response(JSON.stringify(hit), { status: 200 }); }
  let r = db[table].slice();
  for (const col of ['who', 'player']) if (q.get(col)) r = r.filter(x => x[col] === q.get(col).slice(3));
  if (q.get('created_at')) r = r.filter(x => x.created_at > q.get('created_at').slice(3));
  if (q.get('or')) { const m = q.get('or').match(/depth\.gt\.(\d+),and\(depth\.eq\.(\d+),id\.lt\.(\d+)\)/); r = r.filter(x => x.depth > +m[1] || (x.depth === +m[2] && x.id < +m[3])); }
  if (h.Prefer === 'count=exact') return new Response('[]', { headers: { 'content-range': r.length ? `0-0/${r.length}` : `*/0` } });
  r.sort((a, b) => b.depth - a.depth || a.id - b.id);
  return new Response(JSON.stringify(r.slice(0, +q.get('limit')).map(({ id, initials, depth }) => ({ id, initials, depth }))));
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
check('rude initials refused', (await call('POST', { initials: 'ass', depth: 300 }, 'b'))[0] === 400, null);
check('bad depth refused', (await call('POST', { initials: 'ABC', depth: -5 }, 'c'))[0] === 400, null);
db.scores.push({ id: 99, initials: 'FUK', depth: 900, who: null, created_at: '2026-01-01' });
const masked = (await call('GET'))[1].top.map(t => t.initials + t.depth).join(' ');
check('rude names already stored show as ???', masked === '???900 ABC500', masked);
const burst = []; for (let k = 0; k < 8; k++) burst.push((await call('POST', { initials: 'SPM', depth: 5 }, 'spam'))[0]);
check('6 scores a minute per connection, then 429', burst.join(',') === '200,200,200,200,200,200,429,429', burst);

// Play stats
const P = '00112233aabbccdd', RUN = '1111222233334444';
check('play ping', (await call('POST', { event: 'play', player: P, run: RUN }))[0] === 200, null);
await call('POST', { event: 'play', player: P, run: RUN });
check('repeat ping within 5 s ignored', db.plays.filter(x => x.player === P).length === 1, db.plays);
check('bad player id refused', (await call('POST', { event: 'play', player: 'nope' }))[0] === 400, null);
const end = { event: 'end', player: P, run: RUN, depth: 812, secs: 95, how: 'mine', orbs: 7, parts: 2, cafes: 0, initials: 'PJR',
  fps: 89.67, worst: 41, device: 'phone', os: 'android', screen: '412x915@2.63', treats: ['Magnet', 'Bubble to go'], streak: 17, sound: true, music: false, repair: 53, intro: 'skipped' };
check('end ping', (await call('POST', end))[0] === 200, null);
await call('POST', { ...end, depth: 900, secs: 120, how: 'rock' });
const row = db.plays.find(x => x.run === RUN);
check('second end updates the same run', row.depth === 900 && row.how === 'rock' && db.plays.filter(x => x.run === RUN).length === 1, row);
check('extras stored', row.fps === 89.7 && row.device === 'phone' && row.treats.join() === 'Magnet,Bubble to go' && row.intro === 'skipped' && row.repair === 53, row);
await call('POST', { ...end, run: '5555666677778888', depth: 40, how: 'left' });
check('end without a start makes the row', !!db.plays.find(x => x.run === '5555666677778888'), db.plays);
check('bad how refused', (await call('POST', { ...end, how: 'boom' }))[0] === 400, null);
check('bad run id refused', (await call('POST', { ...end, run: 'zz' }))[0] === 400, null);
await call('POST', { ...end, run: '0000aaaa0000bbbb', fps: 'fast', device: 'fridge', screen: '<b>', treats: ['<x>'], repair: 140, intro: 'maybe', initials: 'ASS' });
const junk = db.plays.find(x => x.run === '0000aaaa0000bbbb');
check('junk extras stored as empty, run kept', junk.how === 'mine' && [junk.fps, junk.device, junk.screen, junk.treats, junk.repair, junk.intro, junk.initials].every(v => v === null), junk);

console.log(failed ? `${failed} failed, ${passed} passed` : `all ${passed} checks passed`);
process.exit(failed ? 1 : 0);
