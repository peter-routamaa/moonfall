-- MoonFall: Terminal Velocity and the helper drone on each run, for the owner's eyes only (version 190).
-- hard: the run was a Terminal Velocity dive (save.hard, once unlocked). drone_open: the helper drone was unlocked
-- on that device. drone: the drone flew with him on that run (switched on, or unlocked during it).
-- Runs from before version 190 have them empty. Run this in the SQL Editor BEFORE deploying the function that sends
-- them, or the function's writes to plays would fail.

alter table public.plays
  add column if not exists hard boolean,
  add column if not exists drone_open boolean,
  add column if not exists drone boolean;
