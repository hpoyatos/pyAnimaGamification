import logging
import os
import random
import string
from datetime import datetime, timedelta, timezone
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

class EmailModal(discord.ui.Modal, title='Identificação Comunidade Ânima'):
    
    email_input = discord.ui.TextInput(
        label='E-mail Acadêmico ou Pessoal (Ulife)',
        placeholder='ex: ra@ulife.com.br ou seu_email@gmail.com',
        style=discord.TextStyle.short,
        required=True,
        min_length=5,
        max_length=150
    )

    def __init__(self, bot: commands.Bot, conn_factory):
        super().__init__()
        self.bot = bot
        self.conn_factory = conn_factory
        logger.info("Modal de identificação carregado.")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        email_digitado = self.email_input.value.strip().lower()
        
        conn = None
        try:
            conn = self.conn_factory()
            if not conn.is_connected():
                raise RuntimeError("Falha ao conectar no DB dentro do Modal.")
            
            cur = conn.cursor(dictionary=True)
            
            # Buscar usuário no DB por e-mail acadêmico ou e-mail pessoal
            sql_find = """
                SELECT usuario_id, usuario_nome, usuario_email, usuario_email_pessoal, usuario_validado_code 
                FROM usuario 
                WHERE usuario_email = %s OR usuario_email_pessoal = %s
            """
            cur.execute(sql_find, (email_digitado, email_digitado))
            row = cur.fetchone()
            
            if not row:
                cur.close()
                await interaction.followup.send(
                    f"⚠️ O e-mail `{email_digitado}` não foi localizado em nossa base pré-cadastrada.\n\n"
                    "Para solicitar o seu cadastro manual, por favor clique no botão abaixo para preencher seus dados (Nome, RA, IES e Curso).",
                    view=SolicitarCadastroView(self.bot, self.conn_factory, email_digitado),
                    ephemeral=True
                )
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
            
            # Enviar e-mail de validação
            sucesso_email = send_validation_email(email_digitado, codigo_gerado, usuario_nome)
            
            if sucesso_email:
                msg = (
                    f"✅ E-mail enviado para `{email_digitado}` com sucesso!\n\n"
                    "Abra sua caixa de entrada (verifique também a pasta de spam) e pegue o código de 6 caracteres.\n"
                    "Depois volte aqui no Discord e digite o comando: `/validar [seu_codigo]`"
                )
            else:
                msg = "❌ Ocorreu um erro ao tentar enviar o e-mail pelo servidor. Por favor, tente novamente mais tarde ou contate o professor."
                
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
        logger.info("Cog de identificação carregado.")

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
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_identificar(self, interaction: discord.Interaction):
        logger.info("Comando /identificar invocado.")
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
                msg = f"Ei, {user_row['usuario_nome']}, você já está identificado(a) comigo!"
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


    async def _atribuir_cargos_usuario(self, interaction: discord.Interaction, discord_user_id_str: str, ies_sigla: str = None, curso_sigla: str = None, conn=None):
        """Atribui ao usuário a role padrão de validação, a role de IES (se houver) e a role de Curso (se houver)."""
        roles_to_assign = []

        # 1. Role padrão de validação
        role_val_id = os.getenv("DISCORD_VALIDATED_ROLE_ID")
        if role_val_id:
            try:
                roles_to_assign.append(int(role_val_id))
            except ValueError:
                pass

        # Conectar se não recebemos conexão pronta
        local_conn = False
        if not conn:
            try:
                conn = self._get_db_connection()
                local_conn = True
            except Exception as e:
                logger.error(f"Erro ao conectar ao DB em _atribuir_cargos_usuario: {e}")

        if conn and conn.is_connected():
            cur = conn.cursor(dictionary=True)
            # 2. Busca role de IES se ies_sigla existir
            if ies_sigla:
                try:
                    cur.execute("SELECT ies_discord_role FROM anima_ies WHERE ies_sigla = %s", (ies_sigla,))
                    row_ies = cur.fetchone()
                    if row_ies and row_ies.get("ies_discord_role"):
                        roles_to_assign.append(int(row_ies["ies_discord_role"]))
                except Exception as e:
                    logger.error(f"Erro ao buscar ies_discord_role para {ies_sigla}: {e}")

            # 3. Busca role de Curso se curso_sigla existir
            if curso_sigla:
                try:
                    cur.execute("SELECT curso_role FROM anima_curso WHERE curso_sigla = %s", (curso_sigla,))
                    row_curso = cur.fetchone()
                    if row_curso and row_curso.get("curso_role"):
                        roles_to_assign.append(int(row_curso["curso_role"]))
                except Exception as e:
                    logger.error(f"Erro ao buscar curso_role para {curso_sigla}: {e}")

            # 4. Busca role(s) de UC se o usuário estiver matriculado em anima_uc_usuario
            try:
                sql_uc_roles = """
                    SELECT uc.uc_discord_role 
                    FROM anima_uc uc
                    INNER JOIN anima_uc_usuario ucu ON uc.uc_id = ucu.uc_id
                    INNER JOIN usuario u ON ucu.usuario_id = u.usuario_id
                    WHERE u.usuario_discord_id = %s
                """
                cur.execute(sql_uc_roles, (discord_user_id_str,))
                uc_rows = cur.fetchall() or []
                for row_uc in uc_rows:
                    if row_uc.get("uc_discord_role"):
                        try:
                            roles_to_assign.append(int(row_uc["uc_discord_role"]))
                        except ValueError:
                            pass
            except Exception as e:
                logger.error(f"Erro ao buscar uc_discord_role para o usuario_discord_id {discord_user_id_str}: {e}")

            cur.close()
            if local_conn:
                try: conn.close()
                except: pass

        # Remover duplicados mantendo ordem
        roles_to_assign = list(dict.fromkeys(roles_to_assign))
        if not roles_to_assign:
            return False

        user_id_int = int(discord_user_id_str)
        atribuiu_algum = False

        # Aplica os cargos no Discord
        if interaction.guild:
            member = interaction.guild.get_member(user_id_int)
            if not member:
                try:
                    member = await interaction.guild.fetch_member(user_id_int)
                except Exception:
                    pass

            if member:
                for rid in roles_to_assign:
                    role = interaction.guild.get_role(rid)
                    if role:
                        try:
                            await member.add_roles(role, reason="Atribuição de cargos de Validação/IES/Curso")
                            atribuiu_algum = True
                        except Exception as e:
                            logger.error(f"Erro ao adicionar role {rid} para usuário {discord_user_id_str}: {e}")
        else:
            # Caso seja invocado por DM, procura o usuário nas guildas do bot
            for guild in self.bot.guilds:
                for rid in roles_to_assign:
                    role = guild.get_role(rid)
                    if role:
                        try:
                            member = await guild.fetch_member(user_id_int)
                            if member:
                                await member.add_roles(role, reason="Atribuição via DM de Validação/IES/Curso")
                                atribuiu_algum = True
                        except Exception:
                            pass

        return atribuiu_algum

    @app_commands.command(
        name="validar",
        description="Insira o código de validação que você recebeu por e-mail."
    )
    @app_commands.describe(codigo="Código de 6 caracteres enviado para o seu e-mail")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_validar(self, interaction: discord.Interaction, codigo: str):
        logger.info("Comando /validar invocado.")
        codigo = codigo.strip().upper()
        
        if len(codigo) != 6:
            await interaction.response.send_message("❌ Formato inválido. O código possui exatamente 6 caracteres alfanuméricos.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        
        discord_user_id = str(interaction.user.id)
        discord_name = interaction.user.global_name or interaction.user.name

        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(dictionary=True)
            
            sql_find = "SELECT usuario_id, usuario_nome, ies_sigla, curso_sigla FROM usuario WHERE usuario_validado_code = %s"
            cur.execute(sql_find, (codigo,))
            row = cur.fetchone()
            
            if not row:
                cur.close()
                await interaction.followup.send("❌ Código de validação inválido ou não encontrado.", ephemeral=True)
                return
                
            usuario_id = row['usuario_id']
            usuario_nome = row['usuario_nome']
            ies_sigla = row.get('ies_sigla')
            curso_sigla = row.get('curso_sigla')
            
            # Update user making them valid
            tz_br = timezone(timedelta(hours=-3))
            now_str = datetime.now(tz_br).strftime('%Y-%m-%d %H:%M:%S')
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

            # Lançar pontuação de validação/identificação (parametrizada no .env)
            pontos_valor_str = os.getenv("PONTOS_IDENTIFICACAO_VALOR", "0.10")
            pontos_desc = os.getenv("PONTOS_IDENTIFICACAO_DESCRICAO", "Identificou-se com o JocastaBOT!")
            try:
                pontos_valor = float(pontos_valor_str)
            except ValueError:
                pontos_valor = 0.10

            uc_id_para_ponto = None
            try:
                cur.execute("SELECT uc_id FROM anima_uc_usuario WHERE usuario_id = %s LIMIT 1", (usuario_id,))
                row_uc_id = cur.fetchone()
                if row_uc_id:
                    uc_id_para_ponto = row_uc_id.get("uc_id")
            except Exception as e_uc_fetch:
                logger.error(f"Erro ao buscar UC do usuario para lançamento de pontos: {e_uc_fetch}")

            if not uc_id_para_ponto:
                try:
                    cur.execute("SELECT uc_id FROM anima_uc LIMIT 1")
                    row_first_uc = cur.fetchone()
                    if row_first_uc:
                        uc_id_para_ponto = row_first_uc.get("uc_id")
                except Exception:
                    pass

            if uc_id_para_ponto:
                try:
                    sql_ponto = """
                        INSERT INTO pontuacao (usuario_id, uc_id, pontuacao, data_pontuacao, pontuacao_descricao)
                        VALUES (%s, %s, %s, %s, %s)
                    """
                    cur.execute(sql_ponto, (usuario_id, uc_id_para_ponto, pontos_valor, now_str, pontos_desc))
                    conn.commit()
                    logger.info(f"Pontuação de {pontos_valor} lançada para usuario_id={usuario_id} por validação.")
                except Exception as e_ponto:
                    logger.error(f"Erro ao lançar pontuação de validação para usuario_id={usuario_id}: {e_ponto}")
            
            # Atribui Cargos (Padrão, IES, Curso e UCs)
            await self._atribuir_cargos_usuario(interaction, discord_user_id, ies_sigla, curso_sigla, conn=conn)

            # Busca nomes completos de IES, Curso e UCs para enriquecer a mensagem privada
            ies_nome = None
            curso_nome = None
            ucs_lista = []

            if ies_sigla:
                try:
                    cur.execute("SELECT ies_nome FROM anima_ies WHERE ies_sigla = %s", (ies_sigla,))
                    row_ies = cur.fetchone()
                    if row_ies: ies_nome = row_ies.get('ies_nome')
                except Exception as e:
                    logger.error(f"Erro ao buscar ies_nome: {e}")

            if curso_sigla:
                try:
                    cur.execute("SELECT curso_nome FROM anima_curso WHERE curso_sigla = %s", (curso_sigla,))
                    row_c = cur.fetchone()
                    if row_c: curso_nome = row_c.get('curso_nome')
                except Exception as e:
                    logger.error(f"Erro ao buscar curso_nome: {e}")

            try:
                sql_ucs = """
                    SELECT uc.uc_nome 
                    FROM anima_uc uc
                    INNER JOIN anima_uc_usuario ucu ON uc.uc_id = ucu.uc_id
                    WHERE ucu.usuario_id = %s
                """
                cur.execute(sql_ucs, (usuario_id,))
                uc_rows = cur.fetchall() or []
                ucs_lista = [r['uc_nome'] for r in uc_rows if r.get('uc_nome')]
            except Exception as e:
                logger.error(f"Erro ao buscar ucs do usuario: {e}")

            cur.close()

            await interaction.followup.send(
                f"🎉 Parabéns, **{usuario_nome}**!\n"
                f"Sua conta foi vinculada e validada com sucesso! Seus cargos do Discord foram atribuídos.",
                ephemeral=True
            )

            # Envia Mensagem Privada (DM) ao Usuário
            try:
                detalhes = []
                if ies_nome or ies_sigla:
                    detalhes.append(f"🏛️ **IES:** {ies_nome or ies_sigla} (`{ies_sigla}`)")
                if curso_nome or curso_sigla:
                    detalhes.append(f"📚 **Curso:** {curso_nome or curso_sigla} (`{curso_sigla}`)")
                if ucs_lista:
                    detalhes.append(f"📖 **Unidade(s) Curricular(es):** {', '.join(ucs_lista)}")

                str_detalhes = "\n".join(detalhes) if detalhes else "Nenhuma IES/Curso/UC vinculada no momento."

                msg_dm = (
                    f"Olá, **{usuario_nome}**! 👋\n\n"
                    f"Sua identificação na comunidade foi concluída com sucesso! 🎉\n\n"
                    f"**Suas informações identificadas:**\n"
                    f"{str_detalhes}\n\n"
                    f"Seus cargos no servidor já foram atribuídos. Muito obrigado por realizar a sua identificação! 🙏✨\n"
                    f"Agora você já pode utilizar comandos como `/pontos` e `/catalogo` aqui na nossa conversa privada."
                )

                # Tenta enviar a mensagem via DM do usuário
                await interaction.user.send(msg_dm)
                logger.info(f"Mensagem de confirmação DM enviada com sucesso para {usuario_nome} ({discord_name}).")
            except Exception as dm_err:
                logger.warning(f"Não foi possível enviar mensagem privada para {discord_name}: {dm_err}")
            
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

    @app_commands.command(
        name="add_user",
        description="[Admin] Cadastra e valida um usuário diretamente no sistema."
    )
    @app_commands.describe(
        usuario_discord="Membro do Discord a ser cadastrado",
        nome="Nome completo do usuário",
        email="E-mail do usuário",
        ra="RA do usuário (opcional)"
    )
    @app_commands.allowed_installs(guilds=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_add_user(
        self, 
        interaction: discord.Interaction, 
        usuario_discord: discord.User, 
        nome: str, 
        email: str, 
        ra: str = None
    ):
        logger.info(f"Comando /add_user invocado por {interaction.user} (ID: {interaction.user.id}).")
        
        # Validação de Administrador (Admin no server, Dono de qualquer server do bot, ou ID na env DISCORD_ADMIN_USER_ID)
        is_admin = False
        user_id_str = str(interaction.user.id)

        # 1. Checa env DISCORD_ADMIN_USER_ID
        admin_env_id = os.getenv("DISCORD_ADMIN_USER_ID")
        if admin_env_id and user_id_str == admin_env_id.strip():
            is_admin = True

        # 2. Checa se é Member com permissão de Admin ou Dono da Guild atual
        if not is_admin and isinstance(interaction.user, discord.Member):
            if interaction.user.guild_permissions.administrator:
                is_admin = True
            elif interaction.guild and interaction.guild.owner_id == interaction.user.id:
                is_admin = True

        # 3. Checa se o usuário é dono de alguma das guildas onde o bot está presente (funciona inclusive em DM)
        if not is_admin:
            for guild in self.bot.guilds:
                if guild.owner_id == interaction.user.id:
                    is_admin = True
                    break
                member = guild.get_member(interaction.user.id)
                if member and member.guild_permissions.administrator:
                    is_admin = True
                    break

        if not is_admin:
            await interaction.response.send_message(
                "❌ **Acesso Negado**: Este comando é restrito a administradores do sistema.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        discord_user_id = str(usuario_discord.id)
        discord_name = usuario_discord.global_name or usuario_discord.name
        nome = nome.strip()
        email = email.strip().lower()
        ra = ra.strip() if ra else None

        tz_br = timezone(timedelta(hours=-3))
        now_str = datetime.now(tz_br).strftime('%Y-%m-%d %H:%M:%S')

        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(dictionary=True)

            # Verifica se já existe por e-mail ou discord_id
            sql_check = "SELECT usuario_id, usuario_email, usuario_discord_id FROM usuario WHERE usuario_email = %s OR usuario_discord_id = %s"
            cur.execute(sql_check, (email, discord_user_id))
            existente = cur.fetchone()

            if existente:
                usuario_id = existente['usuario_id']
                sql_update = """
                    UPDATE usuario 
                    SET usuario_discord_id = %s,
                        usuario_nome = %s,
                        usuario_email = %s,
                        usuario_ra = COALESCE(%s, usuario_ra),
                        usuario_discord_name = %s,
                        usuario_validado = 1,
                        usuario_validado_data = COALESCE(usuario_validado_data, %s)
                    WHERE usuario_id = %s
                """
                cur.execute(sql_update, (discord_user_id, nome, email, ra, discord_name, now_str, usuario_id))
                conn.commit()
                acao_txt = "atualizado e validado"
            else:
                # Insere o novo usuário validado
                sql_insert = """
                    INSERT INTO usuario 
                    (usuario_discord_id, usuario_nome, usuario_email, usuario_ra, usuario_discord_name, usuario_validado, usuario_validado_data)
                    VALUES (%s, %s, %s, %s, %s, 1, %s)
                """
                cur.execute(sql_insert, (discord_user_id, nome, email, ra, discord_name, now_str))
                conn.commit()
                usuario_id = cur.lastrowid
                acao_txt = "cadastrado e validado"

            cur.close()

            # Atribui os Cargos (Role Padrão, IES e Curso) ao usuário no Discord
            role_concedida = await self._atribuir_cargos_usuario(
                interaction, 
                discord_user_id, 
                ies_sigla=existente.get('ies_sigla') if existente else None, 
                curso_sigla=existente.get('curso_sigla') if existente else None,
                conn=conn
            )
            cur.close()

            role_status_msg = " Cargos do Discord atribuídos com sucesso!" if role_concedida else " ⚠️ Não foi possível atribuir os cargos (verifique se o usuário está no servidor e as roles cadastradas)."

            msg_sucesso = (
                f"✅ **Usuário {acao_txt} com sucesso!** (ID: `{usuario_id}`)\n\n"
                f"👤 **Nome:** {nome}\n"
                f"📧 **E-mail:** `{email}`\n"
                f"🆔 **RA:** `{ra or 'Mantido/N/A'}`\n"
                f"🎮 **Discord:** {usuario_discord.mention} (`{discord_name}` / ID: `{discord_user_id}`)\n"
                f"📅 **Data Atualização:** {now_str}\n"
                f"{role_status_msg}"
            )
            await interaction.followup.send(msg_sucesso, ephemeral=True)

            # Audit logging
            auditoria_id_str = os.getenv("DISCORD_AUDITORIA_CHANNEL_ID")
            if auditoria_id_str:
                try:
                    auditoria_channel = self.bot.get_channel(int(auditoria_id_str))
                    if auditoria_channel:
                        await auditoria_channel.send(
                            f"🛠️ **[ADMIN]** {interaction.user.mention} cadastrou e validou o usuário **{nome}** ({usuario_discord.mention})!"
                        )
                except Exception as audit_err:
                    logger.error(f"Erro ao enviar log de auditoria em cmd_add_user: {audit_err}")

        except Exception as e:
            logger.exception("Erro durante execução do comando '/add_user'.")
            if conn: conn.rollback()
            await interaction.followup.send("❌ Ocorreu um erro interno ao cadastrar o usuário.", ephemeral=True)
        finally:
            if conn:
                try: conn.close()
                except: pass

    @app_commands.command(
        name="aprovar",
        description="[Admin] Aprova a solicitação de cadastro manual de um usuário pendente."
    )
    @app_commands.describe(usuario_discord="Membro do Discord a ser aprovado")
    @app_commands.allowed_installs(guilds=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_aprovar(self, interaction: discord.Interaction, usuario_discord: discord.User):
        logger.info(f"Comando /aprovar invocado por {interaction.user} para {usuario_discord}.")

        # Validação de Administrador (Admin no server, Dono de qualquer server do bot, ou ID na env DISCORD_ADMIN_USER_ID)
        is_admin = False
        user_id_str = str(interaction.user.id)

        # 1. Checa env DISCORD_ADMIN_USER_ID
        admin_env_id = os.getenv("DISCORD_ADMIN_USER_ID")
        if admin_env_id and user_id_str == admin_env_id.strip():
            is_admin = True

        # 2. Checa se é Member com permissão de Admin ou Dono da Guild atual
        if not is_admin and isinstance(interaction.user, discord.Member):
            if interaction.user.guild_permissions.administrator:
                is_admin = True
            elif interaction.guild and interaction.guild.owner_id == interaction.user.id:
                is_admin = True

        # 3. Checa se o usuário é dono de alguma das guildas onde o bot está presente (funciona inclusive em DM)
        if not is_admin:
            for guild in self.bot.guilds:
                if guild.owner_id == interaction.user.id:
                    is_admin = True
                    break
                # Também checa se no servidor o membro possui permissão de administrador
                member = guild.get_member(interaction.user.id)
                if member and member.guild_permissions.administrator:
                    is_admin = True
                    break

        if not is_admin:
            await interaction.response.send_message(
                "❌ **Acesso Negado**: Este comando é restrito a administradores do sistema.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        discord_user_id = str(usuario_discord.id)
        discord_name = usuario_discord.global_name or usuario_discord.name

        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(dictionary=True)

            # Busca o usuário no banco pelo discord_id ou pelo e-mail
            sql_check = "SELECT usuario_id, usuario_nome, ies_sigla, curso_sigla, usuario_validado FROM usuario WHERE usuario_discord_id = %s"
            cur.execute(sql_check, (discord_user_id,))
            user_row = cur.fetchone()

            if not user_row:
                cur.close()
                await interaction.followup.send(
                    f"⚠️ Nenhum cadastro pendente encontrado para {usuario_discord.mention} (`ID: {discord_user_id}`).",
                    ephemeral=True
                )
                return

            usuario_id = user_row['usuario_id']
            usuario_nome = user_row['usuario_nome']
            ies_sigla = user_row.get('ies_sigla')
            curso_sigla = user_row.get('curso_sigla')

            tz_br = timezone(timedelta(hours=-3))
            now_str = datetime.now(tz_br).strftime('%Y-%m-%d %H:%M:%S')

            # Atualiza usuario_validado = 1
            sql_update = """
                UPDATE usuario 
                SET usuario_validado = 1,
                    usuario_validado_data = COALESCE(usuario_validado_data, %s)
                WHERE usuario_id = %s
            """
            cur.execute(sql_update, (now_str, usuario_id))
            conn.commit()

            # Atribui os Cargos no Discord (Padrão, IES, Curso, UCs)
            await self._atribuir_cargos_usuario(interaction, discord_user_id, ies_sigla, curso_sigla, conn=conn)

            # Nomes de IES, Curso e UCs para a DM
            ies_nome = None
            curso_nome = None
            ucs_lista = []

            if ies_sigla:
                try:
                    cur.execute("SELECT ies_nome FROM anima_ies WHERE ies_sigla = %s", (ies_sigla,))
                    r = cur.fetchone()
                    if r: ies_nome = r.get('ies_nome')
                except Exception: pass

            if curso_sigla:
                try:
                    cur.execute("SELECT curso_nome FROM anima_curso WHERE curso_sigla = %s", (curso_sigla,))
                    r = cur.fetchone()
                    if r: curso_nome = r.get('curso_nome')
                except Exception: pass

            try:
                sql_ucs = "SELECT uc.uc_nome FROM anima_uc uc INNER JOIN anima_uc_usuario ucu ON uc.uc_id = ucu.uc_id WHERE ucu.usuario_id = %s"
                cur.execute(sql_ucs, (usuario_id,))
                ucs_lista = [r['uc_nome'] for r in (cur.fetchall() or []) if r.get('uc_nome')]
            except Exception: pass

            cur.close()

            await interaction.followup.send(
                f"✅ **Cadastro aprovado com sucesso para {usuario_discord.mention}!** (ID: `{usuario_id}`)",
                ephemeral=True
            )

            # Envia DM de Boas-vindas/Validação ao Usuário Aprovado
            try:
                detalhes = []
                if ies_nome or ies_sigla: detalhes.append(f"🏛️ **IES:** {ies_nome or ies_sigla} (`{ies_sigla}`)")
                if curso_nome or curso_sigla: detalhes.append(f"📚 **Curso:** {curso_nome or curso_sigla} (`{curso_sigla}`)")
                if ucs_lista: detalhes.append(f"📖 **Unidade(s) Curricular(es):** {', '.join(ucs_lista)}")

                str_detalhes = "\n".join(detalhes) if detalhes else "Nenhuma IES/Curso/UC vinculada no momento."

                msg_dm = (
                    f"Olá, **{usuario_nome}**! 👋\n\n"
                    f"Seu cadastro no sistema de Gamificação foi **aprovado pelo Prof. Henrique Poyatos**! 🎉\n\n"
                    f"**Suas informações validadas:**\n"
                    f"{str_detalhes}\n\n"
                    f"Seus cargos no servidor já foram atribuídos. Muito obrigado por realizar a sua identificação! 🙏✨\n"
                    f"Agora você já pode utilizar todos os comandos liberados como `/pontos` e `/catalogo`."
                )
                await usuario_discord.send(msg_dm)
            except Exception as dm_err:
                logger.warning(f"Não foi possível enviar DM de aprovação para {usuario_discord}: {dm_err}")

            # Audit logging
            auditoria_id_str = os.getenv("DISCORD_AUDITORIA_CHANNEL_ID")
            if auditoria_id_str:
                try:
                    auditoria_channel = self.bot.get_channel(int(auditoria_id_str))
                    if auditoria_channel:
                        await auditoria_channel.send(
                            f"✅ **[APROVAÇÃO]** {interaction.user.mention} aprovou o cadastro do aluno **{usuario_nome}** ({usuario_discord.mention})!"
                        )
                except Exception as audit_err:
                    logger.error(f"Erro ao enviar log de auditoria em cmd_aprovar: {audit_err}")

        except Exception as e:
            logger.exception("Erro durante execução do comando '/aprovar'.")
            if conn: conn.rollback()
            await interaction.followup.send("❌ Ocorreu um erro interno ao aprovar o cadastro.", ephemeral=True)
        finally:
            if conn:
                try: conn.close()
                except: pass


class IesCursoSelectView(discord.ui.View):
    """View contendo os Selects (ComboBox) para selecionar a IES e o Curso provenientes do MariaDB."""

    def __init__(self, bot: commands.Bot, conn_factory, email_digitado: str, nome: str, ra: str, email_pessoal: str, ies_options: list, curso_options: list):
        super().__init__(timeout=300)
        self.bot = bot
        self.conn_factory = conn_factory
        self.email_digitado = email_digitado
        self.nome = nome
        self.ra = ra
        self.email_pessoal = email_pessoal

        self.selected_ies = None
        self.selected_curso = None

        # Select para IES
        ies_select_options = [
            discord.SelectOption(label=f"{row['ies_nome']} ({row['ies_sigla']})", value=row['ies_sigla'], description=f"Sigla: {row['ies_sigla']}")
            for row in ies_options[:25] # Limite da API do Discord (max 25)
        ]
        self.ies_select = discord.ui.Select(
            placeholder="Escolha a sua IES (Faculdade/Universidade)...",
            min_values=1,
            max_values=1,
            options=ies_select_options
        )
        self.ies_select.callback = self.on_ies_select
        self.add_item(self.ies_select)

        # Select para Curso
        curso_select_options = [
            discord.SelectOption(label=f"{row['curso_nome'][:50]} ({row['curso_sigla']})", value=row['curso_sigla'], description=f"Sigla: {row['curso_sigla']}")
            for row in curso_options[:25]
        ]
        self.curso_select = discord.ui.Select(
            placeholder="Escolha a sigla do seu Curso...",
            min_values=1,
            max_values=1,
            options=curso_select_options
        )
        self.curso_select.callback = self.on_curso_select
        self.add_item(self.curso_select)

    async def on_ies_select(self, interaction: discord.Interaction):
        self.selected_ies = self.ies_select.values[0]
        await interaction.response.defer()

    async def on_curso_select(self, interaction: discord.Interaction):
        self.selected_curso = self.curso_select.values[0]
        await interaction.response.defer()

    @discord.ui.button(label="Finalizar Cadastro", style=discord.ButtonStyle.success, emoji="✅")
    async def btn_confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_ies or not self.selected_curso:
            await interaction.response.send_message("⚠️ Por favor, selecione **tanto a IES quanto o Curso** nas opções acima antes de finalizar.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        nome = self.nome
        ra = self.ra
        email_pessoal = self.email_pessoal
        ies = self.selected_ies
        curso = self.selected_curso

        # Determina e-mail acadêmico vs pessoal
        if "ulife.com.br" in self.email_digitado:
            email_acad = self.email_digitado
        else:
            email_acad = self.email_digitado
            if not email_pessoal:
                email_pessoal = self.email_digitado

        discord_user_id = str(interaction.user.id)
        discord_name = interaction.user.global_name or interaction.user.name

        tz_br = timezone(timedelta(hours=-3))
        now_str = datetime.now(tz_br).strftime('%Y-%m-%d %H:%M:%S')

        conn = None
        try:
            conn = self.conn_factory()
            cur = conn.cursor(dictionary=True)

            # Insere o usuário com usuario_validado = 0 (pendente de aprovação)
            sql_insert = """
                INSERT INTO usuario 
                (usuario_discord_id, usuario_nome, usuario_email, usuario_ra, usuario_discord_name, usuario_validado)
                VALUES (%s, %s, %s, %s, %s, 0)
                ON DUPLICATE KEY UPDATE
                    usuario_nome = VALUES(usuario_nome),
                    usuario_ra = COALESCE(VALUES(usuario_ra), usuario_ra),
                    usuario_discord_name = VALUES(usuario_discord_name)
            """
            cur.execute(sql_insert, (discord_user_id, nome, email_acad, ra, discord_name))
            conn.commit()
            cur.close()

            await interaction.followup.send(
                f"📋 **Solicitação enviada com sucesso, {nome}!**\n\n"
                f"🏛️ **IES Selecionada:** `{ies}`\n"
                f"📚 **Curso Selecionado:** `{curso}`\n\n"
                f"Sua solicitação foi registrada no sistema e encaminhada para validação manual com o **Prof. Henrique Poyatos**.\n"
                f"Assim que for aprovada, você receberá uma confirmação aqui no privado com a liberação dos seus cargos no servidor!",
                ephemeral=True
            )

            # Envia dados completos para o canal de Auditoria
            auditoria_id_str = os.getenv("DISCORD_AUDITORIA_CHANNEL_ID")
            if auditoria_id_str:
                try:
                    auditoria_channel = self.bot.get_channel(int(auditoria_id_str))
                    if auditoria_channel:
                        msg_audit = (
                            f"📌 **[SOLICITAÇÃO DE CADASTRO MANUAL PENDENTE]**\n\n"
                            f"👤 **Nome:** {nome}\n"
                            f"📧 **E-mail Acadêmico:** `{email_acad}`\n"
                            f"✉️ **E-mail Pessoal:** `{email_pessoal or 'N/A'}`\n"
                            f"🆔 **RA:** `{ra or 'N/A'}`\n"
                            f"🏛️ **IES:** `{ies}` | 📚 **Curso:** `{curso}`\n"
                            f"🎮 **Discord:** {interaction.user.mention} (`{discord_name}` / ID: `{discord_user_id}`)\n\n"
                            f"🔑 **Para aprovar este cadastro, use o comando:**\n"
                            f"`/aprovar usuario_discord:{interaction.user.mention}`"
                        )
                        await auditoria_channel.send(msg_audit)
                except Exception as audit_err:
                    logger.error(f"Erro ao enviar solicitação pendente para o canal de auditoria: {audit_err}")

        except Exception as e:
            logger.exception("Erro processando solicitação de cadastro manual.")
            if conn: conn.rollback()
            await interaction.followup.send("❌ Ocorreu um erro interno ao registrar sua solicitação. Tente novamente.", ephemeral=True)
        finally:
            if conn:
                try: conn.close()
                except: pass


class SolicitarCadastroView(discord.ui.View):
    def __init__(self, bot: commands.Bot, conn_factory, email_digitado: str):
        super().__init__(timeout=180)
        self.bot = bot
        self.conn_factory = conn_factory
        self.email_digitado = email_digitado

    @discord.ui.button(label="Preencher Dados Pessoais", style=discord.ButtonStyle.primary, emoji="📝")
    async def btn_preencher(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CadastroPendenteModal(self.bot, self.conn_factory, self.email_digitado))


class CadastroPendenteModal(discord.ui.Modal, title='Dados do Usuário (Passo 1/2)'):

    nome_input = discord.ui.TextInput(
        label='Nome Completo',
        placeholder='Seu nome completo',
        style=discord.TextStyle.short,
        required=True,
        max_length=120
    )
    ra_input = discord.ui.TextInput(
        label='RA (Registro Acadêmico)',
        placeholder='Ex: 12345678 (deixe em branco se não houver)',
        style=discord.TextStyle.short,
        required=False,
        max_length=20
    )
    email_pessoal_input = discord.ui.TextInput(
        label='E-mail Pessoal',
        placeholder='ex: seu_email@gmail.com (se diferente do informado)',
        style=discord.TextStyle.short,
        required=False,
        max_length=150
    )

    def __init__(self, bot: commands.Bot, conn_factory, email_digitado: str):
        super().__init__()
        self.bot = bot
        self.conn_factory = conn_factory
        self.email_digitado = email_digitado

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        nome = self.nome_input.value.strip()
        ra = self.ra_input.value.strip() if self.ra_input.value else None
        email_pessoal = self.email_pessoal_input.value.strip().lower() if self.email_pessoal_input.value else None

        # Buscar opções de IES e Cursos no MariaDB
        ies_options = []
        curso_options = []

        conn = None
        try:
            conn = self.conn_factory()
            cur = conn.cursor(dictionary=True)
            
            cur.execute("SELECT ies_sigla, ies_nome FROM anima_ies ORDER BY ies_nome ASC")
            ies_options = cur.fetchall() or []

            cur.execute("SELECT curso_sigla, curso_nome FROM anima_curso ORDER BY curso_nome ASC")
            curso_options = cur.fetchall() or []

            cur.close()
        except Exception as e:
            logger.error(f"Erro ao buscar opções de IES/Curso no DB: {e}")
        finally:
            if conn:
                try: conn.close()
                except: pass

        if not ies_options or not curso_options:
            await interaction.followup.send("❌ Erro ao carregar a lista de IES e Cursos do banco de dados.", ephemeral=True)
            return

        view_selects = IesCursoSelectView(
            self.bot, 
            self.conn_factory, 
            self.email_digitado, 
            nome, 
            ra, 
            email_pessoal, 
            ies_options, 
            curso_options
        )

        await interaction.followup.send(
            f"👍 **Olá {nome}!** Agora selecione sua **IES** e **Curso** nas caixas de seleção abaixo e clique em **Finalizar Cadastro**:",
            view=view_selects,
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(IdentificarCog(bot))


