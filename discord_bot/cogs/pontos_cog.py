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

    def query_usuario_e_pontos(self, user_id: int):
        conn = None
        try:
            conn = self._get_db_connection()
            if not conn.is_connected():
                raise RuntimeError("Conexão com o banco falhou.")
            
            cur = conn.cursor(dictionary=True)
            str_user_id = str(user_id)

            # 1. Buscar dados cadastrais do usuário
            sql_user = """
                SELECT usuario_id, usuario_nome, usuario_email, usuario_ra
                FROM usuario
                WHERE usuario_discord_id = %s
            """
            cur.execute(sql_user, (str_user_id,))
            user_data = cur.fetchone()

            if not user_data:
                cur.close()
                return None, 0, Decimal("0.00"), [], []

            usuario_id = user_data["usuario_id"]

            # 2. Buscar UCs matriculadas do usuário (anima_uc_usuario)
            ucs_matriculadas = []
            try:
                sql_ucs = """
                    SELECT DISTINCT uc.uc_nome
                    FROM anima_uc uc
                    INNER JOIN anima_uc_usuario ucu ON uc.uc_id = ucu.uc_id
                    WHERE ucu.usuario_id = %s
                """
                cur.execute(sql_ucs, (usuario_id,))
                ucs_matriculadas = [r["uc_nome"] for r in (cur.fetchall() or []) if r.get("uc_nome")]
            except Exception as e_uc:
                logger.error(f"Erro ao buscar UCs matriculadas: {e_uc}")

            # 3. Buscar total de pontuação (tabela pontuacao com fallback para ponto)
            try:
                sql_total = """
                    SELECT COUNT(*) AS qtde, COALESCE(SUM(pontuacao), 0) AS soma
                    FROM pontuacao 
                    WHERE usuario_id = %s
                """
                cur.execute(sql_total, (usuario_id,))
                row_total = cur.fetchone() or {"qtde": 0, "soma": Decimal("0.00")}
                total_linhas = int(row_total.get("qtde") or 0)
                soma_pontos = row_total.get("soma") or Decimal("0.00")

                # 4. Buscar lançamentos detalhados de pontuação
                sql_detalhe = """
                    SELECT uc.uc_nome as uc, pontuacao.pontuacao as pontos,
                           pontuacao.data_pontuacao as data, pontuacao.pontuacao_descricao as obs
                    FROM pontuacao 
                    LEFT JOIN anima_uc uc ON (pontuacao.uc_id = uc.uc_id)
                    WHERE pontuacao.usuario_id = %s
                    ORDER BY pontuacao.data_pontuacao DESC
                """
                cur.execute(sql_detalhe, (usuario_id,))
                linhas = cur.fetchall() or []
            except Exception:
                sql_total = """
                    SELECT COUNT(*) AS qtde, COALESCE(SUM(num_ponto), 0) AS soma
                    FROM ponto 
                    WHERE usuario_id = %s
                """
                cur.execute(sql_total, (usuario_id,))
                row_total = cur.fetchone() or {"qtde": 0, "soma": Decimal("0.00")}
                total_linhas = int(row_total.get("qtde") or 0)
                soma_pontos = row_total.get("soma") or Decimal("0.00")

                sql_detalhe = """
                    SELECT uc.uc_nome as uc, ponto.num_ponto as pontos,
                           ponto.dt_ponto as data, ponto.comentario_ponto as obs
                    FROM ponto 
                    LEFT JOIN anima_uc uc ON (ponto.uc_id = uc.uc_id)
                    WHERE ponto.usuario_id = %s
                    ORDER BY ponto.dt_ponto DESC
                """
                cur.execute(sql_detalhe, (usuario_id,))
                linhas = cur.fetchall() or []

            cur.close()
            return user_data, total_linhas, soma_pontos, linhas, ucs_matriculadas

        except Error as e:
            logger.error(f"[MySQL Cog] Error em query_usuario_e_pontos: {e}")
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
                sql_sync = """
                    UPDATE usuario 
                    SET usuario_discord_name = %s 
                    WHERE usuario_discord_id = %s
                """
                cur_sync.execute(sql_sync, (discord_nick, str(user_id)))
                conn_sync.commit()
                cur_sync.close()
                conn_sync.close()
            except Exception as e_sync:
                logger.error(f"Failed to sync user stats for {discord_nick}: {e_sync}")

            # Auditoria Logging
            auditoria_id_str = os.getenv("DISCORD_AUDITORIA_CHANNEL_ID")
            if auditoria_id_str:
                try:
                    auditoria_channel = self.bot.get_channel(int(auditoria_id_str))
                    if auditoria_channel:
                        await auditoria_channel.send(f"👤 **{discord_nick}** consultou seus `/pontos` com o PoyatosBot.")
                except Exception as e:
                    logger.error(f"Erro ao enviar log para auditoria em cmd_pontos: {e}")

            user_data, total_linhas, soma_pontos, linhas, ucs_matriculadas = self.query_usuario_e_pontos(user_id)

            if not user_data:
                msg = (
                    f"Não encontrei um cadastro vinculado ao seu Discord (**{discord_nick}**).\n"
                    "↳ Utilize o comando `/identificar` por mensagem privada comigo para vincular seu perfil de aluno."
                )
                await interaction.followup.send(msg, ephemeral=True)
                return

            import math
            soma_formatada = math.ceil(soma_pontos * 100) / 100

            ucs_totais = list(dict.fromkeys(ucs_matriculadas + [r.get('uc') for r in linhas if r.get('uc')]))
            uc_str = ", ".join(ucs_totais) if ucs_totais else "-"

            header = (
                f"**Resultado para:** `{discord_nick}`\n"
                f"**Nome:** {user_data.get('usuario_nome') or '-'}\n"
                f"**RA:** {user_data.get('usuario_ra') or '-'}\n"
                f"**E-mail:** {user_data.get('usuario_email') or '-'}\n"
                f"**UC:** {uc_str}\n"
                f"**Soma de pontos:** {str(soma_formatada).replace('.', ',')}\n\n"
            )

            if total_linhas == 0:
                body = "ℹ️ _Nenhum lançamento de ponto registrado até o momento._"
            else:
                tipo_emoji = {
                    "Presença": "📍",
                    "Participação": "💬",
                    "Kahoot": "🧠",
                    "Curso": "📚"
                }

                body = "\n".join(
                    f"📅 `{r['data']:%d/%m/%Y}`   🎯 `{str(r['pontos']).replace('.', ',')}`   {r['obs'] or '-'}"
                    if isinstance(r.get('data'), datetime) else
                    f"🎯 `{str(r['pontos']).replace('.', ',')}`   {r['obs'] or '-'}"
                    for r in linhas
                )

            msg = f"{header}{body}"

            if len(msg) > 1900:
                only_ids = "\n".join([f"- ID {idx+1} | pontos={Decimal(str(r.get('pontos') or 0)):.2f}" for idx, r in enumerate(linhas)])
                msg = f"{header}{only_ids}\n_(Resposta reduzida por tamanho.)_"

            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            logger.exception("Falha no comando /pontos")
            await interaction.followup.send(
                "Ocorreu um erro ao consultar seus pontos. Tente novamente em instantes ou avise o administrador.",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(PontosCog(bot))
