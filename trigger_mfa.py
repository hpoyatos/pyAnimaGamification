import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_bot.google_skills_boost import get_google_credentials

LOGIN, PASSWORD, _ = get_google_credentials()
print(f"Iniciando login para: {LOGIN}")

options = webdriver.ChromeOptions()
options.add_argument('--start-maximized')
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)

try:
    print("1) Acessando https://www.skills.google/users/sign_in ...")
    driver.get("https://www.skills.google/users/sign_in")
    time.sleep(2)

    form = driver.find_element(By.ID, "with_google")
    driver.execute_script("arguments[0].submit();", form)

    print("2) Preenchendo e-mail...")
    email_in = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@type='email' or @id='identifierId']")))
    email_in.clear()
    email_in.send_keys(LOGIN)

    next_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Avançar') or contains(., 'Next') or @id='identifierNext']")))
    driver.execute_script("arguments[0].click();", next_btn)

    print("3) Preenchendo senha...")
    pw_in = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@type='password' or @name='Passwd']")))
    pw_in.clear()
    pw_in.send_keys(PASSWORD)

    pw_next_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Avançar') or contains(., 'Next') or @id='passwordNext']")))
    driver.execute_script("arguments[0].click();", pw_next_btn)

    print("4) Aguardando tela pós-senha...")
    time.sleep(4)
    print(f"URL: {driver.current_url}")

    # Cancela modal passkey se houver
    try:
        cancel_passkey = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Cancelar') or contains(., 'Cancel')]"))
        )
        driver.execute_script("arguments[0].click();", cancel_passkey)
        print("Cancelou modal passkey.")
        time.sleep(2)
    except Exception:
        pass

    # Clica em 'Tentar de outro jeito'
    print("5) Procurando botão 'Tentar de outro jeito'...")
    try:
        btn_outro = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Tentar de outro jeito') or contains(., 'Try another way')]")))
        driver.execute_script("arguments[0].click();", btn_outro)
        print("Clicou com sucesso em 'Tentar de outro jeito'!")
        time.sleep(3)
    except Exception as e_outro:
        print(f"Não achou ou não precisou clicar em 'Tentar de outro jeito': {e_outro}")

    # Clica na opção 'Toque em Sim no smartphone'
    print("6) Procurando 'Toque em Sim no seu smartphone ou tablet'...")
    try:
        opt_sim = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@data-challengetype='39']//ancestor::li | //div[@data-challengetype='39'] | //li[contains(., 'Toque em Sim')]")))
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
        # Fallback selenium click
        try:
            target_div = driver.find_element(By.XPATH, "//div[@data-challengetype='39']")
            target_div.click()
        except Exception:
            pass
        print(">>> CLICOU EM 'TOQUE EM SIM NO SMARTPHONE' COM SUCESSO! <<<")
    except Exception as e_sim:
        print(f"Falha ao clicar na opção 'Toque em Sim': {e_sim}")

    time.sleep(3)
    print(f"URL atual do desafio: {driver.current_url}")
    driver.save_screenshot("tela_notificacao_enviada.png")

    print("\n=======================================================")
    print(">>> AGUARDANDO VOCÊ CONFIRMAR 'SIM' NO SMARTPHONE (120s) <<<")
    print("=======================================================\n")

    start_t = time.time()
    aprovado = False
    while time.time() - start_t < 120:
        if "skills.google" in driver.current_url and "accounts.google.com" not in driver.current_url:
            aprovado = True
            print(f"*** SUCESSO! AUTENTICADO! URL: {driver.current_url} ***")
            break
        time.sleep(2)

    if not aprovado:
        print("Tempo esgotado ou não aprovado.")

except Exception as e:
    import traceback
    print("Erro durante o processo:")
    traceback.print_exc()
finally:
    time.sleep(10)
    driver.quit()
