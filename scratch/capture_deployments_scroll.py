import time, os, sys
sys.stdout.reconfigure(encoding='utf-8')
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--window-size=1600,1050')
driver = webdriver.Chrome(options=opts)

try:
    driver.get('http://127.0.0.1:5000/login')
    time.sleep(1)
    driver.find_element(By.ID, 'username').send_keys('icebadger_master')
    driver.find_element(By.ID, 'password').send_keys('Badger@Master#2026!')
    driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
    time.sleep(2)

    driver.execute_script("showPage('templates', document.getElementById('nav-templates'));")
    time.sleep(2)
    driver.execute_script("document.getElementById('lg-deployments-tbody').scrollIntoView({behavior:'instant', block:'center'});")
    time.sleep(1)
    driver.save_screenshot('scratch/cloudflare_op_5_deployments_table.png')
    print("Screenshot saved!")
finally:
    driver.quit()
