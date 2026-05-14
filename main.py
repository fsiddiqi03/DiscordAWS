import asyncio
import logging

import discord
from discord.ext import commands

from config import TOKEN
from commands import ServerCog

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("bot")

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())


@bot.event
async def on_ready():
    logger.info("Bot is on and Ready!")
    try:
        synced = await bot.tree.sync()
        logger.info("Synced %d command(s)", len(synced))
    except Exception as e:
        logger.error("on_ready failed: %s", e)


async def main():
    async with bot:
        await bot.add_cog(ServerCog(bot))
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
