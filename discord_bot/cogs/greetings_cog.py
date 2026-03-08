import logging
import discord
from discord.ext import commands
import re

logger = logging.getLogger("cogs.greetings")

class GreetingsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore messages from bots
        if message.author.bot:
            return

        # Check if the message is in a DM (Direct Message)
        is_dm = isinstance(message.channel, discord.DMChannel)
        
        if is_dm:
            content = message.content.lower().strip()
            
            # Simple regex to match "oi", "ola", "olá", with any number of ! or ? or extra letters
            if re.search(r'\b(o+i+|o+l+a+|o+l+á+|h+e+l+l+o+|h+a+l+o+)\b', content) or content.startswith("oi") or content.startswith("ola") or content.startswith("olá"):
                logger.info(f"Greetings triggered by {message.author} in DM: {message.content}")
                
                greeting_text = (
                    f"Olá, **{message.author.global_name or message.author.name}**! 👋\n\n"
                    "Eu sou o assistente virtual do sistema de Gamificação.\n\n"
                    "Aqui estão os comandos que você pode utilizar comigo neste chat privado:\n\n"
                    "🔹 `/pontos` - Consulta detalhadamente os pontos que você acumulou na Gamificação.\n\n"
                    "_Estou sendo atualizado constantemente, então aguarde por mais novidades no futuro!_"
                )
                
                try:
                    await message.channel.send(greeting_text)
                except Exception as e:
                    logger.error(f"Erro ao enviar DM de saudação: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(GreetingsCog(bot))
