// MoonFall online high scores and play counter.
//   GET  -> { top }                 the 10 deepest runs (GET ?kid=1: the Kid mode board's)
//   POST -> { top, rank, id }       body { initials: "ABC", depth: 812, escaped: true, moon: "jungle", kid: true,
//                                   player: "<16 hex>", run: "<16 hex>" }; saves the run (escaped: the player had repaired the ship;
//                                   moon: dust, jungle or machine; both optional, null if missing; kid: a Kid mode run, on its own
//                                   board; optional, false if missing). top and rank are that run's board. player and run name the
//                                   run the score came from (see checkRun); the same run sent again gets its first answer back.
//   POST -> { ok }                  body { event: "play", player: "<16 hex>", run: "<16 hex>", ver }; a run started (owner's stats)
//   POST -> { ok }                  body { event: "end", player, run, depth, secs, how, orbs, parts, cafes, initials,
//                                         fps, worst, device, os, screen, treats, streak, sound, music, repair, intro, ver }; how it went
//                                   (ver: the game's version number, e.g. 258; moon: dust, jungle or machine; both optional)
//                                   Both run pings may carry hard, droneOpen, drone and kid (booleans; optional).
//                                   The end ping may carry (optional) errors, error, leviFought, leviEscaped,
//                                   missions, suit, badges, nav, cafesPassed, droneCaught, installed, browser, pauses,
//                                   and the frame-rate figures hz, fpsFight, slowPct (all optional).
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
// Fresh boards (owner: "everyone to start with a fresh scoreboard ... keep old scores for the dashboard"):
// the boards and ranks only count scores saved after this moment. Older rows stay in the table for the stats. Set it to the
// go-live time when deploying a new season (the game's BOARD_SEASON starts each phone's own board fresh at the same release).
const BOARD_FROM = '2026-11-14T11:23:00Z';
const SEASON = `created_at=gt.${encodeURIComponent(BOARD_FROM)}`;
const TOP = 10, MAX_DEPTH = 100000, PER_MINUTE = 6, PLAY_GAP_MS = 5000, PINGS_PER_MINUTE = 30;
const HEX16 = /^[0-9a-f]{16}$/, HOW = new Set(['wall', 'rock', 'mine', 'lava', 'quit', 'left', 'launch', 'cave']);
// The fastest a run can go down, in metres a second: the game's fastest fall is about 50 (250 px/s at 8 px a metre,
// +40% from cafes, +15% in Terminal Velocity), so a score deeper than this allows for the time since its run started
// can't be real.
const MAX_MPS = 75;
// Scores must name their run (player and run), so every score is checked against a run (checkRun). The game sends
// them with every score; false only lets through scores from copies of the game too old to send them.
const REQUIRE_RUN = true;
const DEVICE = new Set(['phone', 'tablet', 'desktop']), OS = new Set(['android', 'ios', 'windows', 'mac', 'chromeos', 'linux', 'other']);

// Initials that aren't allowed, since kids play: refused when sent, and shown as ??? if any are already stored.
// Keep in step with BAD_INITIALS in src/moonfall.html (tools/checks.py checks it, in the commit hook and the build).
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

