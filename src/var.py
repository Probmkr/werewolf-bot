from dotenv import load_dotenv
import os

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_SECRET = os.getenv("BOT_SECRET")
BOT_ID = int(os.getenv("BOT_ID"))
MAIN_GUILD = int(os.getenv("MAIN_GUILD"))
GM_CHANNEL = int(os.getenv("GM_CHANNEL"))
