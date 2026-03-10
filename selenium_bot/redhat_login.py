import os
import time
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

def cadastrar_rh124(driver, redhat_id, redhat_email):
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
        
        print("8) VAI DEMORAR BASTANTE PARA RENDERIZAR DE NOVO A TELA. Conferindo na tabela...")
        time.sleep(10) # Atraso extra forte após salvar o modal
        
        found = False
        while True:
            try:
                tabela = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, "/html/body/div/div[2]/div/main/div[2]/div[6]"))
                )
                if redhat_email in tabela.text or redhat_id in tabela.text:
                    print(f"9) loga tudo e me diz se cadastrou o redhat_id e redhat_email ... SUCESSO! Cadastro de {redhat_id} ({redhat_email}) detectado!")
                    found = True
                    break
            except Exception as e_tab:
                pass
            
            # Tentar achar a paginação e clicar se existir
            try:
                paga_next_a = driver.find_element(By.XPATH, "//ul[contains(@class, 'pagination')]//li/a[text()='›']")
                paga_next_li = paga_next_a.find_element(By.XPATH, "..")
                
                if "disabled" in paga_next_li.get_attribute("class"):
                    print("Fim da paginação e aluno não encontrado nas páginas passadas da tabela.")
                    break
                    
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'}); arguments[0].click();", paga_next_a)
                print("Foi para a próxima página aguardando reload.")
                time.sleep(4)
            except Exception as e_page:
                print("Paginação inexistente ou botão next indisponível. Fim da busca na tabela.")
                break
                
        if not found:
            print(f"9) loga tudo e me diz se cadastrou o redhat_id e redhat_email ... FALHA! {redhat_email} não pôde ser verificado na listagem visível.")
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

if __name__ == "__main__":
    print("Starting Red Hat Login Automation...")
    # Aguarda o serviço selenium-chrome inicializar completamente (Grid + Node)
    time.sleep(5)
    drv = login()
    if drv:
        try:
            cadastrar_rh124(drv, "paulobock", "paulobock@gmail.com")
            time.sleep(10) # Tempo para ver o VNC final
        finally:
            drv.quit()

