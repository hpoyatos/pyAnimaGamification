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
            f"_Continue assim! Você pode consultar seu total com o comando `/pontos`._"
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


def send_matricula_recusada_dm(discord_user_id: str, usuario_nome: str, curso_nome: str, motivo: str) -> bool:
    """
    Envia uma mensagem privada no Discord notificando o aluno sobre a recusa/cancelamento
    de sua solicitação de inscrição no curso, informando o motivo.
    """
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token or not discord_user_id:
        logger.warning(f"Ignorando DM de cancelamento para {usuario_nome}. Token ou discord_user_id ausente.")
        return False

    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }

    try:
        # 1. Abre o canal DM
        dm_url = "https://discord.com/api/v10/users/@me/channels"
        dm_payload = {"recipient_id": str(discord_user_id)}
        
        dm_response = requests.post(dm_url, headers=headers, json=dm_payload)
        dm_response.raise_for_status()
        channel_id = dm_response.json().get("id")

        if not channel_id:
            logger.error("Falha ao abrir canal DM para notificação de recusa.")
            return False

        # 2. Envia a notificação com Embed
        msg_url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        
        motivo_limpo = motivo.strip() if motivo else "Nenhum detalhe adicional informado."
        
        embed_payload = {
            "embeds": [{
                "title": "🚫 Atualização na Solicitação de Inscrição",
                "description": (
                    f"Olá, **{usuario_nome}**!\n\n"
                    f"Sua solicitação de inscrição para o curso **{curso_nome}** foi **recusada/cancelada**.\n\n"
                    f"📋 **Motivo informado pela coordenação/professor:**\n"
                    f"> {motivo_limpo}\n\n"
                    f"💡 *Caso deseje tirar dúvidas ou escolher outro curso parceiro, utilize o comando `/inscrever_curso` no Discord ou procure o professor responsável.*"
                ),
                "color": 0xef4444,
                "footer": {
                    "text": "PyAnima Gamification • Gestão Acadêmica"
                }
            }]
        }

        msg_response = requests.post(msg_url, headers=headers, json=embed_payload)
        msg_response.raise_for_status()

        logger.info(f"Notificação de recusa de matrícula enviada com sucesso para {usuario_nome} ({discord_user_id}).")
        return True

    except Exception as e:
        logger.error(f"Erro ao enviar DM de matrícula recusada para {discord_user_id}: {e}")
        return False
