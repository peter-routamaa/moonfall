// A pretend Supabase for testing the scores function (supabase/functions/scores/index.ts) without the real one: a
// stand-in for Deno (env and serve) and a small in-memory copy of the database API (PostgREST) for the `scores` and
// `plays` tables, just enough of GET with filters, POST, PATCH and count=exact for what the function uses.
// A plain script with no exports, so it runs both under Node (tools/test_function.mjs imports it) and inside a test
// page (tools/test_reports.py puts it in the page, before the function and the game).
//   const S = fakeSupabase();   installs Deno and the database's fetch; requests to other addresses go to the real fetch
//   S.db                        the tables' rows ({ scores: [], plays: [] }); a test may add or change rows directly.
//                               As the real database: one score per run, one plays row per (player, run) (409 otherwise)
//   S.handler(request)          the function, once it has called Deno.serve (loading it again replaces it)
//   S.later(seconds)            moves the clock (Date.now) on, for everything after
//   S.fail = 'count'            the first count after the next score insert fails, as a database error then would
//   S.nextId                    the next row id
globalThis.fakeSupabase = () => {
  const S = { db: { scores: [], plays: [] }, nextId: 1, fail: '', handler: null };
  const realNow = Date.now.bind(Date);
  let skew = 0;
  Date.now = () => realNow() + skew;
  S.later = seconds => { skew += seconds * 1000; };
  const env = { SUPABASE_URL: 'https://x.supabase.co', SUPABASE_SERVICE_ROLE_KEY: 'eyJfake' };
  globalThis.Deno = { env: { get: k => env[k] }, serve: f => { S.handler = f; } };
  const realFetch = globalThis.fetch;
  globalThis.fetch = async (url, init = {}) => {
    if (!String(url).startsWith(env.SUPABASE_URL + '/')) return realFetch(url, init);
    const db = S.db, u = new URL(url), q = u.searchParams, h = init.headers || {}, table = u.pathname.split('/').pop();
    const method = init.method || 'GET';
    if (h.apikey !== 'eyJfake') return new Response('no auth', { status: 401 });
    if (!db[table]) return new Response('no table ' + table, { status: 404 });
    if (S.fail === 'armed' && h.Prefer === 'count=exact') { S.fail = ''; return new Response('database down', { status: 503 }); }
    if (S.fail === 'count' && method === 'POST' && table === 'scores') S.fail = 'armed';
    if (method === 'POST') {
      const body = JSON.parse(init.body);
      if (table === 'scores' && body.run && db.scores.some(x => x.run === body.run)) return new Response('duplicate key', { status: 409 });
      if (table === 'plays' && body.run && db.plays.some(x => x.player === body.player && x.run === body.run)) return new Response('duplicate key', { status: 409 });
      const row = { id: S.nextId++, created_at: new Date(Date.now()).toISOString(), ...body };
      db[table].push(row);
      return new Response(h.Prefer === 'return=minimal' ? '' : JSON.stringify([row]), { status: 201 });
    }
    if (method === 'PATCH') {
      const body = JSON.parse(init.body);
      // Every filter is col=eq.value; `ends` is 0 on a row that has none, as the database's default.
      const hit = db[table].filter(x => [...q].every(([col, v]) => String(x[col] ?? (col === 'ends' ? 0 : '')) === v.slice(3)));
      hit.forEach(x => Object.assign(x, body));
      return new Response(JSON.stringify(hit), { status: 200 });
    }
    let r = db[table].slice();
    for (const col of ['who', 'player', 'run']) if (q.get(col)) r = r.filter(x => x[col] === q.get(col).slice(3));
    if (q.get('id')) r = r.filter(x => String(x.id) === q.get('id').slice(3));
    if (table === 'scores' && q.get('kid')) r = r.filter(x => !!x.kid === (q.get('kid') === 'eq.true'));
    for (const c of q.getAll('created_at')) r = r.filter(x => x.created_at > c.slice(3));   // gt. only: the board's season and the spam check
    // lte. only: scores shown on the boards. A row without shown_at is shown, as the database's default (now) would be.
    for (const c of q.getAll('shown_at')) r = r.filter(x => !x.shown_at || x.shown_at <= c.slice(4));
    if (q.get('or')) {
      const m = q.get('or').match(/depth\.gt\.(\d+),and\(depth\.eq\.(\d+),id\.lt\.(\d+)\)/);
      r = r.filter(x => x.depth > +m[1] || (x.depth === +m[2] && x.id < +m[3]));
    }
    if (h.Prefer === 'count=exact') return new Response('[]', { headers: { 'content-range': r.length ? `0-0/${r.length}` : `*/0` } });
    r.sort((a, b) => b.depth - a.depth || a.id - b.id);
    const cols = (q.get('select') || 'id,initials,depth,escaped,moon').split(',');
    return new Response(JSON.stringify(r.slice(0, +q.get('limit')).map(x => Object.fromEntries(cols.map(c => [c, x[c] ?? null])))));
  };
  return S;
};
