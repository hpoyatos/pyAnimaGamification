import os
import logging
import discord
from discord.ext import commands
from discord import app_commands
import mysql.connector
from typing import Optional, Tuple
from datetime import datetime, timedelta
import re
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from utils.certificado_service import CertificadoService

logger = logging.getLogger("cogs.cursos")

class RedHatModal(discord.ui.Modal, title='Inscrição Red Hat Academy'):
    def __init__(self, cog, usuario_id: int, curso_id: int):
        super().__init__()
        self.cog = cog
        self.db_usuario_id = usuario_id
        self.db_curso_id = curso_id

        # Definindo campos internamente para maior robustez na renderização
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
            
            # Check if already enrolled (par de segurança extra, embora cmd_inscrever valide vigência)
            cur.execute("SELECT 1 FROM usuario_curso WHERE usuario_id = %s AND curso_id = %s", (usuario_id, curso_id))
            if cur.fetchone():
                return False, "⚠️ Você já possui uma inscrição para este curso."

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
            return True, "✅ Inscrição solicitada com sucesso! aguarde a confirmação do professor."
            
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
                SELECT curso_id, curso_parceira, curso_nome, curso_dt_inicio, curso_dt_fim, curso_agente
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
                    f"**{c['curso_parceira']} - {c['curso_nome']}**\n"
                    f"📅 Período: `{dt_ini}` até `{dt_fim}`\n"
                    f"📌 ID do Curso: `{c['curso_id']}`\n\n"
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
    @app_commands.describe(curso_id="O ID ou nome do curso (escolha na lista suspensa).")
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
            cur.execute("SELECT curso_id, curso_parceira, curso_agente, curso_url_inscricao FROM curso WHERE curso_id = %s", (curso_id,))
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
            
            # Verificação extra de vigência para solicitação existente
            cur.execute("""
                SELECT 1 
                FROM usuario_curso uc
                JOIN curso c ON uc.curso_id = c.curso_id
                WHERE uc.usuario_id = %s AND uc.curso_id = %s
                AND NOW() <= c.curso_dt_fim
            """, (db_usuario_id, curso_id))
            
            if cur.fetchone():
                await interaction.response.send_message("Você já solicitou esse curso", ephemeral=True)
                return

            if agente and agente.strip().lower() == 'cadastrar_rh124':
                # Needs Modal to collect red hat id and email
                modal = RedHatModal(self, db_usuario_id, curso_id)
                await interaction.response.send_modal(modal)
                return
            
            elif curso.get('curso_parceira') == 'Cisco' and curso.get('curso_url_inscricao'):
                # Cisco with URL: Auto-enroll with 'Inscrito' status and give instructions
                await interaction.response.defer(ephemeral=True)
                url = curso['curso_url_inscricao']
                sucesso, msg = self._realizar_matricula(db_usuario_id, curso_id, None, None, situacao='Inscrito')
                
                if sucesso:
                    msg = (
                        f"✅ **Inscrição realizada com sucesso!**\n\n"
                        f"Para este curso da Cisco, você deve completar sua inscrição manualmente através da URL abaixo:\n"
                        f"🔗 {url}\n\n"
                        f"⚠️ **Instruções Importantes:**\n"
                        f"1. Certifique-se de criar seu usuário no **Cisco Net Academy** e no **Credly.com** utilizando seu **NOME COMPLETO**.\n"
                        f"2. Isso é fundamental para a emissão correta do seu certificado e badge.\n"
                        f"3. Caso já possua as contas, altere o seu nome no perfil para o formato completo antes de finalizar o curso."
                    )
                await interaction.followup.send(msg, ephemeral=True)
                return
                
            else:
                # Does not need Red Hat ID, so proceed and defer
                await interaction.response.defer(ephemeral=True)
                sucesso, msg = self._realizar_matricula(db_usuario_id, curso_id, None, None)
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

    @cmd_inscrever.autocomplete('curso_id')
    async def inscrever_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[int]]:
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Filtra apenas cursos que estão NO PERÍODO de inscrição
            query = """
                SELECT curso_id, curso_nome 
                FROM curso 
                WHERE curso_nome LIKE %s 
                AND curso_dt_inicio <= NOW() AND curso_dt_fim >= NOW()
                LIMIT 25
            """
            cursor.execute(query, (f"%{current}%",))
            rows = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            return [
                app_commands.Choice(name=row['curso_nome'], value=row['curso_id'])
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Erro no autocomplete de inscrição: {e}")
            return []

    @app_commands.command(
        name="enviar_certificado",
        description="Envia o certificado de um curso para validação e registro de horas."
    )
    @app_commands.describe(
        curso_id="O ID do curso (selecione na lista que aparece ao digitar)",
        certificado="O arquivo PDF do certificado"
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_enviar_certificado(self, interaction: discord.Interaction, curso_id: int, certificado: discord.Attachment):
        if not certificado.filename.lower().endswith(".pdf"):
            await interaction.response.send_message("❌ O arquivo enviado não é um PDF.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        conn = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(dictionary=True)

            # 1. Get User Data
            cursor.execute("SELECT usuario_id, usuario_nome FROM usuario WHERE usuario_discord_id = %s", (str(interaction.user.id),))
            user_data = cursor.fetchone()
            
            if not user_data:
                await interaction.followup.send("❌ Eu ainda não te conheço! Use `/identificar` primeiro.", ephemeral=True)
                return

            # 2. Get Course Data
            cursor.execute("SELECT curso_nome, curso_sinonimos FROM curso WHERE curso_id = %s", (curso_id,))
            course_data = cursor.fetchone()
            
            if not course_data:
                await interaction.followup.send("❌ Curso não encontrado.", ephemeral=True)
                return

            # 3. Read PDF
            pdf_bytes = await certificado.read()
            text = CertificadoService.extract_text(pdf_bytes)
            
            # 4. Validate
            is_valid, obs = CertificadoService.validate(
                text, 
                user_data['usuario_nome'], 
                course_data['curso_nome'],
                course_data.get('curso_sinonimos', '')
            )
            
            situacao = "Validado" if is_valid else "Concluído"
            
            # 5. Check if record exists in usuario_curso
            cursor.execute("SELECT usuario_curso_id FROM usuario_curso WHERE usuario_id = %s AND curso_id = %s", (user_data['usuario_id'], curso_id))
            uc_record = cursor.fetchone()

            if uc_record:
                sql = """
                    UPDATE usuario_curso 
                    SET usuario_curso_certificado = %s, 
                        usuario_curso_situacao = %s,
                        usuario_curso_obs = %s
                    WHERE usuario_curso_id = %s
                """
                cursor.execute(sql, (pdf_bytes, situacao, obs, uc_record['usuario_curso_id']))
            else:
                sql = """
                    INSERT INTO usuario_curso 
                    (usuario_id, curso_id, usuario_curso_certificado, usuario_curso_situacao, usuario_curso_obs, usuario_curso_dt_inscricao, usuario_curso_dt_solicitacao)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                dt_agora = datetime.now()
                cursor.execute(sql, (user_data['usuario_id'], curso_id, pdf_bytes, situacao, obs, dt_agora, dt_agora))

            conn.commit()

            # 6. Notify User
            if is_valid:
                msg = (
                    "✅ Seu certificado foi aceito e pré-validado por mim! "
                    "O professor vai procurar formalizar as horas de extensão até o final do semestre "
                    "com o setor responsável (sem garantias de sucesso)."
                )
            else:
                msg = (
                    "⚠️ O certificado foi recebido mas possui alguma inconsistência que será verificada pelo professor.\n"
                    "**Regras de validação:**\n"
                    "1) Nome no certificado deve ser o seu;\n"
                    "2) Nome do curso deve coincidir;\n"
                    "3) Mês/ano deve ser do semestre atual.\n\n"
                    f"**Motivo detectado:** {obs}"
                )
            
            await interaction.followup.send("✅ Certificado enviado com sucesso!", ephemeral=True)
            
            try:
                await interaction.user.send(msg)
            except discord.Forbidden:
                await interaction.followup.send(f"⚠️ Não consegui te enviar uma DM, mas seu certificado está como: **{situacao}**.", ephemeral=True)

        except Exception as e:
            logger.error(f"Erro em cmd_enviar_certificado: {e}")
            await interaction.followup.send(f"❌ Ocorreu um erro ao processar seu certificado.", ephemeral=True)
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()

    @cmd_enviar_certificado.autocomplete('curso_id')
    async def enviar_certificado_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[int]]:
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            query = "SELECT curso_id, curso_nome FROM curso WHERE curso_nome LIKE %s LIMIT 25"
            cursor.execute(query, (f"%{current}%",))
            rows = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            return [
                app_commands.Choice(name=row['curso_nome'], value=row['curso_id'])
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Erro no autocomplete: {e}")
            return []

    async def _validar_badge_playwright(self, badge_id: str):
        url = f"https://www.credly.com/badges/{badge_id}"
        
        # Inicia o motor do Playwright de forma assíncrona
        async with async_playwright() as p:
            # Lança o Chromium em modo headless (sem interface gráfica)
            browser = await p.chromium.launch(headless=True)
            
            # Forçamos o idioma en-US na sessão para as RegEx não quebrarem
            context = await browser.new_context(locale="en-US")
            page = await context.new_page()

            try:
                # Muda de networkidle para domcontentloaded (espera só a casca HTML baixar)
                await page.goto(url, wait_until="domcontentloaded")
                
                # O bote: espera o React renderizar especificamente o bloco que contém a data.
                # Se a conexão estiver rápida, isso resolve em 1 ou 2 segundos.
                await page.wait_for_selector("text=Date issued", timeout=15000)
                
                # Captura o HTML engordado com os dados reais
                html_renderizado = await page.content()
                
                # Passamos a bola para o BeautifulSoup limpar o HTML gerado
                soup = BeautifulSoup(html_renderizado, 'html.parser')
                texto_limpo = soup.get_text(separator=" ", strip=True)
                
                # 1. Extraindo o Nome do Curso
                titulo_pagina = soup.title.string if soup.title else ""
                nome_curso = titulo_pagina.replace(" - Credly", "").strip()
                
                # 2. Extraindo o Nome do Aluno (Estratégia do Link de Perfil)
                nome_aluno = None
                
                # Procura todas as tags <a> cujo href comece com "/users/" seguido de algum texto
                links_usuarios = soup.find_all('a', href=re.compile(r'^/users/[a-zA-Z0-9_-]+$'))
                
                for link in links_usuarios:
                    texto_link = link.get_text(strip=True)
                    # Filtramos para garantir que não vamos pegar botões de menu como "Sign In"
                    if texto_link and texto_link.lower() not in ['sign in', 'create account', 'forgot password']:
                        nome_aluno = texto_link
                        break
                        
                # Fallback de segurança: buscar no JSON-LD (motor de SEO invisível da página)
                if not nome_aluno:
                    scripts_seo = soup.find_all("script", type="application/ld+json")
                    for script in scripts_seo:
                        if script.string:
                            try:
                                import json
                                seo_data = json.loads(script.string)
                                # Caçando o objeto da credencial dentro dos dados estruturados do Google
                                if isinstance(seo_data, list):
                                    for item in seo_data:
                                        if item.get("@type") == "EducationalOccupationalCredential":
                                            nome_aluno = item.get("credentialAwardedTo", {}).get("name")
                            except:
                                continue
                    
                # 3. Extraindo e Formatando a Data
                data_formatada = None
                match_data = re.search(r'Date issued:\s*([A-Z][a-z]+ \d{1,2}, \d{4})', texto_limpo)
                if match_data:
                    data_ingles = match_data.group(1).strip()
                    try:
                        data_formatada = datetime.strptime(data_ingles, "%B %d, %Y").strftime("%d/%m/%Y")
                    except ValueError:
                        data_formatada = data_ingles

                return {
                    "valido": True,
                    "id_badge": badge_id,
                    "nome_aluno": nome_aluno,
                    "curso_capacitacao": nome_curso,
                    "data_conclusao": data_formatada,
                    "url_comprovante": url
                }

            except Exception as e:
                return {"valido": False, "mensagem": f"Erro na renderização: {str(e)}"}
            finally:
                await browser.close()

    def _normalize_string(self, text: str) -> str:
        if not text:
            return ""
        import unicodedata
        text = unicodedata.normalize('NFD', text)
        text = "".join([c for c in text if unicodedata.category(c) != 'Mn'])
        return " ".join(text.lower().split())

    @app_commands.command(
        name="informar_badge",
        description="Valida o curso do aluno através do link da badge do Credly."
    )
    @app_commands.describe(url="O link da sua badge do Credly (ex: https://www.credly.com/badges/...)")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_informar_badge(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer(ephemeral=True)

        # 1. Extrair badge_id da URL
        match = re.search(r'credly\.com/badges/([a-zA-Z0-9\-]+)', url)
        if not match:
            await interaction.followup.send(
                "❌ Link inválido. Envie um link válido do Credly (ex: `https://www.credly.com/badges/id-da-sua-badge`).",
                ephemeral=True
            )
            return

        badge_id = match.group(1)

        conn = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(dictionary=True)

            # 2. Buscar dados do aluno no DB
            cursor.execute("SELECT usuario_id, usuario_nome FROM usuario WHERE usuario_discord_id = %s", (str(interaction.user.id),))
            usuario = cursor.fetchone()

            if not usuario:
                await interaction.followup.send(
                    "❌ Eu ainda não te conheço! Você precisa usar o comando `/identificar` e `/validar` o seu vínculo com o sistema da disciplina primeiro.",
                    ephemeral=True
                )
                return

            # 3. Validar a badge usando Playwright
            res = await self._validar_badge_playwright(badge_id)
            if not res.get("valido"):
                await interaction.followup.send(
                    f"❌ A validação da sua badge falhou: {res.get('mensagem')}",
                    ephemeral=True
                )
                return

            nome_aluno = res.get("nome_aluno")
            curso_capacitacao = res.get("curso_capacitacao")
            data_conclusao = res.get("data_conclusao")
            url_comprovante = res.get("url_comprovante")

            # Regra 1: Valide se o "nome_aluno" corresponde ao nome completo do aluno
            nome_aluno_norm = self._normalize_string(nome_aluno)
            usuario_nome_norm = self._normalize_string(usuario['usuario_nome'])

            if nome_aluno_norm != usuario_nome_norm:
                await interaction.followup.send(
                    f"❌ A validação não pôde ser feita porque o nome na badge do Credly (`{nome_aluno}`) "
                    f"não corresponde exatamente ao seu nome completo cadastrado no sistema (`{usuario['usuario_nome']}`).\n\n"
                    f"💡 **Dica:** Você pode modificar seu nome de exibição a qualquer momento nas configurações de perfil do Credly "
                    f"e tentar submeter novamente a badge para validação.",
                    ephemeral=True
                )
                return

            # Regra 2: Veja se a data de conclusão está dentro do semestre.
            now = datetime.now()
            current_year = now.year
            is_first_semester = 1 <= now.month <= 6

            is_valid_date = False
            try:
                dt_conclusao = datetime.strptime(data_conclusao, "%d/%m/%Y")
                if dt_conclusao.year == current_year:
                    if is_first_semester and 1 <= dt_conclusao.month <= 6:
                        is_valid_date = True
                    elif not is_first_semester and 7 <= dt_conclusao.month <= 12:
                        is_valid_date = True
            except Exception:
                pass

            if not is_valid_date:
                semestre_str = "1º semestre" if is_first_semester else "2º semestre"
                await interaction.followup.send(
                    f"❌ A validação não pôde ser feita porque a data de conclusão da badge ({data_conclusao}) "
                    f"não pertence ao semestre letivo atual ({semestre_str} de {current_year}).",
                    ephemeral=True
                )
                return

            # Localizar o curso pelo curso_capacitacao
            cursor.execute("SELECT curso_id, curso_nome, curso_sinonimos FROM curso")
            cursos = cursor.fetchall()

            curso_match = None
            capacitacao_norm = self._normalize_string(curso_capacitacao)

            for c in cursos:
                # Compara com o nome oficial
                if self._normalize_string(c['curso_nome']) == capacitacao_norm:
                    curso_match = c
                    break
                # Compara com sinônimos (separados por vírgula)
                if c.get('curso_sinonimos'):
                    sinonimos = [self._normalize_string(s) for s in c['curso_sinonimos'].split(',') if s.strip()]
                    if capacitacao_norm in sinonimos:
                        curso_match = c
                        break

            # Se não encontrou por correspondência exata, faz correspondência parcial por substring
            if not curso_match:
                for c in cursos:
                    c_nome_norm = self._normalize_string(c['curso_nome'])
                    if c_nome_norm in capacitacao_norm or capacitacao_norm in c_nome_norm:
                        curso_match = c
                        break

            if not curso_match:
                await interaction.followup.send(
                    f"❌ Não foi possível encontrar nenhum curso cadastrado correspondente à capacitação `{curso_capacitacao}`.",
                    ephemeral=True
                )
                return

            curso_id = curso_match['curso_id']

            # Calcular data_conferencia como now() - 3 horas (para fuso UTC)
            dt_conferencia = datetime.utcnow() - timedelta(hours=3)

            # Verificar se já existe a matrícula (registro em usuario_curso)
            cursor.execute(
                "SELECT usuario_curso_id FROM usuario_curso WHERE usuario_id = %s AND curso_id = %s",
                (usuario['usuario_id'], curso_id)
            )
            uc_record = cursor.fetchone()

            if uc_record:
                sql = """
                    UPDATE usuario_curso 
                    SET usuario_curso_situacao = 'Validado',
                        usuario_curso_url_comprovante = %s,
                        usuario_curso_dt_conferencia = %s,
                        usuario_curso_obs = NULL
                    WHERE usuario_curso_id = %s
                """
                cursor.execute(sql, (url_comprovante, dt_conferencia, uc_record['usuario_curso_id']))
            else:
                sql = """
                    INSERT INTO usuario_curso 
                    (usuario_id, curso_id, usuario_curso_situacao, usuario_curso_url_comprovante, usuario_curso_dt_conferencia, usuario_curso_dt_solicitacao, usuario_curso_dt_inscricao)
                    VALUES (%s, %s, 'Validado', %s, %s, %s, %s)
                """
                dt_agora = datetime.utcnow()
                cursor.execute(sql, (usuario['usuario_id'], curso_id, url_comprovante, dt_conferencia, dt_agora, dt_agora))

            conn.commit()

            await interaction.followup.send(
                f"✅ **Sua badge foi validada com sucesso!**\n\n"
                f"🎓 **Curso:** {curso_match['curso_nome']}\n"
                f"👤 **Aluno:** {usuario['usuario_nome']}\n"
                f"📅 **Conclusão:** {data_conclusao}\n"
                f"🔗 **URL:** {url_comprovante}",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Erro em cmd_informar_badge: {e}")
            await interaction.followup.send(
                "❌ Ocorreu um erro interno ao processar a validação da sua badge. Tente novamente mais tarde.",
                ephemeral=True
            )
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()

async def setup(bot: commands.Bot):
    await bot.add_cog(CursosCog(bot))
