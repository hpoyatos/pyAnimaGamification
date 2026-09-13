import os
import logging
import requests
import socket
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("utils.llm_helper")

def get_ollama_endpoints():
    """
    Retorna a lista ordenada de endpoints candidatos para o Ollama:
    1. Valor explícito de OLLAMA_HOST do .env / ambiente
    2. IP do Host principal da infraestrutura: http://192.168.15.254:11434
    3. Serviços K3s/Docker comuns: ollama-svc, ollama, host.docker.internal
    4. http://localhost:11434
    """
    candidates = []
    env_h = os.getenv("OLLAMA_HOST")
    if env_h and env_h.strip():
        candidates.append(env_h.strip().rstrip("/"))

    defaults = [
        "http://192.168.15.254:11434",
        "http://ollama-svc:11434",
        "http://ollama:11434",
        "http://host.docker.internal:11434",
        "http://localhost:11434"
    ]
    for d in defaults:
        if d not in candidates:
            candidates.append(d)
    return candidates

def get_available_model(endpoint: str, desired_model: str) -> str:
    """Verifica os modelos disponíveis no Ollama e seleciona o mais adequado."""
    try:
        r = requests.get(f"{endpoint}/api/tags", timeout=3)
        if r.status_code == 200:
            models_list = [m.get("name", "") for m in r.json().get("models", [])]
            for m in models_list:
                if m == desired_model or m.startswith(desired_model) or desired_model in m:
                    return m
            if models_list:
                print(f"[LLaMA/Ollama] Modelo '{desired_model}' não encontrado em {endpoint}. Usando instalado: '{models_list[0]}'", flush=True)
                return models_list[0]
    except Exception:
        pass
    return desired_model

def _get_ollama_timeout():
    """Retorna o timeout de leitura em segundos. Se <= 0, retorna None (sem limite)."""
    raw = os.getenv("OLLAMA_TIMEOUT", "3600")
    try:
        val = int(raw)
        return val if val > 0 else None
    except ValueError:
        return 1800

def _is_refusal_response(text: str, original_len: int) -> bool:
    """Detecta se a IA se recusou a responder ou devolveu mensagem de recusa padrão."""
    if not text or not text.strip():
        return True
    t_lower = text.strip().lower()
    refusal_keywords = [
        "não posso ajudar",
        "nao posso ajudar",
        "não posso atender",
        "nao posso atender",
        "não consigo ajudar",
        "nao consigo ajudar",
        "não posso cumprir",
        "nao posso cumprir",
        "não posso realizar",
        "nao posso realizar",
        "i cannot help",
        "i can't help",
        "i am unable to",
        "as an ai",
        "como um modelo de linguagem",
        "como uma inteligência artificial",
        "desculpe, mas não posso",
        "desculpe, mas não consigo",
        "sinto muito, mas não posso"
    ]
    for kw in refusal_keywords:
        if kw in t_lower:
            return True
    # Se o texto original era informativo (> 60 caracteres) e a resposta ficou minúscula (< 25 caracteres)
    if original_len > 60 and len(text.strip()) < 25:
        return True
    return False

