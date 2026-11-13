# MoonFall

A free pixel-art phone game by PermaFrost Productions. Your ship has crashed on a moon. Fall down the shaft beneath it: steer between the walls, dodge rocks, mines and each layer's own hazards, collect crystals and ship parts, stop at cafés for coffee and the shop, and get away from the Leviathans that chase you through the deep. Repair the ship to finish the mission.

- **Three moons**, each with its own rock layers, hazards, scenery, music and six Leviathans (eighteen in all): the **Dust moon** (glazed ice, crumbling ledges, ash vents), the **Jungle moon** (vines, thorn branches, spore pods) and the **Machine moon** (crushers, saw blades, laser gates). Pick one on the start screen and swap any time in Settings.
- **Unlocks** for finishing the mission: every suit colour and **Terminal Velocity** (4 health, 15% faster, raging Leviathans). Repair the ship on Terminal Velocity to earn a helper drone that falls with you and catches some of what you miss.
- **Kid mode** (in Settings): sliders for fewer mines and Leviathan shots, more ship parts and crystals, more health and a slower fall, and a switch for the speed-up after cafés. Kid mode runs have their own high score board.
- Badges, voiced moments from the pilot, and an online high score board shared by everyone who plays.

Play it at **https://peter-routamaa.github.io/moonfall/**. The `docs` folder is what GitHub Pages publishes as the website.

## What's in here

| Path | What it is |
|---|---|
| `src/moonfall.html` | **The game's source**: the whole game in one file (HTML, CSS and JavaScript), exactly as published on claude.ai. Edit this one. A guide at the top of its script explains how the code fits together. |
| `src/share.png` | The link preview picture (1200 × 630) shown when the game's address is shared in WhatsApp, iMessage and so on. The build copies it to `docs/` and adds the preview tags. |
| `src/voices/` | The pilot's voice clips, recorded for MoonFall (64 kbps mono MP3), loaded by the game when sound starts. |
| `docs/index.html`, `docs/voices/` | The website copy, built from `src/` by `tools/build_site.py`. Don't edit these by hand. |
| `PERFORMANCE.md` | **Performance rules.** Read it before adding anything drawn or worked out every frame (a Leviathan, a moon, a hazard, a layer, an effect): the rules, today's per-frame budgets, and how to measure. |
| `tools/` | Build, test and screenshot scripts (see *Working on the game*). |
| `supabase/migrations/20261031000000_scores.sql` | Creates the online high score table. |
| `supabase/migrations/20261031130000_plays.sql` | Creates the private play counter: the `plays` table and the `play_stats` view. |
| `supabase/migrations/20261031180000_run_stats.sql` | Adds run stats (length, depth, how it ended) and the monthly, yearly and per-player views. |
| `supabase/migrations/20261031200000_more_stats.sql` | Adds frame rate, device, treats, streak, sound, repair and intro stats, and the device, treat, depth band and returning-player views. |
| `supabase/migrations/20261102000000_scores_escaped.sql` | Adds the `escaped` column to `scores`: whether the player had repaired the ship when they set the score (empty for older scores). |
| `supabase/migrations/20261111000000_run_version.sql` | Adds the `ver` column to `plays` (the game version that sent the run; empty for runs before version 106) and the `play_by_version` view. |
| `supabase/migrations/20261112000000_moon.sql` | Adds the `moon` column (`dust` or `jungle`) to `scores` and `plays` (empty before version 113) and the `play_by_moon` view. |
| `supabase/migrations/20261113000000_machine_moon.sql` | Lets the `moon` columns hold `machine` too (version 145). |
| `supabase/migrations/20261113120000_hard_drone.sql` | Adds `hard`, `drone_open` and `drone` to `plays`: whether the run was on Terminal Velocity, whether the helper drone was unlocked, and whether it flew (version 190). |
| `supabase/migrations/20261113150000_run_more.sql` | Adds more run stats to `plays`: game errors, the Leviathans fought and escaped, mission progress (missions, suit, badges, navigation computer), cafés passed, drone catches, home-screen app or browser, pauses (version 192). |
| `supabase/migrations/20261113160000_frame_figures.sql` | Adds three frame-rate figures to `plays`: the screen's refresh rate, the average during Leviathan fights, and the share of frames that stuttered (version 194). |
| `supabase/migrations/20261113180000_kid_board.sql` | Adds `kid` to `scores` (Kid mode runs get their own board; every older score is on the Standard one) and to `plays` (version 198). |
| `supabase/functions/scores/index.ts` | The small server function: saves scores, returns the top 10, and records the run stats. |