// kid: the Kid mode board; every score without it is on the normal one. Only this season's scores (BOARD_FROM).
async function top(kid: boolean) {
  const r = await fetch(`${REST}/scores?select=id,initials,depth,escaped,moon&kid=eq.${kid}&${SEASON}&order=depth.desc,id.asc&limit=${TOP}`, { headers: auth });
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

// Rows matching a PostgREST query (filters and select).
async function rows(table: string, query: string) {
  const r = await fetch(`${REST}/${table}?${query}`, { headers: auth });
  if (!r.ok) throw new Error(`rows ${table}: ${r.status} ${await r.text()}`);
  return await r.json();
}

// A unique key already taken (a score's run sent twice at the same moment): PostgREST answers 409.
class Taken extends Error {}
async function insert(table: string, row: unknown, want: boolean) {
  const r = await fetch(`${REST}/${table}`, {
    method: 'POST',
    headers: { ...auth, 'Content-Type': 'application/json', Prefer: want ? 'return=representation' : 'return=minimal' },
    body: JSON.stringify(row),
  });
  if (r.status === 409) throw new Taken(`insert ${table}: ${await r.text()}`);
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
// The game's version number, sent with both pings; empty from copies too old to send it.
const version = (v: unknown) => (whole(v, 100000) && (v as number) >= 1 ? v : null);
// Which moon: the Dust, Jungle or Machine moon; empty from copies too old to send it.
const moonOf = (v: unknown) => (v === 'dust' || v === 'jungle' || v === 'machine' ? v : null);
// Terminal Velocity run, helper drone unlocked on the device, drone flying this run, Kid mode run.
const bool = (v: unknown) => (typeof v === 'boolean' ? v : null);
const flags = (b: Record<string, unknown>) => ({ hard: bool(b.hard), drone_open: bool(b.droneOpen), drone: bool(b.drone), kid: bool(b.kid) });
// Errors, Leviathans fought and escaped, progress on the device, cafes passed, drone catches, how it's played.
const BROWSER = new Set(['safari', 'chrome', 'firefox', 'edge', 'samsung', 'opera', 'inapp', 'other']);
const kinds = (v: unknown) => (Array.isArray(v) && v.length <= 20 && v.every(k => typeof k === 'string' && /^[a-z]{2,16}$/.test(k)) ? v : null);
// Frame-rate figures: refresh rate, fps in Leviathan fights, % of frames missing a refresh.
const tenth = (v: unknown, max: number) => (typeof v === 'number' && v >= 0 && v <= max ? Math.round(v * 10) / 10 : null);
const frames = (b: Record<string, unknown>) => ({
  hz: whole(b.hz, 500) && (b.hz as number) >= 20 ? b.hz : null, fps_fight: tenth(b.fpsFight, 500), slow_pct: tenth(b.slowPct, 100),
});
const more = (b: Record<string, unknown>) => ({
  errors: whole(b.errors, 100000) ? b.errors : null,
  error: typeof b.error === 'string' && b.error.length <= 200 ? b.error.replace(/[^\x20-\x7E]/g, '?') : null,
  levi_fought: kinds(b.leviFought), levi_escaped: kinds(b.leviEscaped),
  missions: whole(b.missions, 10000) ? b.missions : null, suit: whole(b.suit, 100) ? b.suit : null,
  badges: whole(b.badges, 1000) ? b.badges : null, nav: whole(b.nav, 10000) ? b.nav : null,
  cafes_passed: whole(b.cafesPassed, 1000) ? b.cafesPassed : null, drone_caught: whole(b.droneCaught, 10000) ? b.droneCaught : null,
  installed: bool(b.installed), browser: BROWSER.has(b.browser as string) ? b.browser : null, pauses: whole(b.pauses, 10000) ? b.pauses : null,
});

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
    ver: version(b.ver), moon: moonOf(b.moon), ...flags(b), ...more(b), ...frames(b),
  };
}

async function hash(text: string) {
  const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(d)].map(b => b.toString(16).padStart(2, '0')).join('').slice(0, 32);
}

// The connection a request came from, hashed with the secret key (so the stored value can't be turned back into an
// address), or null. Supabase's front door (Cloudflare) replaces any x-forwarded-for a caller sends, and its first
// entry is the caller's address (the same as cf-connecting-ip; tried on the live function with made-up headers).
async function connection(req: Request) {
  const ip = (req.headers.get('x-forwarded-for') ?? '').split(',')[0].trim();
  return ip ? await hash(ip + KEY) : null;
}

// Too many new rows from one connection in the last minute.
async function tooMany(table: string, who: string | null, limit: number) {
  if (!who) return false;
  const since = new Date(Date.now() - 60_000).toISOString();
  return await count(table, `who=eq.${who}&created_at=gt.${encodeURIComponent(since)}`) >= limit;
}

// A score's run must be one the game reported starting (its play ping), long enough ago for the depth at the fastest
// fall, and not deeper than the run's own ending said (unless that ending was only 'left', the app hidden mid-run).
// Returns the reason it can't be real, or ''.
async function checkRun(player: string, run: string, depth: number) {
  const [play] = await rows('plays', `player=eq.${player}&run=eq.${run}&select=created_at,depth,how&limit=1`);
  if (!play) return 'no such run';
  if ((Date.now() - Date.parse(play.created_at)) / 1000 < depth / MAX_MPS) return 'too deep for the time';
  if (typeof play.depth === 'number' && play.how !== 'left' && play.depth < depth) return 'deeper than the run went';
  return '';
}