def gerar_variacao_aviso(texto_original: str, instrucao_personalizada: str = None) -> str:
    """
    Chama um endpoint de LLM local (Ollama ou compatível OpenAI/Llama)
    para reescrever o aviso com variações sutis no vocabulário e estilo.
    Se a IA falhar ou recusar o pedido, retorna o texto original com segurança.
    """
    if not texto_original or not texto_original.strip():
        return texto_original

    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
    ollama_timeout = _get_ollama_timeout()

    instrucao_sistema = (
        "Você é o assistente pedagógico JocastaBOT da comunidade de gamificação acadêmica Anima. "
        "Sua tarefa é apenas reescrever o comunicado acadêmico abaixo com pequenas variações de vocabulário e estilo "
        "para torná-lo dinâmico e envolvente para os estudantes universitários.\n\n"
        "REGRAS ABSOLUTAS:\n"
        "1. Mantenha 100% de todos os links (URLs), comandos do Discord (ex: /inscrever_curso, /pontos), IDs, datas e informações factuais.\n"
        "2. Mantenha o formato com emojis e destaques em negrito do Discord.\n"
        "3. Não invente informações novas e não altere os requisitos do aviso.\n"
        "4. Responda DIRETAMENTE com o texto do aviso reescrito, sem introduções como 'Aqui está' e sem aspas."
    )

    if instrucao_personalizada and instrucao_personalizada.strip():
        instrucao_sistema += f"\nObservação extra do coordenador: {instrucao_personalizada.strip()}"

    endpoints = get_ollama_endpoints()
    for endpoint in endpoints:
        modelo_alvo = get_available_model(endpoint, ollama_model)
        timeout_desc = f"{ollama_timeout}s" if ollama_timeout else "ilimitado"

        # 1. Tenta via /api/chat (formato nativo e robusto para modelos LLaMA 3/3.2)
        chat_url = f"{endpoint}/api/chat"
        chat_payload = {
            "model": modelo_alvo,
            "messages": [
                {"role": "system", "content": instrucao_sistema},
                {"role": "user", "content": f"Reescreva este comunicado com vocabulário alternativo:\n\n{texto_original}"}
            ],
            "stream": False,
            "options": {
                "temperature": 0.5,
                "top_p": 0.9,
                "num_predict": 450
            }
        }
        try:
            print(f"[LLaMA/Ollama] Solicitando variação de aviso via /api/chat em {endpoint} (modelo: {modelo_alvo}, timeout: {timeout_desc})...", flush=True)
            res_chat = requests.post(chat_url, json=chat_payload, timeout=(10, ollama_timeout))
            if res_chat.status_code == 200:
                data = res_chat.json()
                resp = data.get("message", {}).get("content", "").strip()
                if resp:
                    if _is_refusal_response(resp, len(texto_original)):
                        print(f"[LLaMA/Ollama] ⚠️ Resposta descartada por recusa/inconsistência: '{resp}'. Usando texto original.", flush=True)
                        return texto_original
                    print(f"[LLaMA/Ollama] 🎉 Variação de aviso gerada com sucesso via /api/chat ({len(resp)} caracteres)!", flush=True)
                    return resp
        except Exception as e_chat:
            logger.warning(f"Falha ao chamar /api/chat em {endpoint}: {e_chat}. Tentando /api/generate...")

        # 2. Fallback para /api/generate
        gen_url = f"{endpoint}/api/generate"
        gen_payload = {
            "model": modelo_alvo,
            "prompt": f"{instrucao_sistema}\n\nAviso Original:\n{texto_original}\n\nAviso Reescrito:",
            "stream": False,
            "options": {
                "temperature": 0.5,
                "top_p": 0.9,
                "num_predict": 450
            }
        }
        try:
            res_gen = requests.post(gen_url, json=gen_payload, timeout=(10, ollama_timeout))
            if res_gen.status_code == 200:
                data = res_gen.json()
                resp = data.get("response", "").strip()
                if resp:
                    if _is_refusal_response(resp, len(texto_original)):
                        print(f"[LLaMA/Ollama] ⚠️ Resposta descartada por recusa: '{resp}'. Usando texto original.", flush=True)
                        return texto_original
                    print(f"[LLaMA/Ollama] 🎉 Variação de aviso gerada com sucesso via /api/generate!", flush=True)
                    return resp
        except Exception as e_gen:
            logger.warning(f"Falha ao chamar /api/generate em {endpoint}: {e_gen}")
            continue

    print("[LLaMA/Ollama] ⚠️ Todos os endpoints falharam ou recusaram. Mantendo aviso original.", flush=True)
    return texto_original

