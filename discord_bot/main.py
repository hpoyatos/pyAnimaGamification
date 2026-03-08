import os
import logging
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("discord-bot")

class GamificationBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!", 
            intents=discord.Intents.default()
        )

    async def setup_hook(self):
        # Carrega os cogs modularizados
        await self.load_extension("cogs.pontos_cog")
        logger.info("Cogs carregados.")
        
        # Sincroniza os slash commands globalmente
        await self.tree.sync()
        logger.info("Comandos globais sincronizados.")

    async def on_ready(self):
        logger.info(f"Logado como {self.user} (id={self.user.id})")

async def main():
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        logger.error("DISCORD_BOT_TOKEN não encontrado nas variáveis de ambiente.")
        return

    bot = GamificationBot()
    
    async with bot:
        await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
