-- Whether the player had escaped the moon (repaired the ship) when they set the score.
-- Older scores have no answer and stay null; the board shows them as a dash.
-- Run this before deploying the version of the `scores` function that saves and returns it.

alter table public.scores add column if not exists escaped boolean;
