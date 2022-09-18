from typing import TypeAlias, TypedDict
import disnake
from disnake.ext import commands, tasks
from db import DBC
from game_controller import GameBoard, GameController, GameDataType
from var import BOT_ID, ERROR_CODES, GAME_STATUS, GM_CHANNEL, MAIN_GUILD
from logger import LT, Logger
from snowflake import SnowflakeGenerator
from multiprocessing import Process
import threading
import os
import asyncio

gen = SnowflakeGenerator(0)
logger = Logger()
Inter: TypeAlias = disnake.ApplicationCommandInteraction
game_ctl = GameController()


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

    @commands.Cog.listener()
    async def on_interaction(self, interaction: Inter):
        logger.log(
            LT.TRACE, f"inter_type: `{interaction.type}` inter_id `{interaction.id}`")

    @commands.slash_command()
    async def ping(self, interaction: Inter):
        latency = self.bot.latency
        embed = disnake.Embed(title="Pong!", color=0x00ff00)
        embed.add_field(name="latency", value=f"`{int(latency*1000)}ms`")
        await interaction.response.send_message(embed=embed)

class Werewolf(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.games_to_start: list[asyncio.Task] = []
        self.dbctl = DBC()

    def new_embed(self, title: str = "", description: str = "") -> disnake.Embed:
        embed = disnake.Embed(
            title=title, description=description, color=disnake.Color.dark_red())
        # embed.set_author(
        #     name="人狼GM", icon_url="https://cdn.discordapp.com/avatars/1018169450886856875/291ca2bfb08a25033a72d80734c0cd6a.webp")
        return embed

    async def check_role(self, interaction: Inter):
        for role in interaction.author.roles:
            if role.name in ["人狼モデレーター"]:
                break
        else:
            await interaction.response.send_message("あなたにこのコマンドを使う権限はありません。", ephemeral=True)
            return False
        return True

    def add_game_task(self, task: asyncio.Task, guild_id: int):
        self.games_to_start.append(task)

    @tasks.loop(seconds=1)
    async def start_game_tasks(self):
        await self.games_to_start.pop(0)()

    @commands.slash_command()
    async def embed_test(self, interaction: Inter):
        embed = self.new_embed(
            title="Embed Test", description="this is embed test")
        await interaction.response.send_message(embed=embed)

    @commands.slash_command()
    async def wolf(self, interaction: Inter):
        pass

    @wolf.sub_command(description="人狼ゲームで使うチャンネルを設定します")
    async def set_channel(
            self,
            interaction: Inter,
            gm_channel: disnake.abc.GuildChannel = commands.Param(
                None, description="人狼GMがメッセージを送信するチャンネル"),
            text_meeting_channel: disnake.abc.GuildChannel = commands.Param(
                None, description="昼の会議チャンネル"),
            voice_meeting_channel: disnake.abc.GuildChannel = commands.Param(None, description="昼の会議ボイスチャンネル")):

        bad_channel = False
        if not (gm_channel and gm_channel.type == disnake.ChannelType.text):
            bad_channel = True
        if not (text_meeting_channel and text_meeting_channel.type == disnake.ChannelType.text):
            bad_channel = True
        if not (voice_meeting_channel and voice_meeting_channel.type == disnake.ChannelType.voice):
            bad_channel = True
        if bad_channel:
            await interaction.response.send_message(embed=self.new_embed(
                title="設定に失敗しました",
                description="正しいチャンネルタイプを指定してください"))
            return
        self.dbctl.set_channels(interaction.guild_id, gm_channel.id,
                                text_meeting_channel.id, voice_meeting_channel.id)
        await interaction.response.send_message(embed=self.new_embed(title="設定が完了しました"))

    @wolf.sub_command(description="人狼ゲームを開始します")
    async def start(self, interaction: Inter):
        if not await self.check_role(interaction):
            return
        res = self.dbctl.start_game(
            interaction.author.id, interaction.guild_id)
        channel = self.dbctl.get_channels(interaction.guild_id)
        if not res["res"]:
            game_status = res["game_status"]
            error_code = res["code"]
            logger.log(LT.DEBUG, game_status)
            await interaction.response.send_message(
                embed=self.new_embed(
                    title=ERROR_CODES[error_code],
                    description=f"このサーバーでのゲームは{GAME_STATUS[game_status][1]}です。"))
            return
        elif len(channel) < 3:
            await interaction.send(embed=self.new_embed("ゲームを開始する前に先にチャンネル設定を行ってください"))

        await interaction.response.send_message(
            embed=self.new_embed(
                title="ゲームスタート",
                description=f"ゲーム No.`{res['game_id']}`"))
        res = self.dbctl.get_game_from_server(interaction.guild_id)
        game_data: GameDataType = dict(res[0])

        game = GameBoard(game_data, self.bot)
        await game.async_init()
        game_task = asyncio.create_task(game.start())
        self.add_game_task(game_task, interaction.guild_id)
        game_ctl.add_game(game)



    @wolf.sub_command(description="人狼ゲームを強制終了します")
    async def stop(self, interaction: Inter):
        if not await self.check_role(interaction):
            return
        res = self.dbctl.get_game_from_server(interaction.guild_id)
        view = disnake.ui.View()
        snowflake_id = next(gen)
        button = disnake.ui.Button(label="終了", custom_id=str(snowflake_id))
        # button.callback = self.really_stop
        view.add_item(button)

        def check(inter: disnake.MessageInteraction):
            if not type(inter) == disnake.MessageInteraction:
                return False
            component_type = inter.component.type.value == 2
            custom_id = inter.component.custom_id == str(snowflake_id)
            author = inter.author.id == interaction.author.id
            return  component_type and custom_id and author

        if res:
            await interaction.response.send_message(
                embed=self.new_embed(
                    title="ゲームは実行中です",
                    description="本当に終了しますか？"),
                view=view)
            await self.bot.wait_for("interaction", check=check)
            await self.really_stop(interaction)
        else:
            await interaction.response.send_message(
                embed=self.new_embed(
                    title=ERROR_CODES[2]))

    async def really_stop(self, interaction: Inter):
        self.dbctl.end_game(interaction.guild_id)
        embed = self.new_embed(
            title="ゲームを終了しました")
        await interaction.edit_original_message(view=None)
        await interaction.send(embed=embed)

    @wolf.sub_command(description="サーバーでの人狼ゲームのステータスを返します")
    async def status(self, interaction: Inter):
        status = self.dbctl.get_game_from_server(interaction.guild_id)
        if not status:
            await interaction.response.send_message(
                embed=self.new_embed(
                    title=ERROR_CODES[2]))
        else:
            status = dict(status[0])
            logger.log(LT.DEBUG, status)
            embed = self.new_embed(title="現在進行中のゲーム")
            for i in status:
                logger.log(LT.DEBUG, i)
                embed.add_field(name=i, value=f"`{status[i]}`")
            await interaction.response.send_message(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(Werewolf(bot))
    bot.add_cog(Others(bot))
