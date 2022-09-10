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
        all_slash_commands = await self.bot.fetch_global_commands()
        for i in all_slash_commands:
            logger.log(LT.DEBUG, i.name)
        # await channel.send("botが起動しました")

class Werewolf(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.slash_command(description="人狼ゲームに関するメインコマンド")
    async def wolf(self):
        pass

    @wolf.sub_command(description="人狼ゲームを開始します")
    async def start(self, interaction: disnake.ApplicationCommandInteraction):
        await interaction.response.send_message("dummy")

def setup(bot: commands.Bot):
    bot.add_cog(Werewolf(bot))
    bot.add_cog(Others(bot))
