import os
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("DISCORD_BOT_TOKEN")
channel_id = os.getenv("DISCORD_BOASVINDAS_CHANNEL_ID", "1019994811840876635")

headers = {"Authorization": f"Bot {token}"}

res = requests.get(f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=100", headers=headers)
if res.status_code == 200:
    messages = res.json()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=3)
    deleted_count = 0
    
    for m in messages:
        mid = m['id']
        created_at_str = m.get('timestamp')
        if created_at_str:
            # ISO timestamp
            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            if created_at < cutoff:
                del_res = requests.delete(f"https://discord.com/api/v10/channels/{channel_id}/messages/{mid}", headers=headers)
                if del_res.status_code in (200, 204):
                    deleted_count += 1
                    
    print(f"Limpeza de mensagens anteriores a 3 horas concluida. Excluidas: {deleted_count}")
