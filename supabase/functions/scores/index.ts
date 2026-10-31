// MoonFall online high scores and play counter.
//   GET  -> { top }                 the 10 deepest runs
//   POST -> { top, rank, id }       body { initials: "ABC", depth: 812 }; saves the run
//   POST -> { ok }                  body { event: "play", player: "<16 hex>", run: "<16 hex>" }; a run started (owner's stats)
//   POST -> { ok }                  body { event: "end", player, run, depth, secs, how, orbs, parts, cafes, initials,
//                                         fps, worst, device, os, screen, treats, streak, sound, music, repair, intro }; how it went
// The game only knows this function's URL. The secret key comes from the function's own
// environment (Supabase provides SUPABASE_URL plus SUPABASE_SECRET_KEYS on newer projects and
// SUPABASE_SERVICE_ROLE_KEY on all), so no key is ever in the game file.
// Deploy with JWT verification turned off.

function secretKey() {
  try {
    const keys = JSON.parse(Deno.env.get('SUPABASE_SECRET_KEYS') ?? '{}');
    if (typeof keys.default === 'string' && keys.default) return keys.default;
  } catch { /* fall back to the legacy key */ }
  return Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '';
}
const BASE = Deno.env.get('SUPABASE_URL') ?? '';
const KEY = secretKey();
const REST = `${BASE}/rest/v1`;
const TOP = 10, MAX_DEPTH = 100000, PER_MINUTE = 6, PLAY_GAP_MS = 5000;
const HEX16 = /^[0-9a-f]{16}$/, HOW = new Set(['wall', 'rock', 'mine', 'lava', 'quit', 'left']);
const DEVICE = new Set(['phone', 'tablet', 'desktop']), OS = new Set(['android', 'ios', 'windows', 'mac', 'chromeos', 'linux', 'other']);

// Initials that aren't allowed, since kids play: refused when sent, and shown as ??? if any are already stored.
// Keep in step with BAD_INITIALS in docs/index.html.
const BAD = new Set(['ARS', 'ASS', 'BCH', 'CNT', 'COC', 'COK', 'CUM', 'DCK', 'DIC', 'DIK', 'DIX', 'FAG', 'FCK', 'FCU', 'FGT', 'FKU', 'FUC', 'FUK', 'FUQ', 'FUX', 'GFY',
  'HOE', 'HOR', 'JIZ', 'JZZ', 'KKK', 'KMS', 'KNT', 'KYS', 'NAZ', 'NGA', 'NGR', 'NIG', 'NZI', 'PIS', 'PNS', 'PSS', 'PUS', 'SEX', 'SHT', 'SLT', 'SLU', 'SXY', 'TIT', 'TWT', 'VAG', 'WNK', 'WTF', 'XXX']);

const cors = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'content-type',
};
// Legacy service keys are JWTs and also go in Authorization; newer secret keys only go in apikey.
const auth: Record<string, string> = { apikey: KEY, ...(KEY.startsWith('eyJ') ? { Authorization: `Bearer ${KEY}` } : {}) };
const reply = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...cors, 'Content-Type': 'application/json' } });

async function top() {
  const r = await fetch(`${REST}/scores?select=id,initials,depth&order=depth.desc,id.asc&limit=${TOP}`, { headers: auth });
  if (!r.ok) throw new Error(`top: ${r.status} ${await r.text()}`);
  const rows = await r.json();
  return rows.map((s: { initials: string }) => (BAD.has(s.initials) ? { ...s, initials: '???' } : s));
}

// Number of rows in a table matching a PostgREST filter, read from the Content-Range header ("0-0/42").
async function count(table: string, filter: string) {
  const r = await fetch(`${REST}/${table}?select=id&limit=1&${filter}`, { headers: { ...auth, Prefer: 'count=exact' } });
  if (!r.ok) throw new Error(`count: ${r.status} ${await r.text()}`);
  return Number((r.headers.get('content-range') ?? '*/0').split('/')[1]) || 0;
}

async function insert(table: string, row: unknown, want: boolean) {
  const r = await fetch(`${REST}/${table}`, {
    method: 'POST',
    headers: { ...auth, 'Content-Type': 'application/json', Prefer: want ? 'return=representation' : 'return=minimal' },
    body: JSON.stringify(row),
  });
  if (!r.ok) throw new Error(`insert ${table}: ${r.status} ${await r.text()}`);
  return want ? (await r.json())[0] : null;
}

// Updates matching rows and returns how many changed.
async function update(table: string, filter: string, row: unknown) {
  const r = await fetch(`${REST}/${table}?${filter}`, {
    method: 'PATCH',
    headers: { ...auth, 'Content-Type': 'application/json', Prefer: 'return=representation' },
    body: JSON.stringify(row),
  });
  if (!r.ok) throw new Error(`update ${table}: ${r.status} ${await r.text()}`);
  return (await r.json()).length;
}

const whole = (v: unknown, max: number) => Number.isInteger(v) && (v as number) >= 0 && (v as number) <= max;

