import os
import time
import requests
import mysql.connector
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

def login():
    USERNAME = os.getenv('REDHAT_USERNAME')
    PASSWORD = os.getenv('REDHAT_PASSWORD')
    SELENIUM_URL = os.getenv('SELENIUM_URL', 'http://selenium-chrome:4444/wd/hub')

    print("Connecting to Selenium grid at:", SELENIUM_URL)
    options = webdriver.ChromeOptions()
    options.add_argument('--start-maximized')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--no-sandbox')
    options.add_argument('--window-size=1920,1080')
    
    # Opcionalmente rodar headless se REDHAT_HEADLESS for true
    if os.getenv('REDHAT_HEADLESS', 'false').lower() == 'true':
        options.add_argument('--headless')

    driver = webdriver.Remote(command_executor=SELENIUM_URL, options=options)
    
    try:
        url = "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/auth?response_type=code&client_id=rha-webapp-prod&redirect_uri=https%3A%2F%2Frha.ole.redhat.com%2Frha%2Fauth%2Fauthorize&scope=openid+profile+email&state=7lr4ZsHt9AYukVGpTI0R1jQ6b9RB4z&nonce=74T16baQkWKUg7128zEn"
        print("Navigating to:", url)
        driver.get(url)
        
        print("Waiting for username field...")
        username_field = WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.XPATH, "/html/body/div/main/div/div/div/div[2]/div[2]/div/section[1]/form/div[1]/input"))
        )
        
        # Ocultar o banner de cookies (iframe) e overlays para não interceptar cliques
        driver.execute_script("""
            var frames = document.querySelectorAll('iframe, .truste_box_overlay_border, .truste_overlay, [id^="trust"], [class^="trust"]');
            for(var i=0; i<frames.length; i++){
                frames[i].style.display = 'none';
            }
            var gdpr = document.getElementById('gdpr-banner');
            if(gdpr) gdpr.style.display = 'none';
        """)
        
        username_field.clear()
        username_field.send_keys(USERNAME)
        print("Username entered.")
        
        time.sleep(1)
        print("Clicking first next/login button...")
        next_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div/main/div/div/div/div[2]/div[2]/div/section[1]/form/div[2]/button"))
        )
        next_btn.click()
        print("Clicked next.")

        print("Waiting for password field...")
        password_field = WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.XPATH, "/html/body/div/main/div/div/div/div[2]/div[2]/div/section[3]/form/div[2]/div[2]/input"))
        )
        password_field.clear()
        password_field.send_keys(PASSWORD)
        print("Password entered.")
        
        time.sleep(1)
        print("Clicking final login button...")
        login_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div/main/div/div/div/div[2]/div[2]/div/section[3]/form/div[3]/button"))
        )
        login_btn.click()
        print("Clicked login.")
        
        print("Waiting for 'Manage Classes' page to render...")
        validation_element = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div/div[2]/div/main/div[2]/div[1]/div"))
        )
        if "Manage Classes" in driver.page_source or "Manage Classes" in validation_element.text:
            print("Login completo! (Manage Classes encontrado)")
        else:
            print("Login parece ter completado, mas o texto 'Manage Classes' não foi visto onde esperado.")
        
        # Espera para dar tempo de visualizar o resultado no VNC
        time.sleep(3)
        print("Login script finished successfully.")
        return driver

    except Exception as e:
        print(f"Error occurred: {e}")
        driver.save_screenshot("error_screenshot.png")
        try:
            with open("error_page.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
        except Exception as e2:
            print("Could not save page source:", e2)
        driver.quit()
        return None

def cadastrar_rh124(driver, usuario_id, curso_id, redhat_id, redhat_email):
    print(f"\n--- Iniciando cadastro para o aluno: {redhat_id} - {redhat_email} ---")
    try:
        time.sleep(2)
        # Ocultar o banner de cookies caso reapareça na nova página
        driver.execute_script("""
            var frames = document.querySelectorAll('iframe, .truste_box_overlay_border, .truste_overlay, .truste_cm_outerdiv, [id^="trust"], [id^="pop-outerdiv"], [class^="trust"]');
            for(var i=0; i<frames.length; i++){
                frames[i].style.display = 'none';
            }
        """)

        print("1) clica neste cara de alguma forma /html/body/div/div[2]/div/main/div[2]/div[2]/div[2]")
        el1 = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div/div[2]/div/main/div[2]/div[2]/div[2]"))
        )
        el1.click()
        
        print("2) clica em no botão 'Editar Turma' /html/body/div/div[2]/div/main/div[2]/div[4]/div/button")
        el2 = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div/div[2]/div/main/div[2]/div[4]/div/button"))
        )
        el2.click()

        print("3) abriu um modal (dá um atraso, pode demorar), clica primeiro em  'Confirmar o tipo de turma' /html/body/div[3]/div/div/div[2]/div/form/div[1]/div[1]/div/input")
        time.sleep(5) # Atraso extra para o modal comprido renderizar
        el3 = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.ID, "formBasicCheckbox"))
        )
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", el3)
        time.sleep(1)
        el3.click()
        time.sleep(1)
        
        print(f"4) neste cara que pode ser 8 tabs depois (/html/body/div[3]/div/div/div[2]/div/form/div[6]/div/div[2]/div[1]/input) você preenche o campo 'Red Hat Network ID' com: {redhat_id}")
        input_id = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//small[contains(text(), 'Red Hat Network ID')]/following-sibling::input"))
        )
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", input_id)
        time.sleep(1)
        input_id.click()
        input_id.send_keys(redhat_id)
        
        print(f"5) Usando TAB para ir ao campo 'endereço de email' e preenchendo com: {redhat_email}")
        time.sleep(1)
        actions = ActionChains(driver)
        actions.send_keys(Keys.TAB)
        actions.send_keys(redhat_email)
        actions.perform()
        
        print("6) Dando 2 TABs para chegar no botão 'Adicionar aluno' e apertando ENTER")
        time.sleep(1)
        actions = ActionChains(driver)
        actions.send_keys(Keys.TAB)
        actions.send_keys(Keys.TAB)
        actions.send_keys(Keys.ENTER)
        actions.perform()
        time.sleep(2) # Dar tempo de processar a adição ao array React
        
        print("7) clica no botão 'Atualizar' /html/body/div[3]/div/div/div[2]/div/div/button[2]")
        btn_update = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'btn-primary') and (contains(text(), 'Atualizar') or contains(text(), 'Update'))]"))
        )
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'}); arguments[0].click();", btn_update)
        
        print("8) Aguardando tabela de estudantes carregar para verificar a inscrição...")
        time.sleep(10) # Atraso extra forte após salvar o modal
        
        found = False
        loop_count = 0
        while loop_count < 20:
            loop_count += 1
            try:
                # Procurar especificamente pela div com class 'students-list'
                students_div = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.students-list"))
                )
                
                # O texto inteiro do container deve conter o redhat_id ou redhat_email recém cadastrado
                page_text = students_div.text
                if redhat_email in page_text or redhat_id in page_text:
                    print(f"9) [SUCESSO] Aluno {redhat_id} ({redhat_email}) localizado na página atual. Iniciando rotina de baixa (banco, cargo, DM).")
                    found = True
                    dar_baixa_usuario_curso(usuario_id, curso_id)
                    break
                else:
                    print(f"   -> Aluno não encontrado na página atual da tabela (Tentativa {loop_count}).")
            except Exception as e_tab:
                print(f"   -> Tabela students-list não carregou corretamente (Tentativa {loop_count}).")
            
            # Tentar achar a paginação e clicar se existir
            try:
                # Acha o link com o texto "›" (próxima)
                paga_next_a = driver.find_element(By.XPATH, "//ul[contains(@class, 'pagination')]//li/a[text()='›']")
                paga_next_li = paga_next_a.find_element(By.XPATH, "..")
                
                class_attr = paga_next_li.get_attribute("class") or ""
                if "disabled" in class_attr:
                    print("Fim da paginação. O aluno não foi encontrado em nenhuma página da tabela.")
                    break
                    
                # Guardar página atual para verificar se ela realmente muda
                try:
                    active_page = driver.find_element(By.XPATH, "//ul[contains(@class, 'pagination')]//li[contains(@class, 'active')]").text
                except:
                    active_page = None
                        
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'}); arguments[0].click();", paga_next_a)
                print(f"   -> Clicou para ir à próxima página. Aguardando recarregamento...")
                time.sleep(5) # Atraso para dar tempo da próxima página popular ao DOM
                
                # Verificar se continuou na mesma página para evitar loop infinito
                try:
                    new_active_page = driver.find_element(By.XPATH, "//ul[contains(@class, 'pagination')]//li[contains(@class, 'active')]").text
                except:
                    new_active_page = None
                        
                if active_page and new_active_page and active_page == new_active_page:
                    print("ATENÇÃO: A página não mudou após o clique. Interrompendo busca.")
                    break
                    
            except Exception as e_page:
                print("Paginação inexistente ou botão next inativo.")
                break
        
        if loop_count >= 20:
            print("ATENÇÃO: Atingiu o limite máximo de 20 páginas na tabela de alunos. Busca interrompida.")
                
        if not found:
            print(f"9) [FALHA] Cadastro de {redhat_email} não pôde ser verificado em nenhuma página da listagem.")
            driver.save_screenshot("not_found_in_table.png")
            with open("not_found_in_table.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            
    except Exception as e:
        print(f"Erro no cadastro: {e}")
        driver.save_screenshot("error_cadastro.png")
        try:
            with open("error_cadastro.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
        except:
            pass

def dar_baixa_usuario_curso(usuario_id, curso_id):
    conn = None
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "db"),
            port=int(os.getenv("DB_PORT", "3306")),
            database=os.getenv("DB_NAME", "anima"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
        cur = conn.cursor(dictionary=True)
        
        # 1) Atualiza
        cur.execute("UPDATE usuario_curso SET usuario_curso_situacao = 'Concluído' WHERE usuario_id = %s AND curso_id = %s", (usuario_id, curso_id))
        conn.commit()
        print("Status da inscrição atualizado para 'Concluído'.")
        
        # 2 e 3) Busca info relacionadas
        cur.execute("SELECT usuario_discord_id, usuario_nome FROM usuario WHERE usuario_id = %s", (usuario_id,))
        user_row = cur.fetchone()
        
        cur.execute("SELECT * FROM curso WHERE curso_id = %s", (curso_id,))
        curso_row = cur.fetchone()
        
        if not user_row or not user_row.get("usuario_discord_id"):
            print("Usuário não tem discord_id vinculado. Pulando atribuição de cargo e DM.")
            return
            
        discord_id = user_row["usuario_discord_id"]
        usuario_nome = user_row.get("usuario_nome", "Usuário")
        role_id = curso_row["curso_role"] if curso_row else None
        
        discord_token = os.getenv("DISCORD_BOT_TOKEN")
        auditoria_id = os.getenv("DISCORD_AUDITORIA_CHANNEL_ID")
        
        if not discord_token:
            print("Sem DISCORD_BOT_TOKEN nas variáveis de ambiente. Pulando ações de Discord.")
            return
            
        headers = {
            "Authorization": f"Bot {discord_token}",
            "Content-Type": "application/json"
        }
        
        acad = curso_row.get('curso_academia', '') if curso_row else ''
        nome = curso_row.get('curso_nome', '') if curso_row else ''
        
        if auditoria_id:
            try:
                msg_audit1 = f"{usuario_nome} foi cadastrado com sucesso no {acad} - {nome}"
                requests.post(f"https://discord.com/api/v10/channels/{auditoria_id}/messages", headers=headers, json={"content": msg_audit1})
                print("Log de auditoria (cadastro) enviado.")
            except Exception as e:
                print(f"Erro ao logar auditoria (cadastro): {e}")
        
        # Obter Guild ID se precisar dar role
        if role_id:
            try:
                g_resp = requests.get("https://discord.com/api/v10/users/@me/guilds", headers=headers)
                if g_resp.status_code == 200:
                    guilds = g_resp.json()
                    if guilds:
                        guild_id = guilds[0]['id']
                        role_url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{discord_id}/roles/{role_id}"
                        r_resp = requests.put(role_url, headers=headers)
                        if r_resp.status_code == 204:
                            print(f"Role {role_id} concedida com sucesso no guild {guild_id}.")
                        else:
                            print(f"Erro ao conceder role: HTTP {r_resp.status_code}")
            except Exception as e_role:
                print(f"Erro ao atribuir role pela API: {e_role}")
                
        # Mandar DM
        try:
            dm_resp = requests.post("https://discord.com/api/v10/users/@me/channels", headers=headers, json={"recipient_id": discord_id})
            if dm_resp.status_code == 200:
                channel_id = dm_resp.json()['id']
                acad = curso_row.get('curso_academia', '')
                nome = curso_row.get('curso_nome', '')
                inicio = curso_row['curso_dt_inicio'].strftime('%d/%m/%Y') if curso_row.get('curso_dt_inicio') else '-'
                fim = curso_row['curso_dt_fim'].strftime('%d/%m/%Y') if curso_row.get('curso_dt_fim') else '-'
                
                content = (
                    f"🎉 **Confirmação de Inscrição na Academia {acad}**\n\n"
                    f"Sucesso! Sua inscrição no curso foi efetivada pelo nosso sistema automatizado.\n\n"
                    f"**Curso:** {nome}\n"
                    f"**Período:** {inicio} até {fim}\n\n"
                    f"Fique de olho no portal oficial para iniciar seus estudos assim que a turma abrir!"
                )
                
                msg_resp = requests.post(f"https://discord.com/api/v10/channels/{channel_id}/messages", headers=headers, json={"content": content})
                if msg_resp.status_code == 200:
                    print("Mensagem direta enviada para o usuário no Discord com sucesso.")
                    if auditoria_id:
                        try:
                            msg_audit2 = f"{usuario_nome} foi avisado sobre a inscrição no curso {acad} - {nome}"
                            requests.post(f"https://discord.com/api/v10/channels/{auditoria_id}/messages", headers=headers, json={"content": msg_audit2})
                        except Exception as e:
                            print(f"Erro ao logar auditoria (aviso): {e}")
                else:
                    print(f"Erro ao mandar mensagem no Discord: HTTP {msg_resp.status_code}")
        except Exception as e_msg:
            print(f"Erro na etapa de interagir via DM: {e_msg}")
            
    except Exception as e:
        print(f"Erro de DB no modulo de baixa_usuario_curso: {e}")
    finally:
        if conn and conn.is_connected():
            cur.close()
            conn.close()

if __name__ == "__main__":
    print("Starting Red Hat Login Automation...")
    # Aguarda o serviço selenium-chrome inicializar completamente (Grid + Node)
    time.sleep(5)
    drv = login()
    if drv:
        try:
            cadastrar_rh124(drv, 165, 1, "DaniloTamanhao", "danilo.tamanhao2@gmail.com")
            time.sleep(10) # Tempo para ver o VNC final
        finally:
            drv.quit()

