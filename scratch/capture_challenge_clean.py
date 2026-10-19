import time, os, sys
sys.stdout.reconfigure(encoding='utf-8')
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--window-size=1200,800')
# Mask user agent so it doesn't trigger server-side scanner UA check
opts.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
# Disable JS so the challenge screen stays static and doesn't auto-redirect
opts.add_experimental_option("prefs", {'profile.managed_default_content_settings.javascript': 2})

driver = webdriver.Chrome(options=opts)
try:
    driver.get('http://127.0.0.1:5000/lp/adobe-sign')
    time.sleep(1)
    driver.save_screenshot('scratch/antibot_stealth_challenge_screen.png')
    print("Page title:", driver.title)
    print("Found challenge:", len(driver.find_elements(By.CLASS_NAME, 'challenge-container')) > 0)
    if driver.find_elements(By.CLASS_NAME, 'challenge-container'):
        print("Challenge text:", driver.find_element(By.CLASS_NAME, 'challenge-container').text.replace('\n', ' | '))
finally:
    driver.quit()