// The answer for a saved score: its board and its rank there (deeper first, earlier run first on a tie, as the table).
async function placed(row: { id: number, depth: number, kid: boolean }) {
  const above = await count('scores', `kid=eq.${row.kid}&${SEASON}&or=(depth.gt.${row.depth},and(depth.eq.${row.depth},id.lt.${row.id}))`);
  return reply({ top: await top(row.kid), rank: above + 1, id: row.id });
}

Deno.serve(async req => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: cors });
  try {
    if (req.method === 'GET') return reply({ top: await top(new URL(req.url).searchParams.get('kid') === '1') });
    if (req.method !== 'POST') return reply({ error: 'method not allowed' }, 405);
    const body = await req.json().catch(() => null);

    // A run started: one row per run, keyed by the anonymous ID the game made for that device.
    // Repeats from the same ID within 5 s are ignored, which keeps double taps and spam out of the counts.
    if (body?.event === 'play') {
      const player = typeof body.player === 'string' ? body.player : '';
      if (!HEX16.test(player)) return reply({ error: 'bad player id' }, 400);
      const run = typeof body.run === 'string' && HEX16.test(body.run) ? body.run : null;
      const since = new Date(Date.now() - PLAY_GAP_MS).toISOString();
      if (await count('plays', `player=eq.${player}&created_at=gt.${encodeURIComponent(since)}`) > 0) return reply({ ok: true });
      const who = await connection(req);
      if (await tooMany('plays', who, PINGS_PER_MINUTE)) return reply({ error: 'too many runs, try again in a minute' }, 429);
      await insert('plays', { player, run, who, ver: version(body.ver), moon: moonOf(body.moon), ...flags(body) }, false);
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
      if (await update('plays', `player=eq.${player}&run=eq.${run}`, row) > 0) return reply({ ok: true });
      const who = await connection(req);
      if (await tooMany('plays', who, PINGS_PER_MINUTE)) return reply({ error: 'too many runs, try again in a minute' }, 429);
      await insert('plays', { player, run, who, ...row }, false);
      return reply({ ok: true });
    }

    const initials = typeof body?.initials === 'string' ? body.initials.toUpperCase() : '';
    const depth = body?.depth;
    if (!/^[A-Z]{3}$/.test(initials) || !Number.isInteger(depth) || depth < 1 || depth > MAX_DEPTH) {
      return reply({ error: 'initials must be 3 letters and depth a whole number of metres' }, 400);
    }
    if (BAD.has(initials)) return reply({ error: 'those initials are not allowed' }, 400);

    // The run it came from: sent again (a lost reply, the phone's outbox), it gets the same answer, not a second row.
    const player = typeof body?.player === 'string' && HEX16.test(body.player) ? body.player : null;
    const run = typeof body?.run === 'string' && HEX16.test(body.run) ? body.run : null;
    const sameRun = async () => (await rows('scores', `run=eq.${run}&select=id,depth,kid&limit=1`))[0];
    if (player && run) {
      const first = await sameRun();
      if (first) return await placed(first);
      const why = await checkRun(player, run, depth);
      if (why) return reply({ error: `score refused: ${why}` }, 400);
    } else if (REQUIRE_RUN) return reply({ error: 'a score needs its player and run' }, 400);

    // A few runs a minute per connection is plenty; more than that is someone spamming the board.
    const who = await connection(req);
    if (await tooMany('scores', who, PER_MINUTE)) return reply({ error: 'too many scores, try again in a minute' }, 429);

    const escaped = typeof body?.escaped === 'boolean' ? body.escaped : null;
    const kid = body?.kid === true;
    try {
      return await placed(await insert('scores', { initials, depth, who, escaped, moon: moonOf(body?.moon), kid, player, run }, true));
    } catch (e) {
      if (e instanceof Taken && run) return await placed(await sameRun());   // the same run, saved a moment ago
      throw e;
    }
  } catch (e) {
    console.error(e);
    return reply({ error: 'scoreboard error' }, 500);
  }
});
