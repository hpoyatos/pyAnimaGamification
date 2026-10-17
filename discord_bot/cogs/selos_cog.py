import os
import logging
from datetime import datetime
import discord
from discord.ext import commands
from discord import app_commands
import mysql.connector

logger = logging.getLogger("cogs.selos")

def _resolve_discord_nickname(user: discord.User | discord.Member) -> str:
    return user.global_name or getattr(user, "display_name", None) or user.name

class SelosCog(commands.Cog):
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

    def query_usuario_selos(self, discord_id: int):
        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(dictionary=True)

            # Buscar usuário
            sql_user = """
                SELECT usuario_id, usuario_nome, usuario_ra, usuario_email
                FROM usuario
                WHERE usuario_discord_id = %s
            """
            cur.execute(sql_user, (str(discord_id),))
            user_data = cur.fetchone()

            if not user_data:
                cur.close()
                return None, []

            usuario_id = user_data["usuario_id"]

            # Buscar selos conquistados
            sql_selos = """
                SELECT 
                    s.selo_id,
                    s.selo_nome,
                    s.selo_parceiro,
                    aus.usuario_selo_data
                FROM anima_usuario_selo aus
                INNER JOIN anima_selo s ON s.selo_id = aus.selo_id
                WHERE aus.usuario_id = %s
                ORDER BY aus.usuario_selo_data ASC, s.selo_nome ASC
            """
            cur.execute(sql_selos, (usuario_id,))
            selos = cur.fetchall() or []

            cur.close()
            return user_data, selos
        except Exception as e:
            logger.exception(f"Erro ao buscar selos do usuário {discord_id}: {e}")
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

    def query_ranking_selos(self, limit: int = 10):
        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(dictionary=True)

            sql_ranking = """
                SELECT 
                    u.usuario_id,
                    u.usuario_nome,
                    u.usuario_discord_id,
                    u.usuario_discord_name,
                    COUNT(aus.selo_id) AS total_selos,
                    MIN(aus.usuario_selo_data) AS primeiro_selo,
                    GROUP_CONCAT(s.selo_nome ORDER BY aus.usuario_selo_data ASC SEPARATOR '||') AS selos_nomes
                FROM anima_usuario_selo aus
                INNER JOIN usuario u ON u.usuario_id = aus.usuario_id
                INNER JOIN anima_selo s ON s.selo_id = aus.selo_id
                GROUP BY u.usuario_id, u.usuario_nome, u.usuario_discord_id, u.usuario_discord_name
                ORDER BY total_selos DESC, primeiro_selo ASC
                LIMIT %s
            """
            cur.execute(sql_ranking, (limit,))
            ranking = cur.fetchall() or []
            cur.close()
            return ranking
        except Exception as e:
            logger.exception(f"Erro ao buscar ranking de selos: {e}")
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

    @app_commands.command(
        name="meus_selos",
        description="Consulta a lista de selos e badges conquistados por você"
    )
    async def meus_selos(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        user_id = interaction.user.id
        discord_nick = _resolve_discord_nickname(interaction.user)

        # Registro em canal de auditoria se configurado
        auditoria_id_str = os.getenv("DISCORD_AUDITORIA_CHANNEL_ID")
        if auditoria_id_str:
            try:
                auditoria_channel = self.bot.get_channel(int(auditoria_id_str))
                if auditoria_channel:
                    await auditoria_channel.send(f"🎖️ **{discord_nick}** consultou `/meus_selos`.")
            except Exception as e:
                logger.error(f"Erro ao enviar log para auditoria em meus_selos: {e}")

        try:
            user_data, selos = self.query_usuario_selos(user_id)

            if not user_data:
                await interaction.followup.send(
                    f"⚠️ Não encontrei um cadastro vinculado ao seu Discord (**{discord_nick}**).\n"
                    "↳ Utilize o comando `/identificar` para vincular seu perfil acadêmico.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="🎖️ Seus Selos e Badges Conquistados",
                color=0x4285F4,
                timestamp=discord.utils.utcnow()
            )
            embed.set_author(name=discord_nick, icon_url=interaction.user.display_avatar.url)
            embed.add_field(name="👤 Aluno(a)", value=user_data.get("usuario_nome") or "-", inline=True)
            embed.add_field(name="🆔 RA", value=user_data.get("usuario_ra") or "-", inline=True)
            embed.add_field(name="🏆 Total de Selos", value=str(len(selos)), inline=True)

            if not selos:
                embed.description = "ℹ️ _Você ainda não possui nenhum selo registrado._"
            else:
                linhas = []
                for s in selos:
                    data_str = ""
                    if isinstance(s.get("usuario_selo_data"), datetime):
                        data_str = f" • Conquistado em `{s['usuario_selo_data']:%d/%m/%Y}`"
                    parceiro = f"**[{s['selo_parceiro']}]**" if s.get("selo_parceiro") else ""
                    linhas.append(f"🏅 {parceiro} {s['selo_nome']}{data_str}")

                texto_selos = "\n".join(linhas)
                if len(texto_selos) > 4000:
                    texto_selos = texto_selos[:3950] + "\n\n_... (lista truncada por limite do Discord)_"

                embed.description = texto_selos

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.exception(f"Erro ao processar /meus_selos: {e}")
            await interaction.followup.send(
                "❌ Ocorreu um erro ao consultar seus selos. Tente novamente mais tarde.",
                ephemeral=True
            )

    @app_commands.command(
        name="ranking_selos",
        description="Exibe o Top 10 do ranking geral de selos e badges"
    )
    async def ranking_selos(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)

        try:
            ranking = self.query_ranking_selos(limit=10)

            if not ranking:
                await interaction.followup.send(
                    "ℹ️ Ainda não há nenhum selo registrado no ranking.",
                    ephemeral=False
                )
                return

            embed = discord.Embed(
                title="🏆 Ranking Geral de Selos e Conquistas (Top 10)",
                description="Critério: Quantidade de selos conquistados. Desempate: quem conquistou o primeiro selo mais cedo.\n",
                color=0xFFD700,
                timestamp=discord.utils.utcnow()
            )

            medalhas = {1: "🥇", 2: "🥈", 3: "🥉"}

            for pos, r in enumerate(ranking, 1):
                icone = medalhas.get(pos, f"`#{pos:02d}`")
                
                # Identificação Discord: menção se tiver ID, senão nome registrado
                discord_str = f"<@{r['usuario_discord_id']}>" if r.get("usuario_discord_id") else (r.get("usuario_discord_name") or "Desconhecido")
                nome_real = r.get("usuario_nome") or "Aluno"
                total = r.get("total_selos") or 0

                primeiro_data_str = ""
                if isinstance(r.get("primeiro_selo"), datetime):
                    primeiro_data_str = f" • 1º selo em `{r['primeiro_selo']:%d/%m/%Y}`"

                selos_lista = (r.get("selos_nomes") or "").split("||") if r.get("selos_nomes") else []
                # Detalhamento dos selos
                selos_formatados = "\n".join([f"  └ 🔹 {s}" for s in selos_lista])

                campo_titulo = f"{icone} {nome_real} ({discord_str}) — {total} selo{'s' if total != 1 else ''}"
                campo_valor = f"_{primeiro_data_str.strip(' • ')}_\n{selos_formatados}" if primeiro_data_str else selos_formatados

                if len(campo_valor) > 1024:
                    campo_valor = campo_valor[:1000] + "\n  └ _... e mais selos_"

                embed.add_field(
                    name=campo_titulo,
                    value=campo_valor or "Nenhum detalhe",
                    inline=False
                )

            embed.set_footer(text="pyAnimaGamification • Selos & Certificações")
            await interaction.followup.send(embed=embed, ephemeral=False)

        except Exception as e:
            logger.exception(f"Erro ao processar /ranking_selos: {e}")
            await interaction.followup.send(
                "❌ Ocorreu um erro ao carregar o ranking de selos. Tente novamente mais tarde.",
                ephemeral=False
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(SelosCog(bot))
