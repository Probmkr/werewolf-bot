import asyncio
import traceback
from db import DBC
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, TypeAlias, TypedDict
import disnake
from disnake.ext import commands
from snowflake import SnowflakeGenerator
import random as rnd
from lib import get_guild_members
from logger import LT, Logger
from var import GAME_ROLES, ROLE_SETS, WAIT_TIMEOUT
import tracemalloc

tracemalloc.start()

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


class PlayerType(TypedDict):
    game_id: int
    player_id: int
    player_name: str
    role_id: int
    alive: bool


GET: TypeAlias = GameEmbedType
FuncName: TypeAlias = str


def game_embed(type: GET, title: str | None = "", description: str | None = ""):
    return disnake.Embed(title=title, description=description, color=type.value)


def crole_embed(role_id: int, title: str = "", description: str = ""):
    rc = GAME_ROLES[role_id][4]
    return disnake.Embed(title=title, description=description, color=rc)


def role_embed(role_id: int, game_id: int, additional: list[str] = None):
    rd = GAME_ROLES[role_id]
    return disnake.Embed(title=f"あなたの役職は{rd[1]}です", description=rd[2] + ("\n" + "\n".join(additional)) if additional else "" + f"\nゲーム No.`{game_id}`", color=rd[4])


async def timeouted(user: disnake.Member, seconds: int):
    await user.send(embed=crole_embed(1, "タイムアウトしました", f"{seconds}秒以内に決めてください"))


