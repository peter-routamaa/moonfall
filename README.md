# MoonFall

A pixel-art phone game by PermaFrost Productions. Fall through the moon, dodge the walls, collect parts and repair your ship.

This repository is private. Only the `public` folder is published as the website.

## What's in here

| Path | What it is |
|---|---|
| `public/index.html` | The whole game in one file. This is the website people open. |
| `supabase/migrations/20261031000000_scores.sql` | Creates the online high score table. |
| `supabase/functions/scores/index.ts` | The small server function that saves runs and returns the top 10. |

The game works on its own: each device keeps its own top 10. When `SCORES_URL` in `public/index.html` is set, the high score table also shows an online board shared by everyone who plays.

The game file holds no keys or passwords. Players' browsers download the whole game file, so anyone playing can see its code; the scoreboard's database stays private in Supabase.

## Hosting: Cloudflare Pages

The site is published by Cloudflare Pages, connected to this repository:

- **Production branch:** `main`
- **Framework preset:** None
- **Build command:** (empty)
- **Build output directory:** `public`

Every push to `main` republishes the site within a minute or two.

## Scoreboard: Supabase

- **Organisation:** PermaFrost Productions
- **Project:** MoonFall (ref `ukjajizsnowmdjziqkof`, region eu-west-1)
- **Function:** `scores`, deployed with JWT verification **off** (the game calls it without a key)
- **Function URL:** `https://ukjajizsnowmdjziqkof.supabase.co/functions/v1/scores`

To set it up from scratch:

1. In the project's **SQL Editor**, run the whole of `supabase/migrations/20261031000000_scores.sql`. It creates a `scores` table that only the function can read or write.
2. In **Edge Functions**, create a function named exactly `scores` with the code from `supabase/functions/scores/index.ts`, deploy it, and turn **off** JWT verification in its settings.
3. Open the function URL in a browser. You should see `{"top":[...]}`. An error about a missing authorization header means JWT verification is still on.
4. Put the function URL in `public/index.html`:
   ```js
   const SCORES_URL = 'https://ukjajizsnowmdjziqkof.supabase.co/functions/v1/scores';
   ```

From the command line instead: `supabase functions deploy scores --no-verify-jwt`.

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
