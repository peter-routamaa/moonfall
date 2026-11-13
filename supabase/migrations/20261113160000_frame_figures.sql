-- MoonFall: three frame-rate figures per run, for the owner's eyes only (the Performance pass thread, 2026-11-13; the
-- owner agreed to them). The run average (fps) hides drops in Leviathan fights and can't tell a smooth 60 Hz phone from
-- a 120 Hz one struggling.
-- hz: the screen's refresh rate as the game sees it (60, 90, 120, 144 ...).
-- fps_fight: average frames a second while a Leviathan fight is on; empty when the run had no fight.
-- slow_pct: percent of the run's frames that took 1.5 times the screen's own frame time or longer (missed a refresh).
-- Older versions don't send them. Run this in the SQL Editor BEFORE deploying the function that sends them, or the
-- function's writes to plays would fail.

alter table public.plays
  add column if not exists hz smallint check (hz between 20 and 500),
  add column if not exists fps_fight numeric(5, 1) check (fps_fight between 0 and 500),
  add column if not exists slow_pct numeric(4, 1) check (slow_pct between 0 and 100);
