import os
import re
import logging
import discord
from discord import app_commands
from discord.ext import commands
import mysql.connector

logger = logging.getLogger("cogs.perfil")

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "db"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "anima"),
        charset="utf8mb4"
    )

def is_valid_linkedin_url(url: str) -> bool:
    """Valida se uma URL é legitimamente do LinkedIn."""
    if not url:
        return True
    pattern = r"^https?:\/\/(www\.)?linkedin\.com\/(in|company|school)\/[a-zA-Z0-9_\-\.\%\u00C0-\u00FF]+\/?.*$"
    return bool(re.match(pattern, url.strip(), re.IGNORECASE))

def format_instagram_handle(handle: str) -> tuple[str, str]:
    """Retorna o handle limpo e a URL correspondente do Instagram."""
    if not handle:
        return "", ""
    h = handle.strip()
    # Se forneceu URL completa
    if "instagram.com/" in h:
        parts = h.split("instagram.com/")
        h = parts[-1].split("?")[0].replace("@", "").strip("/ ")
    else:
        h = h.replace("@", "").strip("/ ")
    return f"@{h}", f"https://www.instagram.com/{h}"


class PerfilModal(discord.ui.Modal, title="Atualizar Redes Sociais do Perfil"):
    linkedin_input = discord.ui.TextInput(
        label="URL do Perfil do LinkedIn",
        placeholder="https://www.linkedin.com/in/seu-perfil",
        style=discord.TextStyle.short,
        required=False,
        max_length=255
    )

    instagram_input = discord.ui.TextInput(
        label="Perfil do Instagram (@usuario ou link)",
        placeholder="@seu.usuario ou https://instagram.com/seu.usuario",
        style=discord.TextStyle.short,
        required=False,
        max_length=100
    )

    def __init__(self, current_linkedin: str = None, current_instagram: str = None):
        super().__init__()
        if current_linkedin:
            self.linkedin_input.default = current_linkedin
        if current_instagram:
            self.instagram_input.default = current_instagram

    async def on_submit(self, interaction: discord.Interaction):
        linkedin_val = self.linkedin_input.value.strip()
        instagram_val = self.instagram_input.value.strip()

        # Validação do LinkedIn
        if linkedin_val and not is_valid_linkedin_url(linkedin_val):
            await interaction.response.send_message(
                "❌ **URL do LinkedIn inválida!**\n"
                "Certifique-se de que o link começa com `https://www.linkedin.com/in/...` ou `https://linkedin.com/in/...`",
                ephemeral=True
            )
            return

        try:
            conn = get_db_connection()
            cur = conn.cursor(dictionary=True)
            uid = str(interaction.user.id)

            # Garante usuário em anima_usuario_discord
            cur.execute("""
                INSERT INTO anima_usuario_discord (discord_user_id, discord_username, discord_global_name, discord_avatar_url, linkedin_url, instagram_user)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    discord_username = VALUES(discord_username),
                    discord_global_name = VALUES(discord_global_name),
                    discord_avatar_url = VALUES(discord_avatar_url),
                    linkedin_url = VALUES(linkedin_url),
                    instagram_user = VALUES(instagram_user)
            """, (
                uid,
                interaction.user.name,
                interaction.user.global_name or interaction.user.display_name,
                str(interaction.user.display_avatar.url) if interaction.user.display_avatar else None,
                linkedin_val if linkedin_val else None,
                instagram_val if instagram_val else None
            ))
            conn.commit()

            # Busca preferências atuais de privacidade
            cur.execute("SELECT * FROM anima_usuario_discord WHERE discord_user_id = %s", (uid,))
            user_row = cur.fetchone() or {}
            cur.close()
            conn.close()

            view = PrivacidadeConfigView(uid, user_row)
            embed = discord.Embed(
                title="🔒 Configurar Privacidade do Perfil",
                description=(
                    "✅ **Redes sociais salvas com sucesso!**\n\n"
                    "Agora, selecione no menu abaixo **quais informações você autoriza compartilhar** com os outros membros do servidor no comando de perfil (`Apps -> Ver Perfil` ou `/info`):\n\n"
                    "*(IES e Curso são informações públicas da disciplina)*"
                ),
                color=discord.Color.blurple()
            )
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"Erro ao salvar perfil no modal: {e}")
            await interaction.response.send_message(f"❌ Erro ao salvar dados do perfil: {e}", ephemeral=True)


