from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import os

BASE_URL = "http://127.0.0.1:5000"
ARTIFACTS_DIR = r"C:\Users\IT-ADMIN\.gemini\antigravity-ide\brain\9c1c5fe9-439d-41a6-9fe9-389c0d6f9518"

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1600,1050")
driver = webdriver.Chrome(options=opts)

try:
    driver.get(f"{BASE_URL}/login")
    driver.find_element(By.ID, "username").send_keys("admin")
    driver.find_element(By.ID, "password").send_keys("admin")
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(1.5)

    driver.execute_script("showPage('mailbox')")
    time.sleep(2)

    # 1. Capture Compose Modal
    driver.find_element(By.CSS_SELECTOR, ".ribbon-split-btn").click()
    time.sleep(1)
    driver.save_screenshot(os.path.join(ARTIFACTS_DIR, "mailbox_compose_modal.png"))
    print("[1] Saved mailbox_compose_modal.png")
    driver.execute_script("closeComposeModal()")
    time.sleep(0.5)

    # 2. Capture Settings Modal (Auto Replies)
    driver.find_element(By.ID, "suite-btn-settings").click()
    time.sleep(1.5)
    driver.save_screenshot(os.path.join(ARTIFACTS_DIR, "mailbox_settings_modal.png"))
    print("[2] Saved mailbox_settings_modal.png")

    # 3. Capture Rules Tab with New Rule Form
    driver.find_element(By.ID, "tab-nav-rules").click()
    driver.execute_script("openNewRuleForm()")
    time.sleep(0.8)
    driver.save_screenshot(os.path.join(ARTIFACTS_DIR, "mailbox_settings_rules.png"))
    print("[3] Saved mailbox_settings_rules.png")

finally:
    driver.quit()
