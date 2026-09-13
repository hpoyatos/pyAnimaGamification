import os
import sys
import socket
import time
import datetime
import re
import imaplib
import email
from email.header import decode_header
try:
    from dotenv import load_dotenv, dotenv_values
    load_dotenv(override=True)
except Exception:
    load_dotenv = None
    dotenv_values = None
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import base64
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import mysql.connector
import requests

def get_time():
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)).strftime('%H:%M:%S')

def get_aws_credentials():
    """
    Obtém as credenciais AWS EXCLUSIVAMENTE do arquivo .env.
    Lê o arquivo diretamente do disco para garantir que alterações recentes no .env
    sejam refletidas imediatamente, sem usar valores antigos herdados do processo pai.
    """
    env_paths = [
        os.path.join(os.getcwd(), '.env'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'),
        '/home/hpoyatos/CodeProjects/pyAnimaGamification/.env',
        '/app/.env',
        '.env'
    ]
    
    email = None
    password = None
    loaded_from = None

    for p in env_paths:
        if os.path.exists(p) and os.path.isfile(p):
            loaded_from = os.path.abspath(p)
            # 1. Leitura direta do arquivo no disco linha por linha (prioridade absoluta)
            try:
                with open(loaded_from, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#') or '=' not in line:
                            continue
                        k, v = line.split('=', 1)
                        k = k.strip()
                        v = v.strip()
                        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                            v = v[1:-1]
                        if k == 'AWS_EMAIL' and not email:
                            email = v
                        elif k == 'AWS_PASSWORD' and not password:
                            password = v
            except Exception as e:
                print(f"[{get_time()}] Aviso ao ler .env diretamente: {e}")

            # 2. Se algo faltou, tenta dotenv_values
            if (not email or not password) and dotenv_values:
                try:
                    vals = dotenv_values(loaded_from)
                    if not email:
                        email = vals.get('AWS_EMAIL')
                    if not password:
                        password = vals.get('AWS_PASSWORD')
                except Exception:
                    pass

            # Sincroniza com os.environ
            if load_dotenv:
                try:
                    load_dotenv(loaded_from, override=True)
                except Exception:
                    pass

            if email and password:
                break

    # Fallback se não conseguir abrir o arquivo físico
    if not email:
        email = os.getenv('AWS_EMAIL')
    if not password:
        password = os.getenv('AWS_PASSWORD')

    # Garante que os.environ receba os valores limpos (sem qualquer quebra de linha \r ou \n)
    if email:
        email = str(email).strip().replace('\r', '').replace('\n', '')
        os.environ['AWS_EMAIL'] = email
    if password:
        password = str(password).strip().replace('\r', '').replace('\n', '')
        os.environ['AWS_PASSWORD'] = password

    return email, password, loaded_from

def fetch_aws_verification_code():
    """
    Conecta na Gmail API via OAuth2 e busca o código de verificação
    enviado por support@awsacademy.com de forma rápida.
    """
    creds = None
    # Verifica se o token.json existe no ambiente do container
    if os.path.exists('selenium_bot/token.json'):
        # Caminho caso executado na raiz do projeto
        token_path = 'selenium_bot/token.json'
    elif os.path.exists('token.json'):
        # Caminho caso executado de dentro da pasta selenium_bot
        token_path = 'token.json'
    else:
        print(f"[{get_time()}] Erro: Arquivo 'token.json' de OAuth não encontrado. Rode o selenium_bot/generate_gmail_token.py primeiro.")
        return None

    try:
        creds = Credentials.from_authorized_user_file(token_path, ['https://www.googleapis.com/auth/gmail.readonly'])
        
        # Constrói o client side do serviço
        service = build('gmail', 'v1', credentials=creds)
        
        # Filtra os e-mails mais recentes do remetente alvo
        print(f"[{get_time()}] Buscando emails do remetente support@awsacademy.com via Gmail API...")
        query = 'from:support@awsacademy.com subject:"Verification Code For Login"'
        
        # Tenta buscar os unwatched
        results = service.users().messages().list(userId='me', q=query + " is:unread", maxResults=1).execute()
        messages = results.get('messages', [])
        
        if not messages:
            print(f"[{get_time()}] Nenhum email não lido encontrado. Buscando os mais recentes no geral...")
            results = service.users().messages().list(userId='me', q=query, maxResults=1).execute()
            messages = results.get('messages', [])

        if not messages:
            print(f"[{get_time()}] Nenhum email de support@awsacademy.com encontrado.")
            return None

        # Pega a thread/mensagem específica
        msg_id = messages[0]['id']
        msg_obj = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        
        # Leitura rudimentar dos Headers para logging
        headers = msg_obj['payload'].get('headers', [])
        subject = next((header['value'] for header in headers if header['name'].lower() == 'subject'), 'Sem Assunto')
            
        print(f"[{get_time()}] Processando email recente ID {msg_id}: Assunto -> '{subject}'")
        
        # Extrai o corpo do e-mail da API
        body = ""
        parts = msg_obj['payload'].get('parts', [])
        # Tratamento de Partes Multipart (HTML vs Plain)
        if parts:
            for part in parts:
                if part['mimeType'] == 'text/plain' or part['mimeType'] == 'text/html':
                    encoded_data = part['body'].get('data')
                    if encoded_data:
                        body += base64.urlsafe_b64decode(encoded_data).decode('utf-8')
        else:
            # Tratamento de Part único
            encoded_data = msg_obj['payload']['body'].get('data')
            if encoded_data:
                body = base64.urlsafe_b64decode(encoded_data).decode('utf-8')

        # O código tem exatamente 6 caracteres numéricos e alfa (A-Z, 0-9), todos MAIÚSCULOS.
        # Ex: "WB8UZT"
        # O HTML tem um bloco que diz: "Please use the verification code below...<br><br><font...>WB8UZT</font>"
        # Vamos usar um regex agressivo
        
        # Removemos quebras de linha temporariamente para o Regex atuar melhor em tags
        body_clean = re.sub(r'\s+', ' ', body)
        
        # Padrão: 6 letras maíusculas ou dígitos, sozinhos (" WB8UZT ") ou com tags ("<font>WB8UZT</font>")
        # Cuidado para não pegar outras palavras de 6 letras como "Please" ou afins (maiusculas+digitos)
        matches = re.findall(r'\b([A-Z0-9]{6})\b', body_clean)
        
        code_found = None
        for m in matches:
            # Elimina coisas obvias que possam ser codigos HEX se houver (branco/preto)
            if m not in ['FFFFFF', '000000', 'AMAZON']:
                code_found = m
                break
                
        if code_found:
             print(f"[{get_time()}] SUCESSO! Código MFA encontrado no email: {code_found}")
        else:
             print(f"[{get_time()}] FALHA! Não foi possível identificar um código de 6 caracteres na mensagem da API.")
             
        return code_found

    except Exception as e:
        print(f"[{get_time()}] Erro fatal na leitura Gmail API: {e}")
        return None

def awsacademy_login():
    USERNAME, PASSWORD, env_source = get_aws_credentials()
    if not USERNAME or not PASSWORD:
        print(f"[{get_time()}] ❌ ERRO CRÍTICO: Não foi possível obter AWS_EMAIL e AWS_PASSWORD do arquivo .env!")
        return None

    masked_pw = (PASSWORD[:2] + '*' * (len(PASSWORD) - 6) + PASSWORD[-4:]) if len(PASSWORD) >= 6 else '****'
    print(f"[{get_time()}] 🔑 Credenciais AWS carregadas EXCLUSIVAMENTE do .env ({env_source or 'arquivo .env'}):")
    print(f"[{get_time()}] -> Usuário: '{USERNAME}'")
    print(f"[{get_time()}] -> Senha exata: '{PASSWORD}' (tamanho: {len(PASSWORD)} caracteres)")

    # Grava arquivo de debug imediato na raiz para o usuário inspecionar
    try:
        with open("last_aws_login_debug.txt", "w", encoding="utf-8") as f_dbg:
            f_dbg.write(f"Timestamp: {get_time()}\n")
            f_dbg.write(f"Arquivo .env lido: {env_source}\n")
            f_dbg.write(f"Usuario: {USERNAME}\n")
            f_dbg.write(f"Senha exata: {PASSWORD}\n")
            f_dbg.write(f"Tamanho: {len(PASSWORD)} caracteres\n")
            f_dbg.write(f"Bytes da senha: {[ord(c) for c in PASSWORD]}\n")
    except Exception as e_dbg:
        print(f"[{get_time()}] Aviso ao gravar last_aws_login_debug.txt: {e_dbg}")
    # Ordem de resolução: variável de ambiente -> selenium-svc (K3s) -> selenium-chrome -> localhost
    SELENIUM_URL = os.getenv('SELENIUM_URL')
    if not SELENIUM_URL:
        try:
            socket.gethostbyname('selenium-svc')
            SELENIUM_URL = 'http://selenium-svc:4444/wd/hub'
        except Exception:
            try:
                socket.gethostbyname('selenium-chrome')
                SELENIUM_URL = 'http://selenium-chrome:4444/wd/hub'
            except Exception:
                SELENIUM_URL = 'http://localhost:4444/wd/hub'
    elif 'selenium-chrome' in SELENIUM_URL or 'selenium-svc' in SELENIUM_URL:
        host = 'selenium-svc' if 'selenium-svc' in SELENIUM_URL else 'selenium-chrome'
        try:
            socket.gethostbyname(host)
        except Exception:
            SELENIUM_URL = SELENIUM_URL.replace(host, 'localhost')

    print(f"[{get_time()}] Connecting to Selenium grid at: {SELENIUM_URL}")
    options = webdriver.ChromeOptions()
    options.add_argument('--start-maximized')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--no-sandbox')
    options.add_argument('--window-size=1920,1080')
    
    if os.getenv('AWS_HEADLESS', os.getenv('REDHAT_HEADLESS', 'false')).lower() == 'true':
        options.add_argument('--headless')

    driver = None
    try:
        driver = webdriver.Remote(command_executor=SELENIUM_URL, options=options)
    except Exception as e_conn:
        print(f"[{get_time()}] Erro ao conectar ao Selenium Grid ({SELENIUM_URL}): {e_conn}")
        return None
    
    try:
        url = "https://awsacademy.instructure.com/login/saml"
        print(f"[{get_time()}] 1) Navigating to AWS Academy SAML Auth: {url}")
        driver.get(url)
        
        # AWS Academy SAML usa Salesforce Community por baixo (LWC - Lightning Web Components)
        # É uma Web Runtime App e os inputs estão dentro de shadow DOMs (ou lwc scopes)
        
        def find_deep(selector, timeout=20):
            js = """
            function findDeep(sel, root = document) {
                if (root.querySelector && root.querySelector(sel)) return root.querySelector(sel);
                let all = root.querySelectorAll ? root.querySelectorAll('*') : [];
                for (let el of all) {
                    if (el.shadowRoot) {
                        let found = findDeep(sel, el.shadowRoot);
                        if (found) return found;
                    }
                }
                return null;
            }
            return findDeep(arguments[0]);
            """
            end_time = time.time() + timeout
            while time.time() < end_time:
                el = driver.execute_script(js, selector)
                if el:
                    return el
                time.sleep(1)
            return None

        def fill_lwc_input(input_elem, value, name="campo"):
            value = str(value).strip().replace('\r', '').replace('\n', '')
            try:
                driver.execute_script("arguments[0].focus(); arguments[0].click();", input_elem)
            except Exception:
                pass
            time.sleep(0.1)
            try:
                input_elem.send_keys(Keys.CONTROL + "a")
                input_elem.send_keys(Keys.BACK_SPACE)
            except Exception:
                pass
            input_elem.clear()
            input_elem.send_keys(value)
            
            # Dispara os eventos de input, change e blur com composed: true (essencial para LWC Shadow DOM)
            driver.execute_script("""
                let el = arguments[0];
                let val = arguments[1];
                el.value = val;
                el.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
                el.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
                el.dispatchEvent(new CustomEvent('change', { bubbles: true, composed: true, detail: { value: val } }));
                el.blur();
            """, input_elem, value)
            time.sleep(0.2)
            
            # Verificação do valor gravado no DOM
            cur_len = driver.execute_script("return arguments[0].value ? arguments[0].value.length : 0;", input_elem)
            print(f"[{get_time()}] -> {name} preenchido ({cur_len} caracteres registrados no DOM).")

        print(f"[{get_time()}] 2) Waiting for 'Email' field to render (LWC Shadow DOM)...")
        email_field = find_deep("input[name='email']")
        if not email_field:
            email_field = find_deep("input[inputmode='email']")
        if not email_field:
            raise Exception("Campo de email não encontrado na árvore Shadow DOM.")

        fill_lwc_input(email_field, USERNAME, "Email")
        
        print(f"[{get_time()}] 3) Waiting for 'Password' field...")
        password_field = find_deep("input[type='password']")
        if not password_field:
            password_field = find_deep("input[name='password']")
        if not password_field:
            raise Exception("Campo de password não encontrado na árvore Shadow DOM.")
              
        fill_lwc_input(password_field, PASSWORD, "Password")
        
        print(f"[{get_time()}] 4) Localizando e validando botão 'Login'...")
        login_btn = find_deep("lightning-button button")
        if not login_btn:
            login_btn = find_deep("button.slds-button")
        if not login_btn:
            login_btn = find_deep("button[type='button']")
        if not login_btn:
            raise Exception("Botão de login não encontrado na árvore Shadow DOM.")

        # Aguarda até 5s para o botão ser habilitado pela validação LWC
        for _ in range(10):
            is_disabled = driver.execute_script("""
                let btn = arguments[0];
                if (!btn) return true;
                let inner = btn.tagName === 'BUTTON' ? btn : (btn.querySelector ? btn.querySelector('button') : btn);
                let target = inner || btn;
                return target.disabled || target.hasAttribute('disabled') || target.getAttribute('aria-disabled') === 'true' || btn.style.pointerEvents === 'none';
            """, login_btn)
            if not is_disabled:
                print(f"[{get_time()}] -> Botão de Login HABILITADO pela validação do LWC!")
                break
            # Força blur nos campos novamente para acordar a validação do LWC
            driver.execute_script("""
                arguments[0].dispatchEvent(new Event('change', { bubbles: true, composed: true }));
                arguments[0].blur();
                arguments[1].dispatchEvent(new Event('change', { bubbles: true, composed: true }));
                arguments[1].blur();
            """, email_field, password_field)
            time.sleep(0.4)

        # Se ainda estiver com disabled residual, remove os atributos forçadamente
        driver.execute_script("""
            let btn = arguments[0];
            let inner = btn.tagName === 'BUTTON' ? btn : (btn.querySelector ? btn.querySelector('button') : btn);
            if (inner) {
                inner.removeAttribute('disabled');
                inner.disabled = false;
                inner.setAttribute('aria-disabled', 'false');
            }
            btn.style.pointerEvents = 'auto';
        """, login_btn)

        driver.execute_script("arguments[0].click();", login_btn)
        print(f"[{get_time()}] -> Login button clicado. Verificando resposta da AWS...")

        # Verifica se a AWS exibiu mensagem de erro imediata (ex: 'Your login attempt has failed.')
        for _ in range(5):
            time.sleep(1)
            error_elem = find_deep("[data-id='errorWrap'], .error_wrap, c-academy_login .error_wrap")
            if error_elem:
                error_text = driver.execute_script("return arguments[0].innerText || arguments[0].textContent;", error_elem)
                if error_text and error_text.strip():
                    err_msg = error_text.strip()
                    print(f"\n[{get_time()}] ❌❌❌ ERRO DE AUTENTICAÇÃO DA AWS ❌❌❌")
                    print(f"[{get_time()}] A AWS rejeitou as credenciais com a mensagem:")
                    print(f"[{get_time()}] -> '{err_msg}'")
                    print(f"[{get_time()}] Credenciais enviadas:")
                    print(f"[{get_time()}] -> Usuário: {USERNAME}")
                    print(f"[{get_time()}] -> Senha carregada do .env: {masked_pw} (tamanho: {len(PASSWORD)} caracteres)")
                    print(f"[{get_time()}] -> Origem do .env: {env_source}")
                    try:
                        driver.save_screenshot("aws_login_failed.png")
                        with open("aws_login_failed.html", "w", encoding="utf-8") as f:
                            f.write(driver.page_source)
                    except Exception:
                        pass
                    return None
        
        # Parte Crítica: MFA 
        print(f"[{get_time()}] 5) Aguardando renderização do formulário MFA (Verificação Visual)...")
        try:
            # Aguarda a página carregar o input do code
            code_input = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.ID, "j_id0:mfaform:code"))
            )
            print(f"[{get_time()}] -> Formulário MFA detectado!")
        except Exception as e:
            print(f"[{get_time()}] -> Não foi possível detectar o input do MFA imediatamente. Prosseguindo mesmo assim. Erro: {e}")

        
        print(f"[{get_time()}] Iniciando rotina pollings no IMAP para pegar a senha nos próximos 60s...")
        # Polling para o email chegar (Tenta 6 vezes, de 10 em 10 segundos)
        mfa_code = None
        for i in range(7):
            time.sleep(10) # 10s por loop (primeiro loop dá 10 secs pra enviar o email)
            print(f"[{get_time()}] -> Check Email #{i+1}...")  
            mfa_code = fetch_aws_verification_code()
            if mfa_code:
                break
                
        if not mfa_code:
            print(f"[{get_time()}] FALHA CRÍTICA! O código MFA não chegou ou não pôde ser localizado a tempo.")
            driver.save_screenshot("aws_mfa_missing.png")
            return driver
            
        print(f"[{get_time()}] 6) Preenchendo o input Code com: {mfa_code}")
        try:
            code_input = WebDriverWait(driver, 15).until(
                EC.visibility_of_element_located((By.XPATH, "//input[@data-id='inputCode'] | //input[@id='j_id0:mfaform:code']"))
            )
            code_input.clear()
            code_input.send_keys(mfa_code)
        except Exception:
             # Fallback
             code_input = driver.find_element(By.XPATH, "/html/body/form/span/div/div/div/div[2]/div/span[1]/div/input")
             code_input.clear()
             code_input.send_keys(mfa_code)

        print(f"[{get_time()}] 7) Clicando em 'Submit code'...")
        try:
            submit_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//a[@data-id='checkCode' and contains(text(), 'Submit code')]"))
            )
            driver.execute_script("arguments[0].click();", submit_btn)
        except Exception:
            submit_btn = driver.find_element(By.XPATH, "/html/body/form/span/div/div/div/div[2]/div/span[3]/div/p/a")
            driver.execute_script("arguments[0].click();", submit_btn)

        print(f"[{get_time()}] -> Submit clicado. Aguardando login ser efetivado...")
        time.sleep(5)
        
        print(f"[{get_time()}] AWS Academy Login Workflow completado com MFA! Verifique o console VNC.")
        return driver

    except Exception as e:
        print(f"[{get_time()}] Error occurred on AWS Login: {e}")
        if driver:
            try:
                driver.save_screenshot("aws_error_screenshot.png")
            except Exception:
                pass
            try:
                with open("aws_error_page.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
            except Exception as e2:
                pass
            try:
                driver.quit()
            except Exception:
                pass
        return None

def get_db_connection():
    db_host = os.getenv('DB_HOST', 'db')
    db_user = os.getenv('DB_USER')
    db_pass = os.getenv('DB_PASSWORD')
    db_name = os.getenv('DB_NAME', 'anima')
    db_port = int(os.getenv('DB_PORT', '3306'))

    return mysql.connector.connect(
        host=db_host,
        user=db_user,
        password=db_pass,
        database=db_name,
        port=db_port,
        charset="utf8mb4",
        use_pure=True
    )

def dar_baixa_usuario_curso_aws(usuario_id, curso_id):
    """
    Atualiza `usuario_curso` para 'Concluído' e envia as notificações do Discord (Auditoria, DM e Role).
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Update no BD
        update_query = """
            UPDATE usuario_curso 
            SET usuario_curso_situacao = 'Concluído' 
            WHERE usuario_id = %s AND curso_id = %s
        """
        cursor.execute(update_query, (usuario_id, curso_id))
        conn.commit()
        print(f"[{get_time()}] Status do usuario {usuario_id} atualizado para 'Concluído' no DB AWS.")

        # 2. Busca informações para o BOT do Discord
        select_query = """
            SELECT u.usuario_nome,
                   COALESCE(NULLIF(uc.usuario_redhat_email, ''), NULLIF(u.usuario_email, ''), u.usuario_email_pessoal) AS usuario_email,
                   u.usuario_discord_id, 
                   c.curso_parceira, c.curso_nome, c.curso_role
            FROM usuario u
            JOIN usuario_curso uc ON u.usuario_id = uc.usuario_id
            JOIN curso c ON uc.curso_id = c.curso_id
            WHERE u.usuario_id = %s AND c.curso_id = %s
        """
        cursor.execute(select_query, (usuario_id, curso_id))
        dados = cursor.fetchone()

        if dados:
            discord_id = dados.get('usuario_discord_id')
            role_id = dados.get('curso_role')
            usuario_nome = dados.get('usuario_nome')
            usuario_email = dados.get('usuario_email')
            acad = dados.get('curso_parceira')
            nome_curso = dados.get('curso_nome')

            discord_token = os.getenv('DISCORD_BOT_TOKEN')
            auditoria_id = os.getenv('DISCORD_AUDITORIA_CHANNEL_ID')

            if discord_token:
                headers = {
                    "Authorization": f"Bot {discord_token}",
                    "Content-Type": "application/json"
                }

                # a) Auditoria
                if auditoria_id:
                    try:
                        msg_audit = f"{usuario_nome} foi cadastrado com sucesso no {acad} - {nome_curso}"
                        requests.post(f"https://discord.com/api/v10/channels/{auditoria_id}/messages", headers=headers, json={"content": msg_audit})
                        print(f"[{get_time()}] Log de auditoria (cadastro) enviado.")
                    except Exception as e:
                        print(f"[{get_time()}] Erro ao logar auditoria: {e}")

                # b) Role do Servidor (Requer Guild ID global da api)
                if discord_id and role_id:
                    try:
                        g_resp = requests.get("https://discord.com/api/v10/users/@me/guilds", headers=headers)
                        if g_resp.status_code == 200 and g_resp.json():
                            guild_id = g_resp.json()[0]['id']
                            role_url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{discord_id}/roles/{role_id}"
                            requests.put(role_url, headers=headers)
                    except Exception as e:
                        print(f"[{get_time()}] Erro role API: {e}")

                # c) DM e Auditoria do DM
                if discord_id:
                    try:
                        dm_resp = requests.post("https://discord.com/api/v10/users/@me/channels", headers=headers, json={"recipient_id": discord_id})
                        if dm_resp.status_code == 200:
                            channel_id = dm_resp.json()['id']
                            msg_dm = "Um convite para o curso foi enviado para seu e-mail, clique no link presente nele e comece a estudar hoje mesmo!"
                            dm_send = requests.post(f"https://discord.com/api/v10/channels/{channel_id}/messages", headers=headers, json={"content": msg_dm})
                            if dm_send.status_code == 200 and auditoria_id:
                                requests.post(f"https://discord.com/api/v10/channels/{auditoria_id}/messages", headers=headers, json={"content": f"{usuario_nome} foi avisado via DM sobre a inscrição no curso {acad} - {nome_curso}"})
                                print(f"[{get_time()}] DM enviada ao Discord {usuario_nome}.")
                    except Exception as e:
                        print(f"[{get_time()}] Erro ao mandar DM: {e}")
        
    except Exception as e:
        print(f"[{get_time()}] Erro no DB dar_baixa_aws: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn.is_connected():
            conn.close()

def cadastrar_aws(usuario_id, curso_id):
    """
    Rotina completa: Busca usuario BD -> awsacademy_login -> Navega Canvas -> Trata Pessoas -> Trata Novo -> BD = Concluído.
    """
    conn = None
    curso_param = None
    usuario_email = None
    usuario_nome = None

    # Busca o e-mail e nome do Aluno e a String do Curso no BD
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT u.usuario_nome,
                   COALESCE(NULLIF(uc.usuario_redhat_email, ''), NULLIF(u.usuario_email, ''), u.usuario_email_pessoal) AS email_aluno,
                   c.curso_nome,
                   COALESCE(NULLIF(c.curso_param, ''), c.curso_nome) AS turma_param
            FROM usuario_curso uc
            JOIN usuario u ON uc.usuario_id = u.usuario_id
            JOIN curso c ON uc.curso_id = c.curso_id
            WHERE uc.usuario_id = %s AND uc.curso_id = %s
        """, (usuario_id, curso_id))
        dados = cursor.fetchone()
        if dados:
            usuario_email = dados.get('email_aluno')
            usuario_nome = dados.get('usuario_nome') or (str(usuario_email).split('@')[0] if usuario_email else 'Aluno')
            curso_param = dados.get('turma_param') or dados.get('curso_nome')

        # Fallback caso não encontre em usuario_curso: busca avulso
        if not usuario_email:
            cursor.execute("SELECT usuario_email, usuario_email_pessoal, usuario_nome FROM usuario WHERE usuario_id = %s", (usuario_id,))
            u = cursor.fetchone()
            if u:
                usuario_email = u.get('usuario_email') or u.get('usuario_email_pessoal')
                usuario_nome = u.get('usuario_nome') or (str(usuario_email).split('@')[0] if usuario_email else 'Aluno')

        if not curso_param:
            cursor.execute("SELECT curso_param, curso_nome FROM curso WHERE curso_id = %s", (curso_id,))
            c = cursor.fetchone()
            if c:
                curso_param = c.get('curso_param') or c.get('curso_nome')

    except Exception as e:
        print(f"[{get_time()}] Erro MySQL Buscando AWS Payload {e}")
        return
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

    if not usuario_email or not curso_param:
        print(f"[{get_time()}] Erro de BD: usuario_email ({usuario_email}) ou curso_param ({curso_param}) não encontrados para usuario_id={usuario_id}, curso_id={curso_id}.")
        return

    print(f"[{get_time()}] Iniciando Robo AWS CADASTRAR: Aluno -> {usuario_email} ({usuario_nome}) | Turma -> {curso_param}")
    
    # Roda login normal
    driver = awsacademy_login()
    if not driver:
        print(f"[{get_time()}] Login falhou. Abortando processo de cadastro.")
        return

    try:
        wait = WebDriverWait(driver, 60)

        # 1. Clicar em LMS na aba inicial Salesforce (LWC Shadow DOM)
        print(f"[{get_time()}] Home Carregada. Localizando e clicando no menu 'LMS'...")
        js_find_lms = """
        function findDeep(predicate, root = document) {
            if (predicate(root)) return root;
            let all = root.querySelectorAll ? root.querySelectorAll('*') : [];
            for (let el of all) {
                if (predicate(el)) return el;
                if (el.shadowRoot) {
                    let found = findDeep(predicate, el.shadowRoot);
                    if (found) return found;
                }
            }
            return null;
        }
        return findDeep(el => el.innerText && el.innerText.trim().startsWith('LMS'));
        """
        lms_btn = None
        for _ in range(25):
            lms_btn = driver.execute_script(js_find_lms)
            if lms_btn:
                break
            time.sleep(1)

        if not lms_btn:
            raise Exception("Menu 'LMS' não encontrado na Home.")

        orig_handles = list(driver.window_handles)
        driver.execute_script("arguments[0].click();", lms_btn)
        print(f"[{get_time()}] Menu 'LMS' clicado!")

        # 2. Alternar o foco para a nova janela do Canvas LMS
        print(f"[{get_time()}] Aguardando abertura da nova aba do LMS...")
        wait.until(lambda d: len(d.window_handles) > len(orig_handles))
        new_handle = [h for h in driver.window_handles if h not in orig_handles][-1]
        driver.switch_to.window(new_handle)
        print(f"[{get_time()}] Foco alterado para a aba do LMS: {driver.current_url}")

        # Extrair ID numérico do curso (ex: de 'AWS Academy Cloud Foundations [182912]' -> 182912)
        import re
        m = re.search(r'\[(\d+)\]', str(curso_param))
        course_id_num = m.group(1) if m else None

        # 3. Aguardar a tabela 'My Active Classes' renderizar na página do LMS
        print(f"[{get_time()}] Aguardando a tabela 'My Active Classes' carregar...")
        course_link = None
        for attempt in range(1, 13):
            time.sleep(5)
            print(f"[{get_time()}] Tentativa {attempt}/12 de localizar o link do curso...")
            try:
                if course_id_num:
                    xpath_course = f"//a[contains(@href, '/courses/{course_id_num}')]"
                else:
                    xpath_course = f"//a[contains(@href, '/courses/') and contains(., '{curso_param}')]"
                
                links = driver.find_elements(By.XPATH, xpath_course)
                if links:
                    course_link = links[0]
                    print(f"[{get_time()}] Curso encontrado na tabela: {course_link.text} -> {course_link.get_attribute('href')}")
                    break
            except Exception as e_poll:
                pass

        if not course_link:
            # Se não achou na tabela ou demorou muito, tenta navegação direta via URL
            if course_id_num:
                print(f"[{get_time()}] Curso não apareceu a tempo na tabela. Navegando diretamente via URL...")
                driver.get(f"https://awsacademy.instructure.com/courses/{course_id_num}")
            else:
                raise Exception(f"Não foi possível localizar o curso '{curso_param}' na tabela.")
        else:
            # Clicar no link do curso. Note que ele possui target="_blank" e abrirá OUTRA aba
            handles_before_course = list(driver.window_handles)
            driver.execute_script("arguments[0].click();", course_link)
            print(f"[{get_time()}] Link do curso clicado!")
            time.sleep(3)
            # Se abriu nova aba para o curso, troca para ela
            if len(driver.window_handles) > len(handles_before_course):
                course_tab = [h for h in driver.window_handles if h not in handles_before_course][-1]
                driver.switch_to.window(course_tab)
                print(f"[{get_time()}] Foco alterado para a aba do curso: {driver.current_url}")

        # 4. Achar e clicar no Link 'Pessoas' (People) no menu lateral
        print(f"[{get_time()}] Aguardando e clicando na seção 'Pessoas' do curso...")
        pessoas_xpath = "//a[contains(@class, 'people') or @id='pessoas-link' or contains(text(), 'Pessoas') or contains(text(), 'People')]"
        pessoas_link = wait.until(EC.element_to_be_clickable((By.XPATH, pessoas_xpath)))
        driver.execute_script("arguments[0].click();", pessoas_link)
        print(f"[{get_time()}] Seção 'Pessoas' acessada: {driver.current_url}")

        # 5. Clicar no botão '+ Pessoas' (addUsers)
        print(f"[{get_time()}] Clicando no botão '+ Pessoas'...")
        add_users_xpath = "//a[@id='addUsers' or contains(@title, 'Adicionar pessoas') or contains(., 'Pessoas') and contains(@class, 'btn')]"
        add_users_btn = wait.until(EC.element_to_be_clickable((By.XPATH, add_users_xpath)))
        driver.execute_script("arguments[0].click();", add_users_btn)

        # 6. Preencher o e-mail no Textarea do Modal
        print(f"[{get_time()}] Modal aberto. Inserindo e-mail '{usuario_email}'...")
        textarea_xpath = "//textarea[contains(@class, 'textArea') or @name='user_list'] | /html/body/span/span/span/div[1]/div[2]/div/div/div[1]/label/span[2]/div/textarea"
        textarea = wait.until(EC.presence_of_element_located((By.XPATH, textarea_xpath)))
        time.sleep(1)
        textarea.clear()
        textarea.send_keys(usuario_email)
        time.sleep(1)

        # 7. Clicar em 'Próximo'
        print(f"[{get_time()}] Clicando em 'Próximo'...")
        btn_next_xpath = "//button[contains(text(), 'Próximo') or contains(text(), 'Next')] | /html/body/span/span/span/div[2]/button[2]"
        btn_next = wait.until(EC.element_to_be_clickable((By.XPATH, btn_next_xpath)))
        driver.execute_script("arguments[0].click();", btn_next)
        
        # 8. Tratamento para usuário novo (botão 'Clique para adicionar um nome')
        print(f"[{get_time()}] Verificando se exige validação de nome para usuário novo...")
        time.sleep(4)
        
        try:
            add_name_xpath = "//button[@data-cid='Link' and (contains(., 'Clique para adicionar um nome') or contains(., 'Click to add a name'))] | //button[contains(@class, 'view-link')]"
            add_name_btn = WebDriverWait(driver, 6).until(
                EC.element_to_be_clickable((By.XPATH, add_name_xpath))
            )
            print(f"[{get_time()}] Botão 'Clique para adicionar um nome' encontrado! Clicando...")
            driver.execute_script("arguments[0].click();", add_name_btn)
            time.sleep(1)

            # Inserir o nome completo no campo que surge
            name_input_xpath = "//input[@name='name' or contains(@placeholder, 'nome') or contains(@placeholder, 'name')]"
            name_input = WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.XPATH, name_input_xpath))
            )
            name_input.clear()
            name_input.send_keys(usuario_nome)
            print(f"[{get_time()}] Nome preenchido: {usuario_nome}")
            time.sleep(1)

            # Clica no próximo botão Próximo
            btn_next_p2_xpath = "/html/body/span/span/span/div[2]/button[3] | //button[contains(text(), 'Próximo') or contains(text(), 'Next')]"
            btn_next_passo2 = driver.find_element(By.XPATH, btn_next_p2_xpath)
            driver.execute_script("arguments[0].click();", btn_next_passo2)
            print(f"[{get_time()}] Avançado para a tela final de confirmação.")
            time.sleep(3)
        except Exception as e_name:
            print(f"[{get_time()}] Aluno já existia no catálogo Canvas ou tela seguiu direto. ({e_name})")

        # 9. Concluir / Encerrar
        print(f"[{get_time()}] Tela Final -> Submetendo 'Adicionar usuários'...")
        btn_adicionar_xpath = "//button[contains(., 'Adicionar usuários') or contains(., 'Add Users')] | /html/body/span/span/span/div[2]/button[3]"
        btn_adicionar_usuarios = wait.until(EC.element_to_be_clickable((By.XPATH, btn_adicionar_xpath)))
        driver.execute_script("arguments[0].click();", btn_adicionar_usuarios)
        
        print(f"[{get_time()}] 🎉 INSCRIÇÃO EXECUTADA COM SUCESSO! Finalizando processos...")
        time.sleep(3)
        
        # 10. Atualizar BD
        dar_baixa_usuario_curso_aws(usuario_id, curso_id)

    except Exception as e:
        print(f"[{get_time()}] Falha fatal no fluxo de matricula do painel Canvas LMS: {e}")
        try:
            driver.save_screenshot("canvas_error.png")
            with open("canvas_error.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
        except Exception:
            pass
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

def get_pendentes_aws():
    """Busca todas as solicitações pendentes para o agente AWS"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        sql = """
            SELECT uc.usuario_id, uc.curso_id, u.usuario_nome,
                   COALESCE(NULLIF(uc.usuario_redhat_email, ''), NULLIF(u.usuario_email, ''), u.usuario_email_pessoal) AS usuario_email,
                   c.curso_nome,
                   COALESCE(NULLIF(c.curso_param, ''), c.curso_nome) AS curso_param
            FROM usuario_curso uc
            JOIN usuario u ON uc.usuario_id = u.usuario_id
            JOIN curso c ON uc.curso_id = c.curso_id
            WHERE uc.usuario_curso_situacao = 'Pendente'
            AND (
                LOWER(c.curso_agente) IN ('cadastrar_aws', 'aws_agente', 'aws')
                OR (UPPER(c.curso_parceira) = 'AWS' AND (c.curso_agente IS NULL OR c.curso_agente = '' OR LOWER(c.curso_agente) LIKE '%aws%' OR LOWER(c.curso_agente) = 'coordenação'))
            )
            ORDER BY uc.usuario_curso_dt_solicitacao ASC
        """
        cur.execute(sql)
        rows = cur.fetchall()
        return rows
    except Exception as e:
        print(f"[{get_time()}] Erro ao buscar pendências AWS: {e}")
        return []
    finally:
        if conn and conn.is_connected():
            cur.close()
            conn.close()

def processar_fila_aws():
    """Processa todas as solicitações pendentes da fila AWS"""
    pendentes = get_pendentes_aws()
    if not pendentes:
        print(f"[{get_time()}] Nenhuma solicitação pendente encontrada para AWS.")
        return 0

    print(f"[{get_time()}] Encontradas {len(pendentes)} solicitações pendentes para AWS.")
    processadas = 0
    for p in pendentes:
        print(f"\n[{get_time()}] >>> Processando: {p['usuario_nome']} ({p['usuario_email']}) no curso '{p['curso_nome']}'")
        try:
            cadastrar_aws(p['usuario_id'], p['curso_id'])
            processadas += 1
        except Exception as err:
            print(f"[{get_time()}] Erro no processamento de {p['usuario_email']}: {err}")
    return processadas

if __name__ == "__main__":
    print(f"[{get_time()}] Starting AWS Enrollment Worker...")
    if len(sys.argv) >= 3 and str(sys.argv[1]).isdigit() and str(sys.argv[2]).isdigit():
        uid = int(sys.argv[1])
        cid = int(sys.argv[2])
        print(f"[{get_time()}] Modo direto acionado para usuario_id={uid}, curso_id={cid}")
        try:
            cadastrar_aws(uid, cid)
        except Exception as e_dir:
            print(f"[{get_time()}] Erro no cadastro direto: {e_dir}")
        # Também varre a fila geral para garantir que nada ficou pendente
        processar_fila_aws()
    else:
        processar_fila_aws()
