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
GAME_STATUS = [
            ["running", "進行中"],
            ["paused", "一時停止中"],
            ["ended", "終了済み"]]
GAME_ROLES = [
            ["villager", "村人"],
            ["werewolf", "人狼"],
            ["seer", "占い師"],
            ["maniac", "狂人"],
            ["medium", "霊媒師"],
            ["guard", "ガードマン"]]
ERROR_CODES = {
    0: "そのサーバーではすでにゲームが開始されています",
    1: "そのサーバーで進行中のゲームはありません",
    2: "現在実行中のゲームはありません"
}
