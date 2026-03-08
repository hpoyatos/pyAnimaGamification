import os
import requests
import logging

logger = logging.getLogger("discord_api")

def send_discord_dm(discord_user_id: str, usuario_nome: str, num_pontos: float, justificativa: str):
    """
    Usa a API RESTful do Discord para enviar uma mensagem direta a um usuário 
    usando o token HTTP do bot.
    """
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token or not discord_user_id:
        logger.warning(f"Ignorando DM para {usuario_nome}. Token: {'OK' if token else 'FALTOU'}, Discord ID: {discord_user_id}")
        return False
        
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }
    
    # 1. Abre o canal DM (POST /users/@me/channels)
    dm_url = "https://discord.com/api/v10/users/@me/channels"
    dm_payload = {"recipient_id": str(discord_user_id)}
    
    try:
        dm_response = requests.post(dm_url, headers=headers, json=dm_payload)
        dm_response.raise_for_status()
        dm_data = dm_response.json()
        channel_id = dm_data.get("id")
        
        if not channel_id:
            logger.error("Falha ao obter channel_id da resposta da API do Discord.")
            return False
            
        # 2. Envia a mensagem (POST /channels/{channel_id}/messages)
        msg_url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        
        # Formata os pontos sem casa decimal se for inteiro
        pontos_str = str(num_pontos).replace('.', ',')
        if num_pontos.is_integer():
            pontos_str = str(int(num_pontos))
            
        texto_msg = (
            f"Uau! Parabéns, **{usuario_nome}**! 🎉\n\n"
            f"Você acaba de receber **{pontos_str} ponto(s)** por sua excelente participação em aula!\n"
            f"**Motivo:** {justificativa}\n\n"
            "_Continue assim! Você pode consultar seu total com o comando `/pontos`._"
        )
        
        msg_payload = {"content": texto_msg}
        msg_response = requests.post(msg_url, headers=headers, json=msg_payload)
        msg_response.raise_for_status()
        
        logger.info(f"DM de participação enviada com sucesso para {usuario_nome} ({discord_user_id}).")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro na requisição da API do Discord para o usuario_id {discord_user_id}: {e}")
        if e.response is not None:
             logger.error(f"Detalhes do erro: {e.response.text}")
        return False
