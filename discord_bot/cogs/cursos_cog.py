import os
import logging
import discord
from discord.ext import commands
from discord import app_commands
import mysql.connector
from typing import Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger("cogs.cursos")

class RedHatModal(discord.ui.Modal, title='Inscrição Red Hat Academy'):
    def __init__(self, cog, usuario_id: int, curso_id: int):
        super().__init__()
        self.cog = cog
        self.db_usuario_id = usuario_id
        self.db_curso_id = curso_id

        self.redhat_id_input = discord.ui.TextInput(
            label='Red Hat Network ID',
            style=discord.TextStyle.short,
            placeholder='Digite exatamente como cadastrado no portal Red Hat',
            required=True,
            max_length=60
        )
        self.add_item(self.redhat_id_input)

        self.redhat_email_input = discord.ui.TextInput(
            label='E-mail cadastrado na RedHat.com',
            style=discord.TextStyle.short,
            placeholder='O e-mail que você usou na RedHat.com',
            required=True,
            max_length=100
        )
        self.add_item(self.redhat_email_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        sucesso, msg = self.cog._realizar_matricula(
            self.db_usuario_id, 
            self.db_curso_id, 
            self.redhat_id_input.value, 
            self.redhat_email_input.value
        )
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

    def _realizar_matricula(self, usuario_id: int, curso_id: int, redhat_id: Optional[str] = None, redhat_email: Optional[str] = None, situacao: str = 'Pendente') -> Tuple[bool, str]:
        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            cur.execute("SELECT 1 FROM usuario_curso WHERE usuario_id = %s AND curso_id = %s", (usuario_id, curso_id))
            if cur.fetchone():
                return False, "⚠️ Você já possui uma inscrição ativa ou solicitada para este curso."

            dt_agora = discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            sql = """
                INSERT INTO usuario_curso 
                (usuario_id, curso_id, usuario_redhat_id, usuario_redhat_email, usuario_curso_dt_solicitacao, usuario_curso_situacao)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cur.execute(sql, (usuario_id, curso_id, redhat_id, redhat_email, dt_agora, situacao))
            conn.commit()
            
            if situacao == 'Inscrito':
                return True, "✅ Inscrição registrada com sucesso!"
            return True, "✅ Inscrição solicitada com sucesso! Aguarde a liberação do professor."
            
        except Exception as e:
            logger.error(f"Erro ao matricular aluno: {e}")
            if conn:
                conn.rollback()
            return False, "Ocorreu um erro interno ao salvar sua inscrição."
        finally:
            if conn and conn.is_connected():
                cur.close()
                conn.close()

    # ============================================================
    # COMANDO /catalogo
    # ============================================================

    @app_commands.command(
        name="catalogo",
        description="Lista todos os cursos parceiros disponíveis para inscrição com descrições detalhadas."
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_catalogo(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(dictionary=True)
            
            sql = """
                SELECT curso_id, curso_parceira, curso_nome, curso_descricao, curso_dt_inicio, curso_dt_fim, curso_carga_horaria, curso_idioma, curso_url_inscricao
                FROM curso
                WHERE curso_dt_inicio <= NOW() AND curso_dt_fim >= NOW()
                ORDER BY curso_parceira ASC, curso_nome ASC
            """
            cur.execute(sql)
            cursos = cur.fetchall()
            cur.close()

            if not cursos:
                await interaction.followup.send(
                    "📅 Nenhum curso possui matrículas abertas no momento. Fique atento aos novos comunicados!",
                    ephemeral=True
                )
                return

            embeds = []
            current_embed = discord.Embed(
                title="📚 Catálogo de Cursos Parceiros Disponíveis",
                description=(
                    "Confira abaixo os cursos com inscrições abertas!\n"
                    "Para se inscrever em qualquer um deles, use o comando `/inscrever` e selecione o curso no menu suspenso.\n"
                ),
                color=0x3b82f6
            )
            embeds.append(current_embed)

            for c in cursos:
                dt_ini = c['curso_dt_inicio'].strftime('%d/%m/%Y') if c['curso_dt_inicio'] else '-'
                dt_fim = c['curso_dt_fim'].strftime('%d/%m/%Y') if c['curso_dt_fim'] else '-'
                
                # Idioma (exibe quando disponível)
                idioma_map = {
                    'pt-br': '🇧🇷 Português do Brasil (pt-br)',
                    'en-us': '🇺🇸 Inglês (en-us)'
                }
                idioma_line = ""
                bandeira = ""
                if c.get('curso_idioma'):
                    idioma_key = str(c['curso_idioma']).lower().strip()
                    idioma_nome = idioma_map.get(idioma_key, c['curso_idioma'])
                    idioma_line = f"🌐 **Idioma:** `{idioma_nome}`\n"
                    bandeira = " 🇺🇸" if idioma_key == 'en-us' else (" 🇧🇷" if idioma_key == 'pt-br' else "")

                # Carga Horária (exibe quando disponível)
                ch_line = f"⏱️ **Carga Horária:** `{c['curso_carga_horaria']} horas`\n" if c.get('curso_carga_horaria') else ""
                ch_tag = f" ({c['curso_carga_horaria']}h)" if c.get('curso_carga_horaria') else ""

                # Descrição (truncada para respeitar o limite rigoroso de 1024 chars do Discord por campo)
                raw_desc = (c.get('curso_descricao') or '').strip()
                if len(raw_desc) > 350:
                    clean_desc = raw_desc[:347] + "..."
                else:
                    clean_desc = raw_desc
                
                desc_line = f"📝 {clean_desc}\n\n" if clean_desc else ""
                
                field_val = (
                    f"{desc_line}"
                    f"{idioma_line}"
                    f"{ch_line}"
                    f"📅 **Período de Inscrição:** `{dt_ini}` até `{dt_fim}`\n"
                )
                
                if c.get('curso_url_inscricao'):
                    field_val += f"🔗 [Link de Auto-Inscrição Direta]({c['curso_url_inscricao']})\n"
                else:
                    field_val += f"💡 *Use `/inscrever` e selecione este curso no menu.*\n"

                # Limita o campo a no máximo 1000 caracteres de segurança
                if len(field_val) > 1000:
                    field_val = field_val[:997] + "..."

                # Se o embed atual atingiu 6 campos ou 5000 chars, inicia novo embed
                if len(current_embed.fields) >= 6 or (len(current_embed) + len(field_val)) > 5000:
                    current_embed = discord.Embed(
                        title="📚 Catálogo de Cursos Parceiros (Continuação)",
                        color=0x3b82f6
                    )
                    embeds.append(current_embed)

                current_embed.add_field(
                    name=f"🎓 [{c['curso_parceira']}] {c['curso_nome']}{ch_tag}{bandeira}"[:256],
                    value=field_val,
                    inline=False
                )

            # Discord permite até 10 embeds por mensagem
            await interaction.followup.send(embeds=embeds[:10], ephemeral=True)
        except Exception as e:
            logger.error(f"Erro ao listar catálogo de cursos: {e}")
            await interaction.followup.send(
                "❌ Ocorreu um erro ao consultar o catálogo de cursos. Tente novamente mais tarde.",
                ephemeral=True
            )
        finally:
            if conn and conn.is_connected():
                conn.close()

    # ============================================================
    # COMANDO /inscrever COM AUTOCOMPLETE AMIGÁVEL
    # ============================================================

    @app_commands.command(
        name="inscrever",
        description="Realiza sua pré-inscrição em um curso parceiro selecionado no menu."
    )
    @app_commands.describe(curso_id="Selecione o curso desejado na lista suspensa")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_inscrever(self, interaction: discord.Interaction, curso_id: int):
        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(dictionary=True)
            
            # 1. Verifica vínculo do usuário
            cur.execute("SELECT usuario_id, usuario_nome FROM usuario WHERE usuario_discord_id = %s", (str(interaction.user.id),))
            usuario = cur.fetchone()
            
            if not usuario:
                await interaction.response.send_message(
                    "❌ Eu ainda não te conheço! Você precisa usar o comando `/identificar` e `/validar` o seu vínculo acadêmico primeiro.", 
                    ephemeral=True
                )
                return
                
            # 2. Verifica curso
            cur.execute("""
                SELECT curso_id, curso_parceira, curso_nome, curso_agente, curso_url_inscricao, curso_dt_inicio, curso_dt_fim
                FROM curso 
                WHERE curso_id = %s
            """, (curso_id,))
            curso = cur.fetchone()
            
            if not curso:
                await interaction.response.send_message(
                    "❌ Curso não encontrado. Use o comando `/catalogo` para conferir os cursos disponíveis.", 
                    ephemeral=True
                )
                return

            db_usuario_id = usuario['usuario_id']
            
            # 3. Verifica duplicidade de inscrição
            cur.execute("""
                SELECT 1 
                FROM usuario_curso uc
                JOIN curso c ON uc.curso_id = c.curso_id
                WHERE uc.usuario_id = %s AND uc.curso_id = %s
                AND NOW() <= c.curso_dt_fim
            """, (db_usuario_id, curso_id))
            
            if cur.fetchone():
                await interaction.response.send_message(
                    f"⚠️ Você já possui uma inscrição registrada para o curso **{curso['curso_nome']}**.",
                    ephemeral=True
                )
                return

            agente = curso.get('curso_agente')
            
            # 4. Inscrição que requer Red Hat ID
            if agente and agente.strip().lower() == 'cadastrar_rh124':
                modal = RedHatModal(self, db_usuario_id, curso_id)
                await interaction.response.send_modal(modal)
                return
            
            # 5. Cisco com auto-inscrição via URL
            elif curso.get('curso_parceira') == 'Cisco' and curso.get('curso_url_inscricao'):
                await interaction.response.defer(ephemeral=True)
                url = curso['curso_url_inscricao']
                sucesso, msg = self._realizar_matricula(db_usuario_id, curso_id, None, None, situacao='Inscrito')
                
                if sucesso:
                    msg = (
                        f"✅ **Inscrição no curso '{curso['curso_nome']}' registrada com sucesso!**\n\n"
                        f"Para este curso da Cisco, você deve completar sua inscrição diretamente através do link abaixo:\n"
                        f"🔗 {url}\n\n"
                        f"⚠️ **Instruções Importantes:**\n"
                        f"1. Crie seu perfil no **Cisco Networking Academy** e no **Credly** utilizando seu **NOME COMPLETO** ({usuario['usuario_nome']}).\n"
                        f"2. Isso é fundamental para a futura emissão e validação correta da sua certificação."
                    )
                await interaction.followup.send(msg, ephemeral=True)
                return
                
            else:
                # 6. Demais cursos (AWS, Google, etc.)
                await interaction.response.defer(ephemeral=True)
                sucesso, msg = self._realizar_matricula(db_usuario_id, curso_id, None, None)
                if sucesso:
                    msg = f"✅ **Solicitação enviada para '{curso['curso_nome']}'!** Aguarde a confirmação do professor."
                await interaction.followup.send(msg, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Erro em cmd_inscrever: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Ocorreu um erro ao processar sua inscrição.", ephemeral=True)
            else:
                await interaction.followup.send("❌ Ocorreu um erro interno ao processar sua inscrição.", ephemeral=True)
        finally:
            if conn and conn.is_connected():
                conn.close()

    @cmd_inscrever.autocomplete('curso_id')
    async def inscrever_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[int]]:
        """Apresenta a lista suspensa (combo) amigável de cursos parceiros disponíveis"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Filtra apenas cursos com inscrições vigentes
            query = """
                SELECT curso_id, curso_parceira, curso_nome, curso_carga_horaria, curso_idioma
                FROM curso 
                WHERE (curso_nome LIKE %s OR curso_parceira LIKE %s)
                AND curso_dt_inicio <= NOW() AND curso_dt_fim >= NOW()
                ORDER BY curso_parceira ASC, curso_nome ASC
                LIMIT 25
            """
            cursor.execute(query, (f"%{current}%", f"%{current}%"))
            rows = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            choices = []
            for row in rows:
                ch = f" ({row['curso_carga_horaria']}h)" if row.get('curso_carga_horaria') else ""
                flag = " 🇺🇸" if row.get('curso_idioma') == 'en-us' else " 🇧🇷"
                label = f"[{row['curso_parceira']}] {row['curso_nome']}{ch}{flag}"[:100]
                choices.append(app_commands.Choice(name=label, value=row['curso_id']))

            return choices
        except Exception as e:
            logger.error(f"Erro no autocomplete de inscrição: {e}")
            return []

    # ============================================================
    # NOTA: /enviar_certificado e /informar_badge INIBIDOS TEMPORARIAMENTE
    # ============================================================


async def setup(bot: commands.Bot):
    await bot.add_cog(CursosCog(bot))
    logger.info("Cog 'CursosCog' carregado com sucesso.")
