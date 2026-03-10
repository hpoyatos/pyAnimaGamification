import os
import logging
import discord
from discord.ext import commands
from discord import app_commands
import mysql.connector

logger = logging.getLogger("cogs.cursos")

class RedHatModal(discord.ui.Modal, title='Inscrição Red Hat Academy'):
    redhat_id = discord.ui.TextInput(
        label='Red Hat Network ID',
        style=discord.TextStyle.short,
        placeholder='Digite exatamente como cadastrado no portal Red Hat',
        required=True,
        max_length=60
    )

    def __init__(self, cog, usuario_id: int, curso_id: int):
        super().__init__()
        self.cog = cog
        self.db_usuario_id = usuario_id
        self.db_curso_id = curso_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        sucesso, msg = self.cog._realizar_matricula(self.db_usuario_id, self.db_curso_id, self.redhat_id.value)
        await interaction.followup.send(msg, ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error(f"Erro no modal RedHat: {error}")
        await interaction.followup.send('Oops! Ocorreu um erro interno. Tente novamente.', ephemeral=True)


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

    def _realizar_matricula(self, usuario_id: int, curso_id: int, redhat_id: str = None):
        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            # Check if already enrolled
            cur.execute("SELECT 1 FROM usuario_curso WHERE usuario_id = %s AND curso_id = %s", (usuario_id, curso_id))
            if cur.fetchone():
                return False, "⚠️ Você já possui uma inscrição para este curso."

            dt_agora = discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            sql = """
                INSERT INTO usuario_curso 
                (usuario_id, curso_id, usuario_redhat_id, usuario_curso_dt_solicitacao, usuario_curso_situacao)
                VALUES (%s, %s, %s, %s, %s)
            """
            cur.execute(sql, (usuario_id, curso_id, redhat_id, dt_agora, 'Pendente'))
            conn.commit()
            
            return True, "✅ Inscrição solicitada com sucesso! Aguarde a confirmação dos professores."
            
        except Exception as e:
            logger.error(f"Erro ao matricular aluno: {e}")
            if conn:
                conn.rollback()
            return False, "Ocorreu um erro interno ao salvar sua inscrição."
        finally:
            if conn and conn.is_connected():
                cur.close()
                conn.close()

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

    @app_commands.command(
        name="inscrever",
        description="Realiza sua inscrição em um curso parceiro específico."
    )
    @app_commands.describe(curso_id="O ID numérico do curso (conforme exibido no comando /catalogo).")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_inscrever(self, interaction: discord.Interaction, curso_id: int):
        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(dictionary=True)
            
            # Check identifier
            cur.execute("SELECT usuario_id FROM usuario WHERE usuario_discord_id = %s", (str(interaction.user.id),))
            usuario = cur.fetchone()
            
            if not usuario:
                await interaction.response.send_message(
                    "❌ Eu ainda não te conheço! Você precisa usar o comando `/identificar` e `/validar` o seu vínculo com o sistema da disciplina primeiro.", 
                    ephemeral=True
                )
                return
                
            # Check course
            cur.execute("SELECT curso_id, curso_agente FROM curso WHERE curso_id = %s", (curso_id,))
            curso = cur.fetchone()
            
            if not curso:
                await interaction.response.send_message(
                    "❌ Curso não encontrado pelo ID informado. Use `/catalogo` para ver os IDs válidos.", 
                    ephemeral=True
                )
                return

            db_usuario_id = usuario['usuario_id']
            
            # Check duplicate 
            cur.execute("SELECT 1 FROM usuario_curso WHERE usuario_id = %s AND curso_id = %s", (db_usuario_id, curso_id))
            if cur.fetchone():
                await interaction.response.send_message("⚠️ Você já está inscrito neste curso.", ephemeral=True)
                return

            # Handle Agente prompt
            agente = curso['curso_agente']
            if agente and agente.strip().lower() == 'cadastrar_rh124':
                # Needs Modal to collect red hat id
                modal = RedHatModal(self, db_usuario_id, curso_id)
                await interaction.response.send_modal(modal)
                return
                
            else:
                # Does not need Red Hat ID, so proceed and defer
                await interaction.response.defer(ephemeral=True)
                sucesso, msg = self._realizar_matricula(db_usuario_id, curso_id, None)
                await interaction.followup.send(msg, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Erro em cmd_inscrever: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("Ocorreu um erro ao processar seu comando.", ephemeral=True)
            else:
                await interaction.followup.send("Ocorreu um erro interno ao processar.", ephemeral=True)
        finally:
            if conn and conn.is_connected():
                conn.close()

async def setup(bot: commands.Bot):
    await bot.add_cog(CursosCog(bot))
