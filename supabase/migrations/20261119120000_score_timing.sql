-- MoonFall: a genuine score is never refused for its timing; it waits off the board instead (code review, 2026-11-19).
-- Run this in the SQL Editor BEFORE deploying the function that writes these columns (the old function keeps working
-- with them: its new rows get shown_at = now and start_m empty).

-- A dive carried on from a cafe (Save and quit, then Continue dive) is a new run that names the run it carries on
-- (prev). start_m is the depth the server credits it with at its start: the earlier run's depth, but no more than that
-- run's own time on the server allows at the fastest fall. Empty means 0 (a dive from the surface).
alter table public.plays
  add column if not exists prev text check (prev ~ '^[0-9a-f]{16}$'),
  add column if not exists start_m integer check (start_m between 0 and 100000);

-- When a score may show on the boards: the time its run started (on the server) plus the least time its depth takes at
-- the fastest fall. A run whose reports arrived late (played offline, sent when back online) is saved straight away and
-- shows once that time has passed, rather than being refused. Existing rows get the moment this runs (already shown).
alter table public.scores
  add column if not exists shown_at timestamptz not null default now();
