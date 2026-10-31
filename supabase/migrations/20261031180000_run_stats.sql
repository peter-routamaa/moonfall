-- MoonFall run stats, for the owner's eyes only (version 54).
-- Each row in `plays` is one run. The game now also sends how the run went when it ends:
-- how long it lasted, how deep it got, how it ended, and a few counts. Rows from before this have these empty.
-- Months and years are counted in UK time (Europe/London).

alter table public.plays
  add column if not exists run text check (run ~ '^[0-9a-f]{16}$'),
  add column if not exists depth integer check (depth between 0 and 100000),
  add column if not exists secs integer check (secs between 0 and 86400),
  add column if not exists how text check (how in ('wall', 'rock', 'mine', 'lava', 'quit', 'left')),
  add column if not exists orbs integer,
  add column if not exists parts integer,
  add column if not exists cafes integer,
  add column if not exists initials text check (initials ~ '^[A-Z]{3}$'),
  add column if not exists ended_at timestamptz;

create index if not exists plays_run_idx on public.plays (player, run);

-- Everything since the start. The first four columns are the original counter, unchanged.
create or replace view public.play_stats with (security_invoker = true) as
  select
    count(distinct player) as unique_players,
    count(*) as total_plays,
    count(distinct player) filter (where created_at > now() - interval '7 days') as players_last_7_days,
    count(*) filter (where created_at > now() - interval '7 days') as plays_last_7_days,
    round(coalesce(sum(secs), 0) / 3600.0, 1) as hours_played,
    round(avg(secs) / 60.0, 1) as avg_run_minutes,
    max(depth) as deepest_m,
    round(avg(depth)) as avg_depth_m,
    count(*) filter (where how in ('wall', 'rock', 'mine', 'lava')) as deaths,
    count(*) filter (where how = 'wall') as by_wall,
    count(*) filter (where how = 'rock') as by_rock,
    count(*) filter (where how = 'mine') as by_mine,
    count(*) filter (where how = 'lava') as by_lava,
    count(*) filter (where how in ('quit', 'left')) as quit_or_left
  from public.plays
  where player <> 'ffffffffffffffff';

-- One row per month and per year, newest first. new_players = played for the first time that month (or year).
create or replace view public.play_stats_by_month with (security_invoker = true) as
  with p as (
    select *, to_char(created_at at time zone 'Europe/London', 'YYYY-MM') as month,
      min(created_at) over (partition by player) as first_seen
    from public.plays where player <> 'ffffffffffffffff'
  )
  select month,
    count(distinct player) as players,
    count(distinct player) filter (where to_char(first_seen at time zone 'Europe/London', 'YYYY-MM') = month) as new_players,
    count(*) as plays,
    round(coalesce(sum(secs), 0) / 3600.0, 1) as hours_played,
    round(avg(secs) / 60.0, 1) as avg_run_minutes,
    max(depth) as deepest_m,
    round(avg(depth)) as avg_depth_m,
    count(*) filter (where how = 'wall') as by_wall,
    count(*) filter (where how = 'rock') as by_rock,
    count(*) filter (where how = 'mine') as by_mine,
    count(*) filter (where how = 'lava') as by_lava,
    count(*) filter (where how in ('quit', 'left')) as quit_or_left
  from p group by month order by month desc;

create or replace view public.play_stats_by_year with (security_invoker = true) as
  with p as (
    select *, to_char(created_at at time zone 'Europe/London', 'YYYY') as year,
      min(created_at) over (partition by player) as first_seen
    from public.plays where player <> 'ffffffffffffffff'
  )
  select year,
    count(distinct player) as players,
    count(distinct player) filter (where to_char(first_seen at time zone 'Europe/London', 'YYYY') = year) as new_players,
    count(*) as plays,
    round(coalesce(sum(secs), 0) / 3600.0, 1) as hours_played,
    round(avg(secs) / 60.0, 1) as avg_run_minutes,
    max(depth) as deepest_m,
    round(avg(depth)) as avg_depth_m,
    count(*) filter (where how = 'wall') as by_wall,
    count(*) filter (where how = 'rock') as by_rock,
    count(*) filter (where how = 'mine') as by_mine,
    count(*) filter (where how = 'lava') as by_lava,
    count(*) filter (where how in ('quit', 'left')) as quit_or_left
  from p group by year order by year desc;

-- One row per player (per device), most recently active first. initials = the last ones they entered on a high score, if any.
create or replace view public.player_stats with (security_invoker = true) as
  select player,
    (array_agg(initials order by created_at desc) filter (where initials is not null))[1] as initials,
    min(created_at) as first_played,
    max(created_at) as last_played,
    count(*) as plays,
    round(coalesce(sum(secs), 0) / 60.0, 1) as minutes_played,
    max(depth) as deepest_m,
    round(avg(depth)) as avg_depth_m,
    coalesce(sum(orbs), 0) as crystals,
    coalesce(sum(parts), 0) as ship_parts,
    coalesce(sum(cafes), 0) as cafe_stops
  from public.plays where player <> 'ffffffffffffffff'
  group by player order by max(created_at) desc;

revoke all on public.play_stats, public.play_stats_by_month, public.play_stats_by_year, public.player_stats from anon, authenticated;
