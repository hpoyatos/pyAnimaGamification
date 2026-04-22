import logging
import discord
from discord.ext import commands
import re
from discord import app_commands

logger = logging.getLogger("cogs.greetings")

class GreetingsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_help_text(self, author):
        return (
            f"Olá, **{author.global_name or author.name}**! 👋\n\n"
            "Eu sou o assistente virtual do sistema de Gamificação.\n\n"
            "Aqui estão os comandos que você pode utilizar comigo neste chat privado:\n\n"
            "🔹 `/identificar` - Inicia o processo de vincular seu usuário com o portal da disciplina.\n"
            "🔹 `/validar [seu_codigo]` - Termina a vinculação se você já tem o código do e-mail.\n"
            "🔹 `/pontos` - Consulta detalhadamente os pontos que você acumulou na Gamificação.\n"
            "🔹 `/catalogo` - Lista todos os cursos parceiros com inscrições abertas.\n"
            "🔹 `/inscrever [curso_id]` - Realiza sua pré-inscrição em um dos cursos disponíveis no catálogo.\n"
            "🔹 `/enviar_certificado [curso_id] [pdf]` - Envia o certificado de conclusão para validação e registro de horas.\n\n"
            "_Estou sendo atualizado constantemente, então aguarde por mais novidades no futuro!_"
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore messages from bots
        if message.author.bot:
            return

        # Check if the message is in a DM (Direct Message)
        is_dm = isinstance(message.channel, discord.DMChannel)
        
        if is_dm:
            content = message.content.lower().strip()
            
            # Detecta se o usuário digitou o comando como texto sem clicar na caixa de "Slash Command"
            if content.startswith("/identificar") or content.startswith("/validar") or content.startswith("/pontos") or content.startswith("/enviar_certificado"):
                ajuda = (
                    "⚠️ **Atenção:** Você digitou o comando como um texto comum.\n"
                    "Para que o bot entenda sua ação e possa te exibir a caixinha certa, você precisa **digitar a / (barra)** e **selecionar o comando correspondente na lista de opções** que o Discord te mostrará logo acima do seu teclado.\n\n"
                    "_Se os comandos não aparecerem após a barra, recarregue seu Discord (Ctrl+R no PC) porque a lista pode estar desatualizada!_"
                )
                try:
                    await message.channel.send(ajuda)
                except Exception as e:
                    logger.error(f"Erro ao enviar DM de alerta de slash command: {e}")
                return
                
            # Simple regex to match "oi", "ola", "olá", with any number of ! or ? or extra letters
            if re.search(r'\b(o+i+|o+l+a+|o+l+á+|h+e+l+l+o+|h+a+l+o+)\b', content) or content.startswith("oi") or content.startswith("ola") or content.startswith("olá"):
                logger.info(f"Greetings triggered by {message.author} in DM: {message.content}")
                
                greeting_text = self.get_help_text(message.author)
                
                try:
                    await message.channel.send(greeting_text)
                except Exception as e:
                    logger.error(f"Erro ao enviar DM de saudação: {e}")

    @app_commands.command(name="help", description="Mostra a lista de comandos disponíveis e como utilizá-los.")
    async def cmd_help(self, interaction: discord.Interaction):
        await interaction.response.send_message(self.get_help_text(interaction.user), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(GreetingsCog(bot))
