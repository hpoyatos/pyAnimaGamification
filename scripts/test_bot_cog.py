import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import discord
from discord.ext import commands
from discord_bot.cogs.kahoot_cog import KahootCog

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
cog = KahootCog(bot)
print("Cog 'KahootCog' instanciado com sucesso!")
print(f"Comandos registrados no grupo 'quiz': {[c.name for c in cog.quiz_group.commands]}")