class GameBoard:
    game_data: GameDataType
    game_id: int
    game_status_id: int
    host_user_id: int
    guild_id: int
    started: datetime
    # ended: datetime
    bot: commands.Bot
    dbctl: DBC
    interrupt: bool
    status: FuncName
    gm_id: int
    text_id: int
    voice_id: int
    gm: disnake.TextChannel
    text: disnake.TextChannel
    voice: disnake.VoiceChannel
    tasks: list[Callable[[Any], Awaitable[Any]]]
    joining_user: dict[int, int]
    player_num: int
    role_set: dict[int, int]
    day_long: int
    noon_time: int
    night_time: int
    extends: list[int]
    wolf_kill_list: list[int]
    meeting_kill_list: list[int]
    killed_by_wolf: list[int]
    killed_by_meeting: list[int]
    guarded_by_guard: list[int]

    def __init__(self, game_data: GameDataType, bot: commands.Bot, **extra_settings):
        self.game_data = game_data
        self.game_id = game_data["game_id"]
        self.game_status_id = game_data["game_status_id"]
        self.host_user_id = game_data["game_host_user_id"]
        self.guild_id = game_data["game_host_guild_id"]
        self.started = game_data["game_started_at"]
        # self.ended = game_data["game_ended_at"]
        self.bot = bot
        self.dbctl = DBC()
        self.interrupt = False
        gm, text, voice = self.dbctl.get_channels(self.guild_id)
        self.gm_id, self.text_id, self.voice_id = gm[0], text[0], voice[0]
        self.tasks = []
        self.extra = extra_settings
        self.day_long = 150
        self.noon_time = 0
        self.night_time = 0
        self.extends = []
        self.wolf_kill_list = []
        self.meeting_kill_list = []
        self.killed_by_wolf = []
        self.killed_by_meeting = []
        self.guarded_by_guard = []

    async def async_init(self):
        self.guild = await self.bot.fetch_guild(self.guild_id)
        self.gm = await self.guild.fetch_channel(self.gm_id)
        self.text = await self.guild.fetch_channel(self.text_id)
        self.voice = await self.guild.fetch_channel(self.voice_id)
        self.add_task(self.gather_users)

    def add_task(self, func: Callable[[Any], Awaitable[Any]]):
        self.tasks.append(func)

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
            player_num = len(self.joining_user) >= LEAST_PLAYER
            return component_type and custom_id and author and player_num

        async def user_join(interaction: disnake.MessageInteraction):
            user = interaction.author
            await interaction.response.send_message(embed=game_embed(GET.INFO, "受付完了"), ephemeral=True)
            if user.id in self.joining_user:
                del self.joining_user[user.id]
                await self.text.send(f"{user.mention} が抜けました")
            else:
                self.joining_user[user.id] = None
                await self.text.send(f"{user.mention} が参加しました")
            await asyncio.sleep(1)

        async def user_num_check(interaction: disnake.MessageInteraction):
            if len(self.joining_user) < LEAST_PLAYER:
                await interaction.response.send_message(embed=game_embed(GET.BAD, "プレーヤーが3人未満です", "3人以上になってからもう一度開始してください"))
                await asyncio.sleep(3)
                await interaction.delete_original_message()
            else:
                self.player_num = len(self.joining_user)

        self.joining_user = dict()
        view = disnake.ui.View()
        join_button = disnake.ui.Button(label="参加・取り消し")
        join_button.callback = user_join
        start_button = disnake.ui.Button(label="開始", custom_id=button_id)
        start_button.callback = user_num_check
        view.add_item(join_button)
        view.add_item(start_button)
        msg = await self.gm.send(embed=game_embed(GET.INFO, "新しいゲームを開始します！", f"ゲーム No.`{self.game_id}`"), view=view)
        await self.bot.wait_for("interaction", check=check, timeout=WAIT_TIMEOUT)
        await msg.edit(view=None)
        self.add_task(self.set_role_type)

    def get_role_types_description(self):
        role_types = dict()
        for set_id, role_set in ROLE_SETS[self.player_num].items():
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
                # logger.log(LT.TRACE, self.game.player_num)
                # logger.log(LT.TRACE, self.values)
                self.game.role_set = ROLE_SETS[self.game.player_num][int(
                    self.values[0])].copy()
                # logger.log(LT.TRACE, self.game.role_set)
                # await inter.response.send_message("")

    async def set_role_type(self):
        embed = game_embed(GET.INFO, "役職を決めます", "人員構成を選択してください")
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
            # logger.log(LT.TRACE, f"component_type was {component_type}")
            # logger.log(LT.TRACE, f"custom_id was {custom_id}")
            # logger.log(LT.TRACE, f"author was {author}")
            return component_type and custom_id and author

        msg = await self.gm.send(embed=embed, view=view)
        logger.log(LT.DEBUG, "wait for role set")
        await self.bot.wait_for("interaction", check=check, timeout=WAIT_TIMEOUT)
        decide_embed = game_embed(
            GET.INFO, "役職が決まりました", "次に割り振りをします"+"\n"+"DMに役職を送るので確認してください")
        await msg.edit(embed=decide_embed, view=None)
        self.add_task(self.register_players)

    async def set_roles(self):
        random_list = []
        for i, j in self.role_set.items():
            random_list += [i]*j
            # logger.log(LT.DEBUG, random_list)
        rnd.shuffle(random_list)
        # logger.log(LT.DEBUG, random_list)
        for player in self.joining_user:
            self.joining_user[player] = random_list.pop(0)
        # logger.log(LT.DEBUG, self.joining_user)

    async def register_players(self):
        await self.set_roles()
        # wolves_data = self.dbctl.get_role_players(self.game_id, 1)
        wolves = [
            wolf for wolf in self.joining_user if self.joining_user[wolf] == 1]

        async def register(player: int, role: int):
            additional = []
            if role == 1:
                # logger.log(LT.DEBUG, f"role: {role}")
                # logger.log(LT.DEBUG, f"player: {player}")
                # logger.log(LT.DEBUG, f"wolves: {wolves}")
                other_wolves = [wolf for wolf in wolves if wolf != player]
                # logger.log(LT.DEBUG, f"other_wolves: {other_wolves}")
                if other_wolves:
                    wolves_member = await get_guild_members(self.guild, *other_wolves)
                    # logger.log(LT.DEBUG, f"wolves_member: {wolves_member}")
                    wolves_quoted = map(
                        lambda item: f"`{item.display_name}`", wolves_member)
                    additional.append(
                        "他の人狼は、 " + ", ".join(wolves_quoted) + "です")
            user_name = (await self.guild.fetch_member(player)).display_name
            self.dbctl.register_player(self.game_id, player, user_name, role)
            await (await self.bot.fetch_user(player)).send(embed=role_embed(role, self.game_id, additional))

        tasks: list[asyncio.Task] = []
        for player, role in self.joining_user.items():
            tasks.append(register(player, role))

        await asyncio.gather(*tasks)

        self.add_task(self.noon)

    async def noon(self):
        self.day_long = 1
        self.noon_time += 1
        self.dbctl.set_time(self.game_id, noon=self.noon_time)
        await self.text.send(embed=game_embed(
            GET.INFO, f"{self.noon_time}日目の昼が始まりました", "話し合って人狼を探しあてましょう！\n会議時間は2分30秒です\n`/wolf extend`で延長、`/wolf skip`で短縮できます"))
        if self.night_time >= 1:
            if self.killed_by_wolf[-1] != None:
                killed_data: PlayerType = self.dbctl.get_player(
                    self.game_id, self.killed_by_wolf[-1])
                await self.text.send(embed=game_embed(GET.BAD, f"{killed_data['player_name']}が殺されました"))
            elif self.killed_by_wolf[-1] == None:
                await self.text.send(embed=game_embed(GET.GOOD, f"昨夜は誰も殺されませんでした"))
            else:
                raise Exception("self.killed_by_wolf に意味不明の値が代入されました")
        await self.text.set_permissions(self.guild.default_role, send_messages=True)
        ltm = self.day_long % 60
        mins = int(self.day_long / 60)
        await asyncio.sleep(ltm)
        for i in range(mins):
            await self.text.send(embed=game_embed(GET.INFO, f"残り{mins - i}分です"))
            await asyncio.sleep(60)
        while self.extends:
            extend = self.extends.pop(0)
            ltm = extend % 60
            mins = int(extend / 60)
            await self.text.send(embed=game_embed(GET.INFO, f"{mins}分{ltm}秒延長します"))
            await asyncio.sleep(ltm)
            for i in range(mins):
                await self.text.send(embed=game_embed(GET.INFO, f"残り{mins - i}分です"))
                await asyncio.sleep(60)
        if self.noon_time == 1:
            self.add_task(self.night)

    async def vote(self):
        flag = False
        select_id = str(next(gen))
        select = PlayerSelection(self, select_id, skip=True)
        view = disnake.ui.View()
        view.add_item(select)
        await self.text.send(embed=game_embed(GET.INFO, "昼が終了しました"))
        msg = await self.text.send(embed=game_embed(GET.INFO, "投票", "追放したいプレーヤーに投票してください\n選択時間は30秒です"), view=view)
        await asyncio.sleep(30)
        await msg.edit(view=None)
        await self.text.send(embed=game_embed(GET.INFO, "投票終了", "集計中..."))

        summery = dict()
        for player in select.values:
            try:
                summery[int(player)] += 1
            except KeyError:
                summery[int(player)] = 1
        max_player = max(summery.values())
        max_player_num = list(summery.values()).count(max_player)
        if max_player_num >= 2:
            flag = False
        elif max_player_num == 1:
            flag = True

    async def night(self):
        wolves_num = len(self.dbctl.get_role_players(self.game_id, 1))
        humans_num = len(self.dbctl.get_human_players(self.game_id))
        if wolves_num == 0:
            await self.text.send(embed=crole_embed(0, "村人の勝ちです", "人狼が全員追放されました"))
            return

        self.guarded_by_guard = []
        its_night = "夜になりました"

        async def wolf_action():

            wolves: list[PlayerType] = []
            for wolf in self.dbctl.get_role_players(self.game_id, 1):
                wolves.append(dict(wolf))
            wolf_text = "殺す人を決めてください"
            wolves_num = len(wolves)
            multi = wolves_num >= 2
            if wolves_num >= 1:
                async def select_to_kill(wolf: PlayerType):
                    selection_id = str(next(gen))

                    def check(inter: disnake.MessageInteraction):
                        if type(inter) != disnake.MessageInteraction:
                            return False
                        component_type = inter.component.type.value == 3
                        custom_id = inter.component.custom_id == selection_id
                        author = inter.author.id == wolf["player_id"]
                        # logger.log(LT.TRACE, f"component_type was {component_type}")
                        # logger.log(LT.TRACE, f"custom_id was {custom_id}")
                        # logger.log(LT.TRACE, f"author was {author}")
                        return component_type and custom_id and author

                    wolf_user = await self.guild.fetch_member(wolf["player_id"])
                    view = disnake.ui.View()
                    select = PlayerSelection(
                        self, selection_id, except_role=[1])
                    view.add_item(select)
                    await wolf_user.send(embed=crole_embed(1, its_night, "仲間と" if multi else "" + "殺す人を決めましょう"))
                    msg = await wolf_user.send(embed=crole_embed(1, wolf_text, "仲間と選択した中でランダムに決められます" if multi else ""), view=view)
                    try:
                        await self.bot.wait_for("interaction", check=check, timeout=WAIT_TIMEOUT)
                    except asyncio.TimeoutError:
                        await msg.edit(view=None)
                        await timeouted(wolf_user, WAIT_TIMEOUT)
                        return
                    await msg.edit(view=None)
                    if multi:
                        # logger.log(LT.DEBUG, "append wolf_kill_list")
                        self.wolf_kill_list.append(int(select.values[0]))
                    else:
                        # logger.log(LT.DEBUG, "append killed_by_wolf")
                        # logger.log(LT.DEBUG, f"select.values = {select.values}")
                        self.killed_by_wolf.append(int(select.values[0]))
                    await msg.reply(embed=crole_embed(1, "完了しました"))

                # tasks: list[asyncio.Task] = []
                # for wolf in wolves:
                #     tasks.append(select_to_kill(wolf))

                await asyncio.gather(*[select_to_kill(wolf) for wolf in wolves])

                if multi:
                    self.killed_by_wolf.append(rnd.choice(self.wolf_kill_list))

        async def seer_action():
            seers: list[PlayerType] = self.dbctl.get_role_players(
                self.game_id, 2)
            if len(seers) >= 1:
                seer_text = "占う人を決めてください"

                async def select_to_divine(seer: PlayerType):
                    selection_id = str(next(gen))

                    def check(inter: disnake.MessageInteraction):
                        if type(inter) != disnake.MessageInteraction:
                            return False
                        component_type = inter.component.type.value == 3
                        custom_id = inter.component.custom_id == selection_id
                        author = inter.author.id == seer["player_id"]
                        return component_type and custom_id and author

                    seer_user = await self.guild.fetch_member(seer["player_id"])
                    view = disnake.ui.View()
                    select = PlayerSelection(
                        self, selection_id, except_player=[seer["player_id"]])
                    view.add_item(select)
                    await seer_user.send(embed=crole_embed(2, its_night, "村人のために誰かを占いましょう"))
                    msg = await seer_user.send(embed=crole_embed(2, seer_text, "人間か人間でないかが知らされます"), view=view)
                    try:
                        await self.bot.wait_for("interaction", check=check, timeout=WAIT_TIMEOUT)
                    except asyncio.TimeoutError:
                        await msg.edit(view=None)
                        await timeouted(seer_user, WAIT_TIMEOUT)
                        return
                    await msg.edit(view=None)
                    to_seer = int(select.values[0])
                    to_seer_data: PlayerType = self.dbctl.get_player(
                        self.game_id, to_seer)
                    await msg.reply(embed=crole_embed(2, "占いの結果", f"{to_seer_data['player_name']} は人間{'です' if GAME_ROLES[to_seer_data['role_id']][3] else 'ではありません'}"))

                await asyncio.gather(*[select_to_divine(seer) for seer in seers])

        async def medium_action():
            mediums: list[PlayerType] = self.dbctl.get_role_players(
                self.game_id, 4)
            if len(mediums) >= 1:
                killed = self.killed_by_meeting[-1]
                killed_data: PlayerType = self.dbctl.get_player(
                    self.game_id, killed)
                is_human = GAME_ROLES[killed_data["role_id"]][3]
                text = f"{killed_data['player_name']} は人間{'でした' if is_human else 'ではありませんでした'}"

                async def killed_status(medium: PlayerType):
                    medium_user = self.guild.fetch_member(medium["player_id"])
                    await medium_user.send(embed=crole_embed(4, "追放者の結果", text))

                await asyncio.gather(*[killed_status(medium) for medium in mediums])

        async def guard_action():
            guards: list[PlayerType] = self.dbctl.get_role_players(
                self.game_id, 5)
            if len(guards) >= 1:
                guard_text = "守る人を決めてください"

                async def select_to_guard(guard: PlayerType):
                    selection_id = str(next(gen))

                    def check(inter: disnake.MessageInteraction):
                        if type(inter) != disnake.MessageInteraction:
                            return False
                        component_type = inter.component.type.value == 3
                        custom_id = inter.component.custom_id == selection_id
                        author = inter.author.id == guard["player_id"]
                        return component_type and custom_id and author

                    guard_user = await self.guild.fetch_member(guard["player_id"])
                    view = disnake.ui.View()
                    select = PlayerSelection(self, selection_id)
                    view.add_item(select)
                    await guard_user.send(embed=crole_embed(5, its_night, "村人のために誰かを人狼から守りましょう"))
                    msg = await guard_user.send(embed=crole_embed(5, guard_text, "その人が人狼に襲撃されても死ぬことはありません"), view=view)
                    try:
                        await self.bot.wait_for("interaction", check=check)
                    except asyncio.TimeoutError:
                        await msg.edit(view=None)
                        await timeouted(guard_user, WAIT_TIMEOUT)
                        return
                    await msg.edit(view=None)
                    to_guard = int(select.values[0])
                    self.guarded_by_guard.append(to_guard)
                    await msg.reply(embed=crole_embed(5, "完了しました"))

                await asyncio.gather(*[select_to_guard(guard) for guard in guards])

        self.night_time += 1
        await self.text.send(embed=game_embed(GET.INFO, its_night, "全員ミュートです"))
        await self.text.set_permissions(self.guild.default_role, send_messages=False)
        night_tasks = [wolf_action(), seer_action(), guard_action()]
        if self.night_time >= 2:
            night_tasks.append(medium_action())
        await asyncio.gather(*night_tasks)
        logger.log(LT.DEBUG, f"to guard are {self.guarded_by_guard}")

        if self.killed_by_wolf[-1] in self.guarded_by_guard:
            self.killed_by_wolf[-1] = None
        else:
            self.dbctl.kill_player(self.game_id, self.killed_by_wolf[-1])
            killed_user = await self.guild.fetch_member(self.killed_by_wolf[-1])
            await killed_user.send(embed=game_embed(GET.BAD, "あなたは殺されました", "これから先は発言しないでください"))

        await asyncio.sleep(1)

        if wolves_num >= humans_num:
            await self.text.send(embed=crole_embed(1, "人狼の勝ちです", "村人の数が人狼以下になりました"))
            return

        self.add_task(self.noon)

    async def end_game(self):
        self.dbctl.end_game(self.guild_id)
        if not self.interrupt:
            await self.text.send(embed=game_embed(GET.INFO, "ゲームを終了しました"))
        else:
            await self.text.send(embed=game_embed(GET.INFO, "ゲームが中断されました"))

    async def start(self):
        try:
            while self.tasks and not self.interrupt:
                awaitable = self.tasks.pop(0)
                self.status = awaitable.__name__
                await awaitable()
        except asyncio.TimeoutError:
            await self.gm.send(embed=game_embed(GET.BAD, "タイムアウトしました", f"{WAIT_TIMEOUT}秒以内に決定してください"))
        except Exception as e:
            await self.text.send(embed=game_embed(GET.BAD, "エラーが起きたのでゲームを終了します", "[@probmkrnew](https://twitter.com/probmkrnew)にご連絡ください"))
            await self.text.send(f"エラー内容:\n```\n{traceback.format_exc()}\n```")
            # logger.log(LT.ERROR, e)
            # logger.log(LT.ERROR, str(e.__traceback__))
            logger.log(LT.ERROR, traceback.format_exc())
            self.interrupt = True
        await self.end_game()


class GameController:
    games: dict[int, GameBoard]

    def __init__(self):
        self.games = dict()

    def add_game(self, game: GameBoard):
        self.games[game.guild_id] = game


class PlayerSelection(disnake.ui.Select):
    def __init__(self, game: GameBoard, custom_id: str, *, except_role: list[int] = [], except_player: list[int] = [], skip: bool = False):
        super().__init__(custom_id=custom_id)
        self.game = game
        game_data = game.game_data
        players: list[PlayerType] = game.dbctl.get_all_players(
            game_data["game_id"])
        options = [disnake.SelectOption(label=player["player_name"], value=player["player_id"])
                   for player in players if player["player_id"] not in except_player and player["role_id"] not in except_role]
        if skip:
            options.append(disnake.SelectOption(label="skip", value="0"))
        self.options = options
