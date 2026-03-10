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

def get_time():
    return (datetime.datetime.utcnow() - datetime.timedelta(hours=3)).strftime('%H:%M:%S')

def fetch_aws_verification_code():
    """
    Conecta no IMAP do Gmail e busca o código de verificação
    enviado por support@awsacademy.com nos últimos minutos.
    """
    IMAP_SERVER = "imap.gmail.com"
    USERNAME = os.getenv('SMTP_USER')
    PASSWORD = os.getenv('SMTP_PASSWORD')

    if not USERNAME or not PASSWORD:
        print("Erro: Credenciais de email (SMTP_USER/SMTP_PASSWORD) não fornecidas.")
        return None

    try:
        print(f"[{get_time()}] Conectando ao IMAP em {IMAP_SERVER}...")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(USERNAME, PASSWORD)
        mail.select("inbox")
        
        # Procura e-mails com assunto e remetente específicos
        # Vamos pegar os mais recentes (últimos 5 minutos idealmente, mas pegaremos os não lidos ou todos recentes)
        print(f"[{get_time()}] Buscando emails do remetente support@awsacademy.com...")
        
        # Tenta buscar os não lidos primeiro
        status, messages = mail.search(None, '(UNSEEN FROM "support@awsacademy.com")')
        
        if not messages[0]:
            print(f"[{get_time()}] Nenhum email não lido encontrado. Buscando todos os recentes do remetente...")
            status, messages = mail.search(None, '(FROM "support@awsacademy.com")')

        if not messages[0]:
            print(f"[{get_time()}] Nenhum email de support@awsacademy.com encontrado.")
            return None

        # Pega a lista de IDs de mensagens e converte em array
        # Pega o último ID (mais recente)
        mail_ids = messages[0].split()
        latest_id = mail_ids[-1]

        # Busca a mensagem (RFC822)
        status, data = mail.fetch(latest_id, '(RFC822)')
        
        # Parseia o raw format em objeto Email
        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)
        
        # Lê o assunto (opcional, apenas para log)
        subject, encoding = decode_header(msg["Subject"])[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding if encoding else "utf-8")
            
        print(f"[{get_time()}] Processando email recente: Assunto -> '{subject}'")
        
        # Extrai o corpot do e-mail
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                if content_type in ["text/plain", "text/html"] and "attachment" not in content_disposition:
                    try:
                        part_body = part.get_payload(decode=True).decode()
                        body += part_body
                    except:
                        pass
        else:
            try:
                body = msg.get_payload(decode=True).decode()
            except:
                pass

        # O código tem exatamente 6 caracteres numéricos e alfa (A-Z, 0-9), todos MAIÚSCULOS.
        # Ex: "WB8UZT"
        # O HTML tem um bloco que diz: "Please use the verification code below...<br><br><font...>WB8UZT</font>"
        # Vamos usar um regex agressivo
        
        # Removemos quebras de linha temporariamente para o Regex atuar melhor em tags
        body_clean = re.sub(r'\\s+', ' ', body)
        
        # Padrão: 6 letras maíusculas ou dígitos, sozinhos (" WB8UZT ") ou com tags ("<font>WB8UZT</font>")
        # Cuidado para não pegar outras palavras de 6 letras como "Please" ou afins (maiusculas+digitos)
        matches = re.findall(r'\b([A-Z0-9]{6})\b', body)
        
        code_found = None
        for m in matches:
            # Elimina coisas muito obvias que possam ser codigos HEX se houver
            if m not in ['FFFFFF', '000000']:
                code_found = m
                break
                
        if code_found:
             print(f"[{get_time()}] SUCESSO! Código MFA encontrado no email: {code_found}")
        else:
             print(f"[{get_time()}] FALHA! Não foi possível identificar um código de 6 caracteres na mensagem.")
             
        mail.close()
        mail.logout()
        return code_found

    except Exception as e:
        print(f"[{get_time()}] Erro fatal na leitura IMAP: {e}")
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
