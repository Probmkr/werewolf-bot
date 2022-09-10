import disnake
from disnake.ext import commands

from var import GM_CHANNEL, MAIN_GUILD
from logger import LT, Logger

logger = Logger()

class Others(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # guild = await self.bot.fetch_guild(MAIN_GUILD)
        channel = await self.bot.fetch_channel(GM_CHANNEL)
        logger.log(LT.INFO, f"logged in as {self.bot.user}")
        await channel.send("botが起動しました")

def setup(bot: commands.Bot):
    bot.add_cog(Others(bot))
