# MoonFall performance rules

Read this before adding anything that is drawn or worked out every frame: a Leviathan, a moon, a hazard, a background
layer, an effect, a HUD read-out. It is what the version 129 performance pass found, turned into rules. Each rule names
the code that already follows it, so there is a pattern to copy.

The game runs on phones at 60 or 120 frames a second, so a frame has 8 to 16 ms for everything. No scene is slow on
average. What phones feel is **stutter**: a frame that suddenly has to build something. Most rules below are about
never building anything in the middle of play.

## The short list

1. **Make no canvas, pattern or image during play.** Make them once (at start-up, at a cafe, in the thin shaft before a
   fight) and reuse them.
2. **A store of ready-made images must have a fixed upper size**, and must never be emptied all at once when it fills.
3. **A colour that changes over time gets no image of its own.** Recolour a reused sheet, or draw the shape straight in.
4. **Anything asked once per wall row is asked hundreds of times a frame.** It must answer from memory and make no
   objects or arrays.
5. **Draw runs, not pixels.** Neighbouring rows or pixels that come out the same are one rectangle.
6. **Never composite over the whole screen every frame.** Paint into a canvas the size of the thing, a few times a second.
7. **Touch the page (the HUD) only when a value changes, and don't measure it every frame.**
8. **Throttle by time, not by frame**, so a 120 Hz phone doesn't do twice the work.
9. **Measure before and after with `tools/prof.py`**, on every moon, and check the picture is unchanged.
10. **Run `python3 tools/levi_budget.py` before publishing anything a Leviathan draws.** It counts every Leviathan (eighteen since version 145) against
    the budgets below in about two seconds and fails (exit 1) naming the creature and the number that's over.
    Two gates run it for you, so it holds even for someone who has not read this file: a commit that changes
    `src/moonfall.html` (`tools/hooks/pre-commit`) and the website build (`tools/build_site.py`) both stop when it
    fails. Never skip them (`--no-verify`); fix the creature.

## Budgets (what the game costs now; stay inside these)

From the profiler's seeded 15 km run at 320 x 694 game pixels. Counts are exact and repeat run to run.

| Per frame | Now | Notes |
|---|---|---|
| Rectangles on screen, falling | 500-730 (Dust), 540-1,000 (Jungle), 530-880 (Machine), about 1,200 with Jungle vines on screen | |
| Images stamped on screen | 120-185 | |
| Pixels covered by images | 0.74-0.90 million since version 154 (was 0.8-1.1 million) | the cost a phone's graphics chip feels most |
| Rectangles into off-screen canvases, in a fight | 315-710 | the Leviathan's paints |
| Canvases created | **0 in steady play** | about 1,000 over a whole run, nearly all first-time use; 16-56 per fight |
| Page changes | about 1 | the depth read-out and the smooth-scroll nudge |
| Page measurements (forced layouts) | 0 in the fall | 3.4 at a cafe counter (`placeSay`), tolerated |
| Wall maths while falling | `hash` 430-620, `bossAt` 120-210, `voidAt` 77-110 calls | |

A Leviathan, measured on its own by `tools/levi_budget.py` (all eighteen, averaged over 30 moments; version 141, Machine six added in 145). The
script holds these limits too: change both together.

| | Range across the eighteen |
|---|---|
| Background shape (`LEVI_DRAW[kind]`), drawing calls per frame | 117-749 (limit 750) |
| One fight paint (three `bossStage` steps) | 1,018-2,094 rectangles (limit 2,172), 30-194 stamps (limit 195) |
| One paint while fading in | 1,206-3,084 rectangles (limit 3,334) |

If a new thing pushes a number well outside its range, fix that before publishing. If it has to, say so in the notes
with the before and after.

Why the script exists (version 141): in version 137 Gnashbloom was reshaped (wide-open jaws, three small mouths on its
stalk) by a thread that hadn't read this file, and nothing counted it: its background went to 931 calls a frame, its
fight paint to 2,384 rectangles and its fade-in to 4,041, and the owner felt the fight stutter on a phone. Version 140
brought it back inside; `levi_budget.py` would have failed version 137 on all three.

## Rules in detail

### 1. Images and canvases

- `document.createElement('canvas')`, `createPattern`, `createImageData` and `getImageData` don't belong in code that
  runs every frame. If the profiler's `makers` list shows a function making canvases all through a run, that is the bug.
- **Fixed upper size.** `wallArt` keeps at most 18 sheets and, when a new colour needs one, takes over the sheet unused
  the longest. `elderFrame` keeps three colours and drops the oldest. Do it like that. Before version 129 two stores
  were emptied whenever they passed 24 colours, so even the colours in constant use were rebuilt again and again.
- **Recolour, don't rebuild.** For flat single-colour shapes, draw every shape once in white on a mask sheet, then
  colour a copy: `globalCompositeOperation = 'copy'`, draw the mask, `'source-atop'`, fill with the colour
  (`wallArt`; `backTileIn` does the same for the back layers). Use `'source-atop'`, not `'source-in'`, if the sheet has
  regions in different colours: `'source-in'` clears everything outside the rectangle being filled.
