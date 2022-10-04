import asyncio
import disnake

from logger import LT, Logger

logger = Logger()

async def get_guild_members(guild: disnake.Guild, *users_id: int) -> tuple[disnake.Member]:
    logger.log(LT.DEBUG, users_id)
    async def get(user_id):
        return await guild.fetch_member(user_id)

    return await asyncio.gather(*[get(user_id) for user_id in users_id])


async def check_role(interaction: disnake.AppCmdInter, *, wolf_moderator: bool = True, channel_moderator: bool = False):
    def is_wolf_moderator(interaction: disnake.AppCmdInter):
        for role in interaction.author.roles:
            if role.name in ["人狼モデレーター"]:
                return True
        else:
            return False

    ok = True
    if wolf_moderator:
        ok = is_wolf_moderator(interaction) and ok
    if channel_moderator:
        ok = interaction.author.guild_permissions.manage_channels and ok

    if not ok:
        await interaction.response.send_message("あなたにこのコマンドを使う権限はありません。", ephemeral=True)
    return ok