# MoonFall

A pixel-art phone game by PermaFrost Productions. Fall through the moon, dodge the walls, collect parts and repair your ship.

Play it at **https://peter-routamaa.github.io/moonfall/**. The `docs` folder is what GitHub Pages publishes as the website.

## What's in here

| Path | What it is |
|---|---|
| `docs/index.html` | The whole game in one file. This is the website people open. |
| `supabase/migrations/20261031000000_scores.sql` | Creates the online high score table. |
| `supabase/migrations/20261031130000_plays.sql` | Creates the private play counter: the `plays` table and the `play_stats` view. |
| `supabase/migrations/20261031180000_run_stats.sql` | Adds run stats (length, depth, how it ended) and the monthly, yearly and per-player views. |
| `supabase/functions/scores/index.ts` | The small server function: saves runs, returns the top 10, and counts plays. |

The game works on its own: each device keeps its own top 10. When `SCORES_URL` in `docs/index.html` is set, the high score table also shows an online board shared by everyone who plays.

Nothing in this repository is secret: the game file holds no keys or passwords, and the scoreboard function reads its key from Supabase. The scoreboard's database stays private in Supabase.

## Hosting: GitHub Pages

**Settings → Pages:** source **Deploy from a branch**, branch **main**, folder **/docs**. Every push to `main` republishes the site within a minute or two.

## Working on it together

Anyone can read this repository, but only people you add can change it. To let a friend help: **Settings → Collaborators → Add people**, enter their GitHub username, and they accept the invite. They can then push changes, or open pull requests for you to review.

## Scoreboard: Supabase

- **Organisation:** PermaFrost Productions
- **Project:** MoonFall (ref `ukjajizsnowmdjziqkof`, region eu-west-1)
- **Function:** `scores`, deployed with JWT verification **off** (the game calls it without a key)
- **Function URL:** `https://ukjajizsnowmdjziqkof.supabase.co/functions/v1/scores`

To set it up from scratch:

1. In the project's **SQL Editor**, run `supabase/migrations/20261031000000_scores.sql`, then `supabase/migrations/20261031130000_plays.sql`, then `supabase/migrations/20261031180000_run_stats.sql`. They create the `scores` and `plays` tables, which only the function can read or write, and the stats views.
2. In **Edge Functions**, create a function named exactly `scores` with the code from `supabase/functions/scores/index.ts`, deploy it, and turn **off** JWT verification in its settings.
3. Open the function URL in a browser. You should see `{"top":[...]}`. An error about a missing authorization header means JWT verification is still on.
4. Put the function URL in `docs/index.html`:
   ```js
   const SCORES_URL = 'https://ukjajizsnowmdjziqkof.supabase.co/functions/v1/scores';
   ```

From the command line instead: `supabase functions deploy scores --no-verify-jwt`.

## Play stats (private)

Each device gets an anonymous random ID the first time it plays (16 hex characters, stored in the browser; no name or anything personal). Every run sends a ping when it starts and another when it ends, with how long it lasted (paused time doesn't count), how deep it got, how it ended (`wall`, `rock`, `mine`, `lava`, `quit` from the pause menu, or `left` if the game was closed or hidden mid-run), the crystals, ship parts and café stops of that run, and the player's last high score initials if they have entered any. Only the owner can see the numbers, in Supabase (**Table Editor**, or `select * from <view>;` in the SQL Editor):

| View | What it shows |
|---|---|
| `play_stats` | Totals since the start: players, plays, the last 7 days, hours played, average run, deepest and average depth, and how runs ended. |
| `play_stats_by_month` | One row per month (UK time), newest first: players, new players, plays, hours, average run, depth, how runs ended. |
| `play_stats_by_year` | The same per year. |
| `player_stats` | One row per player (device), most recent first: initials, first and last played, plays, minutes played, deepest and average depth, crystals, parts, café stops. |

- Players are devices: one person on a phone and a laptop counts twice, and clearing the browser's data counts again.
- Repeat start pings from the same device within 5 seconds are ignored. Runs from before version 54 have no length or depth.
- The ID `ffffffffffffffff` is reserved for testing and isn't counted.

## Name filter

Kids may play, so rude or offensive initials are refused: the game won't accept them, the function rejects them, and any already stored show as `???`. The list lives in two places that should be kept the same: `BAD_INITIALS` in `docs/index.html` and `BAD` in `supabase/functions/scores/index.ts`.

## How the online board behaves

- A run is sent when it makes the top 10 on that device and the player taps **Enter** on their initials.
- The **TOP 10** button next to BEST on the main menu opens the board at any time.
- With no signal, the run is saved on the device and sent the next time the board opens.
- The function only accepts three letters and a whole number of metres up to 100,000, and refuses more than 6 runs a minute from one connection.
- Scores come from each player's phone, so a determined friend could fake one. That's fine for a game among friends.

## Looking after the board

- **Remove a silly score:** Supabase → **Table Editor** → `scores` → select the row → delete. This is permanent.
- **Wipe the whole board:** run `truncate public.scores;` in the SQL Editor. This is permanent too.
- **Free projects pause** after a while without use. If the board stops loading, open the project in Supabase and restore it. Players' runs wait on their phones in the meantime.
