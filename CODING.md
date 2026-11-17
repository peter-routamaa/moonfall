# MoonFall code rules

Read this before adding or changing any code in `src/moonfall.html`, together with `PERFORMANCE.md` for anything drawn
or worked out every frame. These rules come from the code review of 15 November 2026: each one is something the
review found going wrong (see *Why these rules* at the end). Following them should make most future reviews
unnecessary. Rules marked **[checked]** are enforced by a script that fails the commit or the website build, so they
can't be forgotten. When a new rule can be checked by a script, add the check (rule 13) rather than only writing it
here.

## The short list

1. **Decide where it goes before writing it.** Find the section it belongs in (the code map at the top of the script
   lists them; `grep -n "^// ---------- " src/moonfall.html` jumps between them) and put it there, not wherever you
   happen to be working. Use the table under *Where things go*. Something that fits no section gets a new section with
   a `// ---------- name ----------` header, and its name goes into the code map's section list in the same edit.
   **[checked: tools/checks.py, every section header is named in the code map]**
2. **One entry per kind.** A Leviathan is one entry in `LEVIATHANS`, a hazard one entry in `HAZARDS`, an attack one in
   `BOSS_ATTACKS`, a kind of shot one in `SHOT_TYPES`. Everything about that one thing (its numbers, drawing, update,
   hit test) goes in its entry. Never add an `if (kind === 'x')` branch somewhere else; if the entry needs a new
   ability, add a field and say what it means in the note at the top of that table.
   **[checked: the game's checkLeviathans() / checkHazards() at load, failed by tools/smoke.py]**
3. **One definition per fact.** A number that has to agree with another gets one named constant (as `LAVA_Q` /
   `LAVA_TOP` for the lava pockets). A shape or formula used in two places becomes one function (`lavaThick`). If a
   JavaScript timing must match a CSS one (a card turn, a fade), name it once in JavaScript and say which CSS rule it
   matches.
4. **Comments say what the code does and why, as it is now.** No history in comments: no "version N", "was", "used
   to", "until", old values. History goes in `MOONFALL-NOTES.md` and the commit message. Keep the owner's words only when
   they state a decision a later editor must respect. When you change code, fix its comment in the same edit; never
   leave a comment that describes a rule or function that isn't there.
   **[checked: tools/checks.py, no "version N", version tag (v197, v197-200, v0.224), "no longer", "used to", "was
   replaced" or "previously" in a comment. A comment that must name a version for another reason (how the version
   number is shown) puts `history-ok` in it]**
5. **Names say what things are, and never hide another.** No one- or two-letter names for anything that lives more
   than a few lines (loop counters and pixel-art coordinates are fine). A local never reuses the name of a global or
   a well-known value: `S` (scenery palette), `P` (palette), `W`, `H`, `sc` (the scale), `cv` (the world canvas), `c`,
   `clock`, `moon`, `state`, `save`, `player`, `boss`, `camY`. **[checked: tools/checks.py, with the JavaScript parser:
   parameters, every name in a declaration, destructuring, loop variables, catch parameters]**
6. **Lines a reader can follow.** In logic, one statement per line; pixel-art drawing may pack a few `fillRect` calls
   together. No ternary nested more than two deep (pick with `if`, or a small lookup table). Aim for 120 characters,
   160 at most, except data tables and sprite rows. **[checked: tools/checks.py, as ratchets: the number of script
   lines over 160 characters that aren't data rows (only literals, names, brackets and commas), and of ternaries nested
   more than two deep, may not go up; lower `LONG_LINES_MAX` / `DEEP_TERNARIES_MAX` when a tidy-up brings one down]**
7. **One error must never stop the game.** There is one frame loop (`frame()`, which survives errors); don't add
   another. Code that borrows shared state to draw elsewhere (`c`, `clock`, `player.x`, `stampDirect`, `bossTmp`) puts
   it back in a `try { } finally { }`. A `setTimeout` checks the state is still what it was made for when it fires.
   Event listeners are added once, at load, never inside something that runs again.
8. **Trust nothing from outside.** Values from `localStorage`, the scores server or the address are checked for
   type before use, with a safe default. A reply missing what it should have is treated as no reply. Anything that
   can be sent twice (a lost reply, a retry from the outbox) must be safe to send twice.
9. **Every state, screen and card is played by the smoke test.** A new state (through `setState`), screen or card
   goes into `tools/smoke.py` in the same change. **[checked: tools/smoke.py fails if a state the game can enter was
   never reached]**
10. **Every player can use it.** Buttons and inputs have a name a screen reader can say (`aria-label`, or a `<label>`
    whose first labelable element is the input). Touch targets are at least 44 px (an invisible `::before` can grow a
    small button). Under `prefers-reduced-motion`, motion becomes a plain fade or nothing; never an animation with a
    tiny duration that still runs (it flickers). Keyboard actions ignore `e.repeat`, and held keys are let go on
    `blur` and when the page is hidden.
