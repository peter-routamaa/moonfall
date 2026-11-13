-- MoonFall: more run stats for the owner's eyes only (version 192; the owner picked them 2026-11-13).
-- errors / error: game errors since the device's last finished run, and the first one's message (200 characters).
-- levi_fought / levi_escaped: the Leviathans whose fight started this run, and the ones he got away from.
-- missions, suit, badges, nav: progress on the device (missions finished, suit worn, badges earned, nav crystals paid).
-- cafes_passed / drone_caught: cafe ledges gone past (landed at or not; cafes = landed), items the drone caught.
-- installed / browser / pauses: home-screen app or browser tab, which browser, pauses the player chose.
-- Runs from before version 192 have them empty. Run this in the SQL Editor BEFORE deploying the function that sends
-- them, or the function's writes to plays would fail.

alter table public.plays
  add column if not exists errors integer check (errors between 0 and 100000),
  add column if not exists error text check (char_length(error) <= 200),
  add column if not exists levi_fought text[],
  add column if not exists levi_escaped text[],
  add column if not exists missions integer check (missions between 0 and 10000),
  add column if not exists suit integer check (suit between 0 and 100),
  add column if not exists badges integer check (badges between 0 and 1000),
  add column if not exists nav integer check (nav between 0 and 10000),
  add column if not exists cafes_passed integer check (cafes_passed between 0 and 1000),
  add column if not exists drone_caught integer check (drone_caught between 0 and 10000),
  add column if not exists installed boolean,
  add column if not exists browser text check (browser in ('safari', 'chrome', 'firefox', 'edge', 'samsung', 'opera', 'inapp', 'other')),
  add column if not exists pauses integer check (pauses between 0 and 10000);
