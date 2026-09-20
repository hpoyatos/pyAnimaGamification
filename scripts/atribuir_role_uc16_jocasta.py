import os
import sys
import asyncio
import logging
import mysql.connector
import discord
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("atribuir_role_uc16")

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
AUDITORIA_CHANNEL_ID = int(os.getenv("DISCORD_AUDITORIA_CHANNEL_ID", "1020418840401813564"))
UC_ID = 16

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "192.168.15.254"),
        port=int(os.getenv("DB_PORT", "30306")),
        database=os.getenv("DB_NAME", "anima"),
        user=os.getenv("DB_USER", "anima_bot"),
        password=os.getenv("DB_PASSWORD"),
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
        use_pure=True
    )

def get_validated_users_for_uc(uc_id):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # 1. Informações da UC
    cur.execute("SELECT uc_id, uc_nome, uc_discord_role FROM anima_uc WHERE uc_id = %s", (uc_id,))
    uc_info = cur.fetchone()
    if not uc_info:
        logger.error(f"UC ID {uc_id} não encontrada no banco de dados.")
        cur.close()
        conn.close()
        return None, []

    # 2. Usuários vinculados na UC 16 que já foram validados e possuem discord_id
    sql = """
        SELECT u.usuario_id, u.usuario_nome, u.usuario_email, u.usuario_email_pessoal, 
               u.usuario_telefone, u.usuario_discord_id, u.usuario_discord_name, u.usuario_validado
        FROM usuario u
        INNER JOIN anima_uc_usuario ucu ON u.usuario_id = ucu.usuario_id
        WHERE ucu.uc_id = %s
          AND u.usuario_validado = 1
          AND u.usuario_discord_id IS NOT NULL
          AND TRIM(u.usuario_discord_id) != ''
    """
    cur.execute(sql, (uc_id,))
    users = cur.fetchall()
    cur.close()
    conn.close()
    return uc_info, users

