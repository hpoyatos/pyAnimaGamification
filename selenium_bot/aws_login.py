import os
if os.path.exists('.env') or os.path.exists('selenium_bot/.env'):
    from dotenv import load_dotenv
    load_dotenv()
import time
import datetime
import re
import imaplib
import email
from email.header import decode_header
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import base64
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import mysql.connector
import requests

def get_time():
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)).strftime('%H:%M:%S')

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
    USERNAME = os.getenv('AWS_EMAIL')
    PASSWORD = os.getenv('AWS_PASSWORD')
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
    
    if os.getenv('REDHAT_HEADLESS', 'false').lower() == 'true':
        options.add_argument('--headless')

    driver = webdriver.Remote(command_executor=SELENIUM_URL, options=options)
    
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

        print(f"[{get_time()}] 2) Waiting for 'Email' field to render (LWC Shadow DOM)...")
        email_field = find_deep("input[name='email']")
        if not email_field:
            email_field = find_deep("input[inputmode='email']")
        if not email_field:
            raise Exception("Campo de email não encontrado na árvore Shadow DOM.")

        email_field.clear()
        email_field.send_keys(USERNAME)
        print(f"[{get_time()}] -> Email inserido: {USERNAME}")
        
        print(f"[{get_time()}] 3) Waiting for 'Password' field...")
        password_field = find_deep("input[type='password']")
        if not password_field:
            password_field = find_deep("input[name='password']")
        if not password_field:
            raise Exception("Campo de password não encontrado na árvore Shadow DOM.")
              
        password_field.clear()
        password_field.send_keys(PASSWORD)
        print(f"[{get_time()}] -> Password inserido.")
        
        print(f"[{get_time()}] 4) Clicking 'Login' button...")
        login_btn = find_deep("lightning-button button")
        if not login_btn:
            login_btn = find_deep("button.slds-button")
        if not login_btn:
            raise Exception("Botão de login não encontrado na árvore Shadow DOM.")

        driver.execute_script("arguments[0].click();", login_btn)
        print(f"[{get_time()}] -> Login button clicado. O email com o código MFA deve ser despachado pela AWS...")
        
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
        driver.save_screenshot("aws_error_screenshot.png")
        try:
            with open("aws_error_page.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
        except Exception as e2:
            pass
        driver.quit()
        return None

def get_db_connection():
    db_host = os.getenv('DB_HOST')
    db_user = os.getenv('DB_USER')
    db_pass = os.getenv('DB_PASSWORD')
    db_name = os.getenv('DB_NAME')
    db_port = int(os.getenv('DB_PORT', '3306'))

    return mysql.connector.connect(
        host=db_host,
        user=db_user,
        password=db_pass,
        database=db_name,
        port=db_port
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
            SELECT u.usuario_nome, u.usuario_email, u.usuario_discord_id, 
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
                            msg_dm = f"Olá! Você acaba de ser inscrito no curso de certificação oficial: **{acad} - {nome_curso}**!\nVerifique o seu e-mail corporativo (`{usuario_email}`) fornecido à universidade. Lá estará o convite nominal da plataforma."
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
        cursor.execute("SELECT usuario_email, usuario_nome FROM usuario WHERE usuario_id = %s", (usuario_id,))
        u = cursor.fetchone()
        if u:
            usuario_email = u['usuario_email']
            usuario_nome = u.get('usuario_nome') or str(usuario_email).split('@')[0]

        cursor.execute("SELECT curso_param FROM curso WHERE curso_id = %s", (curso_id,))
        c = cursor.fetchone()
        if c:
            curso_param = c['curso_param']

    except Exception as e:
        print(f"[{get_time()}] Erro MySQL Buscando AWS Payload {e}")
        return
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

    if not usuario_email or not curso_param:
        print(f"[{get_time()}] Erro de BD: usuario_email ({usuario_email}) ou curso_param ({curso_param}) não encontrados.")
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
        driver.quit()

def get_pendentes_aws():
    """Busca todas as solicitações pendentes para o agente AWS"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        sql = """
            SELECT uc.usuario_id, uc.curso_id, u.usuario_nome, u.usuario_email, c.curso_nome, c.curso_param
            FROM usuario_curso uc
            JOIN usuario u ON uc.usuario_id = u.usuario_id
            JOIN curso c ON uc.curso_id = c.curso_id
            WHERE uc.usuario_curso_situacao = 'Pendente'
            AND (c.curso_agente = 'cadastrar_aws' OR c.curso_agente = 'aws_agente')
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
    processar_fila_aws()
