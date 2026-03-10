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
        return None}")
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
            print(f"[{get_time()}] -> Check IMAP #{i+1}...")
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

if __name__ == "__main__":
    print(f"[{get_time()}] Starting AWS Academy Automation (MFA Embedded)...")
    time.sleep(3)
    drv = awsacademy_login()
    if drv:
        try:
            time.sleep(20) # Tempo para ver o VNC final do painel Canvas/LMS AWS
        finally:
            drv.quit()
