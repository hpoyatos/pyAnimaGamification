import sys
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from discord_bot.main import GamificationBot

async def test_bot():
    bot = GamificationBot()
    print("Testando setup_hook do bot...")
    await bot.setup_hook()
    print(f"Cogs carregados ({len(bot.cogs)}): {list(bot.cogs.keys())}")
    print(f"Comandos registrados na árvore ({len(bot.tree.get_commands())}): {[c.name for c in bot.tree.get_commands()]}")
    print("Bot validado com sucesso!")

if __name__ == "__main__":
    asyncio.run(test_bot())
