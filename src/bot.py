import disnake
from disnake.ext import commands

from var import BOT_TOKEN

bot = commands.Bot("gm!", intents=disnake.Intents.all())

bot.load_extension("cogs")

bot.run(BOT_TOKEN)