def gerar_descricao_quiz(titulo_quiz: str, perguntas_com_alternativas: list) -> str:
    """
    Gera uma descrição envolvente, concisa e informativa para um Quiz baseando-se
    no seu título, perguntas e alternativas.
    Retorna a string gerada pela IA ou uma descrição padrão em caso de falha.
    """
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
    ollama_timeout = _get_ollama_timeout()

    # Monta o resumo das questões e alternativas
    linhas_perguntas = []
    if perguntas_com_alternativas:
        for idx, item in enumerate(perguntas_com_alternativas, 1):
            enunciado = item.get("enunciado", "").strip()
            alts = item.get("alternativas", [])
            alts_str = ", ".join([f"{a.get('letra')}) {a.get('texto')}" for a in alts if a.get('texto')])
            if alts_str:
                linhas_perguntas.append(f"Pergunta {idx}: {enunciado} [Alternativas: {alts_str}]")
            else:
                linhas_perguntas.append(f"Pergunta {idx}: {enunciado}")

    bloco_conteudo = "\n".join(linhas_perguntas) if linhas_perguntas else f"Quiz focado nos tópicos de: {titulo_quiz}"

    prompt_sistema = (
        "Você é um assistente pedagógico da plataforma de gamificação Anima.\n"
        "Sua tarefa é gerar a descrição de um Quiz acadêmico em EXATAMENTE UMA ÚNICA FRASE instigante e direta, enumerando os assuntos abordados.\n\n"
        "ESTRUTURA OBRIGATÓRIA:\n"
        "Inicie a frase com 'Avalie o quanto você sabe sobre [Título/Tema]', enumere os principais conceitos e tópicos das perguntas separados por vírgula, e finalize com ', além de [aspecto prático/ético/mercado].'\n\n"
        "EXEMPLOS DE REFERÊNCIA (SIGA ESTRITAMENTE ESTE FORMATO):\n"
        "- Exemplo 1: Avalie o quanto você sabe sobre a LGPD, seus pilares, a classificação de dados pessoais e sensíveis, além da ética em projetos de dados e o perfil do profissional de dados do futuro.\n"
        "- Exemplo 2: Avalie o quanto você sabe sobre Estruturas de Dados, arrays, listas encadeadas, pilhas e filas, além da complexidade de algoritmos e sua eficiência no desenvolvimento de software.\n"
        "- Exemplo 3: Avalie o quanto você sabe sobre Computação em Nuvem, modelos IaaS, PaaS e SaaS, arquiteturas escaláveis e segurança, além do impacto estratégico em soluções corporativas.\n\n"
        "REGRAS:\n"
        "1. Escreva estritamente UMA ÚNICA FRASE (sem quebras de linha, sem ponto e vírgula, sem múltiplos parágrafos).\n"
        "2. NÃO coloque aspas no início ou fim.\n"
        "3. NÃO use saudações nem metalinguagem como 'Aqui está' ou 'Descrição:'.\n"
        "4. NÃO revele o gabarito de nenhuma questão.\n"
        "5. Responda DIRETAMENTE com a frase gerada."
    )

    prompt_usuario = (
        f"Título do Quiz: {titulo_quiz}\n\n"
        f"Conteúdo das Perguntas e Alternativas:\n{bloco_conteudo}\n\n"
        f"Descrição em frase única (começando com 'Avalie o quanto você sabe sobre'):"
    )

    endpoints = get_ollama_endpoints()
    for endpoint in endpoints:
        modelo_alvo = get_available_model(endpoint, ollama_model)
        payload = {
            "model": modelo_alvo,
            "prompt": f"{prompt_sistema}\n\n{prompt_usuario}",
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.9,
                "num_predict": 90
            }
        }
        url = f"{endpoint}/api/generate"
        try:
            timeout_desc = f"{ollama_timeout}s" if ollama_timeout else "ilimitado"
            print(f"[LLaMA/Ollama] Disparando geração de descrição para '{titulo_quiz}' em {url} (modelo: {modelo_alvo}, timeout: {timeout_desc})...", flush=True)
            response = requests.post(url, json=payload, timeout=(10, ollama_timeout))
            if response.status_code == 200:
                data = response.json()
                descricao = data.get("response", "").strip()
                if descricao:
                    # Remove prefixos comuns de IA
                    for prefix in ["Descrição:", "Descrição do Quiz:", "Descricao:", "Aqui está a descrição:", "Aqui está:"]:
                        if descricao.startswith(prefix):
                            descricao = descricao[len(prefix):].strip()
                    # Remove aspas caso o modelo tenha colocado
                    descricao = descricao.strip('"\'')
                    # Garante frase única contínua sem quebras de linha
                    descricao = " ".join(descricao.split())
                    if not descricao.endswith("."):
                        descricao += "."
                    print(f"[LLaMA/Ollama] 🎉 Descrição gerada com sucesso via {endpoint} ({len(descricao)} caracteres)!", flush=True)
                    return descricao
            else:
                print(f"[LLaMA/Ollama] Endpoint {endpoint} respondeu HTTP {response.status_code}: {response.text}", flush=True)
        except requests.exceptions.ConnectionError:
            print(f"[LLaMA/Ollama] Conexão recusada em {endpoint}, tentando próximo endpoint...", flush=True)
            continue
        except requests.exceptions.Timeout:
            print(f"[LLaMA/Ollama] Timeout ({timeout_desc}) em {endpoint}, tentando próximo...", flush=True)
            continue
        except Exception as e:
            print(f"[LLaMA/Ollama] Erro ao consultar {endpoint}: {e}", flush=True)
            continue

    print(f"[LLaMA/Ollama] ⚠️ Todos os endpoints falharam ao gerar descrição para '{titulo_quiz}'. Usando fallback.", flush=True)
    # Fallback caso a IA não responda
    return f"Avalie o quanto você sabe sobre {titulo_quiz}, seus conceitos fundamentais e ferramentas, além de suas aplicações práticas no mercado de tecnologia."

