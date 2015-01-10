drop table if exists userinfo;
create table userinfo (
  user_id integer not null,
  picture text,
  auth_token text
);
drop table if exists groups;
create table groups (
  user_id integer not null,
  group_id integer not null,
  screen_name text,
  picture text
);
drop table if exists postinfo;
create table postinfo (
  group_id integer not null,
  picture text,
  content text,
  link text,
  like integer,
  comm integer,
  repo integer
);
