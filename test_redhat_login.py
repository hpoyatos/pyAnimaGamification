import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_bot.redhat_login import get_redhat_credentials

USERNAME, PASSWORD, env_source = get_redhat_credentials()
print(f"Testando login Red Hat para usuário: '{USERNAME}'")

options = webdriver.ChromeOptions()
options.add_argument('--start-maximized')
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)

try:
    url = "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/auth?response_type=code&client_id=rha-webapp-prod&redirect_uri=https%3A%2F%2Frha.ole.redhat.com%2Frha%2Fauth%2Fauthorize&scope=openid+profile+email&state=7lr4ZsHt9AYukVGpTI0R1jQ6b9RB4z&nonce=74T16baQkWKUg7128zEn"
    print("Navegando para SSO Red Hat...")
    driver.get(url)
    time.sleep(3)

    print("Procurando campo de username...")
    username_field = wait.until(
        EC.visibility_of_element_located((By.XPATH, "//input[@id='username' or @name='username' or contains(@class, 'pf-c-form-control')] | /html/body/div/main/div/div/div/div[2]/div[2]/div/section[1]/form/div[1]/input"))
    )
    
    driver.execute_script("""
        var frames = document.querySelectorAll('iframe, .truste_box_overlay_border, .truste_overlay, [id^="trust"], [class^="trust"]');
        for(var i=0; i<frames.length; i++){
            frames[i].style.display = 'none';
        }
    """)

    username_field.clear()
    username_field.send_keys(USERNAME)
    print("Username inserido.")

    next_btn = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//button[@id='login-show-step2' or @type='submit' or contains(., 'Next') or contains(., 'Avançar')] | /html/body/div/main/div/div/div/div[2]/div[2]/div/section[1]/form/div[2]/button"))
    )
    driver.execute_script("arguments[0].click();", next_btn)
    print("Clicou em Next.")
    time.sleep(3)

    print("Procurando campo de senha...")
    password_field = wait.until(
        EC.visibility_of_element_located((By.XPATH, "//input[@type='password' or @id='password' or @name='password'] | /html/body/div/main/div/div/div/div[2]/div[2]/div/section[3]/form/div[2]/div[2]/input"))
    )
    password_field.clear()
    password_field.send_keys(PASSWORD)
    print("Senha inserida.")

    login_btn = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//button[@id='rh-password-verification-submit-button' or @type='submit' or contains(., 'Log in')] | /html/body/div/main/div/div/div/div[2]/div[2]/div/section[3]/form/div[3]/button"))
    )
    driver.execute_script("arguments[0].click();", login_btn)
    print("Clicou em Login.")

    time.sleep(8)
    print("URL atual pós login:", driver.current_url)
    driver.save_screenshot("tela_redhat_pos_login.png")

    print("Conteúdo do título:", driver.title)
    if "Manage Classes" in driver.page_source or "rha.ole.redhat.com" in driver.current_url:
        print(">>> SUCESSO NO LOGIN RED HAT! <<<")
    else:
        print("Atenção: verifique tela_redhat_pos_login.png")

except Exception as e:
    import traceback
    print("Erro durante teste:")
    traceback.print_exc()
    driver.save_screenshot("erro_redhat_login.png")
finally:
    time.sleep(15)
    driver.quit()
