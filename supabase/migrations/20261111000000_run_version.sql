-- MoonFall: the game version on each run, for the owner's eyes only (version 106).
-- The game now sends its version number with the start and end of each run, so the frame rate and other stats
-- can be compared between versions. Runs from before version 106 have it empty.

alter table public.plays
  add column if not exists ver integer check (ver between 1 and 100000);

-- Versions: how smoothly each version runs on each kind of device.
-- worst_frame_ms_p90 = 9 runs in 10 had a slowest frame below this.
create or replace view public.play_by_version with (security_invoker = true) as
  select ver, coalesce(device, 'unknown') as device, coalesce(os, 'unknown') as os,
    count(distinct player) as players,
    count(*) as plays,
    round(avg(fps), 1) as avg_fps,
    min(fps) as lowest_fps,
    round(avg(worst_ms)) as avg_worst_frame_ms,
    round((percentile_cont(0.9) within group (order by worst_ms))::numeric) as worst_frame_ms_p90,
    min(created_at) as first_run,
    max(created_at) as last_run
  from public.plays
  where player <> 'ffffffffffffffff' and ended_at is not null
  group by 1, 2, 3 order by ver desc nulls last, plays desc;

revoke all on public.play_by_version from anon, authenticated;
