create table if not exists games (
  game_id bigserial primary key,
  game_status_id int not null,
  game_host_user_id bigserial not null,
  game_host_guild_id bigserial not null,
  game_started_at timestamp default(current_timestamp),
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
  role_description text
);

create table if not exists game_players (
  game_id bigserial not null,
  player_id bigserial not null primary key,
  role_id serial not null
);
