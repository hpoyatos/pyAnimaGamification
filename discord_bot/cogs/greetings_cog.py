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
        if len(regras) > 900:
            regras = regras[:900] + "...\n_(regras resumidas por tamanho)_"

        nome_exibicao = author.global_name or author.name
        is_validado = self._is_usuario_validado(author.id)

        header = (
            f"Olá, **{nome_exibicao}**! 👋\n\n"
            f"Seja muito bem-vindo(a)! Eu sou o assistente virtual do sistema de **Gamificação** do Prof. Henrique Poyatos.\n\n"
            f"📜 **REGRAS DO SERVIDOR:**\n"
            f"```\n{regras}\n```\n\n"
        )

        if not is_validado:
            comandos_txt = (
                "📍 **Comandos disponíveis para você no momento:**\n\n"
                "🔹 `/identificar` - Inicia o processo de vincular seu usuário com o portal da disciplina.\n"
                "🔹 `/validar [seu_codigo]` - Conclui a identificação após receber o código no e-mail.\n"
                "🔹 `/gerenciar_temas_de_interesse` - Escolhe seus temas de tecnologia favoritos.\n\n"
                "💡 *Após a identificação, os demais comandos (como `/pontos`, `/inscrever_curso`) serão liberados!*"
            )
        else:
            comandos_txt = (
                "🎉 **Comandos liberados no seu perfil:**\n\n"
                "🔹 `/identificar` - Revisa ou atualiza a vinculação do seu usuário.\n"
                "🔹 `/validar [seu_codigo]` - Valida o código recebido no e-mail.\n"
                "🔹 `/pontos` - Consulta detalhadamente seus pontos acumulados na Gamificação.\n"
                "🔹 `/inscrever_curso` - Consulta os detalhes completos e realiza sua inscrição em cursos parceiros.\n"
                "🔹 `/gerenciar_temas_de_interesse` - Escolhe seus temas de tecnologia favoritos.\n"
            )

        full_msg = f"{header}{comandos_txt}"
        if len(full_msg) > 1900:
            full_msg = full_msg[:1850] + "\n\n_(Mensagem resumida por tamanho)_"

        return full_msg

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Disparado quando um novo usuário entra no servidor."""
        logger.info(f"🔔 Evento de novo membro capturado: {member} (ID: {member.id}) no servidor {member.guild.name}")
        
        # Log no canal de auditoria
        auditoria_id_str = os.getenv("DISCORD_AUDITORIA_CHANNEL_ID")
        if auditoria_id_str:
            try:
                auditoria_channel = self.bot.get_channel(int(auditoria_id_str))
                if auditoria_channel:
                    nome_exibicao = member.global_name or member.name
                    await auditoria_channel.send(
                        f"📥 **[NOVO MEMBRO]** {member.mention} (`{nome_exibicao}` / ID: `{member.id}`) acabou de entrar no servidor **{member.guild.name}**!"
                    )
            except Exception as audit_err:
                logger.error(f"Erro ao enviar log de auditoria no on_member_join: {audit_err}")

        msg = self.get_help_text(member)
        
        # Tenta enviar via DM
        dm_enviada = False
        try:
            await member.send(msg)
            dm_enviada = True
            logger.info(f"✅ Mensagem de boas-vindas enviada via DM para o novo membro {member}.")
        except Exception as e:
            logger.warning(f"⚠️ Não foi possível enviar DM para {member} (DM bloqueada ou fechada): {e}")

        # Envia a mensagem de boas-vindas no canal de Boas-vindas (DISCORD_BOASVINDAS_CHANNEL_ID)
        canal_id_str = os.getenv("DISCORD_BOASVINDAS_CHANNEL_ID", "1019994811840876635")
        if canal_id_str:
            try:
                canal = self.bot.get_channel(int(canal_id_str))
                if canal:
                    alerta = (
                        f"👋 Olá {member.mention}! Seja bem-vindo(a) ao servidor!\n"
                        f"Por favor, use meu comando `/identificar` por mensagem privada comigo para vincular seu perfil e liberar o acesso!"
                    )
                    await canal.send(alerta)
                    logger.info(f"✅ Mensagem de boas-vindas publicada no canal de boas-vindas ({canal_id_str}) para {member}.")
            except Exception as c_err:
                logger.error(f"Erro ao enviar mensagem no canal de boas-vindas: {c_err}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        is_dm = (message.guild is None) or isinstance(message.channel, discord.DMChannel)
        boas_vindas_channel_id = os.getenv("DISCORD_BOASVINDAS_CHANNEL_ID", "1019994811840876635")

        # 1. Mensagem enviada dentro do canal #boas-vindas
        if message.channel and str(message.channel.id) == str(boas_vindas_channel_id):
            # Tenta apagar a mensagem pública para manter o canal limpo
            try:
                await message.delete()
            except Exception:
                pass

            # Envia DM para o usuário explicando que comandos e identificação são no privado
            try:
                nome_usuario = message.author.global_name or message.author.display_name or message.author.name
                dm_text = (
                    f"👋 Olá, **{nome_usuario}**!\n\n"
                    f"Vi que você enviou uma mensagem ou tentou rodar um comando no canal de boas-vindas do servidor.\n\n"
                    f"🔒 **Para sua privacidade e segurança, a execução de comandos (como `/identificar`, `/validar`, etc.) é feita diretamente aqui no PRIVADO (DM) comigo!**\n\n"
                    f"👉 Por favor, envie o comando desejado (como `/identificar`) diretamente aqui nesta conversa particular! 🚀"
                )
                await message.author.send(dm_text)
                logger.info(f"DM de orientação enviada para {message.author} após mensagem no canal #boas-vindas.")
            except Exception as e_dm:
                logger.warning(f"Não foi possível enviar DM para {message.author}: {e_dm}")
            return
        
        # 2. Mensagens enviadas em DM privada
        if is_dm:
            content = message.content.lower().strip()
            
            if content.startswith("/identificar") or content.startswith("/validar") or content.startswith("/pontos") or content.startswith("/inscrever_curso") or content.startswith("/gerenciar_temas_de_interesse"):
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
                
            # Sempre que receber qualquer mensagem privada no DM, responde com as instruções/comandos
            logger.info(f"Greetings triggered by DM from {message.author}: {message.content}")
            greeting_text = self.get_help_text(message.author)
            try:
                await message.channel.send(greeting_text)
            except Exception as e:
                logger.error(f"Erro ao enviar DM de saudação: {e}")

    @app_commands.command(name="help", description="Mostra a lista de comandos disponíveis e as regras do servidor.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_help(self, interaction: discord.Interaction):
        logger.info(f"Comando /help invocado por {interaction.user}.")
        await interaction.response.defer(ephemeral=True)
        try:
            msg = self.get_help_text(interaction.user)
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            logger.exception(f"Erro ao processar /help: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao carregar a ajuda.", ephemeral=True)

    @app_commands.command(name="ajuda", description="Mostra a lista de comandos disponíveis e as regras do servidor.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_ajuda(self, interaction: discord.Interaction):
        logger.info(f"Comando /ajuda invocado por {interaction.user}.")
        await interaction.response.defer(ephemeral=True)
        try:
            msg = self.get_help_text(interaction.user)
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            logger.exception(f"Erro ao processar /ajuda: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao carregar a ajuda.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(GreetingsCog(bot))
