import os
import requests
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("DISCORD_BOT_TOKEN")
if not token:
    print("[ERRO] DISCORD_BOT_TOKEN não encontrado.")
    exit(1)

headers = {"Authorization": f"Bot {token}"}

# 1. Busca as guilds do bot
res_guilds = requests.get("https://discord.com/api/v10/users/@me/guilds", headers=headers)
guilds = res_guilds.json()
print(f"Guilds encontradas: {len(guilds)}")

discord_roles_map = {}
for g in guilds:
    g_id = g['id']
    g_name = g['name']
    print(f"Buscando roles da guild: {g_name} ({g_id})...")
    res_roles = requests.get(f"https://discord.com/api/v10/guilds/{g_id}/roles", headers=headers)
    roles = res_roles.json()
    print(f"Total de roles na guild {g_name}: {len(roles)}")
    for r in roles:
        # Ignora @everyone
        if r['name'] != '@everyone':
            discord_roles_map[str(r['id'])] = r['name']

print(f"\nTotal de roles mapeadas no Discord: {len(discord_roles_map)}")
for rid, rname in list(discord_roles_map.items())[:20]:
    print(f"  {rid} -> {rname}")
