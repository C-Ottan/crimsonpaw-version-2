import time, os, sys, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# 1. Capture Security Verification Challenge Screen (disable JS so it doesn't auto-redirect)
opts_no_js = Options()
opts_no_js.add_argument('--headless=new')
opts_no_js.add_argument('--window-size=1200,800')
opts_no_js.add_argument('--blink-settings=imagesEnabled=true')
opts_no_js.add_experimental_option("prefs", {'profile.managed_default_content_settings.javascript': 2}) # 2 = block javascript

driver_challenge = webdriver.Chrome(options=opts_no_js)
try:
    driver_challenge.get('http://127.0.0.1:5000/lp/adobe-sign')
    time.sleep(1)
    driver_challenge.save_screenshot('scratch/antibot_challenge_modal.png')
    print("Screenshot 1 saved: scratch/antibot_challenge_modal.png")
finally:
    driver_challenge.quit()

# 2. Capture Dashboard Bot Counters and Security Metrics
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

    driver.execute_script("showPage('dashboard', document.getElementById('nav-dashboard'));")
    time.sleep(2)
    driver.save_screenshot('scratch/antibot_dashboard_metrics.png')
    print("Screenshot 2 saved: scratch/antibot_dashboard_metrics.png")

finally:
    driver.quit()

print("✓ Screenshots captured successfully!")
