import os
import logging
import discord
from discord.ext import commands
from discord import app_commands
import mysql.connector

logger = logging.getLogger("cogs.cursos")

class CursosCog(commands.Cog):
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
            use_pure=True,
            connection_timeout=5,
        )

    @app_commands.command(
        name="catalogo",
        description="Lista todos os cursos parceiros disponíveis para inscrição no momento."
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_catalogo(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(dictionary=True)
            
            # Buscando cursos válidos (ativos na data atual)
            sql = """
                SELECT curso_id, curso_academia, curso_nome, curso_dt_inicio, curso_dt_fim, curso_agente
                FROM curso
                WHERE curso_dt_inicio <= NOW() AND curso_dt_fim >= NOW()
                ORDER BY curso_dt_inicio ASC
            """
            cur.execute(sql)
            cursos = cur.fetchall()
            cur.close()

            if not cursos:
                await interaction.followup.send(
                    "Nenhum curso possui matrículas abertas no momento. Fique de olho nas novidades!",
                    ephemeral=True
                )
                return

            mensagem = "**📚 Catálogo de Cursos Disponíveis:**\n\n"
            for c in cursos:
                dt_ini = c['curso_dt_inicio'].strftime('%d/%m/%Y') if c['curso_dt_inicio'] else '-'
                dt_fim = c['curso_dt_fim'].strftime('%d/%m/%Y') if c['curso_dt_fim'] else '-'
                
                mensagem += (
                    f"**{c['curso_academia']} - {c['curso_nome']}**\n"
                    f"📅 Período: `{dt_ini}` até `{dt_fim}`\n"
                    f"🔗 ID do Curso: `{c['curso_id']}`\n\n"
                )

            # Limite de mensagens longas no discord é 2000
            if len(mensagem) > 1900:
                mensagem = mensagem[:1900] + "\n... (Lista muito grande, procure a coordenação para a lista completa)."

            await interaction.followup.send(mensagem, ephemeral=True)
        except Exception as e:
            logger.error(f"Erro ao listar catálogo de cursos: {e}")
            await interaction.followup.send(
                "Ocorreu um erro ao consultar o catálogo de cursos. Tente novamente mais tarde.",
                ephemeral=True
            )
        finally:
            if conn and conn.is_connected():
                conn.close()

async def setup(bot: commands.Bot):
    await bot.add_cog(CursosCog(bot))
