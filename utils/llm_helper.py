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
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
    ollama_timeout = int(os.getenv("OLLAMA_TIMEOUT", "300")) # 5 minutos por padrão para hardware modesto


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
        logger.info(f"Tentando gerar variação de aviso via Ollama ({url}, modelo: {ollama_model}, timeout: {ollama_timeout}s)...")
        response = requests.post(url, json=payload, timeout=ollama_timeout)

        
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


def gerar_descricao_quiz(titulo_quiz: str, perguntas_com_alternativas: list) -> str:
    """
    Gera uma descrição envolvente, concisa e informativa para um Quiz baseando-se
    no seu título, perguntas e alternativas.
    Retorna a string gerada pela IA ou uma descrição padrão em caso de falha.
    """
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
    ollama_timeout = int(os.getenv("OLLAMA_TIMEOUT", "300"))

    # Monta o resumo das questões e alternativas
    linhas_perguntas = []
    for idx, item in enumerate(perguntas_com_alternativas, 1):
        enunciado = item.get("enunciado", "").strip()
        alts = item.get("alternativas", [])
        alts_str = ", ".join([f"{a.get('letra')}) {a.get('texto')}" for a in alts if a.get('texto')])
        if alts_str:
            linhas_perguntas.append(f"Pergunta {idx}: {enunciado} [Alternativas: {alts_str}]")
        else:
            linhas_perguntas.append(f"Pergunta {idx}: {enunciado}")

    bloco_conteudo = "\n".join(linhas_perguntas) if linhas_perguntas else "Sem perguntas detalhadas cadastradas ainda."

    prompt_sistema = (
        "Você é o especialista pedagógico da plataforma de gamificação acadêmica Anima.\n"
        "Sua tarefa é criar uma descrição/resumo envolvente, profissional e cativante para um Quiz de estudantes, "
        "com base no título e no conteúdo das perguntas e alternativas fornecidas abaixo.\n\n"
        "DIRETRIZES:\n"
        "1. Escreva 1 a 2 parágrafos curtos explicando os temas centrais abordados no quiz e convidando os estudantes a testarem seus conhecimentos.\n"
        "2. Destaque as principais habilidades ou tópicos conceituais presentes nas perguntas.\n"
        "3. Não mencione o gabarito ou qual alternativa está correta.\n"
        "4. Responda APENAS com o texto da descrição, sem títulos prévios como 'Descrição:' ou 'Aqui está a descrição:'."
    )

    prompt_usuario = (
        f"Título do Quiz: {titulo_quiz}\n\n"
        f"Perguntas e Alternativas:\n{bloco_conteudo}\n\n"
        f"Descrição do Quiz:"
    )

    payload = {
        "model": ollama_model,
        "prompt": f"{prompt_sistema}\n\n{prompt_usuario}",
        "stream": False,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9
        }
    }

    try:
        url = f"{ollama_host}/api/generate"
        logger.info(f"Gerando descrição do quiz '{titulo_quiz}' via Ollama ({url}, modelo: {ollama_model})...")
        response = requests.post(url, json=payload, timeout=ollama_timeout)
        if response.status_code == 200:
            data = response.json()
            descricao = data.get("response", "").strip()
            if descricao:
                logger.info(f"Descrição gerada com sucesso para o quiz '{titulo_quiz}'.")
                return descricao
    except Exception as e:
        logger.error(f"Erro ao gerar descrição com LLaMA para o quiz: {e}")

    # Fallback caso a IA não responda
    return f"Quiz interativo sobre {titulo_quiz}, testando conceitos teóricos e práticos aplicados em sala de aula."

