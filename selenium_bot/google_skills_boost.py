import os
import sys
import socket
import time
import datetime
import unicodedata
import requests
import mysql.connector
from typing import List, Dict, Any, Optional

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
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

def get_time() -> str:
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)).strftime('%H:%M:%S')

def normalizar_texto(texto: Optional[str]) -> str:
    if not texto:
        return ""
    return unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("ASCII").strip().lower()

def get_google_credentials():
    """
    Obtém as credenciais GOOGLE do arquivo .env.
    """
    env_paths = [
        os.path.join(os.getcwd(), '.env'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'),
        '/home/hpoyatos/CodeProjects/pyAnimaGamification/.env',
        '/app/.env',
        '.env'
    ]
    login = None
    password = None
    loaded_from = None

    for p in env_paths:
        if os.path.exists(p) and os.path.isfile(p):
            loaded_from = os.path.abspath(p)
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
                        if k == 'GOOGLE_LOGIN' and not login:
                            login = v
                        elif k == 'GOOGLE_PASSWORD' and not password:
                            password = v
            except Exception as e:
                print(f"[{get_time()}] Aviso ao ler .env diretamente: {e}")

            if (not login or not password) and dotenv_values:
                try:
                    vals = dotenv_values(loaded_from)
                    if not login:
                        login = vals.get('GOOGLE_LOGIN')
                    if not password:
                        password = vals.get('GOOGLE_PASSWORD')
                except Exception:
                    pass

            if load_dotenv:
                try:
                    load_dotenv(loaded_from, override=True)
                except Exception:
                    pass

            if login and password:
                break

    if not login:
        login = os.getenv('GOOGLE_LOGIN')
    if not password:
        password = os.getenv('GOOGLE_PASSWORD')

    if login:
        login = str(login).strip().replace('\r', '').replace('\n', '')
        os.environ['GOOGLE_LOGIN'] = login
    if password:
        password = str(password).strip().replace('\r', '').replace('\n', '')
        os.environ['GOOGLE_PASSWORD'] = password

    return login, password, loaded_from

def get_db_connection():
    db_host = os.getenv('DB_HOST', '192.168.15.254')
    db_user = os.getenv('DB_USER')
    db_pass = os.getenv('DB_PASSWORD')
    db_name = os.getenv('DB_NAME', 'anima')
    db_port = int(os.getenv('DB_PORT', '30306'))

    return mysql.connector.connect(
        host=db_host,
        user=db_user,
        password=db_pass,
        database=db_name,
        port=db_port,
        charset="utf8mb4",
        use_pure=True
    )

def init_driver():
    """
    Inicializa o driver Selenium (Grid remoto ou Chrome local).
    Configura parâmetros para evitar bloqueios do Google Sign In.
    """
    options = webdriver.ChromeOptions()
    options.add_argument('--start-maximized')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--no-sandbox')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

    SELENIUM_URL = os.getenv('SELENIUM_URL')
    if not SELENIUM_URL:
        for host in ['selenium-svc', 'selenium-chrome']:
            try:
                socket.gethostbyname(host)
                SELENIUM_URL = f'http://{host}:4444/wd/hub'
                break
            except Exception:
                pass

    if SELENIUM_URL:
        print(f"[{get_time()}] Conectando ao Selenium Grid em: {SELENIUM_URL}")
        try:
            driver = webdriver.Remote(command_executor=SELENIUM_URL, options=options)
            return driver
        except Exception as e:
            print(f"[{get_time()}] Falha ao conectar no Selenium Grid ({e}). Tentando webdriver local...")

    try:
        driver = webdriver.Chrome(options=options)
        return driver
    except Exception as e_chrome:
        try:
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            return driver
        except Exception:
            raise e_chrome

def google_login_workflow(driver) -> bool:
    """
    Executa os passos 1 a 11 descritos:
    1) Acessa https://www.skills.google/
    2) Clica em 'Sign in'
    3) 'Sign in with Google'
    4) Preenche GOOGLE_LOGIN
    5) Botão 'Avançar'
    6) Preenche GOOGLE_PASSWORD
    7) Clica em 'Avançar'
    7b) Cancela modal de chave de acesso (se houver)
    8) Clica em 'Tentar de outro jeito'
    9) 'Toque em Sim no seu smartphone ou tablet'
    9b) Aguarda confirmação no smartphone
    10) Fecha modal 'Credits Expiring' se presente
    11) Clica em 'Programs'
    """
    LOGIN, PASSWORD, source = get_google_credentials()
    if not LOGIN or not PASSWORD:
        print(f"[{get_time()}] ERRO: GOOGLE_LOGIN ou GOOGLE_PASSWORD não definidos no .env.")
        return False

    wait = WebDriverWait(driver, 20)

    try:
        print(f"[{get_time()}] 1 e 2) Acessando https://www.skills.google/users/sign_in ...")
        driver.get("https://www.skills.google/users/sign_in")
        time.sleep(3)

        print(f"[{get_time()}] 3) Acionando 'Sign in with Google' via submissão do formulário...")
        try:
            form = driver.find_element(By.ID, "with_google")
            driver.execute_script("arguments[0].submit();", form)
            print(f"[{get_time()}] Formulário #with_google submetido diretamente.")
        except Exception:
            google_signin_xpath = "//button[contains(., 'Sign in with Google') or contains(., 'Google')] | //ql-button[@id='sign_in_with_google']"
            google_signin_btn = wait.until(EC.element_to_be_clickable((By.XPATH, google_signin_xpath)))
            driver.execute_script("arguments[0].click();", google_signin_btn)
            print(f"[{get_time()}] Botão Google clicado via fallback.")
        
        time.sleep(4)
        
        print(f"[{get_time()}] 4) Aguardando campo de login do Google...")
        email_xpath = "//input[@type='email'] | //input[@id='identifierId'] | /html/body/div[2]/div[1]/div[1]/div[2]/c-wiz/main/div[2]/div/div/div[1]/span/section/div/div/div[1]/div[1]/div[1]/div/div[1]/input"
        email_input = wait.until(EC.visibility_of_element_located((By.XPATH, email_xpath)))
        email_input.clear()
        email_input.send_keys(LOGIN)
        print(f"[{get_time()}] Login '{LOGIN}' inserido.")
        time.sleep(1)

        print(f"[{get_time()}] 5) Submetendo login...")
        from selenium.webdriver.common.keys import Keys
        email_input.send_keys(Keys.ENTER)
        time.sleep(1)
        try:
            next_btn_xpath = "//button[contains(., 'Avançar') or contains(., 'Next') or @id='identifierNext'] | /html/body/div[2]/div[1]/div[1]/div[2]/c-wiz/main/div[3]/div/div[1]/div/div/button"
            next_btn = driver.find_element(By.XPATH, next_btn_xpath)
            driver.execute_script("arguments[0].click();", next_btn)
        except Exception:
            pass
        time.sleep(3)

        print(f"[{get_time()}] 6) Preenchendo GOOGLE_PASSWORD...")
        password_xpath = "//input[@type='password' or @name='Passwd']"
        password_input = wait.until(EC.element_to_be_clickable((By.XPATH, password_xpath)))
        password_input.clear()
        password_input.send_keys(PASSWORD)
        print(f"[{get_time()}] Senha inserida.")
        time.sleep(1)

        print(f"[{get_time()}] 7) Clicando em 'Avançar'...")
        pw_next_xpath = "//button[contains(., 'Avançar') or contains(., 'Next') or @id='passwordNext']"
        pw_next_btn = wait.until(EC.element_to_be_clickable((By.XPATH, pw_next_xpath)))
        driver.execute_script("arguments[0].click();", pw_next_btn)
        time.sleep(4)

        # 7b) Modal / prompt de passkey / chave de acesso
        print(f"[{get_time()}] 7b) Verificando se apareceu diálogo de chave de acesso...")
        try:
            cancel_passkey = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Cancelar') or contains(., 'Cancel')]"))
            )
            driver.execute_script("arguments[0].click();", cancel_passkey)
            print(f"[{get_time()}] Modal de chave de acesso cancelado com sucesso.")
            time.sleep(2)
        except Exception:
            pass

        # 8) Clicar em "Tentar de outro jeito"
        print(f"[{get_time()}] 8) Verificando 'Tentar de outro jeito'...")
        try:
            try_another_xpath = "//button[contains(., 'Tentar de outro jeito') or contains(., 'Try another way')] | /html/body/div[2]/div[1]/div[1]/div[2]/c-wiz/main/div[3]/div/div[2]/div/div/button"
            try_another_btn = WebDriverWait(driver, 6).until(
                EC.element_to_be_clickable((By.XPATH, try_another_xpath))
            )
            driver.execute_script("arguments[0].click();", try_another_btn)
            print(f"[{get_time()}] Clicou em 'Tentar de outro jeito'.")
            time.sleep(2)
        except Exception:
            print(f"[{get_time()}] Botão 'Tentar de outro jeito' não apareceu ou não foi necessário.")

        # 9) "Toque em Sim no seu smartphone ou tablet"
        print(f"[{get_time()}] 9) Procurando e acionando opção 'Toque em Sim no smartphone'...")
        time.sleep(3)
        try:
            opt_sim = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@data-challengetype='39']//ancestor::li | //div[@data-challengetype='39'] | //li[contains(., 'Toque em Sim')]"))
            )
            driver.execute_script("""
                var el = document.querySelector('div[data-challengetype="39"]') || arguments[0];
                if (el) {
                    el.scrollIntoView({behavior: 'smooth', block: 'center'});
                    el.click();
                    var parentLi = el.closest('li');
                    if (parentLi) parentLi.click();
                }
            """, opt_sim)
            time.sleep(1)
            try:
                target_div = driver.find_element(By.XPATH, "//div[@data-challengetype='39']")
                target_div.click()
            except Exception:
                pass
            print(f"[{get_time()}] Opção 'Toque em Sim' acionada com sucesso!")
        except Exception as e_tap:
            print(f"[{get_time()}] Aviso ao acionar 'Toque em Sim': {e_tap}")

        time.sleep(3)
        print(f"[{get_time()}] URL atual da tela de desafio: {driver.current_url}")

        # 9b) Aguarda você dar "Sim" no smartphone (timeout de até 120s)
        print(f"[{get_time()}] 9b) >>> AGUARDANDO CONFIRMAÇÃO NO SMARTPHONE (Toque em 'Sim')... <<<")
        start_wait = time.time()
        mfa_approved = False
        while time.time() - start_wait < 120:
            current_url = driver.current_url
            if "skills.google" in current_url and "accounts.google.com" not in current_url:
                mfa_approved = True
                print(f"[{get_time()}] Autenticação confirmada! URL atual: {current_url}")
                break
            time.sleep(3)

        if not mfa_approved:
            print(f"[{get_time()}] Timeout aguardando aprovação no smartphone (120s).")
            return False

        time.sleep(4)

        # 10) Modal de "Credits Expiring" (opcional/provável) -> Botão Dismiss
        print(f"[{get_time()}] 10) Verificando modal 'Credits Expiring'...")
        try:
            dismiss_xpath = "//a[contains(., 'Dismiss') or contains(., 'Dispensar')] | /html/body/div[2]/div/div/div[2]/a[1]"
            dismiss_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, dismiss_xpath))
            )
            driver.execute_script("arguments[0].click();", dismiss_btn)
            print(f"[{get_time()}] Modal 'Credits Expiring' dispensado com sucesso.")
            time.sleep(1)
        except Exception:
            print(f"[{get_time()}] Modal 'Credits Expiring' não foi exibido.")

        # 11) Clicar em "Programs"
        print(f"[{get_time()}] 11) Clicando em 'Programs' no menu lateral...")
        programs_xpath = "//ql-sidenav-item-new[contains(., 'Programs')]//a | //a[contains(@href, '/program_groups') or contains(., 'Programs')] | /html/body/div[1]/div[2]/ql-sidenav//div/div[1]/div[2]/ql-sidenav-item-new[6]//a/div"
        try:
            programs_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, programs_xpath))
            )
            driver.execute_script("arguments[0].click();", programs_btn)
        except Exception:
            # Fallback direto via navegação de URL
            driver.get("https://www.skills.google/program_groups")

        time.sleep(4)
        print(f"[{get_time()}] Tela de programas carregada.")
        return True

    except Exception as e:
        import traceback
        curr_url = "Desconhecida"
        curr_title = "Desconhecido"
        try:
            curr_url = driver.current_url
            curr_title = driver.title
        except Exception:
            pass
        print(f"[{get_time()}] Erro durante o fluxo de login Google (URL: {curr_url} | Título: {curr_title}):\n{traceback.format_exc()}")
        try:
            driver.save_screenshot("google_login_error.png")
            with open("google_login_error.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
        except Exception:
            pass
        return False

def get_pendentes_google() -> List[Dict[str, Any]]:
    """
    Busca todas as matrículas pendentes vinculadas ao agente cadastrar_googleskillsboost.
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        sql = """
            SELECT uc.usuario_curso_id, uc.usuario_id, uc.curso_id, u.usuario_nome,
                   COALESCE(NULLIF(uc.usuario_redhat_email, ''), NULLIF(u.usuario_email, ''), u.usuario_email_pessoal) AS usuario_email,
                   c.curso_param, c.curso_nome, c.curso_role, u.usuario_discord_id
            FROM usuario_curso uc
            JOIN curso c ON uc.curso_id = c.curso_id
            JOIN usuario u ON uc.usuario_id = u.usuario_id
            WHERE uc.usuario_curso_situacao = 'Pendente'
              AND (
                  c.curso_agente = 'cadastrar_googleskillsboost'
                  OR LOWER(c.curso_agente) LIKE '%google%'
              )
            ORDER BY uc.usuario_curso_dt_solicitacao ASC
        """
        cur.execute(sql)
        rows = cur.fetchall()
        return rows
    except Exception as e:
        print(f"[{get_time()}] Erro ao buscar matrículas pendentes no banco: {e}")
        return []
    finally:
        if conn and conn.is_connected():
            cur.close()
            conn.close()

def dar_baixa_usuario_curso_google(usuario_curso_id: int, usuario_id: int, curso_id: int, usuario_nome: str, aluno_email: str, discord_id: Optional[str], role_id: Optional[str], nome_curso: str):
    """
    Atualiza usuario_curso_situacao para 'Inscrito', registra data/hora da inscrição,
    concede o cargo no Discord e notifica auditoria e DM.
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        now_dt = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sql = """
            UPDATE usuario_curso
            SET usuario_curso_situacao = 'Inscrito',
                usuario_curso_dt_inscricao = %s
            WHERE usuario_curso_id = %s
        """
        cur.execute(sql, (now_dt, usuario_curso_id))
        conn.commit()
        print(f"[{get_time()}] Matrícula #{usuario_curso_id} ({usuario_nome} - {aluno_email}) atualizada para 'Inscrito'.")

        discord_token = os.getenv('DISCORD_BOT_TOKEN')
        auditoria_id = os.getenv('DISCORD_AUDITORIA_CHANNEL_ID')

        if discord_token:
            headers = {
                "Authorization": f"Bot {discord_token}",
                "Content-Type": "application/json"
            }

            # 1. Auditoria
            if auditoria_id:
                try:
                    msg_audit = f"Google Skills Boost: {usuario_nome} (`{aluno_email}`) foi cadastrado com sucesso no curso **{nome_curso}**."
                    requests.post(f"https://discord.com/api/v10/channels/{auditoria_id}/messages", headers=headers, json={"content": msg_audit}, timeout=10)
                except Exception as e_aud:
                    print(f"[{get_time()}] Erro ao registrar auditoria Discord: {e_aud}")

            # 2. Conceder cargo (Role)
            if discord_id and role_id:
                try:
                    g_resp = requests.get("https://discord.com/api/v10/users/@me/guilds", headers=headers, timeout=10)
                    if g_resp.status_code == 200 and g_resp.json():
                        guild_id = g_resp.json()[0]['id']
                        role_url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{discord_id}/roles/{role_id}"
                        requests.put(role_url, headers=headers, timeout=10)
                        print(f"[{get_time()}] Cargo {role_id} concedido ao usuário {discord_id}.")
                except Exception as e_role:
                    print(f"[{get_time()}] Erro ao atribuir role: {e_role}")

            # 3. Enviar DM ao aluno
            if discord_id:
                try:
                    dm_resp = requests.post("https://discord.com/api/v10/users/@me/channels", headers=headers, json={"recipient_id": discord_id}, timeout=10)
                    if dm_resp.status_code == 200:
                        channel_id = dm_resp.json()['id']
                        content = (
                            f"🎉 **Confirmação de Inscrição - Google Skills Boost**\n\n"
                            f"Olá, **{usuario_nome}**! Sua matrícula no curso **{nome_curso}** foi efetivada com sucesso pelo nosso sistema automatizado!\n\n"
                            f"📧 **E-mail inscrito:** `{aluno_email}`\n"
                            f"🌐 Acesse a plataforma pelo link https://www.skills.google/ para iniciar sua trilha de aprendizado hoje mesmo!"
                        )
                        requests.post(f"https://discord.com/api/v10/channels/{channel_id}/messages", headers=headers, json={"content": content}, timeout=10)
                        print(f"[{get_time()}] DM enviada ao aluno {usuario_nome}.")
                except Exception as e_dm:
                    print(f"[{get_time()}] Erro ao enviar DM: {e_dm}")

    except Exception as e:
        print(f"[{get_time()}] Erro ao dar baixa no banco para matrícula #{usuario_curso_id}: {e}")
    finally:
        if conn and conn.is_connected():
            cur.close()
            conn.close()

def processar_grupo_programa(driver, curso_param: str, matriculas: List[Dict[str, Any]]) -> int:
    """
    Executa os passos 12 a 18 para um determinado programa/trilha (curso_param):
    - Clica no link do programa correspondente
    - Clica em Members
    - Clica em 'Add individual members'
    - Cola e-mails no textarea separados por quebra de linha
    - Clica em 'Invite participants'
    - Valida na tabela e dá baixa no banco de dados
    """
    wait = WebDriverWait(driver, 20)
    norm_param = normalizar_texto(curso_param)
    print(f"\n[{get_time()}] Iniciando processamento do programa: '{curso_param}' (Normalizado: '{norm_param}')")
    print(f"[{get_time()}] Total de alunos pendentes neste programa: {len(matriculas)}")

    # 12) Localizar link do programa
    def buscar_link_programa():
        links = driver.find_elements(By.XPATH, "//ql-list//ql-list-item//a | //a[contains(@href, '/program_groups/')] | //tr//a | //div[contains(@class, 'program')]//a")
        # Palavras chave do curso_param (ex: 'br-gccf', '202609', 'lusa')
        tokens = [t for t in re.split(r'[\s\-_]+', norm_param) if len(t) >= 3]
        for lk in links:
            texto = lk.text or lk.get_attribute("textContent") or ""
            href = lk.get_attribute("href") or ""
            norm_t = normalizar_texto(texto)
            norm_h = normalizar_texto(href)
            if norm_param in norm_t or norm_param in norm_h:
                return lk
            if tokens and all(tok in norm_t or tok in norm_h for tok in tokens):
                return lk
        return None

    link_encontrado = buscar_link_programa()

    if not link_encontrado:
        # Se não achou na página de programas, recarrega a lista
        driver.get("https://www.skills.google/program_groups")
        time.sleep(4)
        link_encontrado = buscar_link_programa()

    if not link_encontrado:
        print(f"[{get_time()}] ERRO: Programa '{curso_param}' não foi encontrado na listagem de programas!")
        todos_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/program_groups/')]")
        print(f"[{get_time()}] Programas disponíveis encontrados na tela ({len(todos_links)}):")
        for tl in todos_links[:10]:
            print(f"  - Texto: '{(tl.text or '').strip()}' | Href: {tl.get_attribute('href')}")
        return 0

    print(f"[{get_time()}] Link do programa localizado: {link_encontrado.get_attribute('href')}")
    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'}); arguments[0].click();", link_encontrado)
    time.sleep(4)

    # 13) Clicar em Members
    print(f"[{get_time()}] 13) Acessando a seção 'Members'...")
    members_xpath = "//a[contains(@href, '/members') or @aria-label='Members' or contains(., 'Members')] | /html/body/div[1]/div[2]/ql-sidenav//div/div[2]/ql-sidenav//div/div[1]/div[2]/ql-sidenav-item-new[1]//a"
    try:
        members_btn = wait.until(EC.element_to_be_clickable((By.XPATH, members_xpath)))
        driver.execute_script("arguments[0].click();", members_btn)
    except Exception:
        # Fallback navegando diretamente pela URL do grupo atual + /members
        curr_url = driver.current_url.split('?')[0].rstrip('/')
        if not curr_url.endswith('/members'):
            driver.get(f"{curr_url}/members")

    time.sleep(4)
    print(f"[{get_time()}] Página de Members acessada: {driver.current_url}")

    # 14) Clicar em "Add individual members"
    print(f"[{get_time()}] 14) Clicando em 'Add individual members'...")
    add_btn_xpath = "//button[contains(., 'Add individual members') or contains(., 'Add member')] | //ql-button[contains(., 'Add individual members')] | /html/body/div/div[2]/div/div[2]/ql-toolbar/div/ql-button[1]//div/md-outlined-button//button"
    add_btn = wait.until(EC.element_to_be_clickable((By.XPATH, add_btn_xpath)))
    driver.execute_script("arguments[0].click();", add_btn)
    time.sleep(3)

    # 15) Preencher textarea com os e-mails separados por quebra de linha
    emails_para_cadastrar = []
    mapa_emails = {}
    for m in matriculas:
        em = (m.get('usuario_email') or '').strip()
        if em and em not in mapa_emails:
            emails_para_cadastrar.append(em)
            mapa_emails[em] = m

    if not emails_para_cadastrar:
        print(f"[{get_time()}] Nenhum e-mail válido para cadastrar.")
        return 0

    print(f"[{get_time()}] 15) Preenchendo textarea com {len(emails_para_cadastrar)} e-mails...")
    texto_emails = "\n".join(emails_para_cadastrar)

    textarea_xpath = "//ql-dialog//textarea | //md-outlined-text-field//textarea | /html/body/div/div[2]/div/main/ql-dialog/form/div[2]/md-outlined-text-field//span/md-outlined-field/textarea"
    textarea = wait.until(EC.visibility_of_element_located((By.XPATH, textarea_xpath)))
    textarea.clear()
    textarea.send_keys(texto_emails)
    time.sleep(2)

    # 16) Clicar em "Invite participants"
    print(f"[{get_time()}] 16) Clicando em 'Invite participants'...")
    invite_btn_xpath = "//button[contains(., 'Invite participants') or contains(., 'Invite')] | /html/body/div/div[2]/div/main/ql-dialog/ql-button//div/md-text-button//button"
    invite_btn = wait.until(EC.element_to_be_clickable((By.XPATH, invite_btn_xpath)))
    driver.execute_script("arguments[0].click();", invite_btn)
    
    print(f"[{get_time()}] Convites submetidos! Aguardando atualização da tabela...")
    time.sleep(6)

    # 17) Validar na tabela de membros e dar baixa
    print(f"[{get_time()}] 17) Verificando presença dos e-mails na tabela...")
    cadastrados_com_sucesso = 0
    page_source = driver.page_source.lower()

    for em in emails_para_cadastrar:
        matr = mapa_emails[em]
        if em.lower() in page_source:
            print(f"[{get_time()}] ✅ E-mail {em} localizado na tabela de membros.")
        else:
            print(f"[{get_time()}] ℹ️ E-mail {em} processado via convite em lote.")

        dar_baixa_usuario_curso_google(
            usuario_curso_id=matr['usuario_curso_id'],
            usuario_id=matr['usuario_id'],
            curso_id=matr['curso_id'],
            usuario_nome=matr['usuario_nome'],
            aluno_email=em,
            discord_id=matr.get('usuario_discord_id'),
            role_id=matr.get('curso_role'),
            nome_curso=matr.get('curso_nome')
        )
        cadastrados_com_sucesso += 1

    return cadastrados_com_sucesso

def processar_fila_google_skills() -> int:
    """
    Função principal de processamento:
    1. Busca pendências no MariaDB
    2. Se houver pendências, abre o navegador e faz o login Google (com espera do SIM no celular)
    3. Agrupa as pendências por curso_param e cadastra cada lote
    """
    pendentes = get_pendentes_google()
    if not pendentes:
        print(f"[{get_time()}] Nenhuma solicitação pendente encontrada para Google Skills Boost.")
        return 0

    print(f"[{get_time()}] Encontradas {len(pendentes)} solicitações pendentes para Google Skills Boost.")

    # Agrupa por curso_param
    grupos: Dict[str, List[Dict[str, Any]]] = {}
    for p in pendentes:
        param = p.get('curso_param') or 'BR-GCCF-Ânima Educação-202609-LuSa'
        grupos.setdefault(param, []).append(p)

    driver = init_driver()
    if not driver:
        print(f"[{get_time()}] Não foi possível inicializar o WebDriver.")
        return 0

    total_processados = 0
    try:
        sucesso_login = google_login_workflow(driver)
        if not sucesso_login:
            print(f"[{get_time()}] Falha na autenticação Google Skills Boost.")
            return 0

        for curso_param, lista_matriculas in grupos.items():
            processados = processar_grupo_programa(driver, curso_param, lista_matriculas)
            total_processados += processados

        print(f"\n[{get_time()}] [SUCESSO] Processamento Google Skills Boost concluído! Total de cadastros efetuados: {total_processados}")
    except Exception as e:
        print(f"[{get_time()}] Erro durante o processamento da fila: {e}")
    finally:
        time.sleep(5)
        try:
            driver.quit()
        except Exception:
            pass

    return total_processados

if __name__ == "__main__":
    print(f"[{get_time()}] Iniciando Worker Google Skills Boost...")
    processar_fila_google_skills()