- **`disc()` and `ring()` keep an image per colour and size for good.** Call them only with a small fixed set of colours
  and sizes. For a colour or size that animates, either set `stampDirect` around the drawing (as `bossStage` does) or
  use `fillRect`. Discs wider than 48 px radius and rings over 60 are drawn row by row every time: keep those rare.
- **One scratch canvas for throwaway work.** `scratch(w, h)` hands out a shared 240 x 160 canvas, cleared. `checks()`
  repaints one 2 x 2 canvas for every new colour. Don't make a canvas to use once.
- **Build at a quiet moment.** A fight's five paint canvases are made in the thin shaft, with the music (`bossBufs`),
  not on the fight's first frame. Wall tiles are painted a few rows a frame ahead of the camera (`prepaint`, 24 rows a
  frame). Anything big that a new feature needs should be made at a cafe, in the thin shaft, or spread the same way.

### 2. Colours that change

Rock colours blend over 120 m around every layer boundary, in 16 steps: **a new colour every 60 px of depth, about 12
different ones on screen at once**. A Leviathan fading in has a new palette for every paint. So:

- Never key an image on a blended or fading colour. Key on the palette object from `palAt()` (they are shared and
  remembered), or on a rock layer's own colour: `Q.pure` is true for those.
- Work a derived colour out once and keep it on the palette object, as `Q.near`, `Q.far`, `Q.lev0` and `bossPal` do.
  `mix()` every frame for a value that doesn't change is waste. `applyMoon` throws the palettes away, so nothing goes stale.
- `mix()` takes `'#RRGGBB'` only.

### 3. Leviathans

- The shading (`bossBand`) is three passes over the paint canvas per band since version 154 (fill the band colour, cut the
  shifted shape out, lay it on with `source-atop`), not four; the picture is the same for every Leviathan whose shape
  has no half-covered pixels. Keep shapes on whole pixels (round a bob before using it, as `gearY` does): the jellyfish's
  threads sit on half pixels, so it keeps the old four-pass way.
- All of a Leviathan's fight art goes through `bossStage`: three steps into a canvas the size of the creature
  (`BOSS_BOX`), started at most 20 times a second (`BOSS_PAINT_EVERY`). Every frame then only stamps the finished
  canvas. Never draw fight art straight to the screen, and never add a compositing pass over the whole screen: that is
  what once took a 120 Hz phone to about 10 frames a second in a fight.
- Draw with `disc`, `ring`, `bpx`, `bline`, `fillPoly`, `fillEllipse` and `limb`, with colours from the palette
  `bossStage` hands in. They all work when `stampDirect` is on. Don't keep your own images per colour.
- Long thin parts (legs, veins, antennae) are `limb` quads, not rows of small discs and not `bline` (a rectangle per
  pixel). Rows of discs are what put the first drafts of the spider, frog and mantis at about three times the busiest of the others.
- See-through glows: `disc` with `globalAlpha` below 1 is fine (it goes through the scratch canvas). A see-through
  `ring` still makes an image per colour, so give it a fixed colour.
- Shots: one image per colour set and size (`shotImg`), with fixed colours.
- The background creature (`LEVI_DRAW[kind]`) is drawn in full every frame it is near the screen, so its count matters
  most. Keep it inside the table above.

### 4. A new moon

- A moon is five rock layers (`MOON_MATS`) plus its surface colours, hazards and Leviathans. Everything keyed on a
  palette copes with new colours on its own; nothing should be keyed on a colour written out in code.
- `applyMoon` must retire or pool everything it replaces (tiles, back layers) so that swapping moons leaks nothing.
- Hazards are drawn every frame they are on screen, and a moon's signature hazard is on screen a lot. Budget them like
  anything else: the Jungle vines were 1,100 one-pixel rectangles a frame until their rows were merged.
- Profile the new moon on its own (`&moon=<name>`): the run fights every one of its Leviathans.

### 5. Wall and world maths

- `edgesRaw` runs for every wall row of every tile, and `edgeAt` hundreds of times a frame. Anything they call
  (`voidAt`, `bossAt`, `splitAt`, `ledge`, `cavernAt`) must be cheap.
- **Remember the answer per stretch and seed**, as `voidInfo` and `splitAt` do (a small `Map`, checked against `SEED`,
  capped at 64 entries). Before that, one `splitAt` question walked its whole stretch and set off about 1,600 `bossAt`
  and 800 `voidAt` calls a frame.
- **Make nothing in these paths**: no `{...}` or `[...]` returned per call, no `.map`, no `for (const x of [a, b])`.
  It was about a thousand small objects a frame for the phone to clear up (the cost was not measured on a phone, but
  it is free to avoid).

### 6. Rectangles

- Merge. If a loop draws one row or one pixel at a time, keep the run going while the next one is the same and draw it
  once (`drawMoonAt`'s `rows`, the vines in `drawJungleHazard`, Gnashbloom's stalk in `trapStalkStrip`: 61 overlapping
  discs became about 16 rectangles, version 140). End the run wherever something else must be drawn in
  between, so the overlap order stays the same.
