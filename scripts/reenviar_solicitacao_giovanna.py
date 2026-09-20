import os
import sys
import asyncio
import logging
import mysql.connector
import discord
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("resend_audit")

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
AUDITORIA_CHANNEL_ID = int(os.getenv("DISCORD_AUDITORIA_CHANNEL_ID", "1020418840401813564"))

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

async def main():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # Busca o cadastro recente de Giovanna
    cur.execute("SELECT * FROM usuario WHERE usuario_discord_id = '1502721171517472861'")
    novo = cur.fetchone()

    if not novo:
        logger.error("Registro recente de Giovanna não encontrado!")
        return

    nome = novo['usuario_nome']
    current_id = novo['usuario_id']
    discord_id = novo['usuario_discord_id']
    discord_name = novo['usuario_discord_name']
    email_acad = novo['usuario_email']
    email_pessoal = novo.get('usuario_email_pessoal') or '12925123632@ulife.com.br'
    ra = novo['usuario_ra'] or '12925123632'
    ies = novo['ies_sigla'] or 'UniRitter'
    curso = novo['curso_sigla'] or 'ECP'

    # Busca pré-existente
    cur.execute(
        """
        SELECT usuario_id, usuario_nome, usuario_email, usuario_email_pessoal, ies_sigla, curso_sigla, usuario_ra, usuario_telefone
        FROM usuario
        WHERE LOWER(TRIM(usuario_nome)) = LOWER(TRIM(%s)) AND usuario_id != %s
        ORDER BY usuario_id ASC
        """,
        (nome, current_id)
    )
    duplicados = cur.fetchall() or []
    cur.close()
    conn.close()

    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True

    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        logger.info(f"Bot conectado como {client.user}!")
        channel = client.get_channel(AUDITORIA_CHANNEL_ID)
        if not channel:
            logger.error(f"Canal de auditoria {AUDITORIA_CHANNEL_ID} não encontrado.")
            await client.close()
            return

        msg_audit = (
            f"📌 **[SOLICITAÇÃO DE CADASTRO MANUAL PENDENTE]**\n\n"
            f"👤 **Nome:** {nome}\n"
            f"📧 **E-mail Acadêmico:** `{email_acad}`\n"
            f"✉️ **E-mail Pessoal:** `{email_pessoal or 'N/A'}`\n"
            f"🆔 **RA:** `{ra or 'N/A'}`\n"
            f"🏛️ **IES:** `{ies}` | 📚 **Curso:** `{curso}`\n"
            f"🎮 **Discord:** <@{discord_id}> (`{discord_name}` / ID: `{discord_id}`)\n"
            f"🔢 **ID Criado/Pendente:** `{current_id}`\n\n"
        )

        if duplicados:
            dup = duplicados[0]
            dup_id = dup['usuario_id']
            dup_email = dup.get('usuario_email') or dup.get('usuario_email_pessoal') or 'N/A'
            dup_tel = dup.get('usuario_telefone') or 'N/A'
            dup_ies = dup.get('ies_sigla') or 'N/A'
            dup_curso = dup.get('curso_sigla') or 'N/A'
            msg_audit += (
                f"⚠️ **ALERTA: CONTA PRÉ-EXISTENTE LOCALIZADA COM O MESMO NOME!**\n"
                f"Encontrado registro mais antigo: **ID `{dup_id}`** ({dup['usuario_nome']})\n"
                f"• E-mail cadastrado anteriormente: `{dup_email}`\n"
                f"• Telefone: `{dup_tel}` | IES: `{dup_ies}` | Curso: `{dup_curso}`\n\n"
                f"🔀 **Deseja fundir este cadastro no registro antigo (ID {dup_id})?**\n"
                f"Use o comando:\n"
                f"`/fundir_usuario id_manter:{dup_id} usuario_discord:<@{discord_id}>`\n\n"
                f"Ou para aprovar normalmente como cadastro separado (ID {current_id}):\n"
                f"`/aprovar usuario_discord:<@{discord_id}>`"
            )
        else:
            msg_audit += (
                f"🔑 **Para aprovar este cadastro, use o comando:**\n"
                f"`/aprovar usuario_discord:<@{discord_id}>`"
            )

        await channel.send(msg_audit)
        logger.info("Mensagem de solicitação pendente reenviada com sucesso para o canal de auditoria!")
        await client.close()

    await client.start(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