// The extra run stats are optional (older copies of the game don't send them); anything missing or malformed is stored as empty.
function extras(b: Record<string, unknown>) {
  const fps = typeof b.fps === 'number' && b.fps >= 0 && b.fps <= 500 ? Math.round(b.fps * 10) / 10 : null;
  const treats = Array.isArray(b.treats) && b.treats.length <= 20 && b.treats.every(t => typeof t === 'string' && /^[A-Za-z][A-Za-z ]{0,23}$/.test(t)) ? b.treats : null;
  return {
    fps, worst_ms: whole(b.worst, 10000) ? b.worst : null,
    device: DEVICE.has(b.device as string) ? b.device : null, os: OS.has(b.os as string) ? b.os : null,
    screen: typeof b.screen === 'string' && /^[0-9]{2,5}x[0-9]{2,5}@[0-9.]{1,5}$/.test(b.screen) ? b.screen : null,
    treats, streak: whole(b.streak, 100000) ? b.streak : null,
    sound: typeof b.sound === 'boolean' ? b.sound : null, music: typeof b.music === 'boolean' ? b.music : null,
    repair: whole(b.repair, 100) ? b.repair : null, intro: b.intro === 'watched' || b.intro === 'skipped' ? b.intro : null,
  };
}

async function hash(text: string) {
  const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(d)].map(b => b.toString(16).padStart(2, '0')).join('').slice(0, 32);
}

Deno.serve(async req => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: cors });
  try {
    if (req.method === 'GET') return reply({ top: await top() });
    if (req.method !== 'POST') return reply({ error: 'method not allowed' }, 405);
    const body = await req.json().catch(() => null);

    // A run started: one row per run, keyed by the anonymous ID the game made for that device.
    // Repeats from the same ID within 5 s are ignored, which keeps double taps and spam out of the counts.
    if (body?.event === 'play') {
      const player = typeof body.player === 'string' ? body.player : '';
      if (!HEX16.test(player)) return reply({ error: 'bad player id' }, 400);
      const run = typeof body.run === 'string' && HEX16.test(body.run) ? body.run : null;
      const since = new Date(Date.now() - PLAY_GAP_MS).toISOString();
      if (await count('plays', `player=eq.${player}&created_at=gt.${encodeURIComponent(since)}`) === 0) await insert('plays', { player, run }, false);
      return reply({ ok: true });
    }

    // A run ended (or the game was hidden mid-run, sent again with the real ending later): fill in that run's row.
    // If its start ping never arrived, the row is made now.
    if (body?.event === 'end') {
      const { player, run, depth, secs, how, orbs, parts, cafes } = body;
      if (typeof player !== 'string' || !HEX16.test(player) || typeof run !== 'string' || !HEX16.test(run)) return reply({ error: 'bad player or run id' }, 400);
      if (!whole(depth, MAX_DEPTH) || !whole(secs, 86400) || !HOW.has(how) || !whole(orbs, 10000) || !whole(parts, 10000) || !whole(cafes, 1000)) {
        return reply({ error: 'bad run stats' }, 400);
      }
      const initials = typeof body.initials === 'string' && /^[A-Z]{3}$/.test(body.initials) && !BAD.has(body.initials) ? body.initials : null;
      const row = { depth, secs, how, orbs, parts, cafes, initials, ...extras(body), ended_at: new Date().toISOString() };
      if (await update('plays', `player=eq.${player}&run=eq.${run}`, row) === 0) await insert('plays', { player, run, ...row }, false);
      return reply({ ok: true });
    }

    const initials = typeof body?.initials === 'string' ? body.initials.toUpperCase() : '';
    const depth = body?.depth;
    if (!/^[A-Z]{3}$/.test(initials) || !Number.isInteger(depth) || depth < 1 || depth > MAX_DEPTH) {
      return reply({ error: 'initials must be 3 letters and depth a whole number of metres' }, 400);
    }
    if (BAD.has(initials)) return reply({ error: 'those initials are not allowed' }, 400);

    // A few runs a minute per connection is plenty; more than that is someone spamming the board.
    const ip = (req.headers.get('x-forwarded-for') ?? '').split(',')[0].trim();
    const who = ip ? await hash(ip + BASE) : null;
    if (who) {
      const since = new Date(Date.now() - 60_000).toISOString();
      if (await count('scores', `who=eq.${who}&created_at=gt.${encodeURIComponent(since)}`) >= PER_MINUTE) {
        return reply({ error: 'too many scores, try again in a minute' }, 429);
      }
    }

    const row = await insert('scores', { initials, depth, who }, true);
    // Rank in the same order as the table: deeper first, earlier run first on a tie.
    const above = await count('scores', `or=(depth.gt.${depth},and(depth.eq.${depth},id.lt.${row.id}))`);
    return reply({ top: await top(), rank: above + 1, id: row.id });
  } catch (e) {
    console.error(e);
    return reply({ error: 'scoreboard error' }, 500);
  }
});
