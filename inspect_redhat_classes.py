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

    # Inspeciona cards de turmas
    cards = driver.find_elements(By.XPATH, "//div[contains(@class, 'card') or contains(@class, 'class')] | /html/body/div/div[2]/div/main/div[2]/div[2]/div")
    print(f"Cards/divs encontrados: {len(cards)}")
    for i, c in enumerate(cards):
        txt = (c.text or "").strip().replace('\n', ' | ')
        if txt:
            print(f"Card {i}: {txt[:120]}")

    driver.save_screenshot("tela_classes_redhat.png")
    with open("classes_redhat.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)

finally:
    time.sleep(5)
    driver.quit()
