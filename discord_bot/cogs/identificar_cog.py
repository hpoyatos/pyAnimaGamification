import logging
import os
import random
import string
from datetime import datetime, timedelta, timezone
import discord
from discord.ext import commands
from discord import app_commands
import mysql.connector

from utils.email_sender import send_validation_email

logger = logging.getLogger("cogs.identificar")

def generate_random_code(length=6):
    """Gera um código alfanumérico aleatório em uppercase."""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

class EmailModal(discord.ui.Modal, title='Identificação Gamificação'):
    
    email_input = discord.ui.TextInput(
        label='E-mail Cadastrado',
        placeholder='ex: ra@ulife.com.br',
        style=discord.TextStyle.short,
        required=True,
        min_length=5,
        max_length=60
    )

    def __init__(self, bot: commands.Bot, conn_factory):
        super().__init__()
        self.bot = bot
        self.conn_factory = conn_factory
        logger.info("Modal de identificação carregado.")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        email_digitado = self.email_input.value.strip().lower()
        
        conn = None
        try:
            conn = self.conn_factory()
            if not conn.is_connected():
                raise RuntimeError("Falha ao conectar no DB dentro do Modal.")
            
            cur = conn.cursor(dictionary=True)
            
            # Buscar usuário no DB
            sql_find = "SELECT usuario_id, usuario_nome, usuario_validado_code FROM usuario WHERE usuario_email = %s"
            cur.execute(sql_find, (email_digitado,))
            row = cur.fetchone()
            
            if not row:
                cur.close()
                await interaction.followup.send(f"⚠️ E-mail `{email_digitado}` não encontrado no sistema. Por favor, verifique a grafia ou fale com o professor.", ephemeral=True)
                return
            
            usuario_id = row['usuario_id']
            usuario_nome = row['usuario_nome']
            codigo_existente = row['usuario_validado_code']
            
            # Reutiliza ou cria o código
            if codigo_existente and len(codigo_existente) == 6:
                codigo_gerado = codigo_existente
                logger.info(f"Reutilizando código existente para {email_digitado}: {codigo_gerado}")
            else:
                codigo_gerado = generate_random_code()
                sql_update_code = "UPDATE usuario SET usuario_validado_code = %s WHERE usuario_id = %s"
                cur.execute(sql_update_code, (codigo_gerado, usuario_id))
                conn.commit()
            
            cur.close()
            
            # Enviar e-mail
            sucesso_email = send_validation_email(email_digitado, codigo_gerado, usuario_nome)
            
            if sucesso_email:
                msg = (
                    f"✅ E-mail enviado para `{email_digitado}` com sucesso!\n\n"
                    "Abra sua caixa de entrada (verifique também o spam) e pegue o código de 6 caracteres.\n"
                    "Depois volte aqui e digite o comando: `/validar [seu_codigo]`"
                )
            else:
                msg = "❌ Ocorreu um erro ao tentar enviar o e-mail pelo servidor. Por favor, tente novamente mais tarde ou contate o administrador."
                
            await interaction.followup.send(msg, ephemeral=True)
            
        except Exception as e:
            logger.exception("Erro processando modal de e-mail.")
            await interaction.followup.send("Ocorreu um erro interno. Tente novamente mais tarde.", ephemeral=True)
        finally:
            if conn:
                try: conn.close()
                except: pass


class IdentificarCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("Cog de identificação carregado.")

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

    @app_commands.command(
        name="identificar",
        description="Vincula seu usuário do Discord ao seu cadastro da disciplina."
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_identificar(self, interaction: discord.Interaction):
        logger.info("Comando /identificar invocado.")
        discord_user_id = str(interaction.user.id)
        
        # Checking if user is already validated
        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(dictionary=True)
            sql_check = "SELECT usuario_nome, usuario_validado FROM usuario WHERE usuario_discord_id = %s"
            cur.execute(sql_check, (discord_user_id,))
            user_row = cur.fetchone()
            cur.close()
            
            if user_row and user_row.get("usuario_validado") == 1:
                # User already validated
                msg = f"Ei, {user_row['usuario_nome']}, você já está identificado(a) comigo!"
                await interaction.response.send_message(msg, ephemeral=True)
                return
                
        except Exception as e:
            logger.exception("DB error checking already validated user in /identificar.")
            await interaction.response.send_message("Ops, erro ao acessar o banco de dados. Tente novamente.", ephemeral=True)
            return
        finally:
            if conn:
                try: conn.close()
                except: pass

        # Open Modal
        await interaction.response.send_modal(EmailModal(self.bot, self._get_db_connection))


    @app_commands.command(
        name="validar",
        description="Insira o código de validação que você recebeu por e-mail."
    )
    @app_commands.describe(codigo="Código de 6 caracteres enviado para o seu e-mail")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_validar(self, interaction: discord.Interaction, codigo: str):
        logger.info("Comando /validar invocado.")
        codigo = codigo.strip().upper()
        
        if len(codigo) != 6:
            await interaction.response.send_message("❌ Formato inválido. O código possui excatamente 6 caracteres alfanuméricos.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        
        discord_user_id = str(interaction.user.id)
        discord_name = interaction.user.global_name or interaction.user.name

        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(dictionary=True)
            
            sql_find = "SELECT usuario_id, usuario_nome FROM usuario WHERE usuario_validado_code = %s"
            cur.execute(sql_find, (codigo,))
            row = cur.fetchone()
            
            if not row:
                cur.close()
                await interaction.followup.send("❌ Código de validação inválido ou não encontrado.", ephemeral=True)
                return
                
            usuario_id = row['usuario_id']
            usuario_nome = row['usuario_nome']
            
            # Update user making them valid
            tz_br = timezone(timedelta(hours=-3))
            now_str = datetime.now(tz_br).strftime('%Y-%m-%d %H:%M:%S')
            sql_update = """
                UPDATE usuario 
                SET usuario_validado = 1, 
                    usuario_validado_data = %s,
                    usuario_discord_id = %s,
                    usuario_discord_name = %s,
                    usuario_data_ultima_atualizacao = %s
                WHERE usuario_id = %s
            """
            cur.execute(sql_update, (now_str, discord_user_id, discord_name, now_str, usuario_id))
            conn.commit()
            cur.close()
            
            # Aplica o Cargo (Role) no Discord
            role_id_str = os.getenv("DISCORD_VALIDATED_ROLE_ID")
            if role_id_str:
                try:
                    role_id = int(role_id_str)
                    # Caso o comando seja rodado em um Servidor (Guild)
                    if interaction.guild:
                        role = interaction.guild.get_role(role_id)
                        if role and isinstance(interaction.user, discord.Member):
                            await interaction.user.add_roles(role, reason="Validação Gamificação")
                    else:
                        # Caso o comando seja rodado na DM, procuramos o usuário nos servidores em que o bot está
                        for guild in self.bot.guilds:
                            role = guild.get_role(role_id)
                            if role:
                                try:
                                    member = await guild.fetch_member(interaction.user.id)
                                    if member:
                                        await member.add_roles(role, reason="Validação Gamificação via DM")
                                        logger.info(f"Role {role_id} concedida a {discord_name} no server {guild.name}")
                                except discord.NotFound:
                                    # O usuário não está neste servidor especificamente
                                    pass
                                except Exception as inner_e:
                                    logger.error(f"Erro ao fetch_member ou add_roles em {guild.name}: {inner_e}")
                except Exception as e:
                    logger.error(f"Erro global ao atribuir cargo de validação para {discord_name}: {e}")
            
            await interaction.followup.send(
                f"🎉 Parabéns, **{usuario_nome}**!\n"
                f"Sua conta foi vinculada com sucesso. Acesso liberado aos comandos como `/pontos`.",
                ephemeral=True
            )
            
            # Audit logging
            auditoria_id_str = os.getenv("DISCORD_AUDITORIA_CHANNEL_ID")
            if auditoria_id_str:
                try:
                    auditoria_channel = self.bot.get_channel(int(auditoria_id_str))
                    if auditoria_channel:
                        await auditoria_channel.send(f"🔐 **{discord_name}** validou sua conta como o usuário `{usuario_nome}`!")
                except Exception as e:
                    logger.error(f"Erro ao enviar log de auditoria em cmd_validar: {e}")
                    
        except Exception as e:
            logger.exception("Erro durante comando '/validar'.")
            if conn: conn.rollback()
            await interaction.followup.send("Erro interno ao tentar validar o código. Contate o administrador.", ephemeral=True)
        finally:
            if conn:
                try: conn.close()
                except: pass

    @app_commands.command(
        name="add_user",
        description="[Admin] Cadastra e valida um usuário diretamente no sistema."
    )
    @app_commands.describe(
        usuario_discord="Membro do Discord a ser cadastrado",
        nome="Nome completo do usuário",
        email="E-mail do usuário",
        ra="RA do usuário (opcional)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.allowed_installs(guilds=True)
    @app_commands.allowed_contexts(guilds=True)
    async def cmd_add_user(
        self, 
        interaction: discord.Interaction, 
        usuario_discord: discord.User, 
        nome: str, 
        email: str, 
        ra: str = None
    ):
        logger.info(f"Comando /add_user invocado por {interaction.user} (ID: {interaction.user.id}).")
        await interaction.response.defer(ephemeral=True)

        discord_user_id = str(usuario_discord.id)
        discord_name = usuario_discord.global_name or usuario_discord.name
        nome = nome.strip()
        email = email.strip().lower()
        ra = ra.strip() if ra else None

        tz_br = timezone(timedelta(hours=-3))
        now_str = datetime.now(tz_br).strftime('%Y-%m-%d %H:%M:%S')

        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(dictionary=True)

            # Verifica se já existe por e-mail ou discord_id
            sql_check = "SELECT usuario_id, usuario_email, usuario_discord_id FROM usuario WHERE usuario_email = %s OR usuario_discord_id = %s"
            cur.execute(sql_check, (email, discord_user_id))
            existente = cur.fetchone()

            if existente:
                if existente.get('usuario_email') == email:
                    await interaction.followup.send(f"⚠️ Já existe um usuário cadastrado com o e-mail `{email}` (ID: {existente['usuario_id']}).", ephemeral=True)
                else:
                    await interaction.followup.send(f"⚠️ Este usuário do Discord ({usuario_discord.mention}) já está vinculado ao e-mail `{existente['usuario_email']}` (ID: {existente['usuario_id']}).", ephemeral=True)
                cur.close()
                return

            # Insere o novo usuário validado
            sql_insert = """
                INSERT INTO usuario 
                (usuario_discord_id, usuario_nome, usuario_email, usuario_ra, usuario_discord_name, usuario_validado, usuario_validado_data)
                VALUES (%s, %s, %s, %s, %s, 1, %s)
            """
            cur.execute(sql_insert, (discord_user_id, nome, email, ra, discord_name, now_str))
            conn.commit()
            novo_id = cur.lastrowid
            cur.close()

            # Atribui o Cargo (Role) DISCORD_VALIDATED_ROLE_ID ao usuário no Discord
            role_concedida = False
            role_id_str = os.getenv("DISCORD_VALIDATED_ROLE_ID")
            if role_id_str:
                try:
                    role_id = int(role_id_str)
                    target_member = None
                    if interaction.guild:
                        target_member = interaction.guild.get_member(usuario_discord.id)
                        if not target_member:
                            try:
                                target_member = await interaction.guild.fetch_member(usuario_discord.id)
                            except Exception:
                                pass

                    if target_member:
                        role = interaction.guild.get_role(role_id)
                        if role:
                            await target_member.add_roles(role, reason="Cadastro manual de usuário via /add_user")
                            role_concedida = True
                    else:
                        # Tenta encontrar o membro em outras guilds conhecidas pelo bot
                        for guild in self.bot.guilds:
                            role = guild.get_role(role_id)
                            if role:
                                try:
                                    member = await guild.fetch_member(usuario_discord.id)
                                    if member:
                                        await member.add_roles(role, reason="Cadastro manual de usuário via /add_user")
                                        role_concedida = True
                                        break
                                except Exception:
                                    pass
                except Exception as role_err:
                    logger.error(f"Erro ao atribuir cargo /add_user para {discord_name}: {role_err}")

            role_status_msg = " Cargo de validação concedido com sucesso!" if role_concedida else " ⚠️ Não foi possível atribuir o cargo (verifique se o usuário está no servidor e a role configurada)."

            msg_sucesso = (
                f"✅ **Usuário cadastrado e validado com sucesso!** (ID: `{novo_id}`)\n\n"
                f"👤 **Nome:** {nome}\n"
                f"📧 **E-mail:** `{email}`\n"
                f"🆔 **RA:** `{ra or 'N/A'}`\n"
                f"🎮 **Discord:** {usuario_discord.mention} (`{discord_name}` / ID: `{discord_user_id}`)\n"
                f"📅 **Data Validação:** {now_str}\n"
                f"{role_status_msg}"
            )
            await interaction.followup.send(msg_sucesso, ephemeral=True)

            # Audit logging
            auditoria_id_str = os.getenv("DISCORD_AUDITORIA_CHANNEL_ID")
            if auditoria_id_str:
                try:
                    auditoria_channel = self.bot.get_channel(int(auditoria_id_str))
                    if auditoria_channel:
                        await auditoria_channel.send(
                            f"🛠️ **[ADMIN]** {interaction.user.mention} cadastrou e validou o usuário **{nome}** ({usuario_discord.mention})!"
                        )
                except Exception as audit_err:
                    logger.error(f"Erro ao enviar log de auditoria em cmd_add_user: {audit_err}")

        except Exception as e:
            logger.exception("Erro durante execução do comando '/add_user'.")
            if conn: conn.rollback()
            await interaction.followup.send("❌ Ocorreu um erro interno ao cadastrar o usuário.", ephemeral=True)
        finally:
            if conn:
                try: conn.close()
                except: pass

    @cmd_add_user.error
    async def cmd_add_user_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ **Acesso Negado**: Este comando é restrito a administradores do servidor.",
                ephemeral=True
            )
        else:
            logger.error(f"Erro no handler do comando /add_user: {error}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Ocorreu um erro ao executar este comando.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(IdentificarCog(bot))
