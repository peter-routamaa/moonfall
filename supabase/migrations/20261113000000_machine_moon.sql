-- MoonFall: the Machine moon (version 145). The moon columns from 20261112000000_moon.sql only allowed 'dust' and
-- 'jungle'; this lets them hold 'machine' too. Run it in the SQL Editor before deploying the function that sends it.
-- (Postgres named the inline checks <table>_moon_check.)

alter table public.scores drop constraint if exists scores_moon_check;
alter table public.scores add constraint scores_moon_check check (moon in ('dust', 'jungle', 'machine'));

alter table public.plays drop constraint if exists plays_moon_check;
alter table public.plays add constraint plays_moon_check check (moon in ('dust', 'jungle', 'machine'));
