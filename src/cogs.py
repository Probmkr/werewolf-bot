import time
from typing import TypeAlias, TypedDict
from xml.dom import NotFoundErr
import disnake
import disnake.errors as diserr
from disnake.ext import commands, tasks
from db import DBC
from game_controller import GameBoard, GameController, GameDataType
from var import BOT_ID, ERROR_CODES, GAME_STATUS, GM_CHANNEL, MAIN_GUILD
from logger import LT, Logger
from snowflake import SnowflakeGenerator
import asyncio
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN
from lib import check_role

gen = SnowflakeGenerator(0)
logger = Logger()
Inter: TypeAlias = disnake.ApplicationCommandInteraction
game_ctl = GameController()


def new_embed(title: str = "", description: str = "") -> disnake.Embed:
    embed = disnake.Embed(
        title=title, description=description, color=disnake.Color.dark_red())
    # embed.set_author(
    #     name="人狼GM", icon_url="https://cdn.discordapp.com/avatars/1018169450886856875/291ca2bfb08a25033a72d80734c0cd6a.webp")
    return embed


def dround(num: int):
    return Decimal(str(num)).quantize(Decimal('0'), rounding=ROUND_HALF_UP)


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

    @commands.slash_command()
    async def delete_category(self, interaction: Inter, category: disnake.CategoryChannel):
        if not await check_role(interaction, wolf_moderator=False, channel_moderator=True):
            return

        async def delete(channel: disnake.abc.GuildChannel):
            await channel.delete()
        channels = category.channels
        await interaction.response.send_message(embed=new_embed("カテゴリー削除開始", f"カテゴリーの中にある {len(channels)} 個のチャンネルを削除します"), ephemeral=True)
        await asyncio.gather(*[delete(channel) for channel in channels])
        await category.delete()
        await interaction.edit_original_message(embed=new_embed("カテゴリー削除完了", "カテゴリー内の全てのチャンネルが削除されました"))

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

    @wolf.sub_command(description="人狼で使うチャンネルを自動で作ります")
    async def auto_create_channes(
        self,
        interaction: Inter,
        new_category: bool = True,
        parent_category: disnake.CategoryChannel = None,
        category_name: str = "人狼",
        gm_channel_name: str = "人狼gm",
        text_channel_name: str = "人狼chat",
        voice_channel_name: str = "人狼vc"):

        if not await check_role(interaction, channel_moderator=True):
            return
        gm_ch: disnake.TextChannel = None
        text_ch: disnake.TextChannel = None
        voice_ch: disnake.VoiceChannel = None
        parent: disnake.CategoryChannel | disnake.Guild = None
        if new_category or parent_category:
            parent = parent_category or await interaction.guild.create_category(category_name)
        else:
            parent = interaction.channel.category or interaction.guild
        gm_ch, text_ch, voice_ch = await asyncio.gather(*[
            parent.create_text_channel(gm_channel_name),
            parent.create_text_channel(text_channel_name),
            parent.create_voice_channel(voice_channel_name)
        ])
        self.dbctl.set_channels(interaction.guild_id, gm_ch.id, text_ch.id, voice_ch.id)
        await interaction.response.send_message(embed=new_embed("完了しました"), ephemeral=True)


    @wolf.sub_command(description="人狼ゲームで使うチャンネルを設定します")
    async def set_channels(
            self,
            interaction: Inter,
            gm_channel: disnake.abc.GuildChannel = commands.Param(
                description="人狼GMがメッセージを送信するチャンネル"),
            text_meeting_channel: disnake.abc.GuildChannel = commands.Param(
                description="昼の会議チャンネル"),
            voice_meeting_channel: disnake.abc.GuildChannel = commands.Param(
                description="昼の会議ボイスチャンネル")):

        if not await check_role(interaction):
            return
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
        await interaction.response.defer()
        if not await check_role(interaction):
            return
        res = self.dbctl.start_game(
            interaction.author.id, interaction.guild_id)
        channels = self.dbctl.get_channels(interaction.guild_id)
        if not res["res"]:
            game_status = res["game_status"]
            error_code = res["code"]
            await interaction.edit_original_message(
                embed=self.new_embed(
                    title=ERROR_CODES[error_code],
                    description=f"このサーバーでのゲームは{GAME_STATUS[game_status][1]}です。"))
            return
        elif len(channels) < 3:
            await interaction.send(embed=self.new_embed("ゲームを開始する前に先にチャンネル設定を行ってください"))
            return

        try:
            guild = interaction.guild
            [await guild.fetch_channel(channel_id[0]) for channel_id in channels]
        except diserr.NotFound:
            await interaction.edit_original_message(embed=new_embed("チャンネル設定が正しくありません", "`/wolf set_channels` で設定し直してください"))
            self.dbctl.end_game(interaction.guild_id)
            return

        await interaction.edit_original_message(
            embed=self.new_embed(
                title="ゲームを開始します",
                description=f"ゲーム No.`{res['game_id']}`"))
        game_data: GameDataType = self.dbctl.get_game_from_server(interaction.guild_id)[0]

        game = GameBoard(game_data, self.bot)
        await game.async_init()
        game_task = asyncio.create_task(game.start())
        self.add_game_task(game_task, interaction.guild_id)
        game_ctl.add_game(game)

    @wolf.sub_command(description="人狼ゲームを強制終了します")
    async def stop(self, interaction: Inter):
        if not await check_role(interaction):
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
            return component_type and custom_id and author

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
        try:
            game_ctl.games[interaction.guild_id].interrupt = True
        except TypeError as e:
            logger.log(LT.WARNING, e)
        except KeyError as e:
            logger.log(LT.INFO, e)
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
            embed = self.new_embed(title="現在進行中のゲーム")
            for i in status:
                embed.add_field(name=i, value=f"`{status[i]}`")
            await interaction.response.send_message(embed=embed)

    class ExtendButton(disnake.ui.Button):
        def __init__(self, player_num: int, original_inter: Inter, original_msg: str, game: GameBoard, extend_seconds: int, custom_id: str):
            super().__init__(label="投票", custom_id=custom_id)
            self.vote = {original_inter.author.id}
            self.least_num = int(player_num/2)+1
            self.original_inter = original_inter
            self.original_msg = original_msg
            self.seconds = extend_seconds
            self.game = game

        async def callback(self, interaction: disnake.MessageInteraction):
            self.vote.add(interaction.author.id)
            vote_num = len(self.vote)
            text = f"ただいま{vote_num}/{self.least_num}人が投票しています"
            await self.original_inter.edit_original_message(embed=new_embed(self.original_msg, text))
            await interaction.response.send_message("投票しました", ephemeral=True)
            if vote_num >= self.least_num:
                await self.original_inter.send(embed=new_embed("延長が決定しました"))
                self.game.extends.append(self.seconds)

    @wolf.sub_command(description="昼の会議時間を伸ばします")
    async def extend(self, interaction: Inter, seconds: int = commands.Param(description="延長する秒数を指定してください（30秒以上）")):
        not_noon = False
        game = None
        try:
            game = game_ctl.games[interaction.guild_id]
            if game.status != "noon":
                not_noon = True
        except KeyError:
            not_noon = True

        # if not_noon:
        #     interaction.response.send_message("今は昼の会議中ではありません", ephemeral=True)
        #     return

        if seconds < 30:
            await interaction.response.send_message(embed=self.new_embed("30秒以上にしてください"), ephemeral=True)
            return
        button_id = str(next(gen))
        button = None
        try:
            player_num = len(self.dbctl.get_all_players(game.game_id))
            view = disnake.ui.View()
            text = f"{int(player_num/2)+1}人の投票が必要です"
            button = self.ExtendButton(
                player_num, interaction, text, game, seconds, button_id)
            view.add_item(button)
            await interaction.response.send_message(embed=self.new_embed(text), view=view, ephemeral=False)
        except Exception as e:
            logger.log(LT.WARNING, e)
            await interaction.response.send_message("error", ephemeral=True)
            return


def setup(bot: commands.Bot):
    bot.add_cog(Werewolf(bot))
    bot.add_cog(Others(bot))
