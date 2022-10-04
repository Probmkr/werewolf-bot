create table if not exists games (
  game_id bigserial primary key,
  game_status_id int not null,
  game_host_user_id bigserial not null,
  game_host_guild_id bigserial not null,
  game_started_at timestamp default(current_timestamp),
  noon_time int default(0),
  night_time int default(0),
  game_ended_at timestamp
);

create table if not exists game_status (
  status_id int not null primary key,
  status_code text not null,
  status_name text not null
);

create table if not exists roles (
  role_id int not null primary key,
  role_code text not null,
  role_name text not null,
  role_description text,
  mankind boolean not null
);

create table if not exists game_players (
  game_id bigserial not null,
  player_id bigserial not null,
  player_name text not null,
  role_id serial not null,
  alive boolean not null default(true)
);

create table if not exists channels (
  setting_type smallint not null,
  setting_code text not null,
  setting_name text not null
);

create table if not exists channel_settings (
  setting_type smallint not null,
  setting_guild bigserial not null,
  setting_value bigserial not null
);

create table if not exists guild_roles (
  setting_type smallint not null,
  setting_code text not null,
  setting_name text not null,
  setting_description text
);

create table if not exists guild_role_settings (
  setting_guild bigserial not null,
  setting_type smallint not null,
  setting_value bigserial not null
);
