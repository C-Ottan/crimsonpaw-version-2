import sys
sys.stdout.reconfigure(encoding='utf-8')
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options as ChromeOptions

options = ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(options=options)

try:
    driver.get('http://127.0.0.1:5000/login')
    time.sleep(1)
    driver.find_element(By.ID, 'username').send_keys('admin')
    driver.find_element(By.ID, 'password').send_keys('admin')
    driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
    time.sleep(1.5)

    driver.execute_script("showPage('templates')")
    time.sleep(1.5)

    # First: click Landing preview tab
    driver.find_element(By.ID, 'btn-prev-landing').click()
    time.sleep(1)

    iframe = driver.find_element(By.ID, 'lg-preview-iframe')
    select_land = Select(driver.find_element(By.ID, 'lg-landing-template'))
    
    print("=== TESTING LANDING TEMPLATES ===")
    for opt in select_land.options:
        val = opt.get_attribute('value')
        select_land.select_by_value(val)
        time.sleep(1)
        srcdoc = iframe.get_attribute('srcdoc') or ''
        title_label = driver.find_element(By.ID, 'lg-preview-tab-label').text
        print(f"Template: {val:<15} | Label: {title_label:<30} | srcdoc len: {len(srcdoc)} | Has '{val}': {val in srcdoc}")

    print("\n=== TESTING SUCCESS TEMPLATES ===")
    driver.find_element(By.ID, 'btn-prev-success').click()
    time.sleep(1)
    select_succ = Select(driver.find_element(By.ID, 'lg-success-template'))
    for opt in select_succ.options:
        val = opt.get_attribute('value')
        select_succ.select_by_value(val)
        time.sleep(1)
        srcdoc = iframe.get_attribute('srcdoc') or ''
        title_label = driver.find_element(By.ID, 'lg-preview-tab-label').text
        print(f"Success Template: {val:<15} | Label: {title_label:<30} | srcdoc len: {len(srcdoc)} | Has '{val}': {val in srcdoc}")

finally:
    driver.quit()
