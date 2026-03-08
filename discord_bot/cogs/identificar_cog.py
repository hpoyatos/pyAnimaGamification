import logging
import os
import random
import string
from datetime import datetime
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
    async def cmd_identificar(self, interaction: discord.Interaction):
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
                msg = f"Ei, {user_row['usuario_nome']}, você já está identificado comigo!"
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
    async def cmd_validar(self, interaction: discord.Interaction, codigo: str):
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
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            sql_update = """
                UPDATE usuario 
                SET usuario_validado = 1, 
                    usuario_validado_data = %s,
                    usuario_discord_id = %s,
                    usuario_discord_name = %s
                WHERE usuario_id = %s
            """
            cur.execute(sql_update, (now_str, discord_user_id, discord_name, usuario_id))
            conn.commit()
            cur.close()
            
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

async def setup(bot: commands.Bot):
    await bot.add_cog(IdentificarCog(bot))