11. **Sound follows the page.** Any state that plays music stops it when the page is hidden and picks it up again on
    return (see the `visibilitychange` handler). Noise longer than the 1 s noise buffer sets `loop = true`. The music
    scheduler skips beats it missed; don't schedule from `setInterval` without that guard. Every oscillator and buffer
    source is passed to `freeAfter` with the filters and gains only it uses, so the chain leaves the audio graph when it
    ends (iPhones otherwise keep finished nodes until a garbage collection, and the sound breaks up after 15-20 minutes).
    **[checked: tools/checks.py]**
12. **Prove that a tidy-up changed nothing.** Moving or restructuring code: `tools/same_pixels.py <before.html>` must
    say SAME, and `tools/fight_makes.py --fp=3` must print the same fingerprints on both versions. Only comments
    changed: a careful diff. A refactor never mixes with a behaviour change in the same commit.
13. **Rules that can be checked are checked, and checks fail closed.** A new rule a script can test from the source
    goes into `tools/checks.py` (seconds, run by the commit hook and the build); one that needs the game running goes
    into `tools/smoke.py`. A check that hits an error, or finds less than it expected (fewer fights, no result), fails;
    it never prints OK.

## Where things go

| You're adding | It goes in |
|---|---|
| A Leviathan | an entry in `LEVIATHANS` ("Leviathans: one entry per kind"), its kind in `LEVI_SETS`, its groan in `Sfx.groan`; then `tools/levi_budget.py` (PERFORMANCE.md) |
| A hazard | an entry in `HAZARDS` (the hazards section), with `moon` and `layer` |
| A Leviathan attack or kind of shot | `BOSS_ATTACKS` / `SHOT_TYPES` (boss fights) |
| A moon | `MOON_SURF` (canvas and palette), the rock layers, `LEVI_SETS`, its `HAZARDS` entries, the music's key and instruments; read PERFORMANCE.md section 4 first |
| Anything on the shaft walls or in the shaft | the shaft (walls, layers), alien life (creatures and growths) |
| Something you pick up, or that hurts you | damage and pickups |
| A spark, burst or explosion effect | effects |
| Anything about the café, its shop or perks | coffee stop |
| A badge | badges |
| A new screen, card or card face | the HTML, then "the title card and its faces" (title cards) or "DOM: elements and the HUD" |
| A setting | "settings and Kid mode", and the save's field list in "saved settings" |
| A new field in the save | "saved settings": add it to the list of fields there, with where it's repaired |
| A run statistic sent to the stats | run stats, plus a migration and the scores function (README, *Play stats*) |
| A sound or a voice clip | sound; music in music |
| Phone-specific behaviour (wake lock, back button, Home Screen) | its own section for phones |
| A test or a check | `tools/checks.py` (from the source) or `tools/smoke.py` (needs the game running) |

If two places seem right, pick the one a newcomer would look in first, and leave a one-line pointer comment in the
other.

## Before you finish a change

- It's in the right section; any new section is in the code map.
- Its comments say what and why; none mention versions; comments on code you changed are updated.
- Any `%` a player reads goes through `pctify` (the pixel fonts' `%` reads as a 2): static card text is listed where `pctify` is defined, text set at run time calls it after setting.
- `python3 tools/checks.py` and `python3 tools/smoke.py` say OK (both run in the build anyway).
- Anything drawn or worked out every frame: the PERFORMANCE.md checklist too.
- The history (what changed, why, the owner's request) is in `MOONFALL-NOTES.md` and the commit message.

## Why these rules

What the 2026-11-15 review found, by rule:

1. The café shop sat under the "badges" heading, the helper drone under "damage and pickups", sparks under "level
   generation", the menu buttons under "the launch": each was added next to whatever was being worked on.
2. Adding a Leviathan meant touching about 16 places, with nothing to say one was missed.
3. The lava pocket's shape was written out in six places, including the drops that hurt the pilot.
4. 412 "version N" notes in comments, and a dozen comments that no longer matched their code.
5. Leviathan drawing functions declared a local `S` 20 times, hiding the scenery palette (renamed, now checked).
6. A 627-character line of nested ternaries chose which button got focus.
7. Any error in a frame stopped the game for good.
8. A lost reply could put the same score on the board twice; a reply without a board left the table on "Loading…".
9. No test of the game's logic at all.
10. Kid mode sliders had no spoken names; reduced motion turned the low-health blink into a flicker.
11. Launch music kept playing in the background; long noises stopped with a click. Later, on an iPhone, the sound
    crackled and cut in and out after 15-20 minutes of play: no finished sound was ever disconnected.
12. The pixel check said DIFFERENT on identical files, so nobody could trust it. A later review found it hashed only
    one byte in three, so a change in one colour channel could pass as SAME.
13. A release check printed OK after running no fights at all.

These rules catch the problems we know about. A fresh look at the code now and then (before a big feature, or every
few dozen versions) is still worth it: it finds new kinds of problems, which then become new rules here.
