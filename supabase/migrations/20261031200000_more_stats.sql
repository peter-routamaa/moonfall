-- MoonFall: more run stats, for the owner's eyes only (version 55).
-- Frame rate and slowest frame, device, system and screen, treats bought, best near-miss streak, sound and music
-- switches, ship repair %, and whether the opening was watched or skipped (on the first run of each launch only).
-- Plus views built from what's already kept: where runs end in 250 m bands, and players who come back.
-- Months are in UK time (Europe/London).

alter table public.plays
  add column if not exists fps numeric(5, 1) check (fps between 0 and 500),
  add column if not exists worst_ms integer check (worst_ms between 0 and 10000),
  add column if not exists device text check (device in ('phone', 'tablet', 'desktop')),
  add column if not exists os text check (os in ('android', 'ios', 'windows', 'mac', 'chromeos', 'linux', 'other')),
  add column if not exists screen text check (screen ~ '^[0-9]{2,5}x[0-9]{2,5}@[0-9.]{1,5}$'),
  add column if not exists treats text[],
  add column if not exists streak integer check (streak between 0 and 100000),
  add column if not exists sound boolean,
  add column if not exists music boolean,
  add column if not exists repair integer check (repair between 0 and 100),
  add column if not exists intro text check (intro in ('watched', 'skipped'));

-- Totals: the existing columns unchanged, then the new ones.
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
    count(*) filter (where how in ('quit', 'left')) as quit_or_left,
    max(streak) as best_streak,
    round(avg(streak), 1) as avg_best_streak,
    round(100.0 * avg(sound::int)) as sound_on_pct,
    round(100.0 * avg(music::int)) as music_on_pct,
    count(*) filter (where intro = 'watched') as intro_watched,
    count(*) filter (where intro = 'skipped') as intro_skipped,
    round(avg(fps), 1) as avg_fps,
    round(avg(worst_ms)) as avg_worst_frame_ms
  from public.plays
  where player <> 'ffffffffffffffff';

-- Per player: the existing columns unchanged, then best streak and their latest repair %, device and system.
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
    coalesce(sum(cafes), 0) as cafe_stops,
    max(streak) as best_streak,
    (array_agg(repair order by created_at desc) filter (where repair is not null))[1] as repair_pct,
    (array_agg(device order by created_at desc) filter (where device is not null))[1] as device,
    (array_agg(os order by created_at desc) filter (where os is not null))[1] as os,
    round(avg(fps), 1) as avg_fps
  from public.plays where player <> 'ffffffffffffffff'
  group by player order by max(created_at) desc;

-- Devices: how smoothly the game runs on each kind of device. worst_frame_ms_p90 = 9 runs in 10 had a slowest frame below this.
create or replace view public.play_by_device with (security_invoker = true) as
  select coalesce(device, 'unknown') as device, coalesce(os, 'unknown') as os,
    count(distinct player) as players,
    count(*) as plays,
    round(avg(fps), 1) as avg_fps,
    round(avg(worst_ms)) as avg_worst_frame_ms,
    round((percentile_cont(0.9) within group (order by worst_ms))::numeric) as worst_frame_ms_p90,
    mode() within group (order by screen) as common_screen
  from public.plays
  where player <> 'ffffffffffffffff' and ended_at is not null
  group by 1, 2 order by plays desc;

-- Treats: how often each café treat is bought.
create or replace view public.play_treats with (security_invoker = true) as
  select t as treat, count(*) as times_bought, count(distinct player) as players
  from public.plays, unnest(treats) as t
  where player <> 'ffffffffffffffff'
  group by t order by times_bought desc;

-- Where runs end, in 250 m bands, and what ended them.
create or replace view public.play_depth_bands with (security_invoker = true) as
  select (depth / 250) * 250 as from_m, (depth / 250) * 250 + 249 as to_m,
    count(*) as runs,
    count(distinct player) as players,
    count(*) filter (where how = 'wall') as by_wall,
    count(*) filter (where how = 'rock') as by_rock,
    count(*) filter (where how = 'mine') as by_mine,
    count(*) filter (where how = 'lava') as by_lava,
    count(*) filter (where how in ('quit', 'left')) as quit_or_left
  from public.plays
  where player <> 'ffffffffffffffff' and depth is not null
  group by 1, 2 order by 1;

-- Players who come back: grouped by the month they first played (plus an 'all' row), how many played again on a later
-- day, and how many of those came back within 7 days of their first day.
create or replace view public.play_returning with (security_invoker = true) as
  with d as (
    select player, (created_at at time zone 'Europe/London')::date as day
    from public.plays where player <> 'ffffffffffffffff' group by 1, 2
  ), f as (
    select player, min(day) as first_day from d group by player
  ), r as (
    select f.player, to_char(f.first_day, 'YYYY-MM') as first_month,
      exists (select 1 from d where d.player = f.player and d.day > f.first_day) as came_back,
      exists (select 1 from d where d.player = f.player and d.day > f.first_day and d.day <= f.first_day + 7) as within_7
    from f
  )
  select first_month, count(*) as new_players,
    count(*) filter (where came_back) as came_back,
    count(*) filter (where within_7) as came_back_within_7_days,
    round(100.0 * count(*) filter (where came_back) / nullif(count(*), 0)) as came_back_pct
  from r group by first_month
  union all
  select 'all', count(*), count(*) filter (where came_back), count(*) filter (where within_7),
    round(100.0 * count(*) filter (where came_back) / nullif(count(*), 0))
  from r
  order by first_month desc;

revoke all on public.play_stats, public.player_stats, public.play_by_device, public.play_treats, public.play_depth_bands, public.play_returning
  from anon, authenticated;
