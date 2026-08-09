import os
import logging
import discord
from discord.ext import commands
import re
from discord import app_commands
import mysql.connector

logger = logging.getLogger("cogs.greetings")

# Calcula o caminho relativo do arquivo de regras a partir da pasta deste cog
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_FILE_PATH = os.path.join(BASE_DIR, "arquivos", "regras.txt")

def get_regras_text():
    """Lê o arquivo de regras.txt dinamicamente."""
    try:
        if os.path.exists(RULES_FILE_PATH):
            with open(RULES_FILE_PATH, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception as e:
        logger.error(f"Erro ao ler regras.txt em '{RULES_FILE_PATH}': {e}")
    return "⚠ Respeite as regras do servidor e mantenha a convivência harmoniosa!"

class GreetingsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_db_connection(self):
        host = os.getenv("DB_HOST", "db")
        port = int(os.getenv("DB_PORT", "3306"))
        database = os.getenv("DB_NAME", "anima")
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")

        return mysql.connector.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
            use_pure=True,
            connection_timeout=5,
        )

    def _is_usuario_validado(self, discord_user_id: int) -> bool:
        """Verifica se o usuário do Discord está validado no banco de dados."""
        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT usuario_validado FROM usuario WHERE usuario_discord_id = %s", (str(discord_user_id),))
            row = cur.fetchone()
            cur.close()
            return bool(row and row.get("usuario_validado") == 1)
        except Exception as e:
            logger.error(f"Erro ao verificar usuario_validado em GreetingsCog: {e}")
            return False
        finally:
            if conn:
                try: conn.close()
                except: pass

    def get_help_text(self, author: discord.User | discord.Member):
        regras = get_regras_text()
        nome_exibicao = author.global_name or author.name
        is_validado = self._is_usuario_validado(author.id)

        header = (
            f"Olá, **{nome_exibicao}**! 👋\n\n"
            f"Seja muito bem-vindo(a)! Eu sou o assistente virtual do sistema de **Gamificação** do Prof. Henrique Poyatos.\n\n"
            f"📜 **REGRAS DO SERVIDO:**\n"
            f"```\n{regras}\n```\n\n"
        )

        if not is_validado:
            comandos_txt = (
                "📍 **Comandos disponíveis para você no momento:**\n\n"
                "🔹 `/identificar` - Inicia o processo de vincular seu usuário com o portal da disciplina (informe seu e-mail acadêmico ou pessoal).\n"
                "🔹 `/validar [seu_codigo]` - Conclui a identificação após receber o código de 6 dígitos no seu e-mail.\n\n"
                "💡 *Após a sua identificação ser concluída, os demais comandos (como `/pontos`, `/catalogo`, `/inscrever`) serão liberados automaticamente!*"
            )
        else:
            comandos_txt = (
                "🎉 **Comandos liberados no seu perfil:**\n\n"
                "🔹 `/identificar` - Revisa ou atualiza a vinculação do seu usuário.\n"
                "🔹 `/validar [seu_codigo]` - Valida o código recebido no e-mail.\n"
                "🔹 `/pontos` - Consulta detalhadamente seus pontos acumulados na Gamificação.\n"
                "🔹 `/catalogo` - Lista os cursos parceiros com inscrições abertas.\n"
                "🔹 `/inscrever [curso_id]` - Realiza sua pré-inscrição em um dos cursos parceiros.\n"
                "🔹 `/enviar_certificado [curso_id] [pdf]` - Envia seu certificado de conclusão para registro de horas.\n"
                "🔹 `/informar_badge [link_da_badge]` - Valida a conclusão de curso via badge do Credly.\n"
            )

        return f"{header}{comandos_txt}"

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Disparado quando um novo usuário entra no servidor."""
        logger.info(f"Novo membro entrou no servidor: {member} (ID: {member.id})")
        msg = self.get_help_text(member)
        try:
            await member.send(msg)
            logger.info(f"Mensagem de boas-vindas enviada via DM para o novo membro {member}.")
        except Exception as e:
            logger.warning(f"Não foi possível enviar DM de boas-vindas para novo membro {member}: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        is_dm = isinstance(message.channel, discord.DMChannel)
        
        if is_dm:
            content = message.content.lower().strip()
            
            if content.startswith("/identificar") or content.startswith("/validar") or content.startswith("/pontos") or content.startswith("/enviar_certificado") or content.startswith("/informar_badge"):
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
                
            if re.search(r'\b(o+i+|o+l+a+|o+l+á+|h+e+l+l+o+|h+a+l+o+)\b', content) or content.startswith("oi") or content.startswith("ola") or content.startswith("olá"):
                logger.info(f"Greetings triggered by {message.author} in DM: {message.content}")
                greeting_text = self.get_help_text(message.author)
                try:
                    await message.channel.send(greeting_text)
                except Exception as e:
                    logger.error(f"Erro ao enviar DM de saudação: {e}")

    @app_commands.command(name="help", description="Mostra a lista de comandos disponíveis e as regras do servidor.")
    async def cmd_help(self, interaction: discord.Interaction):
        await interaction.response.send_message(self.get_help_text(interaction.user), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(GreetingsCog(bot))

