from typing import List, TypeAlias
# import mariadb as mydb
import psycopg2
import psycopg2.extras
from logger import LT, Logger
from var import DSN, GAME_ROLES, GAME_STATUS, RESET_DB
from snowflake import SnowflakeGenerator

gen = SnowflakeGenerator(0)
logger = Logger()


class DBController():
    dsn: str
    reset_db: bool
    game_status_list: List[List[str]]
    role_list: List[List[str]]

    def get_dict_conn(self):
        return psycopg2.connect(self.dsn, cursor_factory=psycopg2.extras.DictCursor)

    def __init__(self, *, dsn=DSN, reset_db=RESET_DB, game_status=GAME_STATUS, game_roles=GAME_ROLES):
        self.dsn = dsn
        self.reset_db = reset_db
        self.game_status_list = game_status
        self.role_list = game_roles
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
                for id, status in enumerate(self.game_status_list):
                    with conn.cursor() as cur:
                        sql = "insert into game_status (status_id, status_code, status_name) values (%s, %s, %s)"
                        params = (id, status[0], status[1])
                        cur.execute(sql, params)
                conn.commit()
            with self.get_dict_conn() as conn:
                for id, role in enumerate(self.role_list):
                    with conn.cursor() as cur:
                        sql = "insert into roles (role_id, role_code, role_name) values (%s, %s, %s)"
                        params = (id, role[0], role[1])
                        cur.execute(sql, params)
                conn.commit()
        except Exception as e:
            logger.log(LT.WARNING, e)
            return False
        return True

    def start_game(self, host_user_id: int, host_guild_id: int) -> dict:
        with self.get_dict_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select game_status_id from games where game_host_guild_id = %s and game_status_id <> 2",
                    (host_guild_id,))
                res = cur.fetchone()
                logger.log(LT.DEBUG, res)
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
                    conn.commit()
                    return {"res": True}
                else:
                    return {"res": False, "code": 1}


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

    def get_game_from_server(self, host_guild_id: int, game_status_ids: List[int] | None = [0, 1]) -> List[List] | None:
        with self.get_dict_conn() as conn:
            with conn.cursor() as cur:
                if game_status_ids:
                    or_list = [f"game_status_id = {i}" for i in game_status_ids]
                    cur.execute(
                        "select * from games where game_host_guild_id = %s and " + " or ".join(or_list),
                        (host_guild_id,))
                else:
                    cur.execute(
                        "select * from games where game_host_guild_id = %s",
                        (host_guild_id,))
                return cur.fetchall()


DBC: TypeAlias = DBController
