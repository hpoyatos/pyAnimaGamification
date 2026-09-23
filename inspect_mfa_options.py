import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_bot.google_skills_boost import get_google_credentials

LOGIN, PASSWORD, _ = get_google_credentials()
options = webdriver.ChromeOptions()
options.add_argument('--start-maximized')
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_experimental_option('excludeSwitches', ['enable-automation'])
options.add_experimental_option('useAutomationExtension', False)

driver = webdriver.Chrome(options=options)
try:
    print("Acessando...")
    driver.get('https://www.skills.google/users/sign_in')
    time.sleep(2)
    form = driver.find_element(By.ID, 'with_google')
    driver.execute_script('arguments[0].submit();', form)

    wait = WebDriverWait(driver, 15)
    email_xpath = "//input[@type='email' or @id='identifierId']"
    email_input = wait.until(EC.visibility_of_element_located((By.XPATH, email_xpath)))
    email_input.clear()
    email_input.send_keys(LOGIN)

    next_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Avançar') or contains(., 'Next') or @id='identifierNext']")))
    driver.execute_script("arguments[0].click();", next_btn)

    pw_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@type='password' or @name='Passwd']")))
    pw_input.clear()
    pw_input.send_keys(PASSWORD)

    pw_next_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Avançar') or contains(., 'Next') or @id='passwordNext']")))
    driver.execute_script("arguments[0].click();", pw_next_btn)

    time.sleep(3)
    btn_outro = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Tentar de outro jeito')]")))
    driver.execute_script("arguments[0].click();", btn_outro)
    print("Clicou em 'Tentar de outro jeito' com sucesso!")
    time.sleep(4)

    with open('tela_opcoes_mfa.html', 'w', encoding='utf-8') as f:
        f.write(driver.page_source)

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    print("\n--- OPÇÕES ENCONTRADAS NA LISTA DE MÉTODOS DE RECUPERAÇÃO ---")
    for li in soup.find_all('li'):
        txt = li.get_text(strip=True, separator=" ")
        if txt:
            print("LI:", txt)

except Exception as e:
    print("Erro:", e)
finally:
    driver.quit()
