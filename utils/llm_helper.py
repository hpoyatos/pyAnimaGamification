import os
import logging
import requests

logger = logging.getLogger("utils.llm_helper")

def gerar_variacao_aviso(texto_original: str, instrucao_personalizada: str = None) -> str:
    """
    Chama um endpoint de LLM local (Ollama ou compatível OpenAI/Llama)
    para reescrever o aviso com variações sutis no vocabulário e estilo,
    tornando-o mais natural sem perder nenhuma informação essencial, links ou datas.
    
    Se o LLM não responder ou ocorrer erro, faz fallback seguro para o texto_original.
    """
    if not texto_original or not texto_original.strip():
        return texto_original

    # Configurações do endpoint LLM local
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2:latest")

    instrucao_sistema = (
        "Você é o assistente JocastaBOT da comunidade de gamificação acadêmica Anima. "
        "Sua tarefa é reescrever o aviso fornecido fazendo pequenas variações nas palavras e frases "
        "para que pareça novo, dinâmico e natural para os alunos.\n"
        "REGRAS ESTRITAS:\n"
        "1. Mantenha exatamente todas as informações factuais, links (URLs), IDs, datas, prazos e comandos do Discord (ex: /pontos, /inscrever_curso).\n"
        "2. Preserve a formatação do Discord (emojis, negritos, itálicos, tópicos se houver).\n"
        "3. Não invente nenhuma informação nova.\n"
        "4. Responda APENAS com o texto final reescrito, sem introduções, sem saudações do tipo 'Aqui está' e sem aspas."
    )

    if instrucao_personalizada and instrucao_personalizada.strip():
        instrucao_sistema += f"\nObservação extra do coordenador: {instrucao_personalizada.strip()}"

    payload = {
        "model": ollama_model,
        "prompt": f"{instrucao_sistema}\n\nAviso Original:\n{texto_original}\n\nAviso Variado:",
        "stream": False,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9
        }
    }

    try:
        url = f"{ollama_host}/api/generate"
        logger.info(f"Tentando gerar variação de aviso via Ollama ({url}, modelo: {ollama_model})...")
        response = requests.post(url, json=payload, timeout=25)
        
        if response.status_code == 200:
            data = response.json()
            resposta_llm = data.get("response", "").strip()
            if resposta_llm:
                logger.info("Variação gerada com sucesso pelo LLaMA/Ollama!")
                return resposta_llm
            else:
                logger.warning("Ollama retornou resposta vazia. Usando texto original.")
        else:
            logger.warning(f"Ollama respondeu status {response.status_code}: {response.text}")
    except requests.exceptions.Timeout:
        logger.warning("Timeout ao aguardar resposta do LLM local (Ollama). Usando texto original.")
    except requests.exceptions.ConnectionError:
        logger.warning(f"Não foi possível conectar ao Ollama em {ollama_host}. Usando texto original.")
    except Exception as e:
        logger.error(f"Erro inesperado ao consultar LLM local: {e}")

    # Fallback seguro: retorna o texto original intacto
    return texto_original
