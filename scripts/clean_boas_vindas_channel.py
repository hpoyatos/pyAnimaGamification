import os
import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("DISCORD_BOT_TOKEN")
channel_id = os.getenv("DISCORD_BOASVINDAS_CHANNEL_ID", "1019994811840876635")

headers = {"Authorization": f"Bot {token}"}

res = requests.get(f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=50", headers=headers)
if res.status_code == 200:
    messages = res.json()
    deleted_count = 0
    for m in messages:
        mid = m['id']
        author = m.get('author', {})
        is_bot = author.get('bot', False)
        if not is_bot:
            del_res = requests.delete(f"https://discord.com/api/v10/channels/{channel_id}/messages/{mid}", headers=headers)
            if del_res.status_code in (200, 204):
                deleted_count += 1
    print(f"Varredura concluida. Total de mensagens nao-bot excluidas: {deleted_count}")
