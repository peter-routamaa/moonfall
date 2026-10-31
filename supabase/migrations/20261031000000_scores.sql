-- MoonFall online high scores.
-- One row per submitted run. Nobody reads or writes this table directly: the `scores`
-- Edge Function does it with the project's service key, after checking the input.

create table if not exists public.scores (
  id bigint generated always as identity primary key,
  initials text not null check (initials ~ '^[A-Z]{3}$'),
  depth integer not null check (depth between 1 and 100000),
  who text,                                  -- hashed IP, only used to slow down spam
  created_at timestamptz not null default now()
);

create index if not exists scores_rank_idx on public.scores (depth desc, id asc);
create index if not exists scores_who_idx on public.scores (who, created_at desc);

-- Row level security on with no policies: the public API keys can't touch the table.
alter table public.scores enable row level security;
revoke all on public.scores from anon, authenticated;