- Set `fillStyle` when the colour changes, not for every rectangle.
- Something that doesn't change from frame to frame (or changes a few times a second) is painted into an image and
  stamped: the surface hills and props do this (`SURFACE_HZ`).
- Still open: the planet's ring and bands are redrawn every frame (about 450 rectangles; start screen, intro and menu
  sky only). A good first job if those screens ever need to be lighter.

### 7. Pixels covered

- **Don't stamp see-through pixels.** Drawing a transparent part of an image still costs a phone its pixels. The wall
  overlay is drawn as two strips, one per wall (`t.wl`, `t.wr` in `tile`; version 154): about 20% fewer pixels a frame in a
  fight, 9% falling. Same for a Leviathan's paint canvas (`BOSS_BOX`): size it to the creature's own pixels, measured over
  many moments (version 154 cut the Machine six by about 15%), keeping each edge's change even (the dither checks) and the
  box symmetric for the ones that don't dive.
- Every full-width layer adds about 220,000 pixels a frame. The rock and the two back layers are drawn only across the
  strip the shaft spans, and the wall overlay supplies the rest. A new back layer must do the same.
- A void or a boss cavern is nearly the whole screen wide, so nothing is saved there: keep those scenes' extra layers few.

### 8. The page (HUD and cards)

- Change text or a class only when the value changes (`setDepth` compares with what is shown; `shiftWorld` only writes
  the transform when it differs).
- Don't read sizes or positions (`offsetWidth`, `getBoundingClientRect`) every frame. Measure when something changes
  (a resize, fonts loaded, a card opening) and keep the number, as `measureCafeCard` does.
- The HUD's height never changes during a run. Keep it so: a read-out that can be empty keeps its place, invisible.
- **Nothing slow in the tap that opens a card.** A card's turn starts in that tap, so a few tens of ms of work there is a
  visible judder. Make what it needs ahead of time in idle moments on the menu (`prepLeviPics`, version 152: the
  Leviathans card painted all eighteen portraits in the tap, 71 ms on a desktop; now 2 ms).

### 9. Time and frame rate

- Work that needn't happen every frame is limited by the clock (`BOSS_PAINT_EVERY`, `SURFACE_HZ`), never "every Nth frame".
- Everything moves by `dt`. Test at 120 Hz in your head: twice the frames must not mean twice the paints.

### 10. Sound

- Music and effects make audio nodes as they go: about 40 a second in the run's music, 28-143 in a Leviathan track, and
  134-200 for the few seconds of a fight's last lunge. That runs off the drawing thread and costs no frames. How much a
  phone will take has not been tested, so treat today's figures as the ceiling: a new track should not go above them.
  If crackling is ever heard at a fight's end, that lunge is the place to thin out.

## How to measure

1. `python3 tools/prof.py`, serve `tools/out`, open `frame.html?w=390&h=844&page=prof.html` (add `&moon=jungle`).
   When the frame's title says `done`, read `window.__prof` inside it: per scene, rectangles, images, pixels,
   canvases made, page changes and forced layouts; `makers` says which function made each canvas and who called it.
2. Do the same for the build before the change (`python3 tools/prof.py /tmp/before.html prof-old`) and compare.
3. **Trust the counts, not the times.** Times on a desktop are tiny and swing more from run to run than any change
   does, more so when the browser pane is hidden. The counts are exact.
4. For the Leviathans on their own: `python3 tools/levi_budget.py` (counts `fillRect` and `drawImage` while calling
   `LEVI_DRAW[kind]` and `bossStage` three times, normally and fading in, for every moon's; pass another build's file to
   compare, e.g. `git show HEAD~1:src/moonfall.html > /tmp/old.html` then `python3 tools/levi_budget.py /tmp/old.html`).
5. **Picture unchanged?** Run both builds with `&fp=3` and compare the fingerprint lists; for frames that differ, add
   `&shot=<frame numbers>` to both (without `&fp`, so it draws the way a phone does) and compare the pictures pixel
   for pixel. Two things to know: a build differs from itself in a few 0.4 s windows from run to run (about 1% of
   samples), and in the fingerprint mode a see-through glow can differ by 1 in 255 in one colour channel. Neither is a
   real difference. `tools/same_pixels.py` likewise reports the same 4 moments (leftCafe, launch1 twice, launch2) even
   for a build against itself.
6. **On a phone.** None of the above says how it feels. The game sends each run's average frame rate and worst frame
   with its version, device and moon: after a release, compare those for the new version with the one before.

## Before publishing a heavy change: checklist

- [ ] `python3 tools/levi_budget.py` says OK (any change a Leviathan draws).

- [ ] Profiler run on every moon finishes with no errors.
- [ ] No function new to this change appears high in `makers`; canvases per fight and per rock layer are in the table's range.
- [ ] Rectangles, images and pixels per frame are in the table's range for every scene the change touches.
- [ ] A new Leviathan is inside the three Leviathan ranges.
- [ ] Nothing new is called per wall row without remembering its answer.
- [ ] No new page change or page measurement per frame.
- [ ] If the change was meant to draw the same picture: fingerprints and snapshots compared.
- [ ] The numbers, and anything left over the range on purpose, are written in the notes.
