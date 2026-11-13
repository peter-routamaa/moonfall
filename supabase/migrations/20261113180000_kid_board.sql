-- MoonFall version 197: Kid mode gets its own high score board (owner, 2026-11-13: "let's have a separate score board
-- for kid mode"). A score set with any Kid mode setting off normal is stored with kid = true; the function's top 10 and
-- rank only ever compare scores of the same kind. Every score from before is a normal one.
-- Run this before deploying the function that writes `kid` (the old function keeps working with the new column).

alter table public.scores
  add column if not exists kid boolean not null default false;

create index if not exists scores_kid_depth on public.scores (kid, depth desc, id);

-- The owner's stats: was the run played with Kid mode on (empty from older copies).
alter table public.plays
  add column if not exists kid boolean;
