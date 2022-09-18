from db import DBC
from datetime import datetime
from enum import Enum
from typing import List, TypeAlias, TypedDict
import disnake
from disnake.ext import commands
from snowflake import SnowflakeGenerator

from logger import LT, Logger

gen = SnowflakeGenerator(0)
logger = Logger()

class GameDataType(TypedDict):
    game_id: int
    game_status_id: int
    game_host_user_id: int
    game_host_guild_id: int
    game_started_at: datetime
    game_ended_at: datetime


class GameEmbedType(Enum):
    INFO = 0x4169e1
    TIME = 0xff4500
    BAD = 0x000000
    GOOD = 0x008000


GET: TypeAlias = GameEmbedType


class GameBoard:
    game_id: int
    game_status_id: int
    host_user_id: int
    guild_id: int
    started: datetime
    # ended: datetime
    bot: commands.Bot
    dbctl: DBC
    gm_id: int
    text_id: int
    voice_id: int
    gm: disnake.TextChannel
    text: disnake.TextChannel
    voice: disnake.VoiceChannel
    task: List
    user_join: List[int]
    def __init__(self, game_data: GameDataType, bot: commands.Bot, **extra_settings):
        self.game_id = game_data["game_id"]
        self.game_status_id = game_data["game_status_id"]
        self.host_user_id = game_data["game_host_user_id"]
        self.guild_id = game_data["game_host_guild_id"]
        self.started = game_data["game_started_at"]
        # self.ended = game_data["game_ended_at"]
        self.bot = bot
        self.dbctl = DBC()
        gm, text, voice = self.dbctl.get_channels(self.guild_id)
        self.gm_id, self.text_id, self.voice_id = gm[0], text[0], voice[0]
        self.task = []
        self.extra = extra_settings
        self.generate_tasks()

    async def async_init(self):
        self.guild = await self.bot.fetch_guild(self.guild_id)
        self.gm = await self.guild.fetch_channel(self.gm_id)
        self.text = await self.guild.fetch_channel(self.text_id)
        self.voice = await self.guild.fetch_channel(self.voice_id)

    def generate_tasks(self):
        self.task.append(self.gather_users)
        self.task.append(self.end_game)

    def game_embed(self, type: GET, title: str | None = "", description: str | None = ""):
        return disnake.Embed(title=title, description=description, color=type.value)

    async def gather_users(self):
        button_id = str(next(gen))
        host_user_id = self.host_user_id
        def check(inter: disnake.MessageInteraction):
            if not type(inter) == disnake.MessageInteraction:
                return False
            component_type = inter.component.type.value == 2
            custom_id = inter.component.custom_id == str(button_id)
            author = inter.author.id == host_user_id
            logger.log(LT.DEBUG, f"component_type was {component_type}")
            logger.log(LT.DEBUG, f"custom_id was {custom_id}")
            logger.log(LT.DEBUG, f"author was {author}")
            return component_type and custom_id and author
        self.join_user = []
        view = disnake.ui.View()
        join_button = disnake.ui.Button(label="参加・取り消し")
        join_button.callback = self.user_join
        start_button = disnake.ui.Button(label="開始", custom_id=button_id)
        view.add_item(join_button)
        view.add_item(start_button)
        msg = await self.gm.send(embed=self.game_embed(GET.INFO, "新しいゲームを開始します！", f"ゲーム No.`{self.game_id}`"), view=view)
        await self.bot.wait_for("interaction", check=check)
        await msg.edit(view=None)
        await self.gm.send(embed=self.game_embed(GET.INFO, "ゲームスタート！！"))

    async def end_game(self):
        self.dbctl.end_game(self.guild_id)
        await self.gm.send(embed=self.game_embed(GET.INFO, "ゲームを終了しました"))

    async def user_join(self, interaction: disnake.MessageInteraction):
        user = interaction.author
        # await interaction.response.is_done
        if user.id in self.join_user:
            self.join_user.remove(user.id)
            await interaction.response.send_message(f"{user.mention} が抜けました")
        else:
            self.join_user.append(user.id)
            await interaction.response.send_message(f"{user.mention} が参加しました")

    async def start(self):
        while self.task:
            await self.task.pop(0)()


class GameController:
    def __init__(self):
        self.games = dict()

    def add_game(self, game: GameBoard):
        self.games[game.guild_id] = game
