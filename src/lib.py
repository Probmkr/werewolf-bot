import asyncio
import disnake

from logger import LT, Logger

logger = Logger()

async def get_guild_members(guild: disnake.Guild, *users_id: int) -> tuple[disnake.Member]:
    logger.log(LT.DEBUG, users_id)
    async def get(user_id):
        return await guild.fetch_member(user_id)

    return await asyncio.gather(*[get(user_id) for user_id in users_id])
