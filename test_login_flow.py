import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_bot.google_skills_boost import get_google_credentials

LOGIN, PASSWORD, _ = get_google_credentials()
print('Credenciais carregadas para:', LOGIN)

options = webdriver.ChromeOptions()
options.add_argument('--start-maximized')
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)

driver = webdriver.Chrome(options=options)
try:
    print("1) Acessando tela de login...")
    driver.get('https://www.skills.google/users/sign_in')
    time.sleep(2)
    form = driver.find_element(By.ID, 'with_google')
    driver.execute_script('arguments[0].submit();', form)

    wait = WebDriverWait(driver, 15)
    email_xpath = "//input[@type='email' or @id='identifierId']"
    email_input = wait.until(EC.visibility_of_element_located((By.XPATH, email_xpath)))
    email_input.clear()
    email_input.send_keys(LOGIN)
    print("2) Login preenchido.")

    next_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Avançar') or contains(., 'Next') or @id='identifierNext']")))
    driver.execute_script("arguments[0].click();", next_btn)
    print("3) Botao Avancar clicado.")

    time.sleep(3)
    pw_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@type='password' or @name='Passwd']")))
    pw_input.clear()
    pw_input.send_keys(PASSWORD)
    print("4) Senha preenchida.")

    pw_next_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Avançar') or contains(., 'Next') or @id='passwordNext']")))
    driver.execute_script("arguments[0].click();", pw_next_btn)
    print("5) Avancar senha clicado.")

    time.sleep(4)
    print("6) URL apos senha:", driver.current_url)
    driver.save_screenshot("tela_apos_senha.png")
    with open("tela_apos_senha.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)

    # Inspeciona todos os botões e links visíveis
    botoes = driver.find_elements(By.TAG_NAME, "button")
    print(f"Total de botoes na tela: {len(botoes)}")
    for b in botoes:
        t = (b.text or "").strip()
        if t:
            print(" - Botao:", t)

    # Inspeciona listas ul / li
    itens = driver.find_elements(By.XPATH, "//li | //div[@role='link'] | //div[@role='button']")
    print(f"Total de itens interativos: {len(itens)}")
    for it in itens:
        t = (it.text or "").strip().replace('\n', ' ')
        if t:
            print(" - Item:", t[:100])

except Exception as e:
    print("Erro no teste:", e)
    driver.save_screenshot("teste_erro.png")
    with open("teste_erro.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
finally:
    print("Aguardando 20 segundos antes de fechar para inspecionar...")
    time.sleep(20)
    driver.quit()
