import os
import sys
import logging
import asyncio
import subprocess
import discord
from discord.ext import commands
from discord import app_commands
import mysql.connector
import urllib.request
import re
from typing import Optional, Tuple

logger = logging.getLogger("cogs.cursos")

# ============================================================
# MODAL RED HAT (Quando o curso exige Red Hat Network ID)
# ============================================================
# MODAL RED HAT (Quando o curso exige Red Hat Network ID e E-mail de cadastro)
# ============================================================

REDHAT_PORTAL_URL = "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/auth?response_type=code&client_id=rha-webapp-prod&redirect_uri=https%3A%2F%2Frha.ole.redhat.com%2Frha%2Fauth%2Fauthorize&scope=openid+profile+email&state=wM5w525IXv2HhKlLeUkM3G8f15Xfy3&nonce=GYTaZPIfdjhLN4FcbRJA"

class RedHatModal(discord.ui.Modal, title='Inscrição Red Hat Academy'):
    def __init__(self, cog, usuario: dict, curso: dict, default_email: str):
        super().__init__()
        self.cog = cog
        self.usuario = usuario
        self.curso = curso

        self.redhat_id_input = discord.ui.TextInput(
            label='Red Hat Network (RHN) ID',
            style=discord.TextStyle.short,
            placeholder='Ex: henrique_poyatos (ID exato no portal Red Hat)',
            required=True,
            max_length=60
        )
        self.add_item(self.redhat_id_input)

        self.redhat_email_input = discord.ui.TextInput(
            label='E-mail cadastrado na Red Hat',
            style=discord.TextStyle.short,
            placeholder='Ex: seu.email@exemplo.com (mesmo usado no portal)',
            default=default_email,
            required=True,
            max_length=100
        )
        self.add_item(self.redhat_email_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        rhn_id = self.redhat_id_input.value.strip()
        rhn_email = self.redhat_email_input.value.strip()

        sucesso, msg = self.cog._realizar_matricula(
            self.usuario['usuario_id'], 
            self.curso['curso_id'], 
            rhn_id, 
            rhn_email
        )
        if sucesso:
            embed_audit = discord.Embed(
                title="📝 Nova Solicitação de Inscrição em Curso",
                color=0xef4444
            )
            embed_audit.add_field(name="👤 Aluno", value=f"{self.usuario['usuario_nome']} (<@{interaction.user.id}>)", inline=True)
            embed_audit.add_field(name="🎓 Curso", value=f"[{self.curso['curso_parceira']}] {self.curso['curso_nome']}", inline=True)
            embed_audit.add_field(name="📧 E-mail Red Hat", value=f"`{rhn_email}`", inline=True)
            embed_audit.add_field(name="🆔 Red Hat ID", value=f"`{rhn_id}`", inline=True)
            embed_audit.add_field(name="⏳ Status", value="`Em processamento automático`", inline=True)
            embed_audit.add_field(name="👨‍🏫 Responsável", value=f"`{self.curso.get('curso_agente') or 'Coordenação'}`", inline=True)
            await self.cog._log_auditoria(f"🔔 Nova inscrição solicitada por **{self.usuario['usuario_nome']}**.", embed=embed_audit)

            # Dispara robô Red Hat em background se configurado para automação
            agente_curso = (self.curso.get('curso_agente') or '').strip().lower()
            if agente_curso in ['cadastrar_rh124', 'rh124_agente']:
                async def _executar_robo_redhat(uid, cid):
                    try:
                        logger.info(f"Disparando robô Red Hat em background para usuario_id={uid}, curso_id={cid}...")
                        proc = await asyncio.create_subprocess_exec(
                            sys.executable, "-m", "selenium_bot.redhat_login",
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                        )
                        stdout, stderr = await proc.communicate()
                        out_str = stdout.decode('utf-8', errors='replace')
                        err_str = stderr.decode('utf-8', errors='replace')
                        if proc.returncode == 0:
                            logger.info(f"Robô Red Hat finalizado com sucesso (rc=0):\n{out_str}")
                        else:
                            logger.error(f"Robô Red Hat finalizou com ERRO (rc={proc.returncode}):\nSTDOUT:\n{out_str}\nSTDERR:\n{err_str}")
                    except Exception as e_robo:
                        logger.error(f"Erro ao disparar robô Red Hat em background: {e_robo}")

                asyncio.create_task(_executar_robo_redhat(self.usuario['usuario_id'], self.curso['curso_id']))

        await interaction.followup.send(msg, ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error(f"Erro no modal RedHat: {error}")
        await interaction.followup.send('❌ Ocorreu um erro interno. Tente novamente.', ephemeral=True)


GOOGLE_SKILLS_BOOST_URL = "https://www.skills.google/"

def verificar_perfil_google_skills(url: str) -> Tuple[bool, str]:
    if not url:
        return False, "URL não informada."
    url_clean = url.strip()
    if not ('skills.google/public_profiles/' in url_clean or 'cloudskillsboost.google/public_profiles/' in url_clean):
        return False, "A URL deve ser do perfil público do Google Skills Boost (ex: https://www.skills.google/public_profiles/SEU-UUID)."
    
    if not url_clean.startswith('http://') and not url_clean.startswith('https://'):
        url_clean = 'https://' + url_clean

    try:
        req = urllib.request.Request(url_clean, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                return False, f"A página retornou código HTTP {resp.status}. Verifique se o link está correto."
            html = resp.read().decode('utf-8', errors='ignore')

            tem_qwiklabs = 'cdn.qwiklabs.com' in html
            tem_public_profiles = 'public_profiles' in html
            canonical_match = re.search(r'''canonical.*href=['"]([^'"]+)''', html, re.I)
            canonical_url = canonical_match.group(1) if canonical_match else ''

            if canonical_url and 'public_profiles' not in canonical_url:
                return False, "O perfil não parece estar público ou não foi encontrado (redirecionou para a página inicial)."

            if not (tem_qwiklabs and tem_public_profiles):
                return False, "Não foi possível validar o perfil público. Certifique-se de que a opção 'Tornar o perfil público' foi ativada na sua conta."

            nome_perfil = None
            h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.I | re.S)
            if h1_match:
                nome_perfil = h1_match.group(1).strip()
            elif '<title>' in html:
                title = html.split('<title>')[1].split('</title>')[0].strip()
                if '|' in title:
                    nome_perfil = title.split('|')[0].strip()

            return True, nome_perfil or "Perfil Público Confirmado"
    except Exception as e:
        return False, f"Não foi possível acessar a URL informada: {e}"

# ============================================================
# MODAL E VIEW GOOGLE SKILLS BOOST
# ============================================================

class GoogleSkillsBoostModal(discord.ui.Modal, title='Perfil Google Skills Boost'):
    def __init__(self, cog, usuario: dict, curso: dict, chosen_email: Optional[str]):
        super().__init__()
        self.cog = cog
        self.usuario = usuario
        self.curso = curso
        self.chosen_email = chosen_email

        self.url_input = discord.ui.TextInput(
            label='URL do Perfil Público',
            style=discord.TextStyle.short,
            placeholder='https://www.skills.google/public_profiles/...',
            required=True,
            max_length=250
        )
        self.add_item(self.url_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        url_fornecida = self.url_input.value.strip()

        # Validação web da URL
        valido, retorno = await asyncio.to_thread(verificar_perfil_google_skills, url_fornecida)
        if not valido:
            embed_err = discord.Embed(
                title="⚠️ Perfil Não Acessível ou Inválido",
                description=(
                    f"Não conseguimos validar o seu perfil público através do link fornecido:\n"
                    f"`{url_fornecida}`\n\n"
                    f"**Motivo:** {retorno}\n\n"
                    f"👉 **Como resolver:**\n"
                    f"1. Acesse sua conta no **Google Skills Boost**.\n"
                    f"2. Vá em **Configurações / Perfil** e certifique-se de clicar em **'Tornar o perfil público'**.\n"
                    f"3. Copie a URL pública gerada e tente se inscrever novamente com `/inscrever_curso`."
                ),
                color=0xef4444
            )
            await interaction.followup.send(embed=embed_err, ephemeral=True)
            return

        nome_no_perfil = retorno
        sucesso, msg = self.cog._realizar_matricula(
            usuario_id=self.usuario['usuario_id'],
            curso_id=self.curso['curso_id'],
            redhat_id=None,
            redhat_email=self.chosen_email,
            situacao='Pendente',
            url_perfil=url_fornecida
        )

        if sucesso:
            # Envia para o canal de auditoria
            embed_audit = discord.Embed(
                title="📝 Nova Solicitação - Google Skills Boost",
                color=0x4285f4
            )
            embed_audit.add_field(name="👤 Aluno", value=f"{self.usuario['usuario_nome']} (<@{interaction.user.id}>)", inline=True)
            embed_audit.add_field(name="🎓 Curso", value=f"[{self.curso['curso_parceira']}] {self.curso['curso_nome']}", inline=True)
            embed_audit.add_field(name="📧 E-mail Informado", value=f"`{self.chosen_email or 'Não informado'}`", inline=True)
            embed_audit.add_field(name="🌐 Nome no Perfil Google", value=f"`{nome_no_perfil}`", inline=True)
            embed_audit.add_field(name="🔗 URL Perfil Público", value=f"[Abrir Perfil Público]({url_fornecida})", inline=False)
            embed_audit.add_field(name="⏳ Status", value="`Pendente (Aguardando Professor)`", inline=True)
            embed_audit.add_field(name="👨‍🏫 Responsável", value=f"`{self.curso.get('curso_agente') or 'Coordenação'}`", inline=True)
            await self.cog._log_auditoria(f"🔔 Nova inscrição Google Skills Boost solicitada por **{self.usuario['usuario_nome']}**.", embed=embed_audit)

            # Mensagem de sucesso para o aluno
            embed_sucesso = discord.Embed(
                title="✅ Perfil Validado e Inscrição Registrada!",
                description=(
                    f"Seu perfil público do **Google Skills Boost** foi verificado com sucesso!\n\n"
                    f"👤 **Identificação no perfil:** `{nome_no_perfil}`\n"
                    f"🔗 **URL armazenada:** `{url_fornecida}`\n\n"
                    f"⏳ **Status da Matrícula:**\n"
                    f"Seu pedido de matrícula foi registrado! **O professor responsável fará a matrícula depois** e liberará o acesso à trilha."
                ),
                color=0x10b981
            )
            embed_sucesso.set_footer(text="PyAnima Gamification • Google Skills Boost")
            await interaction.followup.send(embed=embed_sucesso, ephemeral=True)
        else:
            await interaction.followup.send(msg, ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.error(f"Erro no modal GoogleSkillsBoost: {error}")
        await interaction.followup.send('❌ Ocorreu um erro interno ao validar seu perfil. Tente novamente.', ephemeral=True)

class GoogleSkillsBoostConfirmacaoView(discord.ui.View):
    def __init__(self, cog, usuario: dict, curso: dict, chosen_email: Optional[str]):
        super().__init__(timeout=180)
        self.cog = cog
        self.usuario = usuario
        self.curso = curso
        self.chosen_email = chosen_email

        self.add_item(discord.ui.Button(
            label="1. Acessar Google Skills Boost",
            url=GOOGLE_SKILLS_BOOST_URL,
            style=discord.ButtonStyle.link,
            emoji="🔗"
        ))

    @discord.ui.button(label="2. Já Tornei Perfil Público, Informar URL", style=discord.ButtonStyle.success, emoji="🌐")
    async def btn_abrir_modal_google(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = GoogleSkillsBoostModal(self.cog, self.usuario, self.curso, self.chosen_email)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary, emoji="❌")
    async def btn_cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed_cancel = discord.Embed(
            title="🚫 Inscrição Cancelada",
            description=f"A solicitação para o curso **{self.curso['curso_nome']}** foi cancelada.",
            color=0x64748b
        )
        await interaction.response.edit_message(embed=embed_cancel, view=None)

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
# VIEW: CONFIRMAÇÃO PRÉVIA RED HAT (Link do portal + Aviso de cadastro prévio)
# ============================================================

class RedHatConfirmacaoView(discord.ui.View):
    def __init__(self, cog, usuario: dict, curso: dict, default_email: str):
        super().__init__(timeout=180)
        self.cog = cog
        self.usuario = usuario
        self.curso = curso
        self.default_email = default_email

        # Botão com link direto para o portal da Red Hat
        self.add_item(discord.ui.Button(
            label="1. Criar/Acessar Conta Red Hat",
            url=REDHAT_PORTAL_URL,
            style=discord.ButtonStyle.link,
            emoji="🔗"
        ))

    @discord.ui.button(label="2. Já Tenho Conta, Preencher Dados", style=discord.ButtonStyle.success, emoji="📝")
    async def btn_abrir_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RedHatModal(self.cog, self.usuario, self.curso, self.default_email)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary, emoji="❌")
    async def btn_cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed_cancel = discord.Embed(
            title="🚫 Inscrição Cancelada",
            description=f"A solicitação para o curso **{self.curso['curso_nome']}** foi cancelada.",
            color=0x64748b
        )
        await interaction.response.edit_message(embed=embed_cancel, view=None)


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

    def _realizar_matricula(self, usuario_id: int, curso_id: int, redhat_id: Optional[str] = None, redhat_email: Optional[str] = None, situacao: str = 'Pendente', url_perfil: Optional[str] = None) -> Tuple[bool, str]:
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
                (usuario_id, curso_id, usuario_redhat_id, usuario_redhat_email, usuario_curso_dt_solicitacao, usuario_curso_situacao, usuario_curso_url_comprovante)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cur.execute(sql, (usuario_id, curso_id, redhat_id, redhat_email, dt_agora, situacao, url_perfil))
            conn.commit()
            
            email_info = f" ({redhat_email})" if redhat_email else ""
            if situacao == 'Inscrito':
                return True, f"✅ **Inscrição registrada com sucesso!**{email_info}"
            return True, f"✅ **Inscrição solicitada com sucesso!**{email_info} Aguarde alguns minutos que já vamos te inscrever no curso."
            
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

    async def _log_auditoria(self, message: str, embed: Optional[discord.Embed] = None):
        """Envia log formatado para o canal de auditoria do Discord."""
        auditoria_id_str = os.getenv("DISCORD_AUDITORIA_CHANNEL_ID")
        if not auditoria_id_str:
            return
        try:
            channel_id = int(auditoria_id_str)
            channel = self.bot.get_channel(channel_id)
            if not channel:
                channel = await self.bot.fetch_channel(channel_id)
            if channel:
                if embed:
                    await channel.send(content=message, embed=embed)
                else:
                    await channel.send(content=message)
        except Exception as e:
            logger.error(f"Erro ao enviar log para canal de auditoria de cursos: {e}")

    async def _processar_finalizacao_inscricao(self, interaction: discord.Interaction, usuario: dict, curso: dict, chosen_email: Optional[str]):
        db_usuario_id = usuario['usuario_id']
        curso_id = curso['curso_id']
        agente = curso.get('curso_agente')

        # 0. Google Skills Boost requer perfil público e URL
        if agente and agente.strip().lower() in ['cadastrar_googleskillsboost', 'googleskillsboost']:
            embed_google_instrucoes = discord.Embed(
                title="🌐 Google Skills Boost - Pré-requisito Obrigatório!",
                description=(
                    f"Para participar de **{curso['curso_nome']}**, você **precisa ter uma conta criada no Google Skills Boost e configurar o seu perfil como PÚBLICO**.\n\n"
                    f"📌 **Instruções:**\n"
                    f"1. Se ainda não tem conta ou não ativou o perfil público, clique no botão **`1. Acessar Google Skills Boost`**.\n"
                    f"2. Na plataforma, vá em **Conta / Configurações** e ative a opção **'Tornar o perfil público'**.\n"
                    f"3. Quando estiver pronto, clique em **`2. Já Tornei Perfil Público, Informar URL`** para informar seu link público (ex: `https://www.skills.google/public_profiles/...`).\n"
                    f"4. Nosso sistema validará o acesso ao perfil em tempo real antes de prosseguir!"
                ),
                color=0x4285f4
            )
            view_google = GoogleSkillsBoostConfirmacaoView(self, usuario, curso, chosen_email)
            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=embed_google_instrucoes, view=view_google)
            else:
                await interaction.edit_original_response(embed=embed_google_instrucoes, view=view_google)
            return

        # 1. Red Hat requer cadastro prévio no portal e coleta do Red Hat Network ID + E-mail
        if agente and agente.strip().lower() == 'cadastrar_rh124':
            embed_rh_instrucoes = discord.Embed(
                title="🔴 Inscrição na Red Hat Academy - Atenção!",
                description=(
                    f"Para que o robô possa te matricular em **{curso['curso_nome']}**, você **precisa ter uma conta ativa no portal da Red Hat** antes de continuar.\n\n"
                    f"⚠️ **Importante:**\n"
                    f"1. Clique no botão **`1. Criar/Acessar Conta Red Hat`** abaixo caso ainda não tenha cadastro.\n"
                    f"2. Após criar/conferir sua conta, clique em **`2. Já Tenho Conta, Preencher Dados`** para abrir o formulário.\n"
                    f"3. As duas informações (**Red Hat Network ID** e o **E-mail exato cadastrado lá**) devem ser **100% precisas**, pois o robô automatizado fará a validação direta no portal com esses dados."
                ),
                color=0xee0000
            )
            default_email = chosen_email or usuario.get('usuario_email_pessoal') or usuario.get('usuario_email') or ""
            view_rh = RedHatConfirmacaoView(self, usuario, curso, default_email)
            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=embed_rh_instrucoes, view=view_rh)
            else:
                await interaction.edit_original_response(embed=embed_rh_instrucoes, view=view_rh)
            return

        # 2. Cisco com link de auto-inscrição
        elif curso.get('curso_parceira') == 'Cisco' and curso.get('curso_url_inscricao'):
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
            url = curso['curso_url_inscricao']
            sucesso, msg = self._realizar_matricula(db_usuario_id, curso_id, None, chosen_email, situacao='Inscrito')
            
            if sucesso:
                embed_audit = discord.Embed(
                    title="📝 Nova Auto-Inscrição em Curso Parceiro",
                    color=0x10b981
                )
                embed_audit.add_field(name="👤 Aluno", value=f"{usuario['usuario_nome']} (<@{interaction.user.id}>)", inline=True)
                embed_audit.add_field(name="🎓 Curso", value=f"[{curso['curso_parceira']}] {curso['curso_nome']}", inline=True)
                embed_audit.add_field(name="📧 E-mail Informado", value=f"`{chosen_email}`", inline=True)
                embed_audit.add_field(name="⏳ Status", value="`Inscrito (Auto-inscrição Cisco)`", inline=True)
                await self._log_auditoria(f"🔔 Auto-inscrição Cisco realizada por **{usuario['usuario_nome']}**.", embed=embed_audit)

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

        # 3. Demais cursos (AWS, Google, Red Hat sem script, etc.)
        else:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
            sucesso, msg = self._realizar_matricula(db_usuario_id, curso_id, None, chosen_email)
            
            if sucesso:
                embed_audit = discord.Embed(
                    title="📝 Nova Solicitação de Inscrição em Curso",
                    color=0x3b82f6
                )
                embed_audit.add_field(name="👤 Aluno", value=f"{usuario['usuario_nome']} (<@{interaction.user.id}>)", inline=True)
                embed_audit.add_field(name="🎓 Curso", value=f"[{curso['curso_parceira']}] {curso['curso_nome']}", inline=True)
                embed_audit.add_field(name="📧 E-mail Informado", value=f"`{chosen_email}`", inline=True)
                embed_audit.add_field(name="⏳ Status", value="`Pendente de Liberação`", inline=True)
                embed_audit.add_field(name="👨‍🏫 Responsável", value=f"`{curso.get('curso_agente') or 'Coordenação'}`", inline=True)
                await self._log_auditoria(f"🔔 Nova solicitação de inscrição recebida de **{usuario['usuario_nome']}**.", embed=embed_audit)

                # Se o curso estiver configurado para automação da AWS, dispara o robô em background
                agente_curso = (curso.get('curso_agente') or '').strip().lower()
                parceira_curso = (curso.get('curso_parceira') or '').strip().upper()
                if agente_curso in ['cadastrar_aws', 'aws_agente', 'aws'] or (parceira_curso == 'AWS' and not agente_curso.startswith('cadastrar_rh')):
                    async def _executar_robo_aws(uid, cid):
                        try:
                            logger.info(f"Disparando robô AWS em background para usuario_id={uid}, curso_id={cid}...")
                            proc = await asyncio.create_subprocess_exec(
                                sys.executable, "-m", "selenium_bot.aws_login", str(uid), str(cid),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE
                            )
                            stdout, stderr = await proc.communicate()
                            out_str = stdout.decode('utf-8', errors='replace')
                            err_str = stderr.decode('utf-8', errors='replace')
                            if proc.returncode == 0:
                                logger.info(f"Robô AWS finalizado com sucesso (rc=0):\n{out_str}")
                            else:
                                logger.error(f"Robô AWS finalizou com ERRO (rc={proc.returncode}):\nSTDOUT:\n{out_str}\nSTDERR:\n{err_str}")
                        except Exception as e_robo:
                            logger.error(f"Erro ao disparar robô AWS em background: {e_robo}")
                    
                    asyncio.create_task(_executar_robo_aws(db_usuario_id, curso_id))

            agente_curso_fmt = (curso.get('curso_agente') or '').strip().lower()
            parceira_fmt = (curso.get('curso_parceira') or '').strip().upper()
            is_auto = (
                agente_curso_fmt in ['cadastrar_aws', 'aws_agente', 'aws', 'cadastrar_rh124', 'rh124_agente']
                or (parceira_fmt == 'AWS' and not agente_curso_fmt.startswith('cadastrar_rh'))
            )
            embed_sucesso = discord.Embed(
                title="✅ Solicitação de Inscrição Enviada!",
                description=(
                    f"Sua inscrição para o curso **{curso['curso_nome']}** foi registrada com sucesso!\n\n"
                    f"📧 **E-mail informado:** `{chosen_email}`\n"
                    f"⏳ **Status:** `Em processamento automático`\n\n"
                    f"O sistema já acionou o robô de inscrição automática da plataforma parceira."
                ) if is_auto else (
                    f"Sua inscrição para o curso **{curso['curso_nome']}** foi registrada com sucesso!\n\n"
                    f"📧 **E-mail informado:** `{chosen_email}`\n"
                    f"⏳ **Status:** `Aguarde alguns minutos que já vamos te inscrever no curso`\n\n"
                    f"A coordenação / professor responsável ({curso.get('curso_agente') or 'Coordenação'}) dará andamento aos acessos."
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
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.errors.NotFound:
            logger.warning("Interação de /inscrever_curso expirou antes do defer (timeout de 3 segundos da API do Discord).")
            return

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
            
            # 3. Verifica duplicidade de inscrição (ativa, solicitada ou já concluída)
            cur.execute("""
                SELECT uc.usuario_curso_situacao, uc.usuario_curso_dt_solicitacao 
                FROM usuario_curso uc
                WHERE uc.usuario_id = %s AND uc.curso_id = %s
            """, (db_usuario_id, curso_id))
            ja_inscrito = cur.fetchone()
            
            if ja_inscrito:
                situacao_txt = ja_inscrito.get('usuario_curso_situacao') or 'Ativa'
                await interaction.followup.send(
                    f"🚫 **Inscrição Impedida:** Você já possui registro para o curso **{curso['curso_nome']}** (Status atual: `{situacao_txt}`).\n"
                    f"Não é permitido se inscrever mais de uma vez no mesmo curso.",
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
        """Menu suspenso com cursos vigentes, carga horária e idioma."""
        def _fetch_choices():
            conn = None
            try:
                conn = self._get_db_connection()
                cursor = conn.cursor(dictionary=True)
                
                # 1. Identifica o usuario_id associado ao Discord do usuário
                cursor.execute(
                    "SELECT usuario_id FROM usuario WHERE usuario_discord_id = %s",
                    (str(interaction.user.id),)
                )
                user_row = cursor.fetchone()
                usuario_id = user_row['usuario_id'] if user_row else None

                # 2. Busca cursos vigentes excluindo os que o usuário já está inscrito
                curr_term = f"%{current or ''}%"
                if usuario_id:
                    query = """
                        SELECT c.curso_id, c.curso_parceira, c.curso_nome, c.curso_carga_horaria, c.curso_idioma
                        FROM curso c
                        WHERE (c.curso_nome LIKE %s OR c.curso_parceira LIKE %s)
                        AND (c.curso_dt_inicio IS NULL OR c.curso_dt_inicio <= NOW() OR DATE(c.curso_dt_inicio) <= CURDATE())
                        AND (c.curso_dt_fim IS NULL OR c.curso_dt_fim >= NOW() OR DATE(c.curso_dt_fim) >= CURDATE())
                        AND c.curso_id NOT IN (
                            SELECT uc.curso_id 
                            FROM usuario_curso uc 
                            WHERE uc.usuario_id = %s
                        )
                        ORDER BY c.curso_parceira ASC, c.curso_nome ASC
                        LIMIT 25
                    """
                    cursor.execute(query, (curr_term, curr_term, usuario_id))
                else:
                    query = """
                        SELECT c.curso_id, c.curso_parceira, c.curso_nome, c.curso_carga_horaria, c.curso_idioma
                        FROM curso c
                        WHERE (c.curso_nome LIKE %s OR c.curso_parceira LIKE %s)
                        AND (c.curso_dt_inicio IS NULL OR c.curso_dt_inicio <= NOW() OR DATE(c.curso_dt_inicio) <= CURDATE())
                        AND (c.curso_dt_fim IS NULL OR c.curso_dt_fim >= NOW() OR DATE(c.curso_dt_fim) >= CURDATE())
                        ORDER BY c.curso_parceira ASC, c.curso_nome ASC
                        LIMIT 25
                    """
                    cursor.execute(query, (curr_term, curr_term))

                rows = cursor.fetchall()
                cursor.close()
                
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
            finally:
                if conn and conn.is_connected():
                    conn.close()

        return await asyncio.to_thread(_fetch_choices)

    # ============================================================
    # COMANDO /cadastrar_google_skills (Acionamento manual do Robô)
    # ============================================================

    @app_commands.command(
        name="cadastrar_google_skills",
        description="Executa o robô Selenium para cadastrar alunos pendentes no Google Skills Boost."
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_cadastrar_google_skills(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        embed_aviso = discord.Embed(
            title="🤖 Robô Google Skills Boost Acionado!",
            description=(
                "🚀 O processo de automação no Google Skills Boost foi iniciado.\n\n"
                "📱 **ATENÇÃO AO SEU SMARTPHONE / TABLET:**\n"
                "Em alguns instantes, o Google enviará uma solicitação de login MFA.\n"
                "👉 **Toque em 'Sim' no seu aparelho para aprovar a entrada do robô!**\n\n"
                "⏳ *Aguardando autenticação e processamento das matrículas pendentes...*"
            ),
            color=0x4285f4
        )
        embed_aviso.set_footer(text="PyAnima Gamification • Google Skills Boost Automation")
        await interaction.followup.send(embed=embed_aviso, ephemeral=True)

        async def _executar_google_skills():
            try:
                logger.info("Executando robô Google Skills Boost sob demanda via comando Discord...")
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, "-m", "selenium_bot.google_skills_boost",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                out_str = stdout.decode('utf-8', errors='replace')
                err_str = stderr.decode('utf-8', errors='replace')

                if proc.returncode == 0:
                    logger.info(f"Robô Google Skills Boost finalizado com sucesso:\n{out_str}")
                    embed_result = discord.Embed(
                        title="✅ Robô Google Skills Boost Concluído!",
                        description=(
                            "🎉 O processamento dos alunos no Google Skills Boost foi finalizado com sucesso!\n\n"
                            "📋 **Detalhes da Execução:**\n"
                            f"```text\n{out_str[-1500:] if len(out_str) > 1500 else out_str}\n```"
                        ),
                        color=0x10b981
                    )
                else:
                    logger.error(f"Robô Google Skills Boost finalizou com ERRO (rc={proc.returncode}):\n{err_str}")
                    embed_result = discord.Embed(
                        title="❌ Erro na Execução do Robô Google Skills Boost",
                        description=(
                            f"O robô encerrou com código de saída `{proc.returncode}`.\n\n"
                            "⚠️ **Logs de Erro:**\n"
                            f"```text\n{err_str[-1500:] if len(err_str) > 1500 else err_str}\n```"
                        ),
                        color=0xef4444
                    )

                try:
                    await interaction.followup.send(embed=embed_result, ephemeral=True)
                except Exception:
                    await self._log_auditoria("Resultado da execução do Robô Google Skills Boost:", embed=embed_result)

            except Exception as e_proc:
                logger.error(f"Erro ao disparar subprocesso do Google Skills Boost: {e_proc}")
                embed_err = discord.Embed(
                    title="⚠️ Falha ao Iniciar Robô",
                    description=f"Ocorreu um erro inesperado: `{e_proc}`",
                    color=0xef4444
                )
                try:
                    await interaction.followup.send(embed=embed_err, ephemeral=True)
                except Exception:
                    pass

        asyncio.create_task(_executar_google_skills())


async def setup(bot: commands.Bot):
    await bot.add_cog(CursosCog(bot))
    logger.info("Cog 'CursosCog' carregado com sucesso.")
