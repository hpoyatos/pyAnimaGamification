import os
import logging
from decimal import Decimal
import discord
from discord.ext import commands
from discord import app_commands
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("cogs.pontos")

def _resolve_discord_nickname(user: discord.User | discord.Member) -> str:
    return user.global_name or getattr(user, "display_name", None) or user.name

class PontosCog(commands.Cog):
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

    def query_pontos_por_discord_user_id(self, user_id: int):
        sql_total = """
            SELECT COUNT(*) AS qtde, COALESCE(SUM(ponto.num_ponto), 0) AS soma
            FROM ponto 
            INNER JOIN usuario ON (ponto.usuario_id = usuario.usuario_id)
            WHERE usuario.usuario_discord_id = %s
        """

        sql_detalhe = """
            SELECT uc.uc_nome as uc, usuario.usuario_nome as nome, usuario.usuario_email as email, 
            ponto.tipo_ponto as tipo, ponto.num_ponto as pontos, ponto.dt_ponto as data,
            ponto.comentario_ponto as obs
            FROM ponto 
            INNER JOIN usuario ON (ponto.usuario_id = usuario.usuario_id)
            INNER JOIN uc ON (ponto.uc_id = uc.uc_id)
            WHERE usuario.usuario_discord_id = %s
            ORDER BY ponto.dt_ponto DESC
        """

        conn = None
        try:
            conn = self._get_db_connection()
            if not conn.is_connected():
                raise RuntimeError("Conexão com o banco falhou.")
            
            cur = conn.cursor(dictionary=True)

            # Para manter paridade caso no bd o tipo discord_id seja string, convertemos para str
            str_user_id = str(user_id)

            cur.execute(sql_total, (str_user_id,))
            row_total = cur.fetchone() or {"qtde": 0, "soma": Decimal("0.00")}
            total_linhas = int(row_total.get("qtde") or 0)
            soma_pontos = row_total.get("soma") or Decimal("0.00")

            cur.execute(sql_detalhe, (str_user_id,))
            linhas = cur.fetchall() or []

            cur.close()
            return total_linhas, soma_pontos, linhas
            
        except Error as e:
            logger.error(f"[MySQL Cog] Error: {e}")
            raise
        finally:
            if conn:
                try: 
                    conn.close()
                except: 
                    pass


    @app_commands.command(
        name="pontos",
        description="Mostra seus pontos registrados na gamificação (use em mensagem privada comigo)."
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_pontos(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            user_id = interaction.user.id
            discord_nick = _resolve_discord_nickname(interaction.user)
            logger.info(f"Comando /pontos chamado por {discord_nick} ({user_id})")
            
            # Sync user's latest info on our database implicitly when they use the bot
            try:
                conn_sync = self._get_db_connection()
                cur_sync = conn_sync.cursor()
                tz_br = timezone(timedelta(hours=-3))
                now_str = datetime.now(tz_br).strftime('%Y-%m-%d %H:%M:%S')
                sql_sync = """
                    UPDATE usuario 
                    SET usuario_discord_name = %s, 
                        usuario_data_ultima_atualizacao = %s 
                    WHERE usuario_discord_id = %s
                """
                cur_sync.execute(sql_sync, (discord_nick, now_str, str(user_id)))
                conn_sync.commit()
                cur_sync.close()
                conn_sync.close()
            except Exception as e_sync:
                logger.error(f"Failed to sync user stats for {discord_nick}: {e_sync}")

            total_linhas, soma_pontos, linhas = self.query_pontos_por_discord_user_id(user_id)

            if total_linhas == 0:
                msg = (
                    f"Não encontrei lançamentos para **{discord_nick}** no Gamification.\n"
                    "↳ Verifique se o seu ID do Discord foi validado corretamente na UI ou se não há pontuações na sua conta."
                )
                await interaction.followup.send(msg, ephemeral=True)
                return

            import math
            soma_formatada = math.ceil(soma_pontos * 100) / 100

            header = (
                f"**Resultado para:** `{discord_nick}`\n"
                f"**Nome:** {linhas[0].get('nome') or ''}\n"
                f"**E-mail:** {linhas[0].get('email') or ''}\n"
                f"**UC:** {linhas[0].get('uc') or ''}\n"
                f"**Soma de pontos:** {str(soma_formatada).replace('.', ',')}\n\n"
            )

            tipo_emoji = {
                "Presença": "📍",
                "Participação": "💬",
                "Kahoot": "🧠",
                "Curso": "📚"
            }

            body = "\n".join(
                f"📅 `{r['data']:%d/%m/%Y}`   🎯 `{str(r['pontos']).replace('.', ',')}`   {tipo_emoji.get(r['tipo'], '🧩')} {r['obs'] or '-'}"
                for r in linhas
            )
            

            msg = f"{header}{body}"

            if len(msg) > 1900:
                only_ids = "\n".join([f"- ID {idx+1} | pontos={Decimal(str(r.get('pontos') or 0)):.2f}" for idx, r in enumerate(linhas)])
                msg = f"{header}{only_ids}\n_(Resposta reduzida por tamanho.)_"

            await interaction.followup.send(msg, ephemeral=True)
            
            # Auditoria Logging
            auditoria_id_str = os.getenv("DISCORD_AUDITORIA_CHANNEL_ID")
            if auditoria_id_str:
                try:
                    auditoria_channel = self.bot.get_channel(int(auditoria_id_str))
                    if auditoria_channel:
                        await auditoria_channel.send(f"👤 **{discord_nick}** consultou seus `/pontos` com o PoyatosBot.")
                except Exception as e:
                    logger.error(f"Erro ao enviar log para auditoria em cmd_pontos: {e}")

        except Exception as e:
            logger.exception("Falha no comando /pontos")
            await interaction.followup.send(
                "Ocorreu um erro ao consultar seus pontos. Tente novamente em instantes ou avise o administrador.",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(PontosCog(bot))
