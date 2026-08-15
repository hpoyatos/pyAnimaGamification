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
        ints = discord.Intents.all()
        
        super().__init__(
            command_prefix="!", 
            intents=ints
        )

    async def setup_hook(self):
        cogs = [
            "discord_bot.cogs.pontos_cog",
            "discord_bot.cogs.greetings_cog",
            "discord_bot.cogs.identificar_cog",
            "discord_bot.cogs.cursos_cog",
            "discord_bot.cogs.kahoot_cog",
            "discord_bot.cogs.temas_cog"
        ]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Cog '{cog}' carregado com sucesso.")
            except Exception as e:
                logger.error(f"Erro ao carregar cog '{cog}': {e}")
        
        # Sincroniza os slash commands globalmente
        try:
            synced = await self.tree.sync()
            logger.info(f"Comandos globais sincronizados ({len(synced)}): {[c.name for c in synced]}")
        except Exception as e:
            logger.error(f"Erro ao sincronizar comandos globais: {e}")

    async def on_ready(self):
        logger.info(f"Logado como {self.user} (id={self.user.id})")
        
        # Auditoria on connect
        auditoria_id_str = os.getenv("DISCORD_AUDITORIA_CHANNEL_ID")
        if auditoria_id_str:
            try:
                channel = self.get_channel(int(auditoria_id_str))
                if channel:
                    await channel.send("✅ Bot Gamification conectado e operacional!")
            except Exception as e:
                logger.error(f"Erro ao enviar log para auditoria em on_ready: {e}")

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
