import os
import mysql.connector
import discord
from dotenv import load_dotenv

load_dotenv()

conn = mysql.connector.connect(
    host=os.getenv("DB_HOST", "db"),
    port=int(os.getenv("DB_PORT", "3306")),
    database=os.getenv("DB_NAME", "anima"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    charset="utf8mb4",
    use_pure=True,
    connection_timeout=5,
)
cur = conn.cursor(dictionary=True)

sql = """
    SELECT curso_id, curso_parceira, curso_nome, curso_descricao, curso_dt_inicio, curso_dt_fim, curso_carga_horaria, curso_idioma, curso_url_inscricao
    FROM curso
    WHERE curso_dt_inicio <= NOW() AND curso_dt_fim >= NOW()
    ORDER BY curso_parceira ASC, curso_nome ASC
"""
cur.execute(sql)
cursos = cur.fetchall()
cur.close()
conn.close()

print(f"Total de cursos encontrados: {len(cursos)}")

embed = discord.Embed(
    title="📚 Catálogo de Cursos Parceiros Disponíveis",
    description=(
        "Confira abaixo os cursos com inscrições abertas!\n"
        "Para se inscrever em qualquer um deles, use o comando `/inscrever` e selecione o curso no menu suspenso.\n"
    ),
    color=0x3b82f6
)

for c in cursos:
    dt_ini = c['curso_dt_inicio'].strftime('%d/%m/%Y') if c['curso_dt_inicio'] else '-'
    dt_fim = c['curso_dt_fim'].strftime('%d/%m/%Y') if c['curso_dt_fim'] else '-'
    
    # Idioma (exibe quando disponível)
    idioma_map = {
        'pt-br': '🇧🇷 Português do Brasil (pt-br)',
        'en-us': '🇺🇸 Inglês (en-us)'
    }
    idioma_line = ""
    bandeira = ""
    if c.get('curso_idioma'):
        idioma_key = str(c['curso_idioma']).lower().strip()
        idioma_nome = idioma_map.get(idioma_key, c['curso_idioma'])
        idioma_line = f"🌐 **Idioma:** `{idioma_nome}`\n"
        bandeira = " 🇺🇸" if idioma_key == 'en-us' else (" 🇧🇷" if idioma_key == 'pt-br' else "")

    # Carga Horária (exibe quando disponível)
    ch_line = f"⏱️ **Carga Horária:** `{c['curso_carga_horaria']} horas`\n" if c.get('curso_carga_horaria') else ""
    ch_tag = f" ({c['curso_carga_horaria']}h)" if c.get('curso_carga_horaria') else ""

    # Descrição
    desc_line = f"📝 {c['curso_descricao']}\n\n" if c.get('curso_descricao') else ""
    
    field_val = (
        f"{desc_line}"
        f"{idioma_line}"
        f"{ch_line}"
        f"📅 **Período de Inscrição:** `{dt_ini}` até `{dt_fim}`\n"
    )
    
    if c.get('curso_url_inscricao'):
        field_val += f"🔗 [Link de Auto-Inscrição Direta]({c['curso_url_inscricao']})\n"
    else:
        field_val += f"💡 *Use `/inscrever` e selecione este curso no menu.*\n"

    embed.add_field(
        name=f"🎓 [{c['curso_parceira']}] {c['curso_nome']}{ch_tag}{bandeira}",
        value=field_val,
        inline=False
    )

print(f"Número de campos no Embed: {len(embed.fields)}")
print(f"Tamanho total de caracteres no Embed: {len(embed)}")

# Discord Embed Limits:
# - Max fields: 25
# - Max total characters per embed: 6000
# - Max value per field: 1024
# - Max embeds per message: 10
if len(embed.fields) > 25:
    print(f"[ALERTA] Excedeu o limite de 25 campos! (Total: {len(embed.fields)})")
if len(embed) > 6000:
    print(f"[ALERTA] Excedeu o limite de 6000 caracteres! (Total: {len(embed)})")
