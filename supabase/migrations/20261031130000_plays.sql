-- MoonFall play counter, for the owner's eyes only.
-- One row per run, keyed by an anonymous random ID the game makes once per device (no name, nothing personal).
-- Only the `scores` Edge Function writes here, with the project's service key.

create table if not exists public.plays (
  id bigint generated always as identity primary key,
  player text not null check (player ~ '^[0-9a-f]{16}$'),
  created_at timestamptz not null default now()
);

create index if not exists plays_player_idx on public.plays (player, created_at desc);

alter table public.plays enable row level security;
revoke all on public.plays from anon, authenticated;

-- The counters. Open this view in the Table Editor, or run `select * from play_stats;` in the SQL Editor.
-- The ID ffffffffffffffff is reserved for testing and isn't counted.
create or replace view public.play_stats with (security_invoker = true) as
  select
    count(distinct player) as unique_players,
    count(*) as total_plays,
    count(distinct player) filter (where created_at > now() - interval '7 days') as players_last_7_days,
    count(*) filter (where created_at > now() - interval '7 days') as plays_last_7_days
  from public.plays
  where player <> 'ffffffffffffffff';

revoke all on public.play_stats from anon, authenticated;
