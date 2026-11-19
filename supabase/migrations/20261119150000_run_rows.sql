-- MoonFall: one stats row per run, and a cap on how often a run's ending can be rewritten (audit of 2026-11-19).
-- Run this in the SQL Editor BEFORE deploying the function that writes `ends` (the old function keeps working with it).
-- The unique index can only be made while no run has two rows: check first with
--   select player, run, count(*) from plays where run is not null group by 1, 2 having count(*) > 1;

-- A run's reports can now be sent more than once (the phone keeps them until the server has them, and two open tabs
-- may send the same one at once): the database, not only the function's check, keeps one row per run.
create unique index if not exists plays_run_key on public.plays (player, run) where run is not null;

-- How many end reports have been written to the run's row. The function stops rewriting a run after a set number, so
-- a run's stats can't be rewritten without end.
alter table public.plays
  add column if not exists ends smallint not null default 0 check (ends between 0 and 1000);
