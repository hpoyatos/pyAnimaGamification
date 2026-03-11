import os
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
    SELENIUM_URL = os.getenv('SELENIUM_URL', 'http://selenium-chrome:4444/wd/hub')

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
        
        print(f"[{get_time()}] 2) Waiting for 'Email' field to render...")
        time.sleep(5)  # Atraso para LWC renderizar componentes dinâmicos no DOM
        
        try:
            # Tenta pegar pelo name="email" ou "inputmode=email"
            email_field = WebDriverWait(driver, 15).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "input[name='email'], input[inputmode='email']"))
            )
        except Exception:
            # Fallback XPath absoluto enviado
            email_field = driver.find_element(By.XPATH, "/html/body/webruntime-app/lwr-router-container/webruntime-inner-app/dxp_data_provider-user-data-provider/dxp_data_provider-data-proxy/community_byo-scoped-header-and-footer/main/webruntime-router-container/dxp_data_provider-user-data-provider/dxp_data_provider-data-proxy/community_layout-slds-flexible-layout/div/community_layout-section/div[3]/community_layout-column/div/c-academy_login/div/div/lightning-input[1]/lightning-primitive-input-simple/div[1]/div/input")

        email_field.clear()
        email_field.send_keys(USERNAME)
        print(f"[{get_time()}] -> Email inserido: {USERNAME}")
        
        print(f"[{get_time()}] 3) Waiting for 'Password' field...")
        try:
            password_field = WebDriverWait(driver, 10).until(
                 EC.visibility_of_element_located((By.CSS_SELECTOR, "input[type='password'], input[name='password']"))
            )
        except Exception:
             password_field = driver.find_element(By.XPATH, "/html/body/webruntime-app/lwr-router-container/webruntime-inner-app/dxp_data_provider-user-data-provider/dxp_data_provider-data-proxy/community_byo-scoped-header-and-footer/main/webruntime-router-container/dxp_data_provider-user-data-provider/dxp_data_provider-data-proxy/community_layout-slds-flexible-layout/div/community_layout-section/div[3]/community_layout-column/div/c-academy_login/div/div/lightning-input[2]/lightning-primitive-input-simple/div[1]/div/input")
             
        password_field.clear()
        password_field.send_keys(PASSWORD)
        print(f"[{get_time()}] -> Password inserido.")
        
        print(f"[{get_time()}] 4) Clicking 'Login' button...")
        try:
            login_btn = WebDriverWait(driver, 10).until(
                 EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Login') or contains(@class, 'slds-button')]"))
            )
            driver.execute_script("arguments[0].click();", login_btn)
        except Exception:
             login_btn = driver.find_element(By.XPATH, "/html/body/webruntime-app/lwr-router-container/webruntime-inner-app/dxp_data_provider-user-data-provider/dxp_data_provider-data-proxy/community_byo-scoped-header-and-footer/main/webruntime-router-container/dxp_data_provider-user-data-provider/dxp_data_provider-data-proxy/community_layout-slds-flexible-layout/div/community_layout-section/div[3]/community_layout-column/div/c-academy_login/div/div/div[3]/lightning-button/button")
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

    return mysql.connector.connect(
        host=db_host,
        user=db_user,
        password=db_pass,
        database=db_name
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
                   c.curso_academia, c.curso_nome, c.curso_role
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
            acad = dados.get('curso_academia')
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

    # Busca o e-mail do Aluno e a String Magica do Curso no BD
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT usuario_email FROM usuario WHERE usuario_id = %s", (usuario_id,))
        u = cursor.fetchone()
        if u:
            usuario_email = u['usuario_email']

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

    print(f"[{get_time()}] Iniciando Robo AWS CADASTRAR: Aluno -> {usuario_email} | Turma -> {curso_param}")
    
    # Roda login normal
    driver = awsacademy_login()
    if not driver:
        print(f"[{get_time()}] Login falhou. Abortando processo de cadastro.")
        return

    try:
        wait = WebDriverWait(driver, 25)

        # 1. Clicar em LMS na aba inicial Salesforce
        print(f"[{get_time()}] Home Carregada. Clicando no menu 'LMS'...")
        lms_btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//li[contains(@data-id, 'lms') and contains(text(), 'LMS')]")
        ))
        driver.execute_script("arguments[0].click();", lms_btn)

        # 2. Alternar o foco para a nova janela do Canvas
        print(f"[{get_time()}] Trocando foco para a aba do Canvas...")
        wait.until(lambda d: len(d.window_handles) > 1)
        driver.switch_to.window(driver.window_handles[-1])

        # 3. Espera até que o botão de cursos esteja clicável
        print(f"[{get_time()}] Clicando no botão de cursos...")
        course_button = wait.until(
            EC.element_to_be_clickable((By.ID, "modded_global_nav_courses_link"))
        )
        course_button.click()

        # 4. Achar e clicar no Curso Específico via curso_param
        curso_param = "https://awsacademy.instructure.com//courses/157321"
        print(f"[{get_time()}] Procurando card do curso pelo href '{curso_param}'...")

        course_link = wait.until(EC.element_to_be_clickable(
            (By.XPATH, f"//a[@href='{curso_param}']")
        ))
        course_link.click()

        # 5. Achar e clicar no Link Pessoas lateral (People)
        print(f"[{get_time()}] Navegando até seção 'Pessoas' do Canvas...")
        pessoas_link = wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(@class, 'people') or @id='pessoas-link']")))
        driver.execute_script("arguments[0].click();", pessoas_link)

        # 6. Modal Adicionar Pessoas
        print(f"[{get_time()}] Clicando no botao + Pessoas (AddUsers)...")
        add_users_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@id='addUsers' or contains(@title, 'Adicionar pessoas')]")))
        driver.execute_script("arguments[0].click();", add_users_btn)

        print(f"[{get_time()}] Modal detectado. InserindWo email '{usuario_email}' no Textarea...")
        textarea_xpath = "/html/body/span/span/span/div[1]/div[2]/div/div/div[1]/label/span[2]/div/textarea"
        textarea = wait.until(EC.presence_of_element_located(
            (By.XPATH, f"{textarea_xpath} | //textarea[contains(@class, 'textArea')]")
        ))
        
        # Um pequeno sleep pois modais do React demoram as vezes a processar inputs
        time.sleep(1)
        textarea.clear()
        textarea.send_keys(usuario_email)
        time.sleep(1)

        print(f"[{get_time()}] Clicando Próximo...")
        btn_next = driver.find_element(By.XPATH, "/html/body/span[1]/span/span/div[2]/button[2]")
        btn_next.click()
        
        # 6. Fallback - Tratamento para usuário não Existente
        print(f"[{get_time()}] Avaliando regras condicionais de usuário novo...")
        time.sleep(4) 
        
        try:
            novo_text = driver.find_element(By.XPATH, "//div[contains(text(), 'Não conseguimos encontrar correspondências abaixo')]")
            if novo_text:
                novo_btn = driver.find_element(By.XPATH, "//span[contains(text(), 'Clique para adicionar um nome')] | /html/body/span[1]/span/span/div[1]/div[2]/div/div/div/div[2]/table/tbody/tr/td[2]/button/span")
                novo_btn.click()
                time.sleep(1)
                
                name_input = driver.switch_to.active_element
                name_input.send_keys(str(usuario_email).split('@')[0])
                
                # Clica no terceiro botao "Próximo" que aparece em fallback
                btn_next_passo2 = driver.find_element(By.XPATH, "/html/body/span[1]/span/span/div[2]/button[3]")
                btn_next_passo2.click()
                print(f"[{get_time()}] Aluno provisionado internamente.")
                time.sleep(3)
        except Exception:
             print(f"[{get_time()}] Aluno já possuía cache ou mapping local na AWS. Seguindo fluxo normal...")

        # 7. Concluir
        print(f"[{get_time()}] Tela Final -> Submetendo Adicionar...")
        wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Os seguintes usuários estão prontos para ser adicionados')]")))
        
        btn_adicionar_usuarios = wait.until(EC.element_to_be_clickable(
             (By.XPATH, "//button/span/span[contains(text(), 'Adicionar usuários')]/../.. | /html/body/span[1]/span/span/div[2]/button[3]")
        ))
        btn_adicionar_usuarios.click()
        
        print(f"[{get_time()}] INSCRIÇÃO EXECUTADA COM SUCESSO! A AWS fará o envio de convite nativo. Finalizando processos...")
        
        # 8. Setar DB, Role, DM e Auditoria
        dar_baixa_usuario_curso_aws(usuario_id, curso_id)

    except Exception as e:
        print(f"[{get_time()}] Falha fatal no fluxo de matricula do painel Canvas LMS: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    print(f"[{get_time()}] AWS Login Helper executado nativamente. Disparando teste local de aws_cadastrar(166, 2)...")
    time.sleep(2)
    cadastrar_aws(166, 2)
