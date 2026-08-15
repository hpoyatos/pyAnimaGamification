import os
import logging
import discord
from discord.ext import commands
from discord import app_commands
import mysql.connector
from typing import Optional, Tuple

logger = logging.getLogger("cogs.cursos")

# ============================================================
# MODAL RED HAT (Quando o curso exige Red Hat Network ID)
# ============================================================

class RedHatModal(discord.ui.Modal, title='Inscrição Red Hat Academy'):
    def __init__(self, cog, usuario_id: int, curso_id: int, chosen_email: str):
        super().__init__()
        self.cog = cog
        self.db_usuario_id = usuario_id
        self.db_curso_id = curso_id
        self.chosen_email = chosen_email

        self.redhat_id_input = discord.ui.TextInput(
            label='Red Hat Network ID',
            style=discord.TextStyle.short,
            placeholder='Digite exatamente seu ID do portal Red Hat',
            required=True,
            max_length=60
        )
        self.add_item(self.redhat_id_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        sucesso, msg = self.cog._realizar_matricula(
            self.db_usuario_id, 
            self.db_curso_id, 
            self.redhat_id_input.value, 
            self.chosen_email
        )
        await interaction.followup.send(msg, ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error(f"Erro no modal RedHat: {error}")
        await interaction.followup.send('❌ Ocorreu um erro interno. Tente novamente.', ephemeral=True)


# ============================================================
# VIEW: SELEÇÃO DE E-MAIL (Quando o usuário tem 2 e-mails cadastrados)
# ============================================================

class EscolhaEmailView(discord.ui.View):
    def __init__(self, cog, usuario: dict, curso: dict, emails: list):
        super().__init__(timeout=120)
        self.cog = cog
        self.usuario = usuario
        self.curso = curso

        options = []
        for tipo, email in emails:
            emoji = "🏫" if tipo == "Institucional" else "📬"
            options.append(
                discord.SelectOption(
                    label=f"E-mail {tipo}",
                    description=email[:50],
                    value=email,
                    emoji=emoji
                )
            )

        self.select_email = discord.ui.Select(
            placeholder="Selecione o e-mail para registrar a inscrição...",
            min_values=1,
            max_values=1,
            options=options
        )
        self.select_email.callback = self.select_callback
        self.add_item(self.select_email)

    async def select_callback(self, interaction: discord.Interaction):
        chosen_email = self.select_email.values[0]
        await self.cog._processar_finalizacao_inscricao(interaction, self.usuario, self.curso, chosen_email)


# ============================================================
# VIEW: DECISÃO DO PRÉ-REQUISITO (Quer fazer o pré-requisito primeiro?)
# ============================================================

class PrerequisitoDecisaoView(discord.ui.View):
    def __init__(self, cog, usuario: dict, curso_original: dict, curso_prereq: dict):
        super().__init__(timeout=120)
        self.cog = cog
        self.usuario = usuario
        self.curso_original = curso_original
        self.curso_prereq = curso_prereq

    @discord.ui.button(label="Sim, Inscrever no Pré-requisito", style=discord.ButtonStyle.primary, emoji="🎓")
    async def btn_trocar_para_prereq(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Troca o curso a ser inscrito para o pré-requisito e segue o fluxo
        await self.cog._iniciar_fluxo_email_ou_matricula(interaction, self.usuario, self.curso_prereq)

    @discord.ui.button(label="Não, Continuar no Curso Atual", style=discord.ButtonStyle.secondary, emoji="➡️")
    async def btn_manter_original(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Mantém o curso original e segue o fluxo
        await self.cog._iniciar_fluxo_email_ou_matricula(interaction, self.usuario, self.curso_original)


# ============================================================
# VIEW: CONFIRMAÇÃO SE JÁ CONCLUIU O PRÉ-REQUISITO
# ============================================================

class PrerequisitoConfirmacaoView(discord.ui.View):
    def __init__(self, cog, usuario: dict, curso_original: dict, curso_prereq: dict):
        super().__init__(timeout=120)
        self.cog = cog
        self.usuario = usuario
        self.curso_original = curso_original
        self.curso_prereq = curso_prereq

    @discord.ui.button(label="Sim, Já Concluí", style=discord.ButtonStyle.success, emoji="✅")
    async def btn_ja_concluiu(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Aluno já concluiu o pré-requisito: segue adiante no fluxo para o curso original
        await self.cog._iniciar_fluxo_email_ou_matricula(interaction, self.usuario, self.curso_original)

    @discord.ui.button(label="Não Concluí", style=discord.ButtonStyle.danger, emoji="❌")
    async def btn_nao_concluiu(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Aluno não concluiu: sugere fazer o pré-requisito primeiro
        embed_sugestao = discord.Embed(
            title="💡 Recomendação Importante de Aprendizado",
            description=(
                f"Você ainda não concluiu o pré-requisito **[{self.curso_prereq['curso_parceira']}] {self.curso_prereq['curso_nome']}**.\n\n"
                f"**Quer fazer esse curso pré-requisito primeiro?** É extremamente recomendado para garantir o melhor aproveitamento do conteúdo!"
            ),
            color=0xf59e0b
        )
        view_decisao = PrerequisitoDecisaoView(self.cog, self.usuario, self.curso_original, self.curso_prereq)
        await interaction.response.edit_message(embed=embed_sugestao, view=view_decisao)


# ============================================================
# VIEW: CONFIRMAÇÃO DE INSCRIÇÃO INICIAL (Sim / Não)
# ============================================================

class ConfirmacaoInscricaoView(discord.ui.View):
    def __init__(self, cog, usuario: dict, curso: dict):
        super().__init__(timeout=120)
        self.cog = cog
        self.usuario = usuario
        self.curso = curso

    @discord.ui.button(label="Sim, Quero Me Inscrever", style=discord.ButtonStyle.success, emoji="✅")
    async def btn_confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Verifica se o curso tem pré-requisito cadastrado
        prereq_id = self.curso.get('curso_prerequisito_id')
        if prereq_id:
            prereq = self.cog._fetch_curso_by_id(prereq_id)
            if prereq:
                # Monta card com os dados do pré-requisito
                dt_ini_p = prereq['curso_dt_inicio'].strftime('%d/%m/%Y') if prereq['curso_dt_inicio'] else '-'
                dt_fim_p = prereq['curso_dt_fim'].strftime('%d/%m/%Y') if prereq['curso_dt_fim'] else '-'
                ch_p = f"{prereq['curso_carga_horaria']} horas" if prereq.get('curso_carga_horaria') else "Não informada"
                idioma_p = "🇺🇸 Inglês (en-us)" if prereq.get('curso_idioma') == 'en-us' else "🇧🇷 Português do Brasil (pt-br)"

                embed_prereq = discord.Embed(
                    title="⚠️ Pré-requisito Obrigatório / Recomendado",
                    description=(
                        f"O curso escolhido (**{self.curso['curso_nome']}**) possui um pré-requisito cadastrado:\n\n"
                        f"🎓 **[{prereq['curso_parceira']}] {prereq['curso_nome']}**\n"
                        f"📝 {prereq.get('curso_descricao') or 'Sem descrição adicional.'}\n\n"
                        f"🌐 **Idioma:** `{idioma_p}` | ⏱️ **Carga Horária:** `{ch_p}`\n"
                        f"📅 **Vigência:** `{dt_ini_p}` até `{dt_fim_p}`\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"❓ **Você já concluiu esse curso antes?**"
                    ),
                    color=0xf59e0b
                )
                view_prereq = PrerequisitoConfirmacaoView(self.cog, self.usuario, self.curso, prereq)
                await interaction.response.edit_message(embed=embed_prereq, view=view_prereq)
                return

        # Sem pré-requisito: segue direto para fluxo de e-mails / matrícula
        await self.cog._iniciar_fluxo_email_ou_matricula(interaction, self.usuario, self.curso)

    @discord.ui.button(label="Não, Cancelar", style=discord.ButtonStyle.secondary, emoji="❌")
    async def btn_cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed_cancel = discord.Embed(
            title="🚫 Inscrição Cancelada",
            description=f"A solicitação para o curso **{self.curso['curso_nome']}** foi cancelada. Fique à vontade para consultar outros cursos quando quiser!",
            color=0x64748b
        )
        await interaction.response.edit_message(embed=embed_cancel, view=None)


# ============================================================
# COG: CURSOS PARCEIROS
# ============================================================

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

    def _fetch_curso_by_id(self, curso_id: int) -> Optional[dict]:
        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(dictionary=True)
            sql = """
                SELECT curso_id, curso_parceira, curso_nome, curso_descricao, curso_agente,
                       curso_url_inscricao, curso_dt_inicio, curso_dt_fim, curso_carga_horaria, 
                       curso_idioma, curso_prerequisito_id
                FROM curso 
                WHERE curso_id = %s
            """
            cur.execute(sql, (curso_id,))
            return cur.fetchone()
        except Exception as e:
            logger.error(f"Erro ao buscar curso #{curso_id}: {e}")
            return None
        finally:
            if conn and conn.is_connected():
                conn.close()

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
            
            email_info = f" ({redhat_email})" if redhat_email else ""
            if situacao == 'Inscrito':
                return True, f"✅ **Inscrição registrada com sucesso!**{email_info}"
            return True, f"✅ **Inscrição solicitada com sucesso!**{email_info} Aguarde a liberação do professor."
            
        except Exception as e:
            logger.error(f"Erro ao matricular aluno: {e}")
            if conn:
                conn.rollback()
            return False, "❌ Ocorreu um erro interno ao salvar sua inscrição."
        finally:
            if conn and conn.is_connected():
                cur.close()
                conn.close()

    async def _iniciar_fluxo_email_ou_matricula(self, interaction: discord.Interaction, usuario: dict, curso: dict):
        """Verifica os e-mails disponíveis do aluno para registrar a inscrição."""
        email_inst = (usuario.get('usuario_email') or '').strip()
        email_pess = (usuario.get('usuario_email_pessoal') or '').strip()

        tem_dois_emails = bool(email_inst and email_pess and email_inst.lower() != email_pess.lower())

        if tem_dois_emails:
            # 2 e-mails: pergunta para qual deles deseja enviar a inscrição
            emails_disponiveis = [
                ("Institucional", email_inst),
                ("Pessoal", email_pess)
            ]
            embed_email = discord.Embed(
                title="📧 Escolha do E-mail de Inscrição",
                description=(
                    f"Você possui mais de um e-mail cadastrado no sistema.\n\n"
                    f"**Para qual dos e-mails devemos registrar sua inscrição em '{curso['curso_nome']}'?**\n"
                    f"Selecione uma das opções abaixo no menu suspenso:"
                ),
                color=0x3b82f6
            )
            view_email = EscolhaEmailView(self, usuario, curso, emails_disponiveis)
            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=embed_email, view=view_email)
            else:
                await interaction.edit_original_response(embed=embed_email, view=view_email)
        else:
            # Apenas 1 e-mail: segue direto
            chosen_email = email_inst or email_pess or None
            await self._processar_finalizacao_inscricao(interaction, usuario, curso, chosen_email)

    async def _processar_finalizacao_inscricao(self, interaction: discord.Interaction, usuario: dict, curso: dict, chosen_email: Optional[str]):
        db_usuario_id = usuario['usuario_id']
        curso_id = curso['curso_id']
        agente = curso.get('curso_agente')

        # 1. Red Hat requer o Red Hat Network ID via Modal
        if agente and agente.strip().lower() == 'cadastrar_rh124':
            modal = RedHatModal(self, db_usuario_id, curso_id, chosen_email or usuario.get('usuario_email'))
            if not interaction.response.is_done():
                await interaction.response.send_modal(modal)
            else:
                await interaction.followup.send("Abra o formulário para informar seu ID Red Hat.", ephemeral=True)
            return

        # 2. Cisco com link de auto-inscrição
        elif curso.get('curso_parceira') == 'Cisco' and curso.get('curso_url_inscricao'):
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
            url = curso['curso_url_inscricao']
            sucesso, msg = self._realizar_matricula(db_usuario_id, curso_id, None, chosen_email, situacao='Inscrito')
            
            embed_cisco = discord.Embed(
                title="✅ Inscrição Pré-Registrada com Sucesso!",
                description=(
                    f"Você foi registrado no curso **{curso['curso_nome']}** utilizando o e-mail `{chosen_email}`.\n\n"
                    f"🔗 **Complete sua inscrição no portal da Cisco:**\n"
                    f"{url}\n\n"
                    f"⚠️ **Instruções Importantes:**\n"
                    f"1. Cadastre-se na Cisco e no Credly utilizando seu **NOME COMPLETO** ({usuario['usuario_nome']}).\n"
                    f"2. Utilize o mesmo e-mail informado para validação automática de certificados."
                ),
                color=0x10b981
            )
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed_cisco, view=None)
            else:
                await interaction.followup.send(embed=embed_cisco, ephemeral=True)
            return

        # 3. Demais cursos (AWS, Google, etc.)
        else:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
            sucesso, msg = self._realizar_matricula(db_usuario_id, curso_id, None, chosen_email)
            
            embed_sucesso = discord.Embed(
                title="✅ Solicitação de Inscrição Enviada!",
                description=(
                    f"Sua inscrição para o curso **{curso['curso_nome']}** foi registrada com sucesso!\n\n"
                    f"📧 **E-mail informado:** `{chosen_email}`\n"
                    f"⏳ **Status:** `Pendente de Liberação`\n\n"
                    f"O professor responsável ({curso.get('curso_agente') or 'Coordenação'}) fará a liberação dos acessos na plataforma parceira."
                ),
                color=0x10b981
            )
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed_sucesso, view=None)
            else:
                await interaction.followup.send(embed=embed_sucesso, ephemeral=True)

    # ============================================================
    # COMANDO /inscrever_curso
    # ============================================================

    @app_commands.command(
        name="inscrever_curso",
        description="Consulta os detalhes completos de um curso parceiro e realiza sua inscrição."
    )
    @app_commands.describe(curso_id="Selecione o curso desejado no menu suspenso")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_inscrever_curso(self, interaction: discord.Interaction, curso_id: int):
        await interaction.response.defer(ephemeral=True)

        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(dictionary=True)
            
            # 1. Verifica vínculo do usuário
            cur.execute("""
                SELECT usuario_id, usuario_nome, usuario_email, usuario_email_pessoal 
                FROM usuario 
                WHERE usuario_discord_id = %s
            """, (str(interaction.user.id),))
            usuario = cur.fetchone()
            
            if not usuario:
                await interaction.followup.send(
                    "❌ Eu ainda não te conheço! Você precisa usar o comando `/identificar` e `/validar` o seu vínculo acadêmico primeiro.", 
                    ephemeral=True
                )
                return
                
            # 2. Busca dados completos do curso
            cur.execute("""
                SELECT curso_id, curso_parceira, curso_nome, curso_descricao, curso_agente, 
                       curso_url_inscricao, curso_dt_inicio, curso_dt_fim, curso_carga_horaria, 
                       curso_idioma, curso_prerequisito_id
                FROM curso 
                WHERE curso_id = %s
            """, (curso_id,))
            curso = cur.fetchone()
            
            if not curso:
                await interaction.followup.send(
                    "❌ Curso não encontrado. Utilize o menu suspenso ao digitar `/inscrever_curso` para escolher um curso com matrículas abertas.", 
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
                await interaction.followup.send(
                    f"⚠️ Você já possui uma inscrição solicitada ou ativa para o curso **{curso['curso_nome']}**.",
                    ephemeral=True
                )
                return

            # 4. Formata o card detalhado com todos os dados do curso
            dt_ini = curso['curso_dt_inicio'].strftime('%d/%m/%Y') if curso['curso_dt_inicio'] else '-'
            dt_fim = curso['curso_dt_fim'].strftime('%d/%m/%Y') if curso['curso_dt_fim'] else '-'
            
            idioma_str = "🇺🇸 Inglês (en-us)" if curso.get('curso_idioma') == 'en-us' else "🇧🇷 Português do Brasil (pt-br)"
            ch_str = f"{curso['curso_carga_horaria']} horas" if curso.get('curso_carga_horaria') else "Não informada"
            desc_str = curso.get('curso_descricao') or "Sem descrição cadastrada no momento."
            
            embed = discord.Embed(
                title=f"🎓 [{curso['curso_parceira']}] {curso['curso_nome']}",
                description=f"### Detalhes do Curso\n{desc_str}\n",
                color=0x3b82f6
            )
            embed.add_field(name="🌐 Idioma", value=f"`{idioma_str}`", inline=True)
            embed.add_field(name="⏱️ Carga Horária", value=f"`{ch_str}`", inline=True)
            embed.add_field(name="📅 Período de Inscrição", value=f"`{dt_ini}` até `{dt_fim}`", inline=True)
            embed.add_field(name="👨‍🏫 Responsável", value=f"`{curso.get('curso_agente') or 'Coordenação'}`", inline=True)

            if curso.get('curso_prerequisito_id'):
                prereq_obj = self._fetch_curso_by_id(curso['curso_prerequisito_id'])
                if prereq_obj:
                    embed.add_field(
                        name="🔗 Pré-requisito Recomendado",
                        value=f"[{prereq_obj['curso_parceira']}] {prereq_obj['curso_nome']}",
                        inline=False
                    )

            if curso.get('curso_url_inscricao'):
                embed.add_field(name="🔗 Auto-Inscrição", value=f"[Link da Plataforma]({curso['curso_url_inscricao']})", inline=True)

            embed.add_field(
                name="❓ Confirmação",
                value="**Confirma a sua inscrição neste curso parceiro?**",
                inline=False
            )
            embed.set_footer(text="PyAnima Gamification • Inscrição em Cursos Parceiros")

            # Anexa os botões Sim / Não
            view = ConfirmacaoInscricaoView(self, usuario, curso)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"Erro em cmd_inscrever_curso: {e}", exc_info=True)
            await interaction.followup.send("❌ Ocorreu um erro ao carregar os dados do curso.", ephemeral=True)
        finally:
            if conn and conn.is_connected():
                conn.close()

    @cmd_inscrever_curso.autocomplete('curso_id')
    async def inscrever_curso_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[int]]:
        """Menu suspenso com cursos vigentes, carga horária e idioma"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
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
            logger.error(f"Erro no autocomplete de inscrever_curso: {e}")
            return []


async def setup(bot: commands.Bot):
    await bot.add_cog(CursosCog(bot))
    logger.info("Cog 'CursosCog' carregado com sucesso.")
