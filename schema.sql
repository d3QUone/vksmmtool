drop table if exists screen_size;
create table screen_size (
  user_ip text,
  w integer,
  h integer
);
drop table if exists userinfo;
create table userinfo (
  user_id integer not null,
  picture text,
  auth_token text,
  last_seen text,
  sort_type text
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
