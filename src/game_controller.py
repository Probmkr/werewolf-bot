import asyncio
from db import DBC
from datetime import datetime
from enum import Enum
from typing import Dict, List, TypeAlias, TypedDict
import disnake
from disnake.ext import commands
from snowflake import SnowflakeGenerator
import random as rnd
from logger import LT, Logger
from var import GAME_ROLES, ROLE_SETS

gen = SnowflakeGenerator(0)
logger = Logger()
LEAST_PLAYER = 1


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
    BAD = 0xff0000
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
    joining_user: Dict[int, int]
    user_num: int
    role_set: dict[int, int]

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
        self.task.append(self.set_role_type)
        self.task.append(self.register_players)
        self.task.append(self.end_game)

    def game_embed(self, type: GET, title: str | None = "", description: str | None = ""):
        return disnake.Embed(title=title, description=description, color=type.value)

    def role_embed(self, role_id: int):
        rd = GAME_ROLES[role_id]
        return disnake.Embed(title=f"あなたの役職は{rd[1]}です", description=rd[2], color=rd[4])

    async def gather_users(self):
        button_id = str(next(gen))
        host_user_id = self.host_user_id

        def check(inter: disnake.MessageInteraction):
            if not type(inter) == disnake.MessageInteraction:
                return False
            component_type = inter.component.type.value == 2
            custom_id = inter.component.custom_id == str(button_id)
            author = inter.author.id == host_user_id
            player_num = len(self.joining_user) >= LEAST_PLAYER
            logger.log(LT.DEBUG, f"component_type was {component_type}")
            logger.log(LT.DEBUG, f"custom_id was {custom_id}")
            logger.log(LT.DEBUG, f"author was {author}")
            logger.log(LT.DEBUG, f"is player over 3 was {player_num}")
            return component_type and custom_id and author and player_num

        async def user_join(interaction: disnake.MessageInteraction):
            user = interaction.author
            # await interaction.response.is_done
            # await interaction.response.defer()
            # await interaction.delete_original_message()
            await interaction.response.send_message(embed=self.game_embed(GET.INFO, "受付完了"))
            if user.id in self.joining_user:
                del self.joining_user[user.id]
                await self.text.send(f"{user.mention} が抜けました")
            else:
                self.joining_user[user.id] = None
                await self.text.send(f"{user.mention} が参加しました")
            await asyncio.sleep(1)
            await interaction.delete_original_message()

        async def user_num_check(interaction: disnake.MessageInteraction):
            if len(self.joining_user) < LEAST_PLAYER:
                await interaction.response.send_message(embed=self.game_embed(GET.BAD, "プレーヤーが3人未満です", "3人以上になってからもう一度開始してください"))
                await asyncio.sleep(3)
                await interaction.delete_original_message()
            else:
                self.user_num = len(self.joining_user)

        self.joining_user = dict()
        view = disnake.ui.View()
        join_button = disnake.ui.Button(label="参加・取り消し")
        join_button.callback = user_join
        start_button = disnake.ui.Button(label="開始", custom_id=button_id)
        start_button.callback = user_num_check
        view.add_item(join_button)
        view.add_item(start_button)
        msg = await self.gm.send(embed=self.game_embed(GET.INFO, "新しいゲームを開始します！", f"ゲーム No.`{self.game_id}`"), view=view)
        await self.bot.wait_for("interaction", check=check)
        await msg.edit(view=None)
        # await self.gm.send(embed=self.game_embed(GET.INFO, "ゲームスタート！！"))

    def get_role_types_description(self):
        role_types = dict()
        for set_id, role_set in ROLE_SETS[self.user_num].items():
            text_list = []
            for id, num in role_set.items():
                text_list.append(f"{GAME_ROLES[id][1]}: {num}人")
            role_types[set_id] = ", ".join(text_list)
        return role_types

    class RoleSetMenu(disnake.ui.Select):
        def __init__(self, custom_id: str, game):
            super().__init__(placeholder="こちらから人員構成を選択してください", custom_id=custom_id)
            self.game: GameBoard = game

        async def callback(self, inter: disnake.MessageInteraction):
            if inter.author.id == self.game.host_user_id:
                logger.log(LT.TRACE, self.game.user_num)
                logger.log(LT.TRACE, self.values)
                self.game.role_set = ROLE_SETS[self.game.user_num][int(
                    self.values[0])].copy()
                logger.log(LT.TRACE, self.game.role_set)
                # await inter.response.send_message("")

    async def set_role_type(self):
        embed = self.game_embed(GET.INFO, "役職を決めます", "人員構成を選択してください")
        view = disnake.ui.View()
        selection_id = str(next(gen))
        menu = self.RoleSetMenu(custom_id=selection_id, game=self)
        role_types = self.get_role_types_description()
        for id, description in role_types.items():
            menu.options.append(disnake.SelectOption(
                label=description, value=id))
        view.add_item(menu)

        def check(inter: disnake.MessageInteraction):
            if not type(inter) == disnake.MessageInteraction:
                return False
            component_type = inter.component.type.value == 3
            custom_id = inter.component.custom_id == str(selection_id)
            author = inter.author.id == self.host_user_id
            logger.log(LT.TRACE, f"component_type was {component_type}")
            logger.log(LT.TRACE, f"custom_id was {custom_id}")
            logger.log(LT.TRACE, f"author was {author}")
            return component_type and custom_id and author

        msg = await self.gm.send(embed=embed, view=view)
        logger.log(LT.DEBUG, "wait for role set")
        await self.bot.wait_for("interaction", check=check)
        decide_embed = self.game_embed(
            GET.INFO, "役職が決まりました", "次に割り振りをします"+"\n"+"DMに役職を送るので確認してください")
        await msg.edit(embed=decide_embed, view=None)

    async def set_roles(self):
        random_list = []
        for i, j in self.role_set.items():
            random_list += [i]*j
            logger.log(LT.DEBUG, random_list)
        rnd.shuffle(random_list)
        logger.log(LT.DEBUG, random_list)
        for player in self.joining_user:
            self.joining_user[player] = random_list.pop(0)
        logger.log(LT.DEBUG, self.joining_user)


    async def register_players(self):
        await self.set_roles()
        # guild = await self.bot.fetch_guild(self.guild_id)
        for player, role in self.joining_user.items():
            self.dbctl.register_player(self.game_id, player, role)
            await (await self.bot.fetch_user(player)).send(embed=self.role_embed(role))

    async def end_game(self):
        self.dbctl.end_game(self.guild_id)
        await self.gm.send(embed=self.game_embed(GET.INFO, "ゲームを終了しました"))

    async def start(self):
        while self.task:
            await self.task.pop(0)()


class GameController:
    def __init__(self):
        self.games = dict()

    def add_game(self, game: GameBoard):
        self.games[game.guild_id] = game