The game works on its own: each device keeps its own top 10. When `SCORES_URL` is set (the build fills it in for the website), the high score table also shows an online board shared by everyone who plays.

Nothing in this repository is secret: the game file holds no keys or passwords, and the scoreboard function reads its key from Supabase. The scoreboard's database stays private in Supabase.

## Hosting: GitHub Pages

**Settings → Pages:** source **Deploy from a branch**, branch **main**, folder **/docs**. Every push to `main` republishes the site within a minute or two.

## Working on the game

You need Python 3, Node 22.13 or newer (for the function test), and Google Chrome for screenshots and the Leviathan budget check (the screenshot script is written for a Mac).

Once per clone, turn on the commit check: `git config core.hooksPath tools/hooks`. From then on a commit that changes `src/moonfall.html` runs `tools/levi_budget.py` on the version being committed and stops if a Leviathan is over the budgets in `PERFORMANCE.md`.

1. Edit `src/moonfall.html`. Search for `// ---------- ` to jump between sections; the guide at the top of the script explains the states, units and canvases. When publishing a new version, add one to `VERSION` near the top (the menu shows it as v0. and the number, for example v0.196).
2. Try it: `python3 tools/test_pages.py`, then `python3 -m http.server 8766 -d tools/out` and open http://localhost:8766/test-board.html (the game with a pretend online board, so nothing real is sent). In the browser console, `__mf` gives you the game's internals, for example `__mf.player` (the pilot) or `__mf.state`. The test pages are silent unless you add `?sound=1` to the address.
3. Screenshots at a phone size, with that server running: `tools/shoot.sh 375 667 tools/out/title.png "scene=title"`. Scenes: `splash`, `title` (add `&clean=1` for the clear main menu with only START, `&arrive=` milliseconds to freeze the flip-in after START, or `&card=how`, `&card=settings`, `&card=news`, `&card=levi`, `&card=badges`, `&card=unlocks` or `&card=kid`; `&kid=1` turns Kid mode on first), `pause`, `cafe` (add `&face=shop` or `&face=tips`), `sign` (add `&side=1` for the right), `play` (add `&hp=1` for low health), `opening` (add `&t=` seconds), `void` (add `&at=` pixels below the first void's top; its floor is 1200 down), `levi` (a deep creature mid-screen: `&k=` its 500 m mark, `&kind=whale|elder|jelly|angler|manta|nautilus` to pick one, since the order is random each run; a cafe one shows with `scene=cafe&n=1&kind=...`; `scene=cafe&face=shop&nav=12` shows the navigation computer 12/40 paid), `board` (the high score table with its moon and escaped columns; `&kid=1` for the Kid mode board), `speedup` (just past cafe `&n=`'s ledge with the SPEED +5% banner, frozen at `&at=` ms). Add `&moon=jungle` to any scene for the Jungle moon (version 113; `kind=` then also takes `centipede`, `flytrap`, `moth`, `spider`, `frog` or `mantis`), or `&moon=machine` for the Machine moon (version 145; `drill`, `sentinel`, `crab`, `wasp`, `beetle` or `gear`). The signature hazards (one per rock layer) have their own contact sheet: `tools/shoot_hazards.sh tools/out/hazards.png` (the Dust moon's glazed ice, crumbling ledges and ash vents; the Jungle moon's vines, thorns and spore pods: open `frame.html?w=640&h=1140&scene=haz&moon=jungle`; the Machine moon's crushers, saws and laser gates: `&moon=machine`).
4. If you tidied code and meant to change nothing on screen: `git show HEAD:src/moonfall.html > /tmp/before.html`, then `python3 tools/same_pixels.py /tmp/before.html`. It plays the same scripted session on both versions (title, falling, mines, a café and its shop, dying, the opening film, the launch) and says SAME if every pixel matches.
5. If you changed anything a Leviathan draws: `python3 tools/levi_budget.py` must say OK (it checks every moon's Leviathans against the budgets in `PERFORMANCE.md` and exits 1 if one is over).
   And `python3 tools/fight_makes.py` must say OK: it plays every Leviathan fight (about a minute) and fails if anything makes a canvas after a fight has started, or if any frame in which the pilot is moving makes more than 6, listing when and which function; it also prints what a settled fight costs a frame, to compare with another build (`python3 tools/fight_makes.py /tmp/before.html`).
   To see what a drawing change costs: `python3 tools/bench.py /tmp/before.html` writes `tools/out/bench-before.html` and `bench-after.html`; open each (with that server running) in a normal browser a few times and compare the frame times shown at the top.
6. For anything heavy (a Leviathan, a moon, a hazard, a layer), follow `PERFORMANCE.md` and check its budgets. To measure: `python3 tools/prof.py` writes `tools/out/prof.html`, which plays a seeded run of the whole game (start screen, menu, intro, a fall landing at every café and fighting every Leviathan of the moon, a death, the ending) and reports per scene what a frame costs: time, rectangles, images, pixels covered, canvases created and by which function, page changes and forced layouts. Open `frame.html?w=390&h=844&page=prof.html` (`&moon=jungle`, `&real=1` for one frame per screen refresh); the result is in `window.__prof` inside the frame. With `&fp=3` it fingerprints the picture every third frame instead, to check two builds draw the same thing over the whole run (see the file's first lines).
   To measure a real phone: open the game there with `?perf=1` added to the address (or tap the menu's version number five times). It plays itself for about a minute and shows what each frame cost, scene by scene; nothing is saved or sent. See `PERFORMANCE.md`, "How to measure".
7. If you changed the scoreboard function: `node tools/test_function.mjs` (runs it against a pretend database; it should say all checks passed). Deploy it in Supabase as described below.
8. Build the website copy: `python3 tools/build_site.py`, then commit and push. GitHub Pages updates a minute or two later. The build stops, before touching `docs/`, if `TEST_START_M` is not 0 or `tools/levi_budget.py` or `tools/fight_makes.py` does not pass.

The claude.ai artifact is published from `src/moonfall.html` by the owner, with Claude.

## Working on it together

Anyone can read this repository, but only people you add can change it. To let a friend help: **Settings → Collaborators → Add people**, enter their GitHub username, and they accept the invite. They can then push changes, or open pull requests for you to review.

## Scoreboard: Supabase

- **Organisation:** PermaFrost Productions
- **Project:** MoonFall (ref `ukjajizsnowmdjziqkof`, region eu-west-1)
- **Function:** `scores`, deployed with JWT verification **off** (the game calls it without a key)
- **Function URL:** `https://ukjajizsnowmdjziqkof.supabase.co/functions/v1/scores`

To set it up from scratch:

1. In the project's **SQL Editor**, run each file in `supabase/migrations/` in turn, oldest first (their names start with the date). They create the `scores` and `plays` tables, which only the function can read or write, and the stats views. When a new migration arrives later, run it before deploying the function that uses it.
2. In **Edge Functions**, create a function named exactly `scores` with the code from `supabase/functions/scores/index.ts`, deploy it, and turn **off** JWT verification in its settings.
3. Open the function URL in a browser. You should see `{"top":[...]}`. An error about a missing authorization header means JWT verification is still on.
4. The website build (`tools/build_site.py`) puts this URL into `docs/index.html` as `SCORES_URL`. If the project ever moves, change `SCORES_URL` at the top of that script and build again.

From the command line instead: `supabase functions deploy scores --no-verify-jwt`.

## Play stats (private)

Each device gets an anonymous random ID the first time it plays (16 hex characters, stored in the browser; no name or anything personal). Every run sends a ping when it starts and another when it ends, with:

- **The run:** the game version, the moon, whether it was on Terminal Velocity or in Kid mode, how long it lasted (paused time doesn't count), how deep it got, how it ended (`wall`, `rock`, `mine`, `lava`, `quit` from the pause menu, or `left` if the game was closed or hidden mid-run), the crystals, ship parts, café stops and cafés passed, the treats bought, the best near-miss streak, the Leviathans fought and escaped, the helper drone (unlocked, flying, catches), and the pauses.
- **Progress on the device:** ship repair %, missions finished, the suit worn, badges earned, crystals paid toward the navigation computer, and the player's last high score initials if they have entered any.
- **The device:** its kind, system, browser, screen size, whether the game runs as a home-screen app, whether sound and music were on, whether the opening was watched or skipped (first run of each launch only), the frame rate, slowest frame, screen refresh rate, frame rate during Leviathan fights and the share of frames that stuttered, and any game errors since its last finished run (with the first one's message).

Only the owner can see the numbers, in Supabase (**Table Editor**, or `select * from <view>;` in the SQL Editor):

| View | What it shows |
|---|---|
| `play_stats` | Totals since the start: players, plays, the last 7 days, hours played, average run, deepest and average depth, how runs ended, streaks, sound and music on, intro watched or skipped, frame rate. |
| `play_stats_by_month` | One row per month (UK time), newest first: players, new players, plays, hours, average run, depth, how runs ended. |
| `play_stats_by_year` | The same per year. |
| `player_stats` | One row per player (device), most recent first: initials, first and last played, plays, minutes played, deepest and average depth, crystals, parts, café stops, best streak, repair %, device, system, frame rate. |
| `play_by_device` | Per kind of device and system: players, plays, average frame rate, slowest frames, the most common screen size. |
| `play_treats` | How often each café treat is bought. |
| `play_depth_bands` | Where runs end, in 250 m bands, and what ended them. |
| `play_returning` | By the month players first played (plus an `all` row): how many came back on a later day, and how many within 7 days. |
| `play_by_version` | Per game version and kind of device: players, plays, average and lowest frame rate, slowest frames, first and last run (version 106 on). |
| `play_by_moon` | Per moon (Dust, Jungle, Machine, or unknown for runs before version 113): players, plays, average and deepest depth, hours. |

- Players are devices: one person on a phone and a laptop counts twice, and clearing the browser's data counts again.
- Repeat start pings from the same device within 5 seconds are ignored. Runs from before version 54 have no length or depth.
- The ID `ffffffffffffffff` is reserved for testing and isn't counted.

## Name filter

Kids may play, so rude or offensive initials are refused: the game won't accept them, the function rejects them, and any already stored show as `???`. The list lives in two places that should be kept the same: `BAD_INITIALS` in `src/moonfall.html` and `BAD` in `supabase/functions/scores/index.ts`.

## How the online board behaves

- A run is sent when it makes the top 10 on that device and the player taps **Enter** on their initials.
- The **BEST** button on the main menu (it says TOP 10) opens the board at any time.
- Standard and Kid mode runs have separate boards, online and on the device; a switch on the high score screen picks one.
- With no signal, the run is saved on the device and sent the next time the board opens.
- The function only accepts three letters and a whole number of metres up to 100,000, and refuses more than 6 runs a minute from one connection.
- Scores come from each player's phone, so a determined friend could fake one. That's fine for a game among friends.

## Looking after the board

- **Remove a silly score:** Supabase → **Table Editor** → `scores` → select the row → delete. This is permanent.
- **Wipe the whole board:** run `truncate public.scores;` in the SQL Editor. This is permanent too.
- **Free projects pause** after a while without use. If the board stops loading, open the project in Supabase and restore it. Players' runs wait on their phones in the meantime.
