import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_bot.redhat_login import get_redhat_credentials

USERNAME, PASSWORD, _ = get_redhat_credentials()

options = webdriver.ChromeOptions()
options.add_argument('--start-maximized')
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)

try:
    url = "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/auth?response_type=code&client_id=rha-webapp-prod&redirect_uri=https%3A%2F%2Frha.ole.redhat.com%2Frha%2Fauth%2Fauthorize&scope=openid+profile+email&state=7lr4ZsHt9AYukVGpTI0R1jQ6b9RB4z&nonce=74T16baQkWKUg7128zEn"
    driver.get(url)
    time.sleep(3)

    user_in = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@id='username' or @name='username'] | /html/body/div/main/div/div/div/div[2]/div[2]/div/section[1]/form/div[1]/input")))
    user_in.clear()
    user_in.send_keys(USERNAME)

    next_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@id='login-show-step2' or @type='submit'] | /html/body/div/main/div/div/div/div[2]/div[2]/div/section[1]/form/div[2]/button")))
    driver.execute_script("arguments[0].click();", next_btn)
    time.sleep(3)

    pw_in = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@type='password' or @id='password'] | /html/body/div/main/div/div/div/div[2]/div[2]/div/section[3]/form/div[2]/div[2]/input")))
    pw_in.clear()
    pw_in.send_keys(PASSWORD)

    log_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@id='rh-password-verification-submit-button' or @type='submit'] | /html/body/div/main/div/div/div/div[2]/div[2]/div/section[3]/form/div[3]/button")))
    driver.execute_script("arguments[0].click();", log_btn)

    time.sleep(8)
    print("URL após login:", driver.current_url)

    # 1. Trata cookies removendo todos os overlays do TrustArc
    print("Removendo overlays de cookies do TrustArc...")
    driver.execute_script("""
        var trusteElements = document.querySelectorAll('.truste_overlay, .truste_cm_outerdiv, .truste_box_overlay, [id^="pop-div"], [id^="pop-outerdiv"]');
        for (var el of trusteElements) {
            el.remove();
        }
    """)
    time.sleep(2)

    # 2. Localiza o card da turma RH124 10.0 (Aug 15, 2026 - Dec 31, 2026)
    print("Procurando o card da turma RH124...")
    card_rh124 = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'offering-card-container') and contains(., 'RH124') and contains(., '2026')]")))
    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", card_rh124)
    time.sleep(1)
    driver.execute_script("arguments[0].click();", card_rh124)
    print("Card da turma RH124 clicado!")
    time.sleep(5)

    driver.save_screenshot("tela_detalhes_turma_rh124.png")
    with open("detalhes_turma_rh124.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)

    # Lista botões da tela de detalhes
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    print("\n--- BOTOES APÓS CLICAR NA TURMA ---")
    for b in soup.find_all(['button', 'a']):
        t = b.get_text(strip=True)
        if any(k in t.lower() for k in ['edit', 'turma', 'aluno', 'student', 'atualizar', 'gerenciar', 'manage']):
            print(f"Tag {b.name}: class={b.get('class')} | text='{t}'")

finally:
    time.sleep(10)
    driver.quit()
