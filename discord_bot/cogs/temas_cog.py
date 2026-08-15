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

class TemasSelect(discord.ui.Select):
    def __init__(self, custom_id: str, placeholder: str, options: list[discord.SelectOption], max_val: int):
        super().__init__(
            custom_id=custom_id,
            placeholder=placeholder,
            min_values=0,
            max_values=max_val,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        # Apenas confirma seleção no estado da View
        await interaction.response.defer()


class GerenciarTemasView(discord.ui.View):
    def __init__(self, discord_user_id: str, all_temas: list[dict], user_tema_ids: set[int]):
        super().__init__(timeout=300)
        self.discord_user_id = discord_user_id
        self.all_temas = all_temas
        self.user_tema_ids = set(user_tema_ids)
        self.selects: list[TemasSelect] = []

        # Divide temas em lotes de até 25 para suportar o limite do Discord
        batch_size = 25
        for i in range(0, len(all_temas), batch_size):
            batch = all_temas[i:i + batch_size]
            part_num = (i // batch_size) + 1
            total_parts = ((len(all_temas) - 1) // batch_size) + 1
            
            opts = []
            for t in batch:
                tid = t['temas_interesse_id']
                nome = t['temas_interesse_nome'][:95]
                desc = (t.get('temas_interesse_descricao') or t.get('temas_interesse_tag') or '')[:95]
                is_selected = tid in self.user_tema_ids
                
                opts.append(discord.SelectOption(
                    label=nome,
                    value=str(tid),
                    description=desc if desc else None,
                    default=is_selected,
                    emoji="🏷️"
                ))

            placeholder = f"Selecione seus interesses (Parte {part_num}/{total_parts})..." if total_parts > 1 else "Selecione seus temas de interesse..."
            sel = TemasSelect(
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

        selected_ids = []
        for s in self.selects:
            selected_ids.extend([int(v) for v in s.values])

        # Remove duplicados mantendo a ordem
        selected_ids = list(dict.fromkeys(selected_ids))

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

            # 2. Deleta temas anteriores do usuário
            cur.execute("DELETE FROM anima_usuario_temas_interesse WHERE discord_user_id = %s", (self.discord_user_id,))

            # 3. Insere os novos temas selecionados
            if selected_ids:
                insert_data = [(self.discord_user_id, tid) for tid in selected_ids]
                cur.executemany("INSERT INTO anima_usuario_temas_interesse (discord_user_id, temas_interesse_id) VALUES (%s, %s)", insert_data)

            conn.commit()
            cur.close()
            conn.close()

            # Monta embed de confirmação
            temas_dict = {t['temas_interesse_id']: t['temas_interesse_nome'] for t in self.all_temas}
            nomes_selecionados = [f"🏷️ **{temas_dict[tid]}**" for tid in selected_ids if tid in temas_dict]

            embed = discord.Embed(
                title="🎯 Temas de Interesse Atualizados!",
                description="Suas preferências foram registradas com sucesso no seu perfil do Discord.",
                color=discord.Color.brand_green()
            )

            if nomes_selecionados:
                embed.add_field(
                    name=f"Seus Temas de Interesse Ativos ({len(nomes_selecionados)}):",
                    value="\n".join(nomes_selecionados),
                    inline=False
                )
            else:
                embed.add_field(
                    name="Nenhum tema selecionado",
                    value="Você não possui nenhum tema de interesse ativo no momento.",
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
            cur = conn.cursor()
            cur.execute("DELETE FROM anima_usuario_temas_interesse WHERE discord_user_id = %s", (self.discord_user_id,))
            conn.commit()
            cur.close()
            conn.close()

            embed = discord.Embed(
                title="🧹 Temas de Interesse Removidos",
                description="Todos os seus temas de interesse foram limpos com sucesso.",
                color=discord.Color.orange()
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
            cur = conn.cursor(dictionary=True)

            # Busca todos os temas cadastrados
            cur.execute("SELECT temas_interesse_id, temas_interesse_nome, temas_interesse_tag, temas_interesse_descricao FROM anima_temas_interesse ORDER BY temas_interesse_nome ASC")
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
