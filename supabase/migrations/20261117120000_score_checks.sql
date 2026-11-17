-- MoonFall: each score tied to the run it came from, and limits on the play pings (code review, 2026-11-15/17).
-- Run this before deploying the function that writes these columns (the old function keeps working with them).

-- The run a score came from (the game's 16-hex run ID) and the device's anonymous player ID. A run can put one score on
-- the board: a score sent again after a lost reply finds its row instead of adding a second one. Older scores have none.
alter table public.scores
  add column if not exists run text check (run ~ '^[0-9a-f]{16}$'),
  add column if not exists player text check (player ~ '^[0-9a-f]{16}$');
create unique index if not exists scores_run_key on public.scores (run) where run is not null;

-- Hashed connection for the play pings, only used to slow down spam (as scores.who).
alter table public.plays
  add column if not exists who text;
create index if not exists plays_who_idx on public.plays (who, created_at desc);
create index if not exists plays_run_idx on public.plays (player, run);

-- How a run ended: also a launch home from a cafe ('launch') or through the deep cave's portal ('cave').
alter table public.plays drop constraint if exists plays_how_check;
alter table public.plays
  add constraint plays_how_check check (how in ('wall', 'rock', 'mine', 'lava', 'quit', 'left', 'launch', 'cave'));
