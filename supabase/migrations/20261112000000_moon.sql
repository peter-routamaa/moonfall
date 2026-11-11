-- MoonFall: which moon a score or a run was on (version 113 adds the Jungle moon).
-- The high score board stays one shared board; the game shows each score's moon in a new MOON column.
-- Scores and runs from before version 113 have it empty (the game shows a dash).

alter table public.scores
  add column if not exists moon text check (moon in ('dust', 'jungle'));

alter table public.plays
  add column if not exists moon text check (moon in ('dust', 'jungle'));

-- Moons: how many players and runs each moon gets, and how deep they go (owner only).
create or replace view public.play_by_moon with (security_invoker = true) as
  select coalesce(moon, 'unknown') as moon,
    count(distinct player) as players,
    count(*) as plays,
    round(avg(depth)) as avg_depth,
    max(depth) as deepest,
    round(sum(secs) / 3600.0, 1) as hours,
    min(created_at) as first_run,
    max(created_at) as last_run
  from public.plays
  where player <> 'ffffffffffffffff'
  group by 1 order by plays desc;

revoke all on public.play_by_moon from anon, authenticated;
