import traceback
from typing import TypeAlias
# import mariadb as mydb
import psycopg2
import psycopg2.extras
import psycopg2.errors
from logger import LT, Logger
from var import DSN, GAME_CHANNELS, GAME_ROLES, GAME_STATUS, GUILD_ROLES, RESET_DB
from snowflake import SnowflakeGenerator

gen = SnowflakeGenerator(0)
logger = Logger()


class DBController():
    dsn: str
    reset_db: bool
    game_status_list: dict[int, list[str]]
    role_list: dict[int, list[str]]
    game_channels: dict[int, list[str]]
    guild_roles: dict[int, list[str]]

    def get_dict_conn(self):
        return psycopg2.connect(self.dsn, cursor_factory=psycopg2.extras.DictCursor)

    def __init__(self, *, dsn=DSN, reset_db=RESET_DB, game_status=GAME_STATUS, game_roles=GAME_ROLES, game_channels=GAME_CHANNELS, guild_roles=GUILD_ROLES):
        self.dsn = dsn
        self.reset_db = reset_db
        self.game_status_list = game_status
        self.role_list = game_roles
        self.game_channels = game_channels
        self.guild_roles = guild_roles
        self.init_db()

    def init_db(self) -> bool:
        if not self.reset_db:
            return True
        with self.get_dict_conn() as conn:
            with conn.cursor() as cur:
                if self.reset_db:
                    cur.execute(open("sqls/del_table.sql", "r").read())
                cur.execute(open("sqls/table.sql", "r").read())
            conn.commit()
        try:
            with self.get_dict_conn() as conn:
                for id, status in self.game_status_list.items():
                    with conn.cursor() as cur:
                        sql = "insert into game_status (status_id, status_code, status_name) values (%s, %s, %s)"
                        params = (id, status[0], status[1])
                        cur.execute(sql, params)
                conn.commit()
            with self.get_dict_conn() as conn:
                for id, role in self.role_list.items():
                    with conn.cursor() as cur:
                        sql = "insert into roles (role_id, role_code, role_name, role_description, mankind) values (%s, %s, %s, %s, %s)"
                        params = (id, role[0], role[1], role[2], role[3])
                        cur.execute(sql, params)
                conn.commit()
            with self.get_dict_conn() as conn:
                for id, channel in self.game_channels.items():
                    with conn.cursor() as cur:
                        sql = "insert into channels (setting_type, setting_code, setting_name) values (%s, %s, %s)"
                        params = (id, channel[0], channel[1])
                        cur.execute(sql, params)
                conn.commit()
            with self.get_dict_conn() as conn:
                for id, role in self.guild_roles.items():
                    with conn.cursor() as cur:
                        sql = "insert into guild_roles (setting_type, setting_code, setting_name, setting_description) values (%s, %s, %s, %s)"
                        params = (id, role[0], role[1], role[2])
                        cur.execute(sql, params)
                conn.commit()
        except Exception as e:
            logger.log(LT.WARNING, traceback.format_exc())
            return False
        return True

    def check_game_exists(self, host_guild_id: int):
        with self.get_dict_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select game_status_id from games where game_host_guild_id = %s and game_status_id <> 2",
                    (host_guild_id,))
                res = cur.fetchone()
                return res


    def start_game(self, host_user_id: int, host_guild_id: int) -> dict:
        with self.get_dict_conn() as conn:
            with conn.cursor() as cur:
                res = self.check_game_exists(host_guild_id)
                if res:
                    return {"res": False, "code": 0, "game_status": res[0]}
                snowflake_id = next(gen)
                cur.execute(
                    "insert into games (game_id, game_status_id, game_host_user_id, game_host_guild_id) values (%s, %s, %s, %s)",
                    (snowflake_id, 0, host_user_id, host_guild_id))
                conn.commit()
                return {"res": True, "game_id": snowflake_id}

    def end_game(self, host_guild_id: int) -> dict:
        with self.get_dict_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select game_id, game_status_id from games where game_host_guild_id = %s and game_status_id <> 2",
                    (host_guild_id,))
                res = cur.fetchone()
                if res:
                    cur.execute(
                        "update games set game_status_id = 2 where game_id = %s",
                        (res[0],))
                    self.delete_all_players(res[0])
                    conn.commit()
                    return {"res": True}
                else:
                    return {"res": False, "code": 1}

    def set_player_role(self, guild_id: int, role_id: int) -> None:
        with self.get_dict_conn() as conn:
            with conn.cursor() as cur:
                if self.get_all_players(guild_id):
                    cur.execute(
                        """update guild_role_settings
                        set setting_value = %s
                        where setting_guild = %s
                        and setting_type = 0""",
                        (role_id, guild_id))
                else:
                    cur.execute(
                        """insert into guild_role_settings
                        values (%s, 0, %s)""",
                        (guild_id, role_id))
            conn.commit()

    def get_player_role(self, guild_id: int) -> list[psycopg2.extras.DictRow]:
        with self.get_dict_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """select * from guild_role_settings
                    where setting_guild = %s
                    and setting_type = 0""",
                    (guild_id,))
                return cur.fetchone()

    def set_channels(self, guild_id, gm_channel: int = None, text_meeting_channel: int = None, voice_meeting_channel: int = None) -> None:
        with self.get_dict_conn() as conn:
            if gm_channel:
                with conn.cursor() as cur:
                    cur.execute(
                        "select * from channel_settings where setting_type = 0 and setting_guild = %s", (guild_id,))
                    res = cur.fetchone()
                    if res:
                        sql = \
                            """update channel_settings
                        set setting_value = %s
                        where setting_type = 0
                        and setting_guild = %s"""
                        params = (gm_channel, guild_id)
                        cur.execute(sql, params)
                    else:
                        sql = \
                            """insert into channel_settings
                            (setting_type, setting_guild, setting_value)
                            values
                            (0, %s, %s)"""
                        params = (guild_id, gm_channel)
                        cur.execute(sql, params)
            if text_meeting_channel:
                with conn.cursor() as cur:
                    cur.execute(
                        "select * from channel_settings where setting_type = 1 and setting_guild = %s", (guild_id,))
                    res = cur.fetchone()
                    if res:
                        sql = \
                            """update channel_settings
                        set setting_value = %s
                        where setting_type = 1
                        and setting_guild = %s"""
                        params = (text_meeting_channel, guild_id)
                        cur.execute(sql, params)
                    else:
                        sql = \
                            """insert into channel_settings
                            (setting_type, setting_guild, setting_value)
                            values
                            (1, %s, %s)"""
                        params = (guild_id, text_meeting_channel)
                        cur.execute(sql, params)
            if voice_meeting_channel:
                with conn.cursor() as cur:
                    cur.execute(
                        "select * from channel_settings where setting_type = 2 and setting_guild = %s", (guild_id,))
                    res = cur.fetchone()
                    if res:
                        sql = \
                            """update channel_settings
                        set setting_value = %s
                        where setting_type = 2
                        and setting_guild = %s"""
                        params = (voice_meeting_channel, guild_id)
                        cur.execute(sql, params)
                    else:
                        sql = \
                            """insert into channel_settings
                            (setting_type, setting_guild, setting_value)
                            values
                            (2, %s, %s)"""
                        params = (guild_id, voice_meeting_channel)
                        cur.execute(sql, params)
            conn.commit()

    def get_channels(self, guild_id) -> list[psycopg2.extras.DictRow]:
        with self.get_dict_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select setting_value from channel_settings where setting_guild = %s",
                    (guild_id,))
                return cur.fetchall()

    def check_table_exists(self, table_name: str) -> bool:
        with self.get_dict_conn() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "select exists (select from pg_tables where schemaname = 'public' and tablename = %s)",
                        (table_name, ))
                    res = cur.fetchone()[0]
                    conn.commit()
                    return res
            except Exception as e:
                logger.log(LT.WARNING, e)
                return False

    def get_game_from_server(self, host_guild_id: int, game_status_ids: list[int] | None = [0, 1]) -> list[psycopg2.extras.DictRow] | None:
        with self.get_dict_conn() as conn:
            with conn.cursor() as cur:
                if game_status_ids:
                    or_list = [
                        f"game_status_id = {i}" for i in game_status_ids]
                    cur.execute(
                        "select * from games where game_host_guild_id = %s and " +
                        " or ".join(or_list),
                        (host_guild_id,))
                else:
                    cur.execute(
                        "select * from games where game_host_guild_id = %s",
                        (host_guild_id,))
                return cur.fetchall()

    def register_player(self, game_id, player_id, player_name, role_id) -> None:
        with self.get_dict_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into game_players
                    (game_id, player_id, player_name, role_id)
                    values (%s, %s, %s, %s)
                    """,
                    (game_id, player_id, player_name, role_id))
            conn.commit()

    def delete_player(self, game_id, player_id) -> None:
        with self.get_dict_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    delete from game_players
                    where game_id = %s
                    and player_id = %s
                    """,
                    (game_id, player_id))
            conn.commit()

    def delete_all_players(self, game_id) -> None:
        with self.get_dict_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "delete from game_players where game_id = %s",
                    (game_id,))
            conn.commit()

    def set_time(self, game_id, *, noon: int = None, night: int = None):
        no_noon = noon == None
        no_night = night == None
        if (no_noon and no_night) or not (no_noon or no_night):
            return False
        elif not no_noon:
            print(noon)
            with self.get_dict_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        update games
                        set noon_time = %s
                        where game_id = %s
                        """,
                        (noon, game_id))
                conn.commit()
        elif not no_night:
            with self.get_dict_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        update games
                        set night_time = %s
                        where game_id = %s
                        """,
                        (night, game_id))
                conn.commit()

    def set_player_alive(self, game_id: int, player_id: int, player_alive: bool = False):
        with self.get_dict_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update game_players set alive = %s where game_id = %s and player_id = %s",
                    (player_alive, game_id, player_id))
                conn.commit()

    def kill_player(self, game_id: int, player_id: int):
        self.set_player_alive(game_id, player_id)

    def get_player(self, game_id: int, player_id: int) -> psycopg2.extras.DictRow:
        with self.get_dict_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select * from game_players where game_id = %s and player_id = %s",
                    (game_id, player_id))
                return cur.fetchone()

    def get_all_players(self, game_id: int, *, alives: bool = True) -> list[psycopg2.extras.DictRow]:
        with self.get_dict_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select * from game_players where game_id = %s" +
                    " and alive = true" if alives else "",
                    (game_id,))
                return cur.fetchall()

    def get_role_players(self, game_id: int, role_id: int, *, alives: bool = True) -> list[psycopg2.extras.DictRow] | None:
        with self.get_dict_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select * from game_players where game_id = %s and role_id = %s" +
                    " and alive = true" if alives else "",
                    (game_id, role_id))
                return cur.fetchall()

    def get_human_players(self, game_id: int, human: bool = True, *, alives: bool = True):
        with self.get_dict_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select * from game_players inner join roles using (role_id) where game_id = %s and mankind = %s" +
                    " and alive = true" if alives else "",
                    (game_id, human))
                return cur.fetchall()

    def for_test(self):
        with self.get_dict_conn() as conn:
            with conn.cursor()as cur:
                cur.execute("select * from channel_settings")
                return cur.fetchall()


DBC: TypeAlias = DBController