class PrivacidadeSelect(discord.ui.Select):
    def __init__(self, user_row: dict):
        options = [
            discord.SelectOption(
                label="Nome Completo",
                value="share_nome",
                description="Exibir seu nome cadastrado na universidade",
                emoji="👤",
                default=bool(user_row.get("share_nome", 1))
            ),
            discord.SelectOption(
                label="E-mail Acadêmico (Ulife)",
                value="share_email_academico",
                description="Exibir seu e-mail institucional",
                emoji="🎓",
                default=bool(user_row.get("share_email_academico", 0))
            ),
            discord.SelectOption(
                label="E-mail Pessoal",
                value="share_email_pessoal",
                description="Exibir seu e-mail pessoal cadastrado",
                emoji="✉️",
                default=bool(user_row.get("share_email_pessoal", 0))
            ),
            discord.SelectOption(
                label="Perfil do LinkedIn",
                value="share_linkedin",
                description="Exibir link para seu LinkedIn",
                emoji="💼",
                default=bool(user_row.get("share_linkedin", 1))
            ),
            discord.SelectOption(
                label="Perfil do Instagram",
                value="share_instagram",
                description="Exibir seu usuário do Instagram",
                emoji="📸",
                default=bool(user_row.get("share_instagram", 1))
            ),
            discord.SelectOption(
                label="Temas de Interesse",
                value="share_temas",
                description="Exibir suas áreas de tecnologia preferidas",
                emoji="🎯",
                default=bool(user_row.get("share_temas", 1))
            )
        ]

        super().__init__(
            placeholder="Selecione as informações que você AUTORIZA compartilhar...",
            min_values=0,
            max_values=len(options),
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()


class PrivacidadeConfigView(discord.ui.View):
    def __init__(self, discord_user_id: str, user_row: dict):
        super().__init__(timeout=300)
        self.discord_user_id = discord_user_id
        self.select = PrivacidadeSelect(user_row)
        self.add_item(self.select)

    @discord.ui.button(label="💾 Salvar Preferências de Privacidade", style=discord.ButtonStyle.success, emoji="✅", row=1)
    async def salvar_privacidade(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.discord_user_id:
            await interaction.response.send_message("❌ Apenas o dono do perfil pode alterar as preferências.", ephemeral=True)
            return

        selected_values = set(self.select.values)
        share_nome = 1 if "share_nome" in selected_values else 0
        share_email_academico = 1 if "share_email_academico" in selected_values else 0
        share_email_pessoal = 1 if "share_email_pessoal" in selected_values else 0
        share_linkedin = 1 if "share_linkedin" in selected_values else 0
        share_instagram = 1 if "share_instagram" in selected_values else 0
        share_temas = 1 if "share_temas" in selected_values else 0

        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                UPDATE anima_usuario_discord
                SET share_nome = %s,
                    share_email_academico = %s,
                    share_email_pessoal = %s,
                    share_linkedin = %s,
                    share_instagram = %s,
                    share_temas = %s
                WHERE discord_user_id = %s
            """, (
                share_nome, share_email_academico, share_email_pessoal,
                share_linkedin, share_instagram, share_temas, self.discord_user_id
            ))
            conn.commit()
            cur.close()
            conn.close()

            embed = discord.Embed(
                title="✅ Perfil e Privacidade Salvos!",
                description="Suas preferências de visibilidade foram salvas com sucesso no servidor.",
                color=discord.Color.brand_green()
            )
            embed.add_field(name="👤 Nome Completo", value="Visível" if share_nome else "🔒 Oculto", inline=True)
            embed.add_field(name="🎓 E-mail Acadêmico", value="Visível" if share_email_academico else "🔒 Oculto", inline=True)
            embed.add_field(name="✉️ E-mail Pessoal", value="Visível" if share_email_pessoal else "🔒 Oculto", inline=True)
            embed.add_field(name="💼 LinkedIn", value="Visível" if share_linkedin else "🔒 Oculto", inline=True)
            embed.add_field(name="📸 Instagram", value="Visível" if share_instagram else "🔒 Oculto", inline=True)
            embed.add_field(name="🎯 Temas de Interesse", value="Visível" if share_temas else "🔒 Oculto", inline=True)

            embed.set_footer(text="Administradores do servidor têm acesso completo para suporte e validação.")

            for child in self.children:
                child.disabled = True

            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"Erro ao salvar privacidade: {e}")
            await interaction.response.send_message(f"❌ Erro ao salvar preferências: {e}", ephemeral=True)


class PerfilCog(commands.Cog, name="PerfilCog"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Registra o Context Menu de Usuário (botão direito -> Apps -> Ver Perfil)
        self.ctx_menu_perfil = app_commands.ContextMenu(
            name="Ver Perfil",
            callback=self.ver_perfil_context_menu
        )
        self.bot.tree.add_command(self.ctx_menu_perfil)

    def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu_perfil.name, type=self.ctx_menu_perfil.type)

    @app_commands.command(name="atualizar_perfil", description="Atualize suas redes sociais (LinkedIn, Instagram) e configure sua privacidade.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_atualizar_perfil(self, interaction: discord.Interaction):
        """Abre o modal para atualizar redes sociais e preferências de compartilhamento."""
        uid = str(interaction.user.id)
        current_linkedin = None
        current_instagram = None

        try:
            conn = get_db_connection()
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT linkedin_url, instagram_user FROM anima_usuario_discord WHERE discord_user_id = %s", (uid,))
            row = cur.fetchone()
            cur.close()
            conn.close()

            if row:
                current_linkedin = row.get("linkedin_url")
                current_instagram = row.get("instagram_user")
        except Exception as e:
            logger.warning(f"Erro ao carregar dados prévios de perfil para {uid}: {e}")

        modal = PerfilModal(current_linkedin=current_linkedin, current_instagram=current_instagram)
        await interaction.response.send_modal(modal)

    async def _render_user_profile_embed(self, invoker: discord.User | discord.Member, target: discord.User | discord.Member, guild: discord.Guild = None) -> discord.Embed:
        """Gera o Embed de perfil respeitando permissões de administrador e preferências de privacidade."""
        target_uid = str(target.id)

        # 1. Verifica se o solicitante é Administrador ou Dono do Servidor
        is_admin_or_owner = False
        if isinstance(invoker, discord.Member):
            if invoker.guild_permissions.administrator:
                is_admin_or_owner = True
            elif guild and guild.owner_id == invoker.id:
                is_admin_or_owner = True
        elif guild and guild.owner_id == invoker.id:
            is_admin_or_owner = True

        # Se for o próprio usuário vendo seu perfil, mostra tudo com tags informativas
        is_self = (invoker.id == target.id)

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        # 1. Busca dados de anima_usuario_discord (sem JOINs de collations diferentes)
        cur.execute("SELECT * FROM anima_usuario_discord WHERE discord_user_id = %s", (target_uid,))
        aud_row = cur.fetchone() or {}

        # 2. Busca dados de usuario (portal da disciplina)
        cur.execute("SELECT * FROM usuario WHERE usuario_discord_id = %s", (target_uid,))
        u_row = cur.fetchone()
        if not u_row and aud_row.get("usuario_id"):
            cur.execute("SELECT * FROM usuario WHERE usuario_id = %s", (aud_row["usuario_id"],))
            u_row = cur.fetchone()
        u_row = u_row or {}

        # Consolida os dados do perfil
        profile_data = {
            "discord_user_id": target_uid,
            "discord_username": aud_row.get("discord_username") or target.name,
            "discord_global_name": aud_row.get("discord_global_name") or target.global_name,
            "usuario_id": aud_row.get("usuario_id") or u_row.get("usuario_id"),
            "usuario_nome": u_row.get("usuario_nome"),
            "usuario_email": u_row.get("usuario_email"),
            "usuario_email_pessoal": u_row.get("usuario_email_pessoal"),
            "usuario_ra": u_row.get("usuario_ra"),
            "ies_sigla": u_row.get("ies_sigla"),
            "curso_sigla": u_row.get("curso_sigla"),
            "usuario_validado": u_row.get("usuario_validado"),
            "linkedin_url": aud_row.get("linkedin_url"),
            "instagram_user": aud_row.get("instagram_user"),
            "share_nome": aud_row.get("share_nome", 1),
            "share_email_academico": aud_row.get("share_email_academico", 0),
            "share_email_pessoal": aud_row.get("share_email_pessoal", 0),
            "share_linkedin": aud_row.get("share_linkedin", 1),
            "share_instagram": aud_row.get("share_instagram", 1),
            "share_temas": aud_row.get("share_temas", 1)
        }

        # Busca nomes completos de IES e Curso
        ies_nome = None
        curso_nome = None
        ies_sigla = profile_data.get("ies_sigla")
        curso_sigla = profile_data.get("curso_sigla")
        if ies_sigla:
            cur.execute("SELECT ies_nome FROM anima_ies WHERE ies_sigla = %s", (ies_sigla,))
            r_ies = cur.fetchone()
            if r_ies: ies_nome = r_ies.get("ies_nome")
        if curso_sigla:
            cur.execute("SELECT curso_nome FROM anima_curso WHERE curso_sigla = %s", (curso_sigla,))
            r_cur = cur.fetchone()
            if r_cur: curso_nome = r_cur.get("curso_nome")

        # Busca temas de interesse do target
        cur.execute("""
            SELECT ti.temas_interesse_nome 
            FROM anima_temas_interesse ti
            INNER JOIN anima_usuario_temas_interesse auti ON ti.temas_interesse_id = auti.temas_interesse_id
            WHERE auti.discord_user_id = %s
            ORDER BY ti.temas_interesse_nome ASC
        """, (target_uid,))
        temas_rows = cur.fetchall()
        temas_list = [r["temas_interesse_nome"] for r in temas_rows]

        cur.close()
        conn.close()

        # Montagem do Embed
        display_name = target.global_name or target.display_name or target.name
        avatar_url = target.display_avatar.url if target.display_avatar else None

        embed = discord.Embed(
            title=f"👤 Perfil de {display_name}",
            color=discord.Color.blue()
        )
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)

        # Se não tiver nenhum dado cadastrado em nenhuma tabela
        if not aud_row and not u_row:
            embed.description = "Este usuário ainda não possui registro detalhado na base de dados da comunidade."
            embed.add_field(name="Discord Tag", value=f"`{target.name}` (ID: `{target.id}`)", inline=False)
            return embed

        # Permissões de exibição
        can_view_all = is_admin_or_owner or is_self

        # 1. Nome Completo (Controlado por share_nome)
        nome_completo = profile_data.get("usuario_nome")
        share_nome = bool(profile_data.get("share_nome", 1))
        if nome_completo:
            if can_view_all:
                tag = " *(🔒 Oculto p/ outros)*" if (not share_nome and not is_self) else ""
                embed.add_field(name="👤 Nome Completo", value=f"{nome_completo}{tag}", inline=True)
            elif share_nome:
                embed.add_field(name="👤 Nome Completo", value=nome_completo, inline=True)
            else:
                embed.add_field(name="👤 Nome", value=display_name, inline=True)

        # 2. IES e Curso (SEMPRE PÚBLICOS)
        ies_str = f"{ies_nome} (`{ies_sigla}`)" if ies_nome else ies_sigla or "-"
        curso_str = f"{curso_nome} (`{curso_sigla}`)" if curso_nome else curso_sigla or "-"
        embed.add_field(name="🏛️ IES", value=ies_str, inline=True)
        embed.add_field(name="📚 Curso", value=curso_str, inline=True)

        # 3. E-mail Acadêmico (Controlado por share_email_academico)
        email_acad = profile_data.get("usuario_email")
        share_email_acad = bool(profile_data.get("share_email_academico", 0))
        if email_acad:
            if can_view_all:
                tag = " *(🔒 Oculto p/ outros)*" if (not share_email_acad and not is_self) else ""
                embed.add_field(name="🎓 E-mail Acadêmico", value=f"`{email_acad}`{tag}", inline=False)
            elif share_email_acad:
                embed.add_field(name="🎓 E-mail Acadêmico", value=f"`{email_acad}`", inline=False)
            else:
                embed.add_field(name="🎓 E-mail Acadêmico", value="*🔒 Oculto pelo usuário*", inline=False)

        # 4. E-mail Pessoal (Controlado por share_email_pessoal)
        email_pess = profile_data.get("usuario_email_pessoal")
        share_email_pess = bool(profile_data.get("share_email_pessoal", 0))
        if email_pess:
            if can_view_all:
                tag = " *(🔒 Oculto p/ outros)*" if (not share_email_pess and not is_self) else ""
                embed.add_field(name="✉️ E-mail Pessoal", value=f"`{email_pess}`{tag}", inline=False)
            elif share_email_pess:
                embed.add_field(name="✉️ E-mail Pessoal", value=f"`{email_pess}`", inline=False)
            else:
                embed.add_field(name="✉️ E-mail Pessoal", value="*🔒 Oculto pelo usuário*", inline=False)

        # 5. LinkedIn (Controlado por share_linkedin)
        linkedin_url = profile_data.get("linkedin_url")
        share_linkedin = bool(profile_data.get("share_linkedin", 1))
        if linkedin_url:
            if can_view_all:
                tag = " *(🔒 Oculto p/ outros)*" if (not share_linkedin and not is_self) else ""
                embed.add_field(name="💼 LinkedIn", value=f"[Acessar LinkedIn]({linkedin_url}){tag}", inline=True)
            elif share_linkedin:
                embed.add_field(name="💼 LinkedIn", value=f"[Acessar LinkedIn]({linkedin_url})", inline=True)
            else:
                embed.add_field(name="💼 LinkedIn", value="*🔒 Oculto pelo usuário*", inline=True)

        # 6. Instagram (Controlado por share_instagram)
        instagram_user = profile_data.get("instagram_user")
        share_instagram = bool(profile_data.get("share_instagram", 1))
        if instagram_user:
            handle, url = format_instagram_handle(instagram_user)
            val_insta = f"[{handle}]({url})" if url else handle
            if can_view_all:
                tag = " *(🔒 Oculto p/ outros)*" if (not share_instagram and not is_self) else ""
                embed.add_field(name="📸 Instagram", value=f"{val_insta}{tag}", inline=True)
            elif share_instagram:
                embed.add_field(name="📸 Instagram", value=val_insta, inline=True)
            else:
                embed.add_field(name="📸 Instagram", value="*🔒 Oculto pelo usuário*", inline=True)

        # 7. Temas de Interesse (Controlado por share_temas)
        share_temas = bool(profile_data.get("share_temas", 1))
        if temas_list:
            str_temas = ", ".join([f"`{t}`" for t in temas_list])
            if can_view_all:
                tag = " *(🔒 Oculto p/ outros)*" if (not share_temas and not is_self) else ""
                embed.add_field(name=f"🎯 Temas de Interesse ({len(temas_list)}){tag}", value=str_temas, inline=False)
            elif share_temas:
                embed.add_field(name=f"🎯 Temas de Interesse ({len(temas_list)})", value=str_temas, inline=False)
            else:
                embed.add_field(name="🎯 Temas de Interesse", value="*🔒 Oculto pelo usuário*", inline=False)

        if is_admin_or_owner and not is_self:
            embed.set_footer(text="👑 Visualização de Administrador: Exibindo todos os dados com indicações de privacidade.")
        else:
            embed.set_footer(text="Use /atualizar_perfil para configurar suas redes e privacidade!")

        return embed

    async def ver_perfil_context_menu(self, interaction: discord.Interaction, member: discord.Member):
        """Context Menu disparado com o botão direito sobre um membro -> Apps -> Ver Perfil."""
        await interaction.response.defer(ephemeral=True)
        try:
            embed = await self._render_user_profile_embed(
                invoker=interaction.user,
                target=member,
                guild=interaction.guild
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Erro ao processar Context Menu Ver Perfil: {e}")
            await interaction.followup.send(f"❌ Erro ao consultar perfil: {e}", ephemeral=True)

    @app_commands.command(name="info", description="Exibe informações de perfil, formação e redes de um membro.")
    @app_commands.describe(usuario="Membro que deseja consultar (deixe em branco para ver o seu próprio perfil)")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_info(self, interaction: discord.Interaction, usuario: discord.Member = None):
        """Comando slash /info para consultar perfil."""
        target = usuario or interaction.user
        await interaction.response.defer(ephemeral=True)
        try:
            embed = await self._render_user_profile_embed(
                invoker=interaction.user,
                target=target,
                guild=interaction.guild
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Erro ao processar comando /info: {e}")
            await interaction.followup.send(f"❌ Erro ao consultar perfil: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PerfilCog(bot))
    logger.info("Cog 'PerfilCog' carregado com sucesso.")
