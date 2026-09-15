import os
import logging
import discord
from discord import app_commands
from discord.ext import commands
import mysql.connector

logger = logging.getLogger("cogs.temas")

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "db"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "anima"),
        charset="utf8mb4"
    )

def _garantir_schema_e_role_ia(conn):
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT COUNT(*) AS total 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
              AND TABLE_NAME = 'anima_temas_interesse' 
              AND COLUMN_NAME = 'discord_role_id'
        """)
        res = cur.fetchone()
        if res and res['total'] == 0:
            cur.execute("ALTER TABLE anima_temas_interesse ADD COLUMN discord_role_id VARCHAR(20) NULL AFTER temas_interesse_descricao")
            conn.commit()
            logger.info("Coluna 'discord_role_id' adicionada com sucesso em anima_temas_interesse.")

        # Garante a role de IA configurada
        cur.execute("""
            UPDATE anima_temas_interesse
            SET discord_role_id = '1212540672482222151'
            WHERE (temas_interesse_nome LIKE '%Inteligência Artificial%' 
               OR temas_interesse_nome LIKE '%IA%' 
               OR temas_interesse_tag = 'IA')
              AND (discord_role_id IS NULL OR discord_role_id = '')
        """)
        conn.commit()
        cur.close()
    except Exception as e:
        logger.error(f"Erro em _garantir_schema_e_role_ia: {e}")

class TemasSelect(discord.ui.Select):
    def __init__(self, view_parent, batch_tema_ids: set[int], custom_id: str, placeholder: str, options: list[discord.SelectOption], max_val: int):
        super().__init__(
            custom_id=custom_id,
            placeholder=placeholder,
            min_values=0,
            max_values=max_val,
            options=options
        )
        self.view_parent = view_parent
        self.batch_tema_ids = batch_tema_ids

    async def callback(self, interaction: discord.Interaction):
        # 1. Remove deste lote todos os temas que estavam marcados no conjunto geral
        self.view_parent.selected_tema_ids.difference_update(self.batch_tema_ids)
        # 2. Adiciona os que o usuário selecionou ativamente neste select
        for val in self.values:
            self.view_parent.selected_tema_ids.add(int(val))

        # 3. Atualiza os defaults nas options do select para manter consistência visual
        for opt in self.options:
            opt.default = int(opt.value) in self.view_parent.selected_tema_ids

        await interaction.response.defer()


class GerenciarTemasView(discord.ui.View):
    def __init__(self, bot: commands.Bot, discord_user_id: str, all_temas: list[dict], user_tema_ids: set[int]):
        super().__init__(timeout=300)
        self.bot = bot
        self.discord_user_id = discord_user_id
        self.all_temas = all_temas
        self.selected_tema_ids = set(user_tema_ids)
        self.selects: list[TemasSelect] = []

        # Divide temas em lotes de até 25 para suportar o limite do Discord
        batch_size = 25
        for i in range(0, len(all_temas), batch_size):
            batch = all_temas[i:i + batch_size]
            part_num = (i // batch_size) + 1
            total_parts = ((len(all_temas) - 1) // batch_size) + 1
            batch_ids = {t['temas_interesse_id'] for t in batch}
            
            opts = []
            for t in batch:
                tid = t['temas_interesse_id']
                nome = t['temas_interesse_nome'][:95]
                desc = (t.get('temas_interesse_descricao') or t.get('temas_interesse_tag') or '')[:95]
                is_selected = tid in self.selected_tema_ids
                
                opts.append(discord.SelectOption(
                    label=nome,
                    value=str(tid),
                    description=desc if desc else None,
                    default=is_selected,
                    emoji="🏷️"
                ))

            placeholder = f"Selecione seus interesses (Parte {part_num}/{total_parts})..." if total_parts > 1 else "Selecione seus temas de interesse..."
            sel = TemasSelect(
                view_parent=self,
                batch_tema_ids=batch_ids,
                custom_id=f"select_temas_part_{part_num}",
                placeholder=placeholder,
                options=opts,
                max_val=len(opts)
            )
            self.selects.append(sel)
            self.add_item(sel)

    @discord.ui.button(label="💾 Salvar Interesses", style=discord.ButtonStyle.success, emoji="✅", row=4)
    async def salvar_interesses(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.discord_user_id:
            await interaction.response.send_message("❌ Apenas o usuário que invocou o comando pode salvar seus temas.", ephemeral=True)
            return

        selected_ids = list(self.selected_tema_ids)

        try:
            conn = get_db_connection()
            cur = conn.cursor(dictionary=True)

            # 1. Garante que o usuário existe em anima_usuario_discord
            cur.execute("""
                INSERT INTO anima_usuario_discord (discord_user_id, discord_username, discord_global_name, discord_avatar_url)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    discord_username = VALUES(discord_username),
                    discord_global_name = VALUES(discord_global_name),
                    discord_avatar_url = VALUES(discord_avatar_url)
            """, (
                str(interaction.user.id),
                interaction.user.name,
                interaction.user.global_name or interaction.user.display_name,
                str(interaction.user.display_avatar.url) if interaction.user.display_avatar else None
            ))

            # 2. Busca os temas que o usuário possuía antes
            cur.execute("SELECT temas_interesse_id FROM anima_usuario_temas_interesse WHERE discord_user_id = %s", (self.discord_user_id,))
            previous_tema_ids = {r['temas_interesse_id'] for r in cur.fetchall()}

            # 3. Deleta temas anteriores do usuário
            cur.execute("DELETE FROM anima_usuario_temas_interesse WHERE discord_user_id = %s", (self.discord_user_id,))

            # 4. Insere os novos temas selecionados
            if selected_ids:
                insert_data = [(self.discord_user_id, tid) for tid in selected_ids]
                cur.executemany("INSERT INTO anima_usuario_temas_interesse (discord_user_id, temas_interesse_id) VALUES (%s, %s)", insert_data)

            conn.commit()

            # 5. Mapeia discord_role_id de todos os temas relevantes
            all_temas_dict = {t['temas_interesse_id']: t for t in self.all_temas}
            
            added_tema_ids = set(selected_ids) - previous_tema_ids
            removed_tema_ids = previous_tema_ids - set(selected_ids)

            roles_to_add = []
            for tid in added_tema_ids:
                r_id = all_temas_dict.get(tid, {}).get('discord_role_id')
                if r_id and str(r_id).strip():
                    try:
                        roles_to_add.append(int(str(r_id).strip()))
                    except ValueError:
                        pass

            roles_to_remove = []
            for tid in removed_tema_ids:
                r_id = all_temas_dict.get(tid, {}).get('discord_role_id')
                if r_id and str(r_id).strip():
                    try:
                        roles_to_remove.append(int(str(r_id).strip()))
                    except ValueError:
                        pass

            cur.close()
            conn.close()

            # 6. Aplica ou remove os cargos no membro do Discord (suporta tanto canal de servidor quanto DM)
            user_id_int = int(self.discord_user_id)
            guilds_to_process = [interaction.guild] if interaction.guild else self.bot.guilds

            cargos_atribuidos_nomes = []
            cargos_removidos_nomes = []
            erros_permissao = []

            for guild in guilds_to_process:
                if not guild:
                    continue
                try:
                    member = guild.get_member(user_id_int)
                    if not member:
                        try:
                            member = await guild.fetch_member(user_id_int)
                        except Exception:
                            member = None

                    if not member:
                        continue

                    # Adiciona novos cargos
                    for rid in roles_to_add:
                        role_obj = guild.get_role(rid)
                        if role_obj:
                            try:
                                await member.add_roles(role_obj, reason="Tema de interesse selecionado pelo usuário")
                                cargos_atribuidos_nomes.append(f"@{role_obj.name}")
                                logger.info(f"[Temas] Cargo {role_obj.name} ({rid}) atribuído a {member.name} em {guild.name}")
                            except discord.Forbidden:
                                erro_txt = f"Sem permissão para atribuir o cargo @{role_obj.name} (coloque o cargo do bot acima dele nas configurações do servidor)"
                                logger.error(f"[Temas] {erro_txt}")
                                erros_permissao.append(erro_txt)
                            except Exception as e_role:
                                logger.error(f"[Temas] Erro ao atribuir cargo {rid} para {member.name}: {e_role}")

                    # Remove cargos desmarcados
                    for rid in roles_to_remove:
                        role_obj = guild.get_role(rid)
                        if role_obj:
                            try:
                                await member.remove_roles(role_obj, reason="Tema de interesse desmarcado pelo usuário")
                                cargos_removidos_nomes.append(f"@{role_obj.name}")
                                logger.info(f"[Temas] Cargo {role_obj.name} ({rid}) removido de {member.name} em {guild.name}")
                            except discord.Forbidden:
                                erro_txt = f"Sem permissão para remover o cargo @{role_obj.name} (coloque o cargo do bot acima dele nas configurações do servidor)"
                                logger.error(f"[Temas] {erro_txt}")
                                erros_permissao.append(erro_txt)
                            except Exception as e_role:
                                logger.error(f"[Temas] Erro ao remover cargo {rid} para {member.name}: {e_role}")

                except Exception as e_guild:
                    logger.error(f"[Temas] Erro ao processar cargos na guilda {guild.name}: {e_guild}")

            # Monta embed de confirmação
            nomes_selecionados = [f"🏷️ **{all_temas_dict[tid]['temas_interesse_nome']}**" for tid in selected_ids if tid in all_temas_dict]

            embed = discord.Embed(
                title="🎯 Temas de Interesse Atualizados!",
                description="Suas preferências foram registradas com sucesso no seu perfil do Discord.",
                color=discord.Color.brand_green()
            )

            if nomes_selecionados:
                embed.add_field(
                    name=f"Seus Temas Ativos ({len(nomes_selecionados)}):",
                    value="\n".join(nomes_selecionados),
                    inline=False
                )
            else:
                embed.add_field(
                    name="Nenhum tema selecionado",
                    value="Você não possui nenhum tema de interesse ativo no momento.",
                    inline=False
                )

            # Detalhes das roles adicionadas ou removidas
            if cargos_atribuidos_nomes:
                embed.add_field(
                    name="🎭 Cargos do Discord Atribuídos (+):",
                    value=", ".join(set(cargos_atribuidos_nomes)),
                    inline=False
                )
            if cargos_removidos_nomes:
                embed.add_field(
                    name="🧹 Cargos do Discord Removidos (-):",
                    value=", ".join(set(cargos_removidos_nomes)),
                    inline=False
                )

            if erros_permissao:
                embed.add_field(
                    name="⚠️ Atenção nas Permissões de Cargo:",
                    value="\n".join(set(erros_permissao)),
                    inline=False
                )

            embed.set_footer(text="Use /gerenciar_temas_de_interesse a qualquer momento para atualizar!")
            
            # Desativa os componentes
            for child in self.children:
                child.disabled = True

            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"Erro ao salvar temas de interesse para {self.discord_user_id}: {e}")
            await interaction.response.send_message(f"❌ Ocorreu um erro ao salvar seus temas de interesse: {e}", ephemeral=True)

    @discord.ui.button(label="🗑️ Limpar Todos", style=discord.ButtonStyle.secondary, emoji="🧹", row=4)
    async def limpar_interesses(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.discord_user_id:
            await interaction.response.send_message("❌ Apenas o usuário que invocou o comando pode limpar seus temas.", ephemeral=True)
            return

        try:
            conn = get_db_connection()
            cur = conn.cursor(dictionary=True)
            
            # Identifica os temas que o usuário possuía antes de limpar
            cur.execute("SELECT temas_interesse_id FROM anima_usuario_temas_interesse WHERE discord_user_id = %s", (self.discord_user_id,))
            user_previous_ids = [r['temas_interesse_id'] for r in cur.fetchall()]

            cur.execute("DELETE FROM anima_usuario_temas_interesse WHERE discord_user_id = %s", (self.discord_user_id,))
            conn.commit()
            cur.close()
            conn.close()

            # Remove os cargos correspondentes do usuário no Discord
            all_temas_dict = {t['temas_interesse_id']: t for t in self.all_temas}
            roles_to_remove = []
            for tid in user_previous_ids:
                r_id = all_temas_dict.get(tid, {}).get('discord_role_id')
                if r_id and str(r_id).strip():
                    try:
                        roles_to_remove.append(int(str(r_id).strip()))
                    except ValueError:
                        pass

            user_id_int = int(self.discord_user_id)
            guilds_to_process = [interaction.guild] if interaction.guild else self.bot.guilds
            cargos_removidos_nomes = []

            for guild in guilds_to_process:
                if not guild:
                    continue
                try:
                    member = guild.get_member(user_id_int)
                    if not member:
                        try:
                            member = await guild.fetch_member(user_id_int)
                        except Exception:
                            member = None

                    if not member:
                        continue

                    for rid in roles_to_remove:
                        role_obj = guild.get_role(rid)
                        if role_obj:
                            try:
                                await member.remove_roles(role_obj, reason="Temas de interesse limpos pelo usuário")
                                cargos_removidos_nomes.append(f"@{role_obj.name}")
                                logger.info(f"[Temas] Cargo {role_obj.name} ({rid}) desvinculado de {member.name} em {guild.name}")
                            except Exception as e_role:
                                logger.error(f"[Temas] Erro ao remover cargo {rid} para {member.name}: {e_role}")
                except Exception as e_guild:
                    logger.error(f"[Temas] Erro ao processar limpeza de cargos na guilda {guild.name}: {e_guild}")

            embed = discord.Embed(
                title="🧹 Temas de Interesse Removidos",
                description="Todos os seus temas de interesse foram limpos com sucesso.",
                color=discord.Color.orange()
            )
            if cargos_removidos_nomes:
                embed.add_field(
                    name="🎭 Cargos do Discord Removidos:",
                    value=", ".join(set(cargos_removidos_nomes)),
                    inline=False
                )
            embed.set_footer(text="Use /gerenciar_temas_de_interesse para escolher novos temas quando quiser!")

            for child in self.children:
                child.disabled = True

            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"Erro ao limpar temas de interesse para {self.discord_user_id}: {e}")
            await interaction.response.send_message(f"❌ Ocorreu um erro ao limpar seus temas: {e}", ephemeral=True)


class TemasCog(commands.Cog, name="TemasCog"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="gerenciar_temas_de_interesse",
        description="Escolha seus temas de interesse de tecnologia e formação para personalizar sua experiência."
    )
    async def gerenciar_temas_de_interesse(self, interaction: discord.Interaction):
        """Comando slash interativo com multi-select para o usuário escolher seus temas de interesse."""
        user_id_str = str(interaction.user.id)

        try:
            conn = get_db_connection()
            _garantir_schema_e_role_ia(conn)
            cur = conn.cursor(dictionary=True)

            # Busca todos os temas cadastrados com seus cargos vinculados
            cur.execute("SELECT temas_interesse_id, temas_interesse_nome, temas_interesse_tag, temas_interesse_descricao, discord_role_id FROM anima_temas_interesse ORDER BY temas_interesse_nome ASC")
            all_temas = cur.fetchall()

            if not all_temas:
                cur.close()
                conn.close()
                await interaction.response.send_message("⚠️ Nenhum tema de interesse cadastrado no sistema no momento.", ephemeral=True)
                return

            # Busca temas que o usuário já possui
            cur.execute("SELECT temas_interesse_id FROM anima_usuario_temas_interesse WHERE discord_user_id = %s", (user_id_str,))
            user_tema_ids = {r['temas_interesse_id'] for r in cur.fetchall()}

            cur.close()
            conn.close()

            view = GerenciarTemasView(
                bot=self.bot,
                discord_user_id=user_id_str,
                all_temas=all_temas,
                user_tema_ids=user_tema_ids
            )

            embed = discord.Embed(
                title="🎯 Gerenciar Temas de Interesse",
                description=(
                    "Selecione no(s) menu(s) abaixo as áreas de tecnologia e formação que você tem interesse em acompanhar.\n\n"
                    "💡 *Você pode selecionar múltiplos temas nos menus e clicar em **Salvar Interesses**.*"
                ),
                color=discord.Color.blurple()
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url if interaction.user.display_avatar else None)
            
            if user_tema_ids:
                nomes_atuais = [t['temas_interesse_nome'] for t in all_temas if t['temas_interesse_id'] in user_tema_ids]
                embed.add_field(
                    name=f"Seus Interesses Atuais ({len(nomes_atuais)}):",
                    value=", ".join(nomes_atuais),
                    inline=False
                )

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"Erro ao abrir gerenciamento de temas para {user_id_str}: {e}")
            await interaction.response.send_message(f"❌ Ocorreu um erro ao consultar os temas de interesse: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TemasCog(bot))
    logger.info("Cog 'TemasCog' carregado com sucesso.")