async def main():
    if not DISCORD_BOT_TOKEN:
        logger.error("DISCORD_BOT_TOKEN não configurado no .env!")
        return

    uc_info, users = get_validated_users_for_uc(UC_ID)
    if not uc_info:
        return

    role_id_str = uc_info.get("uc_discord_role")
    uc_nome = uc_info.get("uc_nome")

    if not role_id_str:
        logger.error(f"A UC '{uc_nome}' não possui uc_discord_role configurada.")
        return

    role_id = int(role_id_str)
    logger.info(f"UC: '{uc_nome}' (ID: {UC_ID}) | Role ID: {role_id}")
    logger.info(f"Total de usuários validados a processar: {len(users)}")

    intents = discord.Intents.default()
    intents.members = True  # Necessário para gerenciar membros e cargos
    intents.guilds = True

    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        logger.info(f"JocastaBOT logada com sucesso como {client.user} (ID: {client.user.id})")
        
        # Canal de auditoria
        audit_channel = client.get_channel(AUDITORIA_CHANNEL_ID)
        if not audit_channel:
            try:
                audit_channel = await client.fetch_channel(AUDITORIA_CHANNEL_ID)
            except Exception as e_audit:
                logger.error(f"Não foi possível obter canal de auditoria: {e_audit}")

        # Mensagem inicial no canal de auditoria
        if audit_channel:
            embed_inicio = discord.Embed(
                title="⚙️ JocastaBOT - Atribuição em Lote de Cargo por UC",
                description=f"Iniciando procedimento de sincronização de cargo para a UC **{uc_nome}** (ID: `{UC_ID}`).\n"
                            f"**Role alvo:** <@&{role_id}> (`{role_id}`)\n"
                            f"**Total de usuários validados elegíveis:** {len(users)}",
                color=discord.Color.blue()
            )
            await audit_channel.send(embed=embed_inicio)

        sucessos = 0
        ja_possuia = 0
        falhas = 0
        detalhes_log = []

        for u in users:
            d_id = int(u["usuario_discord_id"])
            u_nome = u["usuario_nome"]
            u_email = u.get("usuario_email") or u.get("usuario_email_pessoal") or "Sem email"
            d_name = u.get("usuario_discord_name") or "-"

            # Localiza membro em todas as guilds em que o bot está
            member = None
            guild_found = None
            for guild in client.guilds:
                target_role = guild.get_role(role_id)
                if target_role:
                    guild_found = guild
                    member = guild.get_member(d_id)
                    if not member:
                        try:
                            member = await guild.fetch_member(d_id)
                        except discord.NotFound:
                            pass
                        except Exception as e_fetch:
                            logger.warning(f"Erro ao buscar membro {d_id}: {e_fetch}")
                    break

            if not guild_found:
                logger.error(f"Não foi encontrada guilda com o cargo {role_id}!")
                falhas += 1
                detalhes_log.append(f"❌ **{u_nome}**: Cargo {role_id} não encontrado no servidor.")
                continue

            target_role = guild_found.get_role(role_id)

            if not member:
                logger.warning(f"Membro {u_nome} (Discord ID: {d_id}) não está no servidor {guild_found.name}.")
                falhas += 1
                detalhes_log.append(f"⚠️ **{u_nome}** (`{d_id}`): Não está no servidor.")
                continue

            # Verifica se o membro já tem o cargo
            if target_role in member.roles:
                logger.info(f"Membro {member.display_name} ({u_nome}) já possui o cargo {target_role.name}.")
                ja_possuia += 1
                continue

            try:
                await member.add_roles(target_role, reason=f"Inscrição Aceleradora Dual - UC {UC_ID} ({uc_nome})")
                logger.info(f"✅ Cargo {target_role.name} atribuído com sucesso para {member.display_name} ({u_nome})")
                sucessos += 1
                detalhes_log.append(f"✅ **{u_nome}** ({member.mention}) - Cargo adicionado.")
            except Exception as e_role:
                logger.error(f"Erro ao atribuir cargo para {u_nome} ({d_id}): {e_role}")
                falhas += 1
                detalhes_log.append(f"❌ **{u_nome}** ({member.mention}) - Erro: {e_role}")

        # Embed final no canal de auditoria
        if audit_channel:
            descricao_resumo = (
                f"**UC:** {uc_nome} (ID: `{UC_ID}`)\n"
                f"**Cargo:** <@&{role_id}>\n\n"
                f"📊 **Resultados:**\n"
                f"• Cargos atribuídos agora: **{sucessos}**\n"
                f"• Já possuíam o cargo: **{ja_possuia}**\n"
                f"• Não encontrados no servidor / erros: **{falhas}**\n"
                f"• Total avaliado: **{len(users)}**"
            )
            embed_fim = discord.Embed(
                title="📋 JocastaBOT - Conclusão de Atribuição de Cargos",
                description=descricao_resumo,
                color=discord.Color.green() if falhas == 0 else discord.Color.gold()
            )

            # Divide logs detalhados em blocos se necessário para não estourar o limite de embed do Discord
            if detalhes_log:
                chunks = []
                curr_chunk = ""
                for item in detalhes_log:
                    if len(curr_chunk) + len(item) + 1 > 1000:
                        chunks.append(curr_chunk)
                        curr_chunk = item + "\n"
                    else:
                        curr_chunk += item + "\n"
                if curr_chunk:
                    chunks.append(curr_chunk)

                for i, chunk in enumerate(chunks[:5]):
                    name_field = "Detalhes das Ações" if i == 0 else f"Detalhes (continuação {i+1})"
                    embed_fim.add_field(name=name_field, value=chunk, inline=False)

            await audit_channel.send(embed=embed_fim)
            logger.info("Relatório enviado para o canal de auditoria com sucesso.")

        await client.close()

    try:
        await client.start(DISCORD_BOT_TOKEN)
    except Exception as e_run:
        logger.error(f"Erro ao executar bot: {e_run}")

if __name__ == "__main__":
    asyncio.run(main())
