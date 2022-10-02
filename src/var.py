from dotenv import load_dotenv
import os

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_SECRET = os.getenv("BOT_SECRET")
BOT_ID = int(os.getenv("BOT_ID"))
MAIN_GUILD = int(os.getenv("MAIN_GUILD"))
GM_CHANNEL = int(os.getenv("GM_CHANNEL"))
DSN = os.getenv("DSN")
RESET_DB = bool(int(os.getenv("RESET_DB", 0)))
GAME_STATUS = {
    0: ["running", "進行中"],
    1: ["paused", "一時停止中"],
    2: ["ended", "終了済み"]}
GAME_ROLES = {
    0: ["villager", "村人", "人狼を処刑して生き残りましょう", True, 0x32cd32],
    1: ["werewolf", "人狼", "村人を全員殺しましょう", False, 0x800000],
    2: ["seer", "占い師", "人狼を見つけましょう", True, 0x4b0082],
    3: ["maniac", "狂人", "人狼を助けましょう", True, 0xb22222],
    4: ["medium", "霊媒師", "人狼の数を把握しましょう", True, 0x6a5acd],
    5: ["guard", "騎士", "村人を護衛しましょう", True, 0xd2691e]}
GAME_CHANNELS = {
    0: ["gm_channel", "人狼GMチャット"],
    1: ["text_meeting_channel", "人狼昼チャット"],
    2: ["voice_meeting_channel", "人狼昼ボイスチャット"]}
GUILD_ROLES = {
    0: ["player_role", "プレーヤーロール", "生きてるプレーヤーを識別するためのロール"],
    1: ["moderator_role", "モデレーターロール", "「人狼モデレーター」以外のロールでのモデレーターのロール"]
}
ERROR_CODES = {
    0: "そのサーバーではすでにゲームが開始されています",
    1: "そのサーバーで進行中のゲームはありません",
    2: "現在実行中のゲームはありません"}
# ROLE_SETS = {
#     player_num: {
#         1: {role_id: number},
#         2: {...},
#         ...
#     },
#     player_num: {...},
#     ...
# }
ROLE_SETS = {
    1: {
        1: {0: 1},
        2: {1: 1},
        3: {2: 1},
        4: {3: 1},
        5: {4: 1},
        6: {5: 1},
    },
    2: {
        1: {0: 2},
        2: {0: 1, 1: 1},
        3: {1: 2},
        # 4: {0: 1, 2: 1},
        # 5: {1: 1, 2: 1},
        6: {0: 1, 5: 1},
    },
    3: {
        1: {0: 2, 1: 1},
        2: {1: 3},
        3: {0: 1, 1: 2}
    },
    4: {
        1: {0: 2, 1: 1, 2: 1},
        2: {0: 3, 1: 1},
    },
    5: {
        1: {0: 1, 1: 1, 2: 1, 3: 1, 5: 1},
        2: {0: 2, 1: 1, 2: 1, 3: 1},
        3: {0: 3, 1: 1, 5: 1},
        4: {0: 3, 1: 1, 2: 1},
    },
    6: {
        1: {0: 2, 1: 1, 2: 1, 3: 1, 4: 1},
        2: {0: 2, 1: 2, 2: 1, 4: 1},
        3: {0: 1, 1: 2, 2: 1, 3: 1, 5: 1},
    },
    7: {
        1: {0: 2, 1: 2, 2: 1, 3: 1, 5: 1},
        2: {0: 1, 1: 2, 2: 1, 3: 1, 4: 1, 5: 1},
        3: {0: 1, 1: 3, 2: 2, 4: 1},
    }
}
WAIT_TIMEOUT = 60
