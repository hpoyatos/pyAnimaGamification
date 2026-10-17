import os
import sys
import logging
from datetime import datetime
import discord
from discord.ext import commands
from discord import app_commands
import mysql.connector

# Garante acesso à pasta scripts para reutilizar a lógica de migração
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")
ARQUIVOS_DIR = os.path.join(ROOT_DIR, "arquivos")

if SCRIPTS_DIR not in sys.path:
    sys.path.append(SCRIPTS_DIR)

from carregar_usuario_selos_csv import processar_arquivos_csv_selos

logger = logging.getLogger("cogs.selos")

def _resolve_discord_nickname(user: discord.User | discord.Member) -> str:
    return user.global_name or getattr(user, "display_name", None) or user.name

class SelosCog(commands.Cog):
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
            collation="utf8mb4_unicode_ci",
            use_pure=True,
            connection_timeout=5,
        )

    def _is_admin(self, interaction: discord.Interaction) -> bool:
        """
        Valida se o usuário tem privilégios de Administrador.
        Critérios:
        1. ID configurado na env DISCORD_ADMIN_USER_ID
        2. Permissão de Administrator na Guild atual ou Dono da Guild
        3. Dono de qualquer guilda onde o bot está presente
        """
        user_id_str = str(interaction.user.id)
        admin_env_id = os.getenv("DISCORD_ADMIN_USER_ID")
        if admin_env_id and user_id_str == admin_env_id.strip():
            return True

        if isinstance(interaction.user, discord.Member):
            if interaction.user.guild_permissions.administrator:
                return True
            if interaction.guild and interaction.guild.owner_id == interaction.user.id:
                return True

        for guild in self.bot.guilds:
            if guild.owner_id == interaction.user.id:
                return True
            member = guild.get_member(interaction.user.id)
            if member and member.guild_permissions.administrator:
                return True

        return False

    def query_usuario_selos(self, discord_id: int):
        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(dictionary=True)

            # Buscar usuário
            sql_user = """
                SELECT usuario_id, usuario_nome, usuario_ra, usuario_email
                FROM usuario
                WHERE usuario_discord_id = %s
            """
            cur.execute(sql_user, (str(discord_id),))
            user_data = cur.fetchone()

            if not user_data:
                cur.close()
                return None, []

            usuario_id = user_data["usuario_id"]

            # Buscar selos conquistados
            sql_selos = """
                SELECT 
                    s.selo_id,
                    s.selo_nome,
                    s.selo_parceiro,
                    aus.usuario_selo_data
                FROM anima_usuario_selo aus
                INNER JOIN anima_selo s ON s.selo_id = aus.selo_id
                WHERE aus.usuario_id = %s
                ORDER BY aus.usuario_selo_data ASC, s.selo_nome ASC
            """
            cur.execute(sql_selos, (usuario_id,))
            selos = cur.fetchall() or []

            cur.close()
            return user_data, selos
        except Exception as e:
            logger.exception(f"Erro ao buscar selos do usuário {discord_id}: {e}")
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

    def query_ranking_selos(self, limit: int = 10):
        conn = None
        try:
            conn = self._get_db_connection()
            cur = conn.cursor(dictionary=True)

            sql_ranking = """
                SELECT 
                    u.usuario_id,
                    u.usuario_nome,
                    u.usuario_discord_id,
                    u.usuario_discord_name,
                    COUNT(aus.selo_id) AS total_selos,
                    MIN(aus.usuario_selo_data) AS primeiro_selo,
                    GROUP_CONCAT(s.selo_nome ORDER BY aus.usuario_selo_data ASC SEPARATOR '||') AS selos_nomes
                FROM anima_usuario_selo aus
                INNER JOIN usuario u ON u.usuario_id = aus.usuario_id
                INNER JOIN anima_selo s ON s.selo_id = aus.selo_id
                GROUP BY u.usuario_id, u.usuario_nome, u.usuario_discord_id, u.usuario_discord_name
                ORDER BY total_selos DESC, primeiro_selo ASC
                LIMIT %s
            """
            cur.execute(sql_ranking, (limit,))
            ranking = cur.fetchall() or []
            cur.close()
            return ranking
        except Exception as e:
            logger.exception(f"Erro ao buscar ranking de selos: {e}")
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

    @app_commands.command(
        name="meus_selos",
        description="Consulta a lista de selos e badges conquistados por você"
    )
    async def meus_selos(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        user_id = interaction.user.id
        discord_nick = _resolve_discord_nickname(interaction.user)

        auditoria_id_str = os.getenv("DISCORD_AUDITORIA_CHANNEL_ID")
        if auditoria_id_str:
            try:
                auditoria_channel = self.bot.get_channel(int(auditoria_id_str))
                if auditoria_channel:
                    await auditoria_channel.send(f"🎖️ **{discord_nick}** consultou `/meus_selos`.")
            except Exception as e:
                logger.error(f"Erro ao enviar log para auditoria em meus_selos: {e}")

        try:
            user_data, selos = self.query_usuario_selos(user_id)

            if not user_data:
                await interaction.followup.send(
                    f"⚠️ Não encontrei um cadastro vinculado ao seu Discord (**{discord_nick}**).\n"
                    "↳ Utilize o comando `/identificar` para vincular seu perfil acadêmico.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="🎖️ Seus Selos e Badges Conquistados",
                color=0x4285F4,
                timestamp=discord.utils.utcnow()
            )
            embed.set_author(name=discord_nick, icon_url=interaction.user.display_avatar.url)
            embed.add_field(name="👤 Aluno(a)", value=user_data.get("usuario_nome") or "-", inline=True)
            embed.add_field(name="🆔 RA", value=user_data.get("usuario_ra") or "-", inline=True)
            embed.add_field(name="🏆 Total de Selos", value=str(len(selos)), inline=True)

            if not selos:
                embed.description = "ℹ️ _Você ainda não possui nenhum selo registrado._"
            else:
                linhas = []
                for s in selos:
                    data_str = ""
                    if isinstance(s.get("usuario_selo_data"), datetime):
                        data_str = f" • Conquistado em `{s['usuario_selo_data']:%d/%m/%Y}`"
                    parceiro = f"**[{s['selo_parceiro']}]**" if s.get("selo_parceiro") else ""
                    linhas.append(f"🏅 {parceiro} {s['selo_nome']}{data_str}")

                texto_selos = "\n".join(linhas)
                if len(texto_selos) > 4000:
                    texto_selos = texto_selos[:3950] + "\n\n_... (lista truncada por limite do Discord)_"

                embed.description = texto_selos

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.exception(f"Erro ao processar /meus_selos: {e}")
            await interaction.followup.send(
                "❌ Ocorreu um erro ao consultar seus selos. Tente novamente mais tarde.",
                ephemeral=True
            )

    @app_commands.command(
        name="ranking_selos",
        description="[Admin] Exibe o Top 10 do ranking geral de selos e badges"
    )
    async def ranking_selos(self, interaction: discord.Interaction):
        # Validação de Administrador
        if not self._is_admin(interaction):
            await interaction.response.send_message(
                "❌ **Acesso Negado**: Este comando é restrito a administradores do servidor.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=False)

        try:
            ranking = self.query_ranking_selos(limit=10)

            if not ranking:
                await interaction.followup.send(
                    "ℹ️ Ainda não há nenhum selo registrado no ranking.",
                    ephemeral=False
                )
                return

            embed = discord.Embed(
                title="🏆 Ranking Geral de Selos e Conquistas (Top 10)",
                description="Critério: Quantidade de selos conquistados. Desempate: quem conquistou o primeiro selo mais cedo.\n",
                color=0xFFD700,
                timestamp=discord.utils.utcnow()
            )

            medalhas = {1: "🥇", 2: "🥈", 3: "🥉"}

            for pos, r in enumerate(ranking, 1):
                icone = medalhas.get(pos, f"`#{pos:02d}`")
                
                user_id_str = str(r.get("usuario_discord_id") or "").strip()
                nome_real = r.get("usuario_nome") or "Aluno"
                total = r.get("total_selos") or 0
                discord_fallback = r.get("usuario_discord_name") or "Desconhecido"

                discord_tag = discord_fallback
                member_mention = None

                if user_id_str.isdigit():
                    uid_int = int(user_id_str)
                    member_mention = f"<@{uid_int}>"
                    member = None
                    if interaction.guild:
                        member = interaction.guild.get_member(uid_int)
                    if not member:
                        member = self.bot.get_user(uid_int)

                    if member:
                        discord_tag = getattr(member, "display_name", None) or getattr(member, "global_name", None) or member.name

                primeiro_data_str = ""
                if isinstance(r.get("primeiro_selo"), datetime):
                    primeiro_data_str = f"1º selo em `{r['primeiro_selo']:%d/%m/%Y}`"

                selos_lista = (r.get("selos_nomes") or "").split("||") if r.get("selos_nomes") else []
                selos_formatados = "\n".join([f"  └ 🔹 {s}" for s in selos_lista])

                campo_titulo = f"{icone} {nome_real} (@{discord_tag}) — {total} selo{'s' if total != 1 else ''}"

                cabecalho_partes = []
                if member_mention:
                    cabecalho_partes.append(f"👤 {member_mention}")
                if primeiro_data_str:
                    cabecalho_partes.append(f"⏱️ {primeiro_data_str}")

                cabecalho_corpo = " • ".join(cabecalho_partes)
                if cabecalho_corpo:
                    campo_valor = f"{cabecalho_corpo}\n{selos_formatados}"
                else:
                    campo_valor = selos_formatados

                if len(campo_valor) > 1024:
                    campo_valor = campo_valor[:1000] + "\n  └ _... e mais selos_"

                embed.add_field(
                    name=campo_titulo,
                    value=campo_valor or "Nenhum detalhe",
                    inline=False
                )

            embed.set_footer(text="pyAnimaGamification • Painel Administrativo de Selos")
            await interaction.followup.send(embed=embed, ephemeral=False)

        except Exception as e:
            logger.exception(f"Erro ao processar /ranking_selos: {e}")
            await interaction.followup.send(
                "❌ Ocorreu um erro ao carregar o ranking de selos. Tente novamente mais tarde.",
                ephemeral=False
            )

    @app_commands.command(
        name="atualizar_selos",
        description="[Admin] Faz o upload de um relatório CSV e executa a carga e congratulações de selos"
    )
    @app_commands.describe(
        arquivo="Arquivo CSV com o relatório de atividades (ql-group_activity-report*.csv)"
    )
    async def atualizar_selos(
        self,
        interaction: discord.Interaction,
        arquivo: discord.Attachment
    ):
        # Validação de Administrador
        if not self._is_admin(interaction):
            await interaction.response.send_message(
                "❌ **Acesso Negado**: Este comando é restrito a administradores do sistema.",
                ephemeral=True
            )
            return

        # Validação do tipo de arquivo
        if not arquivo.filename.lower().endswith(".csv"):
            await interaction.response.send_message(
                "⚠️ **Arquivo inválido**: Por favor, anexe um arquivo no formato `.csv`.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            os.makedirs(ARQUIVOS_DIR, exist_ok=True)
            caminho_salvo = os.path.join(ARQUIVOS_DIR, arquivo.filename)

            # Baixar o anexo enviado no Discord
            await arquivo.save(caminho_salvo)
            logger.info(f"Arquivo CSV recebido via Discord e salvo em: {caminho_salvo}")

            # Executar o processamento
            resultado = processar_arquivos_csv_selos([caminho_salvo], logger_callback=logger.info)

            # Montar retorno visual do processamento
            embed = discord.Embed(
                title="✅ Carga de Selos Concluída com Sucesso!",
                description=f"**Arquivo processado:** `{arquivo.filename}`\n",
                color=0x2ECC71,
                timestamp=discord.utils.utcnow()
            )

            embed.add_field(name="📥 Novos Selos Cadastrados", value=str(resultado["novos_inseridos"]), inline=True)
            embed.add_field(name="⏩ Selos Existentes (Ignorados)", value=str(resultado["ja_existentes"]), inline=True)
            embed.add_field(name="🎉 Congratulações Enviadas", value=str(resultado["congratulacoes_enviadas"]), inline=True)

            if resultado["detalhes_novos"]:
                linhas_novos = []
                for n in resultado["detalhes_novos"][:10]:
                    linhas_novos.append(f"• {n['aluno']}: *{n['selo']}*")
                if len(resultado["detalhes_novos"]) > 10:
                    linhas_novos.append(f"_... e mais {len(resultado['detalhes_novos']) - 10} conquistas._")
                embed.add_field(name="🎖️ Detalhes dos Novos Selos", value="\n".join(linhas_novos), inline=False)

            if resultado["nao_encontrados"]:
                nao_enc_str = "\n".join([f"• `{em}`" for em in resultado["nao_encontrados"][:5]])
                if len(resultado["nao_encontrados"]) > 5:
                    nao_enc_str += f"\n_... e outros {len(resultado['nao_encontrados']) - 5} e-mails._"
                embed.add_field(name="⚠️ E-mails não mapeados no banco", value=nao_enc_str, inline=False)

            embed.set_footer(text="pyAnimaGamification • Gestão de Selos")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.exception(f"Erro ao processar /atualizar_selos: {e}")
            await interaction.followup.send(
                f"❌ Erro ao processar o arquivo CSV: `{e}`",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(SelosCog(bot))
